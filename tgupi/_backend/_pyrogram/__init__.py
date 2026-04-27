"""Pyrogram backend.

Implementation note — TgCrypto:
    Pyrogram-flavoured libraries optionally accelerate AES-IGE through the
    ``tgcrypto`` C extension. ``tgcrypto`` is not built for Python 3.13+;
    ``cryptography`` works as a faster fallback than the pure-Python
    ``pyaes`` Pyrogram ships. Both are optional — pyrogram detects what's
    available at import.

Implementation note — fork choice:
    We pin ``pyrofork`` instead of upstream ``pyrogram``. Upstream 2.0.x
    still calls ``asyncio.get_event_loop()`` from a fresh thread, which
    raises ``RuntimeError`` on Python 3.14. ``pyrofork`` ships the bug-fix.
    Both packages import as ``pyrogram`` — code is unchanged.
"""
from tgupi._backend._pyrogram._backend import PyrogramBackend, get_message_file_attribute

__all__ = ["PyrogramBackend", "get_message_file_attribute"]
