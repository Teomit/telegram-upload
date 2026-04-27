"""Media metadata extraction via ffprobe.

Replaces hachoir (which abandoned its public API and required name-mangled
private attribute access for MKV files). Uses the ffprobe binary which ships
with ffmpeg — already a project dependency for thumbnail generation.

If ffprobe is not installed, probe() returns an empty MediaInfo rather than
raising — metadata is best-effort, the upload still works.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# MP4 / MOV / M4V are the formats Telegram can stream natively.
STREAMABLE_FORMATS = frozenset({'mov', 'mp4', 'm4a', 'm4v', '3gp', '3g2'})


@dataclass(frozen=True)
class MediaInfo:
    """File metadata extracted by ffprobe.

    All fields are best-effort. None means "not detected", not "missing".
    """
    duration: int | None = None        # seconds
    width: int | None = None
    height: int | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    producer: str | None = None
    format_name: str | None = None     # ffprobe's container format
    has_video: bool = False

    @property
    def supports_streaming(self) -> bool:
        """True if the container is one Telegram can stream natively."""
        if not self.format_name:
            return False
        # ffprobe returns comma-separated names like "mov,mp4,m4a,3gp,3g2,mj2"
        names = {n.strip().lower() for n in self.format_name.split(',')}
        return bool(names & STREAMABLE_FORMATS) and self.has_video


EMPTY = MediaInfo()


def get_ffprobe_command() -> str:
    """Return the ffprobe executable path/name. Honour FFPROBE_COMMAND env."""
    explicit = os.environ.get('FFPROBE_COMMAND')
    if explicit:
        return explicit
    return 'ffprobe.exe' if platform.system() == 'Windows' else 'ffprobe'


def has_ffprobe() -> bool:
    """Check whether ffprobe is available on PATH (or via FFPROBE_COMMAND)."""
    return shutil.which(get_ffprobe_command()) is not None


def probe(path: str) -> MediaInfo:
    """Run ffprobe on a file and return parsed MediaInfo.

    Returns EMPTY MediaInfo on any failure (ffprobe missing, invalid file,
    parse error). Logs at debug level so callers can see why if it matters.
    """
    cmd = [
        get_ffprobe_command(),
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=15)
    except FileNotFoundError:
        logger.debug('ffprobe is not available; metadata extraction skipped for %s', path)
        return EMPTY
    except subprocess.TimeoutExpired:
        logger.debug('ffprobe timed out for %s', path)
        return EMPTY

    if result.returncode != 0:
        logger.debug('ffprobe returned %s for %s: %s', result.returncode, path,
                     result.stderr.decode('utf-8', errors='replace')[:200])
        return EMPTY

    try:
        data = json.loads(result.stdout.decode('utf-8', errors='replace'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug('ffprobe output not parseable for %s: %s', path, e)
        return EMPTY

    fmt = data.get('format') or {}
    streams = data.get('streams') or []
    tags = {k.lower(): v for k, v in (fmt.get('tags') or {}).items()}

    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    width = int(video_stream['width']) if video_stream and 'width' in video_stream else None
    height = int(video_stream['height']) if video_stream and 'height' in video_stream else None

    duration_raw = fmt.get('duration')
    duration: int | None
    try:
        duration = int(float(duration_raw)) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None

    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        title=tags.get('title'),
        artist=tags.get('artist'),
        album=tags.get('album'),
        producer=tags.get('encoder') or tags.get('producer'),
        format_name=fmt.get('format_name'),
        has_video=video_stream is not None,
    )
