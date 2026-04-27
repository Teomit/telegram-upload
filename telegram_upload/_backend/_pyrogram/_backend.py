"""PyrogramBackend — implementation of the TelegramBackend protocol."""
from __future__ import annotations

import contextlib
import json
import logging
import mimetypes
import os
import time
from collections.abc import Iterable
from functools import cached_property
from urllib.parse import urlparse

import click
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
)

from telegram_upload._backend._pyrogram._adapter import PyrogramMessageAdapter
from telegram_upload._media import probe
from telegram_upload.config import SESSION_FILE
from telegram_upload.exceptions import (
    InvalidApiFileError,
    TelegramProxyError,
    TelegramUploadDataLoss,
    TelegramUploadError,
)

logger = logging.getLogger(__name__)

BOT_USER_MAX_FILE_SIZE = 52428800  # 50MB
USER_MAX_FILE_SIZE = 2097152000  # 2GB
PREMIUM_USER_MAX_FILE_SIZE = 4194304000  # 4GB
USER_MAX_CAPTION_LENGTH = 1024
PREMIUM_USER_MAX_CAPTION_LENGTH = 2048
PROXY_ENVIRONMENT_VARIABLE_NAMES = (
    "TELEGRAM_UPLOAD_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
)
ALBUM_FILES = 10
RETRIES = 3


def get_message_file_attribute(message):
    """Compatibility shim mirroring _telethon.get_message_file_attribute.

    Returns an object with a ``.file_name`` attribute or None. Accepts
    either a raw pyrogram Message or a PyrogramMessageAdapter.
    """
    raw = message.raw if isinstance(message, PyrogramMessageAdapter) else message
    if isinstance(message, PyrogramMessageAdapter):
        doc = message.document
        return doc.attributes[0] if doc and doc.attributes else None
    adapter = PyrogramMessageAdapter(raw)
    doc = adapter.document
    return doc.attributes[0] if doc and doc.attributes else None


def _get_proxy_environment_variable() -> str | None:
    for name in PROXY_ENVIRONMENT_VARIABLE_NAMES:
        if name in os.environ:
            return os.environ[name]
    return None


def _parse_proxy(proxy: str | None) -> dict | None:
    """Translate a URL-style proxy string into pyrogram's proxy dict, or None."""
    if not proxy:
        return None
    parsed = urlparse(proxy)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        raise TelegramProxyError(f"Malformed proxy address: {proxy}")
    if parsed.scheme not in {"http", "socks4", "socks5"}:
        # Pyrogram doesn't support mtproxy.
        raise TelegramProxyError(f"Unsupported proxy type for pyrogram backend: {parsed.scheme}")
    return {
        "scheme": parsed.scheme,
        "hostname": parsed.hostname,
        "port": parsed.port,
        "username": parsed.username or "",
        "password": parsed.password or "",
    }


def _make_progress(label: str, file_name: str, total: int):
    """Return a (callback, finish) pair backed by click.progressbar."""
    bar = click.progressbar(label=f'{label} "{file_name}"', length=max(total, 1))

    def callback(current: int, _total: int):
        bar.pos = 0
        bar.update(current)

    def finish():
        with contextlib.suppress(Exception):
            bar.render_finish()

    return callback, finish


def _media_kind(file_path: str, force_file: bool) -> str:
    """Pick which pyrogram send_* method to use for this file."""
    if force_file:
        return "document"
    mime = (mimetypes.guess_type(file_path)[0] or "").split("/")[0]
    return {"video": "video", "image": "photo", "audio": "audio"}.get(mime, "document")


def _load_config(config_file: str) -> dict:
    """Read and validate the JSON config file. Raises TelegramUploadError on parse
    issues, InvalidApiFileError when api_id/api_hash are missing."""
    try:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError as e:
        raise TelegramUploadError(
            f"Configuration file not found: {config_file}\n"
            f"Please create a config file or run telegram-upload with --config option."
        ) from e
    except json.JSONDecodeError as e:
        raise TelegramUploadError(
            f"Invalid JSON in configuration file {config_file}:\n"
            f"  Line {e.lineno}, Column {e.colno}: {e.msg}"
        ) from e
    except OSError as e:
        raise TelegramUploadError(f"Failed to read configuration file {config_file}: {e}") from e

    if "api_id" not in config:
        raise InvalidApiFileError(f"Missing 'api_id' in configuration file: {config_file}")
    if "api_hash" not in config:
        raise InvalidApiFileError(f"Missing 'api_hash' in configuration file: {config_file}")
    return config


def _resolve_session(session_value: str | None) -> tuple[str, str]:
    """Split a session path into (workdir, name) for pyrogram.Client. Creates workdir."""
    session_path = os.path.expanduser(session_value or SESSION_FILE)
    workdir = os.path.dirname(session_path) or "."
    os.makedirs(workdir, exist_ok=True)
    name = os.path.basename(session_path) or "telegram-upload"
    return workdir, name


