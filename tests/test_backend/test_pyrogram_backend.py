import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from tgupi._backend._pyrogram._adapter import PyrogramMessageAdapter
from tgupi._backend._pyrogram._backend import (
    BOT_USER_MAX_FILE_SIZE,
    PREMIUM_USER_MAX_CAPTION_LENGTH,
    PREMIUM_USER_MAX_FILE_SIZE,
    USER_MAX_CAPTION_LENGTH,
    USER_MAX_FILE_SIZE,
    PyrogramBackend,
    _get_proxy_environment_variable,
    _media_kind,
    _parse_proxy,
)
from tgupi.exceptions import InvalidApiFileError, TelegramProxyError, TelegramUploadError

CONFIG_DATA = {"api_hash": "h", "api_id": 1}


class TestParseProxy(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(_parse_proxy(None))

    def test_malformed(self):
        with self.assertRaises(TelegramProxyError):
            _parse_proxy("foo")

    def test_unsupported_scheme(self):
        with self.assertRaises(TelegramProxyError):
            _parse_proxy("mtproxy://secret@host:443")  # mtproxy unsupported by pyrogram

    def test_socks5(self):
        result = _parse_proxy("socks5://user:pass@host:1080")
        self.assertEqual({
            "scheme": "socks5", "hostname": "host", "port": 1080,
            "username": "user", "password": "pass",
        }, result)


class TestMediaKind(unittest.TestCase):
    def test_force_file(self):
        self.assertEqual("document", _media_kind("foo.mp4", force_file=True))

    def test_video(self):
        self.assertEqual("video", _media_kind("foo.mp4", force_file=False))

    def test_photo(self):
        self.assertEqual("photo", _media_kind("foo.jpg", force_file=False))

    def test_audio(self):
        self.assertEqual("audio", _media_kind("foo.mp3", force_file=False))

    def test_other_falls_to_document(self):
        self.assertEqual("document", _media_kind("foo.zip", force_file=False))


class TestPyrogramBackendInit(unittest.TestCase):
    @patch("builtins.open", mock_open(read_data=json.dumps(CONFIG_DATA)))
    @patch("tgupi._backend._pyrogram._backend.Client")
    def test_init_basic(self, mock_client_cls):
        backend = PyrogramBackend("config.json")
        mock_client_cls.assert_called_once()
        kwargs = mock_client_cls.call_args.kwargs
        self.assertEqual(1, kwargs["api_id"])
        self.assertEqual("h", kwargs["api_hash"])
        self.assertIsNotNone(backend)

    @patch("builtins.open", mock_open(read_data="{not json"))
    def test_init_invalid_json(self):
        with self.assertRaises(TelegramUploadError):
            PyrogramBackend("config.json")

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_init_missing_file(self, _):
        with self.assertRaises(TelegramUploadError):
            PyrogramBackend("missing.json")

    @patch("builtins.open", mock_open(read_data=json.dumps({"api_hash": "h"})))
    def test_init_missing_api_id(self):
        with self.assertRaises(InvalidApiFileError):
            PyrogramBackend("config.json")

    @patch("builtins.open", mock_open(read_data=json.dumps({"api_id": 1})))
    def test_init_missing_api_hash(self):
        with self.assertRaises(InvalidApiFileError):
            PyrogramBackend("config.json")


class TestMaxFileSize(unittest.TestCase):
    def _make(self, **me_kwargs):
        backend = PyrogramBackend.__new__(PyrogramBackend)
        # bypass cached_property cache
        backend.__dict__["me"] = MagicMock(**me_kwargs)
        return backend

    def test_user(self):
        b = self._make(is_premium=False, is_bot=False)
        self.assertEqual(USER_MAX_FILE_SIZE, b.max_file_size)
        self.assertEqual(USER_MAX_CAPTION_LENGTH, b.max_caption_length)

    def test_bot(self):
        b = self._make(is_premium=False, is_bot=True)
        self.assertEqual(BOT_USER_MAX_FILE_SIZE, b.max_file_size)

    def test_premium(self):
        b = self._make(is_premium=True, is_bot=False)
        self.assertEqual(PREMIUM_USER_MAX_FILE_SIZE, b.max_file_size)
        self.assertEqual(PREMIUM_USER_MAX_CAPTION_LENGTH, b.max_caption_length)


class TestProxyEnv(unittest.TestCase):
    @patch.dict("os.environ", {"TGUPI_PROXY": "socks5://h:1080"}, clear=True)
    def test_tgupi_proxy(self):
        self.assertEqual("socks5://h:1080", _get_proxy_environment_variable())

    @patch.dict("os.environ", {}, clear=True)
    def test_none(self):
        self.assertIsNone(_get_proxy_environment_variable())


class TestPyrogramMessageAdapter(unittest.TestCase):
    def test_document(self):
        raw = MagicMock()
        raw.document.file_name = "doc.pdf"
        raw.document.file_size = 1234
        raw.document.mime_type = "application/pdf"
        raw.video = None
        raw.audio = None
        raw.voice = None
        raw.video_note = None
        raw.animation = None
        raw.photo = None
        raw.sticker = None
        adapter = PyrogramMessageAdapter(raw)
        doc = adapter.document
        self.assertEqual(1234, doc.size)
        self.assertEqual("doc.pdf", doc.file_name)
        self.assertEqual("application/pdf", doc.mime_type)
        self.assertEqual([("doc.pdf",)], [(a.file_name,) for a in doc.attributes])

    def test_no_media(self):
        raw = MagicMock()
        for attr in ("document", "video", "audio", "voice", "video_note", "animation", "photo", "sticker"):
            setattr(raw, attr, None)
        adapter = PyrogramMessageAdapter(raw)
        self.assertIsNone(adapter.document)

    def test_video(self):
        raw = MagicMock()
        raw.document = None
        raw.video.file_name = None
        raw.video.file_unique_id = "abc"
        raw.video.file_size = 100
        raw.video.mime_type = "video/mp4"
        raw.audio = raw.voice = raw.video_note = raw.animation = raw.photo = raw.sticker = None
        adapter = PyrogramMessageAdapter(raw)
        # should fall back to file_unique_id-based name with video extension
        self.assertEqual("abc.mp4", adapter.document.file_name)
