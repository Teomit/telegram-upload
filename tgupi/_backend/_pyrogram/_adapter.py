"""Telethon-shaped adapter around a pyrogram.types.Message.

The rest of the package (``download_files.DownloadFile`` in particular) was
written against Telethon's message shape: ``message.document.attributes``
contains a list with a ``DocumentAttributeFilename`` whose ``.file_name``
is the file name on disk. Pyrogram exposes the same data differently —
``message.document.file_name`` directly, or ``message.video``,
``message.audio``, ``message.photo`` for the typed equivalents.

This adapter wraps a pyrogram Message and presents the Telethon-shaped
attributes the rest of the codebase expects. That keeps the join-strategy
pipeline (``download_files.JoinDownloadSplitFiles`` etc.) backend-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _AttrFilename:
    """Mimics telethon.tl.types.DocumentAttributeFilename — only `.file_name`."""
    file_name: str


@dataclass
class _DocumentLike:
    """Telethon-shaped document façade backed by a pyrogram media object."""
    size: int
    file_name: str
    mime_type: str | None = None
    attributes: list = field(default_factory=list)


class PyrogramMessageAdapter:
    """Wraps a pyrogram.types.Message so it looks like a Telethon Message.

    Exposes the subset used by ``download_files`` and the CLI:
    ``.document``, ``.text``, ``.sender``, ``.date`` and the underlying
    pyrogram message via ``.raw``.
    """

    __slots__ = ("raw",)

    def __init__(self, raw):
        self.raw = raw

    # --- telethon-shaped fields --------------------------------------------
    @property
    def document(self) -> _DocumentLike | None:
        media = _pick_media(self.raw)
        if media is None:
            return None
        file_name = getattr(media, "file_name", None) or _synthetic_name(self.raw, media)
        size = int(getattr(media, "file_size", 0) or 0)
        mime = getattr(media, "mime_type", None)
        return _DocumentLike(
            size=size,
            file_name=file_name,
            mime_type=mime,
            attributes=[_AttrFilename(file_name=file_name)],
        )

    @property
    def text(self) -> str | None:
        return self.raw.caption or self.raw.text or None

    @property
    def sender(self):
        return self.raw.from_user

    @property
    def date(self):
        return self.raw.date

    @property
    def id(self):
        return self.raw.id


def _pick_media(message):
    """Return the first non-empty media on a pyrogram Message, or None."""
    for attr in ("document", "video", "audio", "voice", "video_note", "animation", "photo", "sticker"):
        media = getattr(message, attr, None)
        if media is not None:
            return media
    return None


def _synthetic_name(message, media) -> str:
    """Best-effort filename when pyrogram doesn't expose ``file_name``."""
    if hasattr(media, "file_unique_id"):
        suffix = _guess_suffix(message)
        return f"{media.file_unique_id}{suffix}"
    return "Unknown"


def _guess_suffix(message) -> str:
    if message.video:
        return ".mp4"
    if message.audio:
        return ".mp3"
    if message.voice:
        return ".ogg"
    if message.photo:
        return ".jpg"
    if message.animation:
        return ".gif"
    if message.sticker:
        return ".webp"
    return ""
