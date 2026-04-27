"""Backend protocol — the surface area the rest of the package relies on.

A concrete backend (``TelethonBackend`` today, ``PyrogramBackend`` next) is
constructed with a config-file path and an optional proxy string. After
``start()`` it must expose the methods/properties listed here.

This module exists for documentation and ``mypy``/IDE type-checking only.
Backends are not required to literally inherit from ``TelegramBackend`` —
duck-typing is fine — but they must satisfy the protocol.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TelegramBackend(Protocol):
    """Methods the CLI uses on a Telegram client."""

    # --- limits exposed to upload_files / caption_formatter ---
    max_file_size: int
    max_caption_length: int

    # --- lifecycle ---
    def start(self) -> Any:
        """Authenticate (interactive prompts for phone/code/password if needed)."""
        ...

    # --- upload ---
    def send_files(
        self,
        entity: Any,
        files: Iterable[Any],
        delete_on_success: bool = False,
        print_file_id: bool = False,
        forward: tuple[Any, ...] = (),
    ) -> list[Any]: ...

    def send_files_as_album(
        self,
        entity: Any,
        files: Iterable[Any],
        delete_on_success: bool = False,
        print_file_id: bool = False,
        forward: tuple[Any, ...] = (),
    ) -> None: ...

    # --- download ---
    def find_files(self, entity: Any) -> Iterable[Any]:
        """Yield messages with files, latest-first, until the first non-file."""
        ...

    def download_files(
        self,
        entity: Any,
        download_files: Iterable[Any],
        delete_on_success: bool = False,
    ) -> None: ...
