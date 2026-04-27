"""Telegram backend abstraction.

The CLI talks to Telegram through one facade — a TelegramBackend. Two
implementations are bundled today: ``PyrogramBackend`` (default) and
``TelethonBackend`` (legacy, removed in Этап 6). Switch via env:
``TELEGRAM_UPLOAD_BACKEND=telethon`` to force the old client.

Anything below this package (``upload_files``, ``download_files``,
``management``) talks only to the methods listed in ``_protocol.py``;
adding a backend means writing a new module here, no edits elsewhere.
"""
from __future__ import annotations

import os


def _resolve_default_backend():
    name = os.environ.get("TELEGRAM_UPLOAD_BACKEND", "pyrogram").lower()
    if name == "pyrogram":
        from telegram_upload._backend._pyrogram import PyrogramBackend, get_message_file_attribute
        return PyrogramBackend, get_message_file_attribute
    if name == "telethon":
        from telegram_upload._backend._telethon import TelethonBackend, get_message_file_attribute
        return TelethonBackend, get_message_file_attribute
    raise ValueError(f"Unknown TELEGRAM_UPLOAD_BACKEND={name!r} (expected 'pyrogram' or 'telethon')")


# Resolved at import time — this lets `from telegram_upload._backend import
# TelegramManagerClient` keep working without conditional code in every caller.
TelegramManagerClient, get_message_file_attribute = _resolve_default_backend()


__all__ = [
    "TelegramManagerClient",
    "get_message_file_attribute",
]
