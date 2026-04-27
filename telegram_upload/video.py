"""Video thumbnail generation via ffmpeg.

Metadata extraction (duration/width/height/tags) lives in `_media.py`
and uses ffprobe. This module is only for grabbing a JPEG frame from
the middle of a video.
"""
import logging
import os
import platform
import subprocess
import tempfile

from telegram_upload._media import probe
from telegram_upload.exceptions import ThumbVideoError

logger = logging.getLogger(__name__)


def get_ffmpeg_command() -> str:
    return os.environ.get(
        'FFMPEG_COMMAND',
        'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg',
    )


def call_ffmpeg(args: list[str]) -> subprocess.Popen:
    try:
        return subprocess.Popen(
            [get_ffmpeg_command(), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ThumbVideoError(
            'ffmpeg command is not available. Thumbnails for videos are not available!'
        ) from e


def get_video_thumb(file: str, output: str | None = None, size: int = 200) -> str | None:
    """Generate a JPEG thumbnail from a video, return its path.

    Returns None if the video has no detectable dimensions or duration,
    or if ffmpeg fails. Raises ThumbVideoError if ffmpeg is missing.
    """
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)

    info = probe(file)
    if not info.width or not info.height:
        return None
    duration = info.duration or 0

    if info.width / info.height > 1:
        scale_w, scale_h = size, -1
    else:
        scale_w, scale_h = -1, size

    p = call_ffmpeg([
        '-y',
        '-ss', str(int(duration / 2)),
        '-i', file,
        '-filter:v', f'scale={scale_w}:{scale_h}',
        '-vframes:v', '1',
        output,
    ])
    p.communicate()
    if p.returncode == 0 and os.path.lexists(output):
        return output
    return None
