import _string
import datetime
import hashlib
import logging
import mimetypes
import os
import zlib
from collections.abc import Mapping, Sequence
from functools import cached_property
from pathlib import Path, PosixPath, WindowsPath
from string import Formatter
from typing import Any

import click

from telegram_upload._media import MediaInfo, probe
from telegram_upload.constants import DURATION_LAST_SEPARATOR, DURATION_SEPARATOR

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4096
VALID_TYPES: tuple[Any, ...] = (str, int, float, complex, bool, datetime.datetime, datetime.date, datetime.time)
AUTHORIZED_METHODS = (Path.home,)
AUTHORIZED_STRING_METHODS = ("title", "capitalize", "lower", "upper", "swapcase", "strip", "lstrip", "rstrip")
AUTHORIZED_DT_METHODS = (
    "astimezone", "ctime", "date", "dst", "isoformat", "isoweekday", "now", "time",
    "timestamp", "today", "toordinal", "tzname", "utcnow", "utcoffset", "weekday"
)


class Duration:
    def __init__(self, seconds: int):
        self.seconds = seconds

    @property
    def as_minutes(self) -> int:
        return self.seconds // 60

    @property
    def as_hours(self) -> int:
        return self.as_minutes // 60

    @property
    def as_days(self) -> int:
        return self.as_hours // 24

    @property
    def for_humans(self) -> str:
        words = ["year", "day", "hour", "minute", "second"]

        if not self.seconds:
            return "now"
        else:
            m, s = divmod(self.seconds, 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            y, d = divmod(d, 365)

            time = [y, d, h, m, s]

            duration = []

            for x, i in enumerate(time):
                if i == 1:
                    duration.append(f"{i} {words[x]}")
                elif i > 1:
                    duration.append(f"{i} {words[x]}s")

            if len(duration) == 1:
                return duration[0]
            elif len(duration) == 2:
                return f"{duration[0]}{DURATION_LAST_SEPARATOR}{duration[1]}"
            else:
                return DURATION_SEPARATOR.join(duration[:-1]) + DURATION_LAST_SEPARATOR + duration[-1]

    def __int__(self) -> int:
        return self.seconds

    def __str__(self) -> str:
        return str(self.seconds)


class FileSize:
    def __init__(self, size: int):
        self.size = size

    @property
    def as_kilobytes(self) -> int:
        return self.size // 1000

    @property
    def as_megabytes(self) -> int:
        return self.as_kilobytes // 1000

    @property
    def as_gigabytes(self) -> int:
        return self.as_megabytes // 1000

    @property
    def as_kibibytes(self) -> int:
        return self.size // 1024

    @property
    def as_mebibytes(self) -> int:
        return self.as_kibibytes // 1024

    @property
    def as_gibibytes(self) -> int:
        return self.as_mebibytes // 1024

    @property
    def for_humans(self, suffix: str = "B") -> str:
        num: float = self.size
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f} Yi{suffix}"

    def __int__(self) -> int:
        return self.size

    def __str__(self) -> str:
        return str(self.size)


class FileMedia:
    """Lazy media metadata for caption templating.

    Wraps a MediaInfo from ffprobe and exposes its fields as plain attributes
    so they're addressable from format strings like ``{file.media.duration}``.
    """

    def __init__(self, path: str):
        self.path = path

    @cached_property
    def info(self) -> MediaInfo:
        return probe(self.path)

    @property
    def duration(self) -> Duration | None:
        return Duration(self.info.duration) if self.info.duration is not None else None

    @property
    def width(self) -> int | None:
        return self.info.width

    @property
    def height(self) -> int | None:
        return self.info.height

    @property
    def title(self) -> str | None:
        return self.info.title

    @property
    def artist(self) -> str | None:
        return self.info.artist

    @property
    def album(self) -> str | None:
        return self.info.album

    @property
    def producer(self) -> str | None:
        return self.info.producer


