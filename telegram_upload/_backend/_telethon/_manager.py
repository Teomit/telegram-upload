import getpass
import json
import logging
import os
import re
from functools import cached_property
from urllib.parse import urlparse

import click
import telethon.sync  # noqa: F401  -- side-effect import enabling sync API
from telethon.errors import ApiIdInvalidError
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.types import DocumentAttributeFilename, InputPeerUser, User

from telegram_upload._backend._telethon._download import TelegramDownloadClient
from telegram_upload._backend._telethon._upload import TelegramUploadClient
from telegram_upload.config import SESSION_FILE
from telegram_upload.exceptions import InvalidApiFileError, TelegramProxyError, TelegramUploadError

logger = logging.getLogger(__name__)


BOT_USER_MAX_FILE_SIZE = 52428800  # 50MB
USER_MAX_FILE_SIZE = 2097152000  # 2GB
PREMIUM_USER_MAX_FILE_SIZE = 4194304000  # 4GB
USER_MAX_CAPTION_LENGTH = 1024
PREMIUM_USER_MAX_CAPTION_LENGTH = 2048
PROXY_ENVIRONMENT_VARIABLE_NAMES = [
    'TELEGRAM_UPLOAD_PROXY',
    'HTTPS_PROXY',
    'HTTP_PROXY',
]


def get_message_file_attribute(message):
    return next(filter(lambda x: isinstance(x, DocumentAttributeFilename),
                       message.document.attributes), None)


def phone_match(value):
    match = re.match(r'\+?[0-9.()\[\] \-]+', value)
    if match is None:
        raise ValueError(f'{value} is not a valid phone')
    return value


def get_proxy_environment_variable():
    for env_name in PROXY_ENVIRONMENT_VARIABLE_NAMES:
        if env_name in os.environ:
            return os.environ[env_name]


def parse_proxy_string(proxy: str | None):
    if not proxy:
        return None
    proxy_parsed = urlparse(proxy)
    if not proxy_parsed.scheme or not proxy_parsed.hostname or not proxy_parsed.port:
        raise TelegramProxyError(f'Malformed proxy address: {proxy}')
    if proxy_parsed.scheme == 'mtproxy':
        return ('mtproxy', proxy_parsed.hostname, proxy_parsed.port, proxy_parsed.username)
    try:
        import socks
    except ImportError as e:
        raise TelegramProxyError('pysocks module is required for use HTTP/socks proxies. '
                                 'Install it using: pip install pysocks') from e
    proxy_type = {
        'http': socks.HTTP,
        'socks4': socks.SOCKS4,
        'socks5': socks.SOCKS5,
    }.get(proxy_parsed.scheme)
    if proxy_type is None:
        raise TelegramProxyError(f'Unsupported proxy type: {proxy_parsed.scheme}')
    return (proxy_type, proxy_parsed.hostname, proxy_parsed.port, True,
            proxy_parsed.username, proxy_parsed.password)


class TelethonBackend(TelegramUploadClient, TelegramDownloadClient):
    def __init__(self, config_file, proxy=None, **kwargs):
        self.config_file = config_file

        # Load and validate configuration file with proper error handling
        try:
            with open(config_file, encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError as e:
            raise TelegramUploadError(
                f"Configuration file not found: {config_file}\n"
                f"Please create a config file or run telegram-upload with --config option."
            ) from e
        except json.JSONDecodeError as e:
            raise TelegramUploadError(
                f"Invalid JSON in configuration file {config_file}:\n"
                f"  Line {e.lineno}, Column {e.colno}: {e.msg}\n"
                f"Please check your JSON syntax."
            ) from e
        except PermissionError as e:
            raise TelegramUploadError(
                f"Permission denied when reading configuration file: {config_file}"
            ) from e
        except OSError as e:
            raise TelegramUploadError(
                f"Failed to read configuration file {config_file}: {e}"
            ) from e

        # Validate required configuration keys
        if 'api_id' not in config:
            raise InvalidApiFileError(
                f"Missing 'api_id' in configuration file: {config_file}"
            )
        if 'api_hash' not in config:
            raise InvalidApiFileError(
                f"Missing 'api_hash' in configuration file: {config_file}"
            )
        proxy = proxy if proxy is not None else get_proxy_environment_variable()
        proxy = parse_proxy_string(proxy)
        if proxy and proxy[0] == 'mtproxy':
            proxy = proxy[1:]
            kwargs['connection'] = ConnectionTcpMTProxyRandomizedIntermediate
        super().__init__(config.get('session', SESSION_FILE), config['api_id'], config['api_hash'],
                         proxy=proxy, **kwargs)

    def start(
            self,
            phone=lambda: click.prompt('Please enter your phone', type=phone_match),
            password=lambda: getpass.getpass('Please enter your password: '),
            *,
            bot_token=None, force_sms=False, code_callback=None,
            first_name='New User', last_name='', max_attempts=3):
        try:
            return super().start(phone=phone, password=password, bot_token=bot_token, force_sms=force_sms,
                                 first_name=first_name, last_name=last_name, max_attempts=max_attempts)
        except ApiIdInvalidError as e:
            raise InvalidApiFileError(self.config_file) from e

    @cached_property
    def me(self) -> User | InputPeerUser:
        return self.get_me()

    @property
    def max_file_size(self):
        if hasattr(self.me, 'premium') and self.me.premium:
            return PREMIUM_USER_MAX_FILE_SIZE
        elif self.me.bot:
            return BOT_USER_MAX_FILE_SIZE
        else:
            return USER_MAX_FILE_SIZE

    @property
    def max_caption_length(self):
        if hasattr(self.me, 'premium') and self.me.premium:
            return PREMIUM_USER_MAX_CAPTION_LENGTH
        else:
            return USER_MAX_CAPTION_LENGTH
