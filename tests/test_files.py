import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from telegram_upload._backend._telethon._manager import USER_MAX_FILE_SIZE
from telegram_upload._media import MediaInfo
from telegram_upload.exceptions import TelegramInvalidFile
from telegram_upload.upload_files import (
    NoDirectoriesFiles,
    NoLargeFiles,
    RecursiveFiles,
    SplitFile,
    SplitFiles,
    get_file_attributes,
)


class TestGetFileAttributes(unittest.TestCase):
    def test_not_video(self):
        self.assertEqual(get_file_attributes('foo.png'), [])

    @patch('telegram_upload.upload_files.probe')
    def test_video(self, mock_probe):
        mock_probe.return_value = MediaInfo(
            duration=1000, width=1920, height=1080,
            format_name='mov,mp4', has_video=True,
        )
        attrs = get_file_attributes('foo.mp4')
        self.assertEqual(1, len(attrs))
        self.assertEqual(1920, attrs[0].w)
        self.assertEqual(1080, attrs[0].h)
        self.assertEqual(1000, attrs[0].duration)
        self.assertTrue(attrs[0].supports_streaming)

    @patch('telegram_upload.upload_files.probe', return_value=MediaInfo())
    def test_video_no_metadata(self, _):
        # ffprobe missing or failed → no DocumentAttributeVideo emitted.
        self.assertEqual([], get_file_attributes('foo.mp4'))


class TestRecursiveFiles(unittest.TestCase):
    @patch('telegram_upload.upload_files.scantree', return_value=[])
    @patch('telegram_upload.upload_files.os.path.isdir', return_value=False)
    def test_one_file(self, m1, m2):
        self.assertEqual(list(RecursiveFiles(MagicMock(), ['foo'])), ['foo'])

    @patch('telegram_upload.upload_files.scantree')
    @patch('telegram_upload.upload_files.os.path.isdir', return_value=True)
    def test_directory(self, m1, m2):
        directory = Mock()
        directory.is_dir.side_effect = [True, False]
        file = Mock()
        file.is_dir.return_value = False
        side_effect = [file] * 3
        m2.return_value = side_effect
        self.assertEqual(list(RecursiveFiles(MagicMock(), ['foo'])), [x.path for x in side_effect])


class TestNoDirectoriesFiles(unittest.TestCase):
    @patch('telegram_upload.upload_files.scantree', return_value=[])
    @patch('telegram_upload.upload_files.os.path.isdir', return_value=False)
    def test_one_file(self, m1, m2):
        self.assertEqual(list(NoDirectoriesFiles(MagicMock(), ['foo'])), ['foo'])

    @patch('telegram_upload.upload_files.os.path.isdir', return_value=True)
    def test_directory(self, m):
        with self.assertRaises(TelegramInvalidFile):
            next(NoDirectoriesFiles(MagicMock(), ['foo']))


class TestNoLargeFiles(unittest.TestCase):
    @patch('telegram_upload.upload_files.os.path.getsize', return_value=USER_MAX_FILE_SIZE - 1)
    @patch('telegram_upload.upload_files.File')
    def test_small_file(self, m1, m2):
        self.assertEqual(len(list(NoLargeFiles(MagicMock(max_file_size=USER_MAX_FILE_SIZE), ['foo']))), 1)

    @patch('telegram_upload.upload_files.os.path.getsize', return_value=USER_MAX_FILE_SIZE + 1)
    def test_big_file(self, m):
        with self.assertRaises(TelegramInvalidFile):
            next(NoLargeFiles(MagicMock(max_file_size=1024 ** 3), ['foo']))


class TestSplitFile(unittest.TestCase):
    def test_file(self):
        this_file = os.path.abspath(__file__)
        size = os.path.getsize(this_file)
        file0 = SplitFile(MagicMock(), this_file, size - 100, 'test.py.00')
        file1 = SplitFile(MagicMock(), this_file, 100, 'test.py.01')
        file1.seek(size - 100, split_seek=True)
        with open(this_file, 'rb') as f:
            content = f.read()
        self.assertEqual(file0.readall() + file1.readall(), content)
        self.assertEqual(file0.file_name, 'test.py.00')
        self.assertEqual(file1.file_size, 100)
        file0.close()
        file1.close()


class TestSplitFiles(unittest.TestCase):
    @patch('telegram_upload.upload_files.os.path.getsize', return_value=USER_MAX_FILE_SIZE - 1)
    @patch('telegram_upload.upload_files.File')
    def test_small_file(self, m1, m2):
        self.assertEqual(len(list(SplitFiles(MagicMock(max_file_size=USER_MAX_FILE_SIZE), ['foo']))), 1)

    @patch('telegram_upload.upload_files.os.path.getsize', return_value=USER_MAX_FILE_SIZE + 1000)
    @patch('telegram_upload.upload_files.SplitFile.__init__', return_value=None)
    @patch('telegram_upload.upload_files.SplitFile.seek')
    def test_big_file(self, m_getsize, m_init, m_seek):
        mock_client = MagicMock(max_file_size=USER_MAX_FILE_SIZE)
        files = list(SplitFiles(mock_client, ['foo']))
        self.assertEqual(len(files), 2)
        self.assertEqual(m_init.call_args_list[0][0], (mock_client, 'foo', USER_MAX_FILE_SIZE, 'foo.00'))
        self.assertEqual(m_init.call_args_list[1][0], (mock_client, 'foo', 1000, 'foo.01'))
