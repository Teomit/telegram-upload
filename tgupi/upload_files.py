import datetime
import math
import mimetypes
import os
from io import SEEK_SET, FileIO
from typing import TYPE_CHECKING

import click

from tgupi.caption_formatter import CaptionFormatter, FilePath
from tgupi.constants import SPLIT_FILE_PART_NUMBER_PADDING
from tgupi.exceptions import TelegramInvalidFile, ThumbError
from tgupi.utils import scantree, truncate
from tgupi.video import get_video_thumb

mimetypes.init()


if TYPE_CHECKING:
    from tgupi._backend import TelegramManagerClient


def is_valid_file(file, error_logger=None):
    error_message = None
    if not os.path.lexists(file):
        error_message = f'File "{file}" does not exist.'
    elif not os.path.getsize(file):
        error_message = f'File "{file}" is empty.'
    if error_message and error_logger is not None:
        error_logger(error_message)
    return error_message is None


def get_file_mime(file: str) -> str:
    """
    Get MIME type category for a file.

    Args:
        file: Path to the file

    Returns:
        MIME type category (e.g., 'video', 'image', 'audio') or empty string
    """
    return (mimetypes.guess_type(file)[0] or '').split('/')[0]


def get_file_thumb(file: str) -> str | None:
    """
    Get thumbnail path for a file.

    Args:
        file: Path to the file

    Returns:
        Path to the thumbnail file, or None if not applicable
    """
    if get_file_mime(file) == 'video':
        return get_video_thumb(file)
    return None


class UploadFilesBase:
    def __init__(self, client: 'TelegramManagerClient', files, thumbnail: str | bool | None = None,
                 force_file: bool = False, caption: str | None = None):
        self._iterator = None
        self.client = client
        self.files = files
        self.thumbnail = thumbnail
        self.force_file = force_file
        self.caption = caption

    def get_iterator(self):
        raise NotImplementedError

    def __iter__(self):
        self._iterator = self.get_iterator()
        return self

    def __next__(self):
        if self._iterator is None:
            self._iterator = self.get_iterator()
        return next(self._iterator)


class RecursiveFiles(UploadFilesBase):

    def get_iterator(self):
        for file in self.files:
            if os.path.isdir(file):
                yield from (entry.path for entry in scantree(file, True) if not entry.is_dir())
            else:
                yield file


class NoDirectoriesFiles(UploadFilesBase):
    def get_iterator(self):
        for file in self.files:
            if os.path.isdir(file):
                raise TelegramInvalidFile(f'"{file}" is a directory.')
            else:
                yield file


class LargeFilesBase(UploadFilesBase):
    def get_iterator(self):
        for file in self.files:
            if os.path.getsize(file) > self.client.max_file_size:
                yield from self.process_large_file(file)
            else:
                yield self.process_normal_file(file)

    def process_normal_file(self, file: str) -> 'File':
        return File(self.client, file, force_file=self.force_file, thumbnail=self.thumbnail, caption=self.caption)

    def process_large_file(self, file):
        raise NotImplementedError


class NoLargeFiles(LargeFilesBase):
    def process_large_file(self, file):
        raise TelegramInvalidFile(f'"{file}" file is too large for Telegram.')


class File(FileIO):
    force_file = False

    def __init__(self, client: 'TelegramManagerClient', path: str, force_file: bool | None = None,
                 thumbnail: str | bool | None = None, caption: str | None = None):
        super().__init__(path)
        self.client = client
        self.path = path
        self.force_file = self.force_file if force_file is None else force_file
        self._thumbnail = thumbnail
        self._caption = caption

    @property
    def file_name(self):
        return os.path.basename(self.path)

    @property
    def file_size(self):
        return os.path.getsize(self.path)

    @property
    def short_name(self):
        return '.'.join(self.file_name.split('.')[:-1])

    @property
    def is_custom_thumbnail(self):
        return self._thumbnail is not False and self._thumbnail is not None

    @property
    def file_caption(self) -> str:
        """Get file caption. If caption parameter is not set, return file name.
        If caption is set, format it with CaptionFormatter.
        Anyways, truncate caption to max_caption_length.
        """
        if self._caption is not None:
            formatter = CaptionFormatter()
            caption = formatter.format(self._caption, file=FilePath(self.path), now=datetime.datetime.now())
        else:
            caption = self.short_name
        return truncate(caption, self.client.max_caption_length)

    def get_thumbnail(self):
        thumb = None
        if self._thumbnail is None and not self.force_file:
            try:
                thumb = get_file_thumb(self.path)
            except ThumbError as e:
                click.echo(f'{e}', err=True)
        elif self.is_custom_thumbnail:
            if not isinstance(self._thumbnail, str):
                raise TypeError(f'Invalid type for thumbnail: {type(self._thumbnail)}')
            elif not os.path.lexists(self._thumbnail):
                raise TelegramInvalidFile(f'{self._thumbnail} thumbnail file does not exists.')
            thumb = self._thumbnail
        return thumb


class SplitFile(File, FileIO):
    force_file = True

    def __init__(self, client: 'TelegramManagerClient', file: str, max_read_size: int, name: str):
        super().__init__(client, file)
        self.max_read_size = max_read_size
        self.remaining_size = max_read_size
        self._name = name

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        if size == -1:
            size = self.remaining_size
        if not self.remaining_size:
            return b''
        size = min(self.remaining_size, size)
        self.remaining_size -= size
        return super().read(size)

    def readall(self) -> bytes:
        return self.read()

    @property
    def file_name(self):
        return self._name

    @property
    def file_size(self):
        return self.max_read_size

    def seek(self, offset: int, whence: int = SEEK_SET, split_seek: bool = False) -> int:
        if not split_seek:
            self.remaining_size += self.tell() - offset
        return super().seek(offset, whence)

    @property
    def short_name(self):
        return self.file_name.split('/')[-1]


class SplitFiles(LargeFilesBase):
    def process_large_file(self, file):
        file_name = os.path.basename(file)
        total_size = os.path.getsize(file)
        parts = math.ceil(total_size / self.client.max_file_size)
        zfill = SPLIT_FILE_PART_NUMBER_PADDING
        for part in range(parts):
            size = total_size - (part * self.client.max_file_size) if part >= parts - 1 else self.client.max_file_size
            splitted_file = SplitFile(self.client, file, size, f'{file_name}.{str(part).zfill(zfill)}')
            splitted_file.seek(self.client.max_file_size * part, split_seek=True)
            yield splitted_file