class PyrogramBackend:
    """TelegramBackend implementation backed by pyrogram (or pyrofork)."""

    def __init__(self, config_file: str, proxy: str | None = None, **kwargs) -> None:
        self.config_file = config_file
        config = _load_config(config_file)
        proxy = proxy if proxy is not None else _get_proxy_environment_variable()
        workdir, name = _resolve_session(config.get("session"))
        self._client = Client(
            name=name,
            api_id=int(config["api_id"]),
            api_hash=config["api_hash"],
            workdir=workdir,
            proxy=_parse_proxy(proxy),
            **kwargs,
        )

    # --- lifecycle ---------------------------------------------------------
    def start(self):
        """Authenticate. Pyrogram itself prompts for phone/code/password."""
        try:
            return self._client.start()
        except RPCError as e:
            # ApiIdInvalid is the canonical bad-credentials error.
            if "API_ID" in str(e).upper():
                raise InvalidApiFileError(self.config_file) from e
            raise

    def stop(self):
        return self._client.stop()

    # --- identity ----------------------------------------------------------
    @cached_property
    def me(self):
        return self._client.get_me()

    @property
    def max_file_size(self) -> int:
        if getattr(self.me, "is_premium", False):
            return PREMIUM_USER_MAX_FILE_SIZE
        if getattr(self.me, "is_bot", False):
            return BOT_USER_MAX_FILE_SIZE
        return USER_MAX_FILE_SIZE

    @property
    def max_caption_length(self) -> int:
        if getattr(self.me, "is_premium", False):
            return PREMIUM_USER_MAX_CAPTION_LENGTH
        return USER_MAX_CAPTION_LENGTH

    # --- upload ------------------------------------------------------------
    def send_files(
        self,
        entity,
        files: Iterable,
        delete_on_success: bool = False,
        print_file_id: bool = False,
        forward: tuple = (),
        send_as_media: bool = False,
    ) -> list:
        """Upload each file. Returns the list of resulting Messages."""
        sent = []
        any_files = False
        for file in files:
            any_files = True
            thumb = file.get_thumbnail() if not send_as_media else None
            try:
                message = self._send_one(entity, file, thumb)
            finally:
                if thumb and not file.is_custom_thumbnail and os.path.lexists(thumb):
                    try:
                        os.remove(thumb)
                    except OSError as e:
                        logger.warning('failed to delete thumb "%s": %s', thumb, e)
            if message is None:
                logger.error('Failed to upload "%s"', file.file_name)
                continue
            if print_file_id:
                file_id = _extract_file_id(message)
                logger.info('Uploaded successfully "%s" (file_id %s)', file.file_name, file_id)
            if delete_on_success:
                logger.info('Deleting "%s"', file.file_name)
                try:
                    os.remove(file.path)
                except OSError as e:
                    logger.warning('failed to delete file "%s": %s', file.path, e)
            for dst in forward:
                self._client.forward_messages(dst, entity, message.id)
            sent.append(message)
        if not any_files:
            from telegram_upload.exceptions import MissingFileError
            raise MissingFileError("Files do not exist.")
        return sent

    def send_files_as_album(
        self,
        entity,
        files: Iterable,
        delete_on_success: bool = False,
        print_file_id: bool = False,
        forward: tuple = (),
    ) -> None:
        """Send files in groups of up to 10 as an album (send_media_group)."""
        batch: list = []
        for file in files:
            batch.append(file)
            if len(batch) == ALBUM_FILES:
                self._send_album_batch(entity, batch, delete_on_success, forward)
                batch = []
        if batch:
            self._send_album_batch(entity, batch, delete_on_success, forward)

    def _send_album_batch(self, entity, batch: list, delete_on_success: bool, forward: tuple) -> None:
        media_items = []
        for file in batch:
            kind = _media_kind(file.path, file.force_file)
            caption = file.file_caption
            if kind == "video":
                info = probe(file.path)
                media_items.append(InputMediaVideo(
                    media=file.path,
                    caption=caption,
                    duration=info.duration or 0,
                    width=info.width or 0,
                    height=info.height or 0,
                    supports_streaming=info.supports_streaming,
                ))
            elif kind == "photo":
                media_items.append(InputMediaPhoto(media=file.path, caption=caption))
            elif kind == "audio":
                media_items.append(InputMediaAudio(media=file.path, caption=caption))
            else:
                media_items.append(InputMediaDocument(media=file.path, caption=caption))
        messages = self._client.send_media_group(chat_id=entity, media=media_items)
        for msg in messages:  # type: ignore[attr-defined]
            for dst in forward:
                self._client.forward_messages(dst, entity, msg.id)
        if delete_on_success:
            for file in batch:
                try:
                    os.remove(file.path)
                except OSError as e:
                    logger.warning('failed to delete file "%s": %s', file.path, e)

    def _send_one(self, entity, file, thumb):
        """Send one file. Retries on FloodWait/RPC; iterative, not recursive."""
        kind = _media_kind(file.path, file.force_file)
        progress, finish = _make_progress("Uploading", file.file_name, file.file_size)
        message = None
        try:
            for attempt in range(RETRIES + 1):
                try:
                    message = self._dispatch_send(entity, file, kind, thumb, progress)
                    break
                except FloodWait as e:
                    wait = int(getattr(e, "value", 0) or 0)
                    logger.warning("FloodWait. Sleeping %ss.", wait)
                    time.sleep(wait)
                    continue  # FloodWait doesn't consume a retry
                except RPCError as e:
                    if attempt < RETRIES:
                        logger.warning('"%s" failed: %s. Retrying (%d/%d)...',
                                       file.file_name, e, attempt + 1, RETRIES)
                        continue
                    logger.error('"%s" failed: %s. Giving up.', file.file_name, e)
                    return None
        finally:
            finish()
        if message is None:
            return None
        remote_size = _remote_size(message)
        if remote_size is not None and remote_size != file.file_size:
            raise TelegramUploadDataLoss(
                f"Remote document size: {remote_size} bytes (local file size: {file.file_size} bytes)"
            )
        return message

    def _dispatch_send(self, entity, file, kind: str, thumb, progress):
        common = {
            "chat_id": entity,
            "caption": file.file_caption,
            "progress": progress,
        }
        if kind == "document":
            return self._client.send_document(
                document=file.path, thumb=thumb, force_document=True, **common,
            )
        if kind == "video":
            info = probe(file.path)
            return self._client.send_video(
                video=file.path, thumb=thumb,
                duration=info.duration or 0, width=info.width or 0, height=info.height or 0,
                supports_streaming=info.supports_streaming,
                **common,
            )
        if kind == "photo":
            return self._client.send_photo(photo=file.path, **common)
        if kind == "audio":
            return self._client.send_audio(audio=file.path, **common)
        raise RuntimeError(f"unreachable media kind {kind!r}")

    # --- download ----------------------------------------------------------
    def find_files(self, entity):
        """Yield messages with a file, latest-first, until a non-file message."""
        for raw in self._client.get_chat_history(entity):
            adapter = PyrogramMessageAdapter(raw)
            if adapter.document is None:
                break
            yield adapter

    def iter_files(self, entity):
        # Async version not needed without interactive mode, but kept on the
        # protocol for symmetry. We adapt the sync iterator.
        async def _gen():
            async for raw in self._client.get_chat_history(entity):
                adapter = PyrogramMessageAdapter(raw)
                if adapter.document is not None:
                    yield adapter
        return _gen()

    def download_files(
        self,
        entity,
        download_files: Iterable,
        delete_on_success: bool = False,
    ) -> None:
        from telegram_upload.exceptions import TelegramUploadNoSpaceError
        from telegram_upload.utils import free_disk_usage, sizeof_fmt

        for download_file in download_files:
            if download_file.size > free_disk_usage():
                raise TelegramUploadNoSpaceError(
                    f'There is no disk space to download "{download_file.file_name}". '
                    f"Space required: {sizeof_fmt(download_file.size - free_disk_usage())}"
                )
            progress, finish = _make_progress("Downloading", download_file.file_name, download_file.size)
            file_name = download_file.file_name
            raw = download_file.message.raw if isinstance(download_file.message, PyrogramMessageAdapter) \
                else download_file.message
            try:
                downloaded = self._client.download_media(
                    raw,
                    file_name=os.path.join(os.getcwd(), file_name),
                    progress=progress,
                )
                if isinstance(downloaded, str):
                    download_file.set_download_file_name(downloaded)
            finally:
                finish()
            if delete_on_success:
                self._client.delete_messages(chat_id=entity, message_ids=raw.id)

    # --- helpers used by tests ---------------------------------------------
    @property
    def client(self):
        """Expose the underlying pyrogram.Client (read-only access)."""
        return self._client


def _extract_file_id(message) -> str:
    media = (
        message.document or message.video or message.audio
        or message.voice or message.video_note or message.animation
        or message.photo or message.sticker
    )
    return getattr(media, "file_id", "") if media is not None else ""


def _remote_size(message) -> int | None:
    media = (
        message.document or message.video or message.audio
        or message.voice or message.video_note or message.animation
    )
    if media is None:
        return None
    return int(getattr(media, "file_size", 0) or 0) or None
