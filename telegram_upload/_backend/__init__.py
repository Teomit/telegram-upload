"""Telegram backend abstraction.

The CLI talks to Telegram through a single facade — a `TelegramBackend`. It
hides whichever client library we currently use (Telethon, Pyrogram, ...).
Today the only implementation is ``_telethon.TelethonBackend``, exposed as
``TelegramManagerClient`` for backwards compatibility with import paths that
existed before the backend split. ``_pyrogram.PyrogramBackend`` is wired in
via the ``TELEGRAM_UPLOAD_BACKEND`` env var (default: ``telethon``).

Anything that talks to Telegram below this package — ``upload_files``,
``download_files``, ``management`` — uses only the methods listed in
``BackendProtocol`` and the abstract message types in ``_types``. Adding a
new backend means writing a new module here, no changes elsewhere.
"""
from __future__ import annotations

import os

from telegram_upload._backend._telethon import (
    TelethonBackend,
    get_message_file_attribute,
)


def get_backend_class():
    """Return the backend class selected via ``TELEGRAM_UPLOAD_BACKEND`` env."""
    name = os.environ.get('TELEGRAM_UPLOAD_BACKEND', 'telethon').lower()
    if name == 'telethon':
        return TelethonBackend
    if name == 'pyrogram':
        from telegram_upload._backend._pyrogram import PyrogramBackend
        return PyrogramBackend
    raise ValueError(f"Unknown TELEGRAM_UPLOAD_BACKEND={name!r} (expected 'telethon' or 'pyrogram')")


# Re-exports for backwards compatibility — the rest of the codebase still
# imports `TelegramManagerClient` from ``telegram_upload._backend``.
TelegramManagerClient = TelethonBackend


__all__ = [
    "TelegramManagerClient",
    "TelethonBackend",
    "get_backend_class",
    "get_message_file_attribute",
]
