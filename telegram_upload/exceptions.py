"""Exceptions and the top-level CLI exception handler."""
import sys

import click

from telegram_upload.config import prompt_config


class ThumbError(Exception):
    pass


class ThumbVideoError(ThumbError):
    pass


class TelegramUploadError(Exception):
    body = ''
    error_code = 1

    def __init__(self, extra_body: str = ''):
        self.extra_body = extra_body

    def __str__(self) -> str:
        msg = self.__class__.__name__
        if self.body:
            msg += f': {self.body}'
        if self.extra_body:
            msg += ('. {}' if self.body else ': {}').format(self.extra_body)
        return msg


class MissingFileError(TelegramUploadError):
    pass


class InvalidApiFileError(TelegramUploadError):
    def __init__(self, config_file: str, extra_body: str = ''):
        self.config_file = config_file
        super().__init__(extra_body)


class TelegramInvalidFile(TelegramUploadError):
    error_code = 3


class TelegramUploadNoSpaceError(TelegramUploadError):
    error_code = 28


class TelegramUploadDataLoss(TelegramUploadError):
    error_code = 29


class TelegramProxyError(TelegramUploadError):
    error_code = 30


def catch(fn):
    """Decorate a CLI command so TelegramUploadError → exit code, not traceback."""
    def wrap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except InvalidApiFileError as e:
            click.echo('The api_id/api_hash combination is invalid. Re-enter both values.')
            prompt_config(e.config_file)
            return catch(fn)(*args, **kwargs)
        except TelegramUploadError as e:
            sys.stderr.write(f'[Error] telegram-upload Exception:\n{e}\n')
            sys.exit(e.error_code)
    return wrap
