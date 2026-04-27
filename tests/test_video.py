import unittest
from unittest.mock import MagicMock, patch

from telegram_upload._media import MediaInfo
from telegram_upload.exceptions import ThumbVideoError
from telegram_upload.video import call_ffmpeg, get_video_thumb


class TestCallFfmpeg(unittest.TestCase):
    @patch('telegram_upload.video.subprocess.Popen', side_effect=FileNotFoundError)
    def test_ffmpeg_missing(self, _):
        with self.assertRaises(ThumbVideoError):
            call_ffmpeg([])


class TestGetVideoThumb(unittest.TestCase):
    @patch('telegram_upload.video.os.path.lexists', return_value=True)
    @patch('telegram_upload.video.call_ffmpeg')
    @patch('telegram_upload.video.probe', return_value=MediaInfo(duration=60, width=1920, height=1080, has_video=True))
    def test_landscape(self, mock_probe, mock_ffmpeg, _):
        mock_ffmpeg.return_value.returncode = 0
        thumb = get_video_thumb('foo.mp4', output='out.jpg')
        self.assertEqual('out.jpg', thumb)
        mock_probe.assert_called_once_with('foo.mp4')

    @patch('telegram_upload.video.os.path.lexists', return_value=True)
    @patch('telegram_upload.video.call_ffmpeg')
    @patch('telegram_upload.video.probe', return_value=MediaInfo(duration=60, width=720, height=1280, has_video=True))
    def test_portrait(self, _, mock_ffmpeg, __):
        mock_ffmpeg.return_value.returncode = 0
        result = get_video_thumb('foo.mp4', output='out.jpg')
        self.assertEqual('out.jpg', result)

    @patch('telegram_upload.video.probe', return_value=MediaInfo())
    def test_no_dimensions_returns_none(self, _):
        # ffprobe not available / returned empty → don't generate thumb, return None.
        self.assertIsNone(get_video_thumb('foo.mp4', output='out.jpg'))

    @patch('telegram_upload.video.os.path.lexists', return_value=False)
    @patch('telegram_upload.video.call_ffmpeg')
    @patch('telegram_upload.video.probe', return_value=MediaInfo(duration=10, width=640, height=480, has_video=True))
    def test_ffmpeg_failure(self, _, mock_ffmpeg, __):
        mock_ffmpeg.return_value.returncode = 1
        self.assertIsNone(get_video_thumb('foo.mp4', output='out.jpg'))


class TestProbeIntegration(unittest.TestCase):
    @patch('telegram_upload._media.subprocess.run')
    def test_probe_parses_json(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                b'{"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.5",'
                b' "tags": {"title": "Hello", "artist": "World"}},'
                b' "streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}'
            ),
            stderr=b'',
        )
        from telegram_upload._media import probe
        info = probe('foo.mp4')
        self.assertEqual(12, info.duration)
        self.assertEqual(1920, info.width)
        self.assertEqual(1080, info.height)
        self.assertEqual('Hello', info.title)
        self.assertEqual('World', info.artist)
        self.assertTrue(info.has_video)
        self.assertTrue(info.supports_streaming)

    @patch('telegram_upload._media.subprocess.run', side_effect=FileNotFoundError)
    def test_probe_no_ffprobe(self, _):
        from telegram_upload._media import probe
        info = probe('foo.mp4')
        self.assertIsNone(info.duration)
        self.assertIsNone(info.width)
        self.assertFalse(info.has_video)
