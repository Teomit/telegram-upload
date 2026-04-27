import os
import platform
import re
import subprocess
import tempfile

from hachoir.core import config as hachoir_config
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from telegram_upload.exceptions import ThumbVideoError

hachoir_config.quiet = True


def video_metadata(file):
    return extractMetadata(createParser(file))


def call_ffmpeg(args):
    try:
        return subprocess.Popen([get_ffmpeg_command()] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise ThumbVideoError('ffmpeg command is not available. Thumbnails for videos are not available!') from e


def get_ffmpeg_command():
    return os.environ.get('FFMPEG_COMMAND',
                          'ffmpeg.exe' if platform.system() == 'Windows' else 'ffmpeg')


def get_video_size(file):
    p = call_ffmpeg([
        '-i', file,
    ])
    stdout, stderr = p.communicate()
    video_lines = re.findall(': Video: ([^\n]+)', stderr.decode('utf-8', errors='ignore'))
    if not video_lines:
        return
    matchs = re.findall(r"(\d{2,6})x(\d{2,6})", video_lines[0])
    if matchs:
        return [int(x) for x in matchs[0]]


def get_video_thumb(file, output=None, size=200):
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
    metadata = video_metadata(file)
    if metadata is None:
        return
    duration = metadata.get('duration').seconds if metadata.has('duration') else 0
    ratio = get_video_size(file)
    if ratio is None:
        raise ThumbVideoError('Video ratio is not available.')
    if ratio[0] / ratio[1] > 1:
        width, height = size, -1
    else:
        width, height = -1, size
    p = call_ffmpeg([
        '-ss', str(int(duration / 2)),
        '-i', file,
        '-filter:v',
        f'scale={width}:{height}',
        '-vframes:v', '1',
        output,
    ])
    p.communicate()
    if not p.returncode and os.path.lexists(file):
        return output