class FileMixin:

    def _calculate_hash(self, hash_calculator: Any) -> str:
        with open(str(self), "rb") as f:
            # Read and update hash string value in blocks
            for byte_block in iter(lambda: f.read(CHUNK_SIZE), b""):
                hash_calculator.update(byte_block)
            return hash_calculator.hexdigest()

    @property
    def md5(self) -> str:
        return self._calculate_hash(hashlib.md5())

    @property
    def sha1(self) -> str:
        return self._calculate_hash(hashlib.sha1())

    @property
    def sha224(self) -> str:
        return self._calculate_hash(hashlib.sha224())

    @property
    def sha256(self) -> str:
        return self._calculate_hash(hashlib.sha256())

    @property
    def sha384(self) -> str:
        return self._calculate_hash(hashlib.sha384())

    @property
    def sha512(self) -> str:
        return self._calculate_hash(hashlib.sha512())

    @property
    def sha3_224(self) -> str:
        return self._calculate_hash(hashlib.sha3_224())

    @property
    def sha3_256(self) -> str:
        return self._calculate_hash(hashlib.sha3_256())

    @property
    def sha3_384(self) -> str:
        return self._calculate_hash(hashlib.sha3_384())

    @property
    def sha3_512(self) -> str:
        return self._calculate_hash(hashlib.sha3_512())

    @property
    def crc32(self) -> str:
        with open(str(self), "rb") as f:
            calculated_hash = 0
            # Read and update hash string value in blocks
            for byte_block in iter(lambda: f.read(CHUNK_SIZE), b""):
                calculated_hash = zlib.crc32(byte_block, calculated_hash)
            return "%08X" % (calculated_hash & 0xFFFFFFFF)

    @property
    def adler32(self) -> str:
        with open(str(self), "rb") as f:
            calculated_hash = 1
            # Read and update hash string value in blocks
            for byte_block in iter(lambda: f.read(CHUNK_SIZE), b""):
                calculated_hash = zlib.adler32(byte_block, calculated_hash)
                if calculated_hash < 0:
                    calculated_hash += 2 ** 32
            return hex(calculated_hash)[2:10].zfill(8)

    @cached_property
    def _file_stat(self) -> os.stat_result:
        return os.stat(str(self))

    @cached_property
    def ctime(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self._file_stat.st_ctime)

    @cached_property
    def mtime(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self._file_stat.st_mtime)

    @cached_property
    def atime(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self._file_stat.st_atime)

    @cached_property
    def size(self) -> FileSize:
        return FileSize(self._file_stat.st_size)

    @cached_property
    def media(self) -> FileMedia:
        return FileMedia(str(self))

    @cached_property
    def mimetype(self) -> str | None:
        mimetypes.init()
        return mimetypes.guess_type(str(self))[0]

    @cached_property
    def suffixes(self) -> str:  # type: ignore[override,misc]
        return "".join(super().suffixes)  # type: ignore[misc]

    @property
    def absolute(self):  # type: ignore[override]
        return super().absolute()  # type: ignore[misc]

    @property
    def relative(self):
        return self.relative_to(Path.cwd())  # type: ignore[attr-defined]


class WindowsFilePath(FileMixin, WindowsPath):  # type: ignore[misc]
    pass


class PosixFilePath(FileMixin, PosixPath):  # type: ignore[misc]
    pass


def FilePath(*args, **kwargs) -> "WindowsFilePath | PosixFilePath":  # noqa: N802 -- public name kept for back-compat
    """Factory that returns an OS-appropriate Path subclass with FileMixin.

    Implemented as a function (not a class) because pathlib was reworked in
    Python 3.12 and the previous ``FilePath(FileMixin, Path)`` ``__new__``
    trick relied on the removed ``Path._from_parts``. A factory is portable
    across 3.11–3.14 and side-steps the metaclass complications.
    """
    cls = WindowsFilePath if os.name == 'nt' else PosixFilePath
    return cls(*args, **kwargs)


class CaptionFormatter(Formatter):

    def get_field(self, field_name: str, args: Sequence[Any], kwargs: Mapping[str, Any]) -> Any:
        try:
            if "._" in field_name:
                raise TypeError(f'Access to private property in {field_name}')
            obj, first = super().get_field(field_name, args, kwargs)
            has_func = hasattr(obj, "__func__")
            has_self = hasattr(obj, "__self__")
            if (has_func and obj.__func__ in AUTHORIZED_METHODS) or \
                    (has_self and isinstance(obj.__self__, str) and obj.__name__ in AUTHORIZED_STRING_METHODS) or \
                    (has_self and isinstance(obj.__self__, datetime.datetime)
                     and obj.__name__ in AUTHORIZED_DT_METHODS):
                obj = obj()
            if not isinstance(obj, VALID_TYPES + (WindowsFilePath, PosixFilePath, FileSize, Duration)):
                raise TypeError(f'Invalid type for {field_name}: {type(obj)}')
            return obj, first
        except (TypeError, AttributeError, KeyError, ValueError) as e:
            # Log the specific error for debugging, but return placeholder
            logger.debug(f'Failed to parse field "{field_name}": {type(e).__name__}: {e}')
            first, rest = _string.formatter_field_name_split(field_name)
            return '{' + field_name + '}', first

    def format(self, format_string: str, /, *args: Any, **kwargs: Any) -> str:
        try:
            return super().format(format_string, *args, **kwargs)
        except ValueError:
            return format_string


@click.command()
@click.argument('file', type=click.Path(exists=True))
@click.argument('caption_format', type=str)
def test_caption_format(file: str, caption_format: str) -> None:
    """Test the caption format on a given file"""
    file_path = FilePath(file)
    formatter = CaptionFormatter()
    print(formatter.format(caption_format, file=file_path, now=datetime.datetime.now()))


if __name__ == '__main__':
    # Testing mode
    test_caption_format()
