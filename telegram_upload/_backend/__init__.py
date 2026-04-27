"""Telegram backend abstraction.

The CLI talks to Telegram through one facade — a TelegramBackend. The
single bundled implementation today is ``PyrogramBackend`` (built on
pyrofork). The split makes it cheap to plug in another backend later
without touching ``upload_files``, ``download_files`` or ``management``.

Anything below this package talks only to the methods listed in
``_protocol.py``.
"""
from telegram_upload._backend._pyrogram import PyrogramBackend, get_message_file_attribute

# Public alias kept stable: callers (management, tests) write
# ``from telegram_upload._backend import TelegramManagerClient``.
TelegramManagerClient = PyrogramBackend


__all__ = [
    "TelegramManagerClient",
    "PyrogramBackend",
    "get_message_file_attribute",
]
