"""Console script for telegram-upload."""
import logging

import click

from telegram_upload.client import TelegramManagerClient, get_message_file_attribute
from telegram_upload.config import CONFIG_FILE, default_config
from telegram_upload.download_files import JoinDownloadSplitFiles, KeepDownloadSplitFiles
from telegram_upload.exceptions import catch
from telegram_upload.logging_config import setup_logging
from telegram_upload.upload_files import NoDirectoriesFiles, NoLargeFiles, RecursiveFiles, SplitFiles, is_valid_file

DIRECTORY_MODES = {
    'fail': NoDirectoriesFiles,
    'recursive': RecursiveFiles,
}
LARGE_FILE_MODES = {
    'fail': NoLargeFiles,
    'split': SplitFiles,
}
DOWNLOAD_SPLIT_FILE_MODES = {
    'keep': KeepDownloadSplitFiles,
    'join': JoinDownloadSplitFiles,
}

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


def get_file_display_name(message):
    parts = []
    document = message.document
    if document and document.mime_type:
        parts.append(document.mime_type.split('/')[0])
    file_attr = get_message_file_attribute(message) if document else None
    if file_attr:
        parts.append(file_attr.file_name)
    if message.text:
        parts.append(f'[{message.text}]' if parts else message.text)
    sender = message.sender
    if sender is not None and getattr(sender, 'first_name', None) is not None:
        parts.append('by')
        if sender.first_name:
            parts.append(sender.first_name)
        if getattr(sender, 'last_name', None):
            parts.append(sender.last_name)
        if getattr(sender, 'username', None):
            parts.append(f'@{sender.username}')
    parts.append(f'{message.date}')
    return ' '.join(parts)


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help_text = kwargs.get('help', '')
        if self.mutually_exclusive:
            kwargs['help'] = (
                f'{help_text} NOTE: This argument is mutually exclusive with '
                f'arguments: [{self.mutually_exclusive_text}].'
            )
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                f"Illegal usage: `{self.name}` is mutually exclusive with "
                f"arguments `{self.mutually_exclusive_text}`."
            )
        return super().handle_parse_result(ctx, opts, args)

    @property
    def mutually_exclusive_text(self):
        return ', '.join(x.replace('_', '-') for x in self.mutually_exclusive)


def _resolve_recipient(value):
    """Convert numeric strings to int, default to 'me'."""
    if value is None:
        return 'me'
    if isinstance(value, str) and value.lstrip('-+').isdigit():
        return int(value)
    return value


@click.command()
@click.argument('files', nargs=-1, required=True)
@click.option('--to', default=None,
              help='Phone number, username, invite link or "me" (saved messages). By default "me".')
@click.option('--config', default=None,
              help=f'Configuration file to use. By default "{CONFIG_FILE}".')
@click.option('-d', '--delete-on-success', is_flag=True,
              help='Delete local file after successful upload.')
@click.option('--print-file-id', is_flag=True,
              help='Print the id of the uploaded file after the upload.')
@click.option('--force-file', is_flag=True,
              help='Force send as a file. The filename will be preserved but the preview will not be available.')
@click.option('-f', '--forward', multiple=True,
              help='Forward the file to a chat (alias or id) or user (username, mobile or id). '
                   'This option can be used multiple times.')
@click.option('--directories', default='fail', type=click.Choice(list(DIRECTORY_MODES.keys())),
              help='Defines how to process directories. By default directories are not accepted.')
@click.option('--large-files', default='fail', type=click.Choice(list(LARGE_FILE_MODES.keys())),
              help='Defines how to process large files unsupported for Telegram. By default large files are rejected.')
@click.option('--caption', type=str, help='Change file description. By default the file name.')
@click.option('--no-thumbnail', is_flag=True, cls=MutuallyExclusiveOption, mutually_exclusive=['thumbnail_file'],
              help='Disable thumbnail generation.')
@click.option('--thumbnail-file', default=None, cls=MutuallyExclusiveOption, mutually_exclusive=['no_thumbnail'],
              help='Path to the preview file to use for the uploaded file.')
@click.option('-p', '--proxy', default=None,
              help='Use an http proxy, socks4, socks5 or mtproxy. '
                   'Example: socks5://user:pass@1.2.3.4:8080 or mtproxy://secret@1.2.3.4:443.')
@click.option('-a', '--album', is_flag=True, help='Send video or photos as an album.')
@click.option('--sort', is_flag=True, help='Sort files by name before uploading.')
@click.option('--log-level', default='INFO', type=click.Choice(LOG_LEVELS, case_sensitive=False),
              help='Set logging level. Default: INFO')
def upload(files, to, config, delete_on_success, print_file_id, force_file, forward, directories, large_files, caption,
           no_thumbnail, thumbnail_file, proxy, album, sort, log_level):
    """Upload one or more files to Telegram using your personal account.

    The maximum file size is 2 GiB for free users and 4 GiB for premium accounts.
    By default, files are saved in your saved messages.
    """
    setup_logging(level=getattr(logging, log_level.upper()))
    logger = logging.getLogger(__name__)
    logger.debug('Starting upload with files: %s', files)

    client = TelegramManagerClient(config or default_config(), proxy=proxy)
    client.start()

    to = _resolve_recipient(to)

    valid_files = filter(
        lambda file: is_valid_file(file, lambda message: click.echo(message, err=True)),
        files,
    )
    files_iter = DIRECTORY_MODES[directories](client, valid_files)
    if directories == 'fail':
        files_iter = list(files_iter)

    if no_thumbnail:
        thumbnail = False
    elif thumbnail_file:
        thumbnail = thumbnail_file
    else:
        thumbnail = None

    files_cls = LARGE_FILE_MODES[large_files]
    files_iter = files_cls(client, files_iter, caption=caption, thumbnail=thumbnail, force_file=force_file)
    if large_files == 'fail':
        files_iter = list(files_iter)

    if sort:
        files_iter = sorted(files_iter, key=lambda x: x.name)

    if album:
        client.send_files_as_album(to, files_iter, delete_on_success, print_file_id, forward)
    else:
        client.send_files(to, files_iter, delete_on_success, print_file_id, forward)


@click.command()
@click.option('--from', '-f', 'from_', default='',
              help='Phone number, username, chat id or "me" (saved messages). By default "me".')
@click.option('--config', default=None,
              help=f'Configuration file to use. By default "{CONFIG_FILE}".')
@click.option('-d', '--delete-on-success', is_flag=True,
              help='Delete telegram message after successful download. Useful for creating a download queue.')
@click.option('-p', '--proxy', default=None,
              help='Use an http proxy, socks4, socks5 or mtproxy.')
@click.option('-m', '--split-files', default='keep', type=click.Choice(list(DOWNLOAD_SPLIT_FILE_MODES.keys())),
              help='Defines how to download large files split in Telegram. By default the files are not merged.')
@click.option('--log-level', default='INFO', type=click.Choice(LOG_LEVELS, case_sensitive=False),
              help='Set logging level. Default: INFO')
def download(from_, config, delete_on_success, proxy, split_files, log_level):
    """Download all the latest messages that are files in a chat.

    By default downloads from "me" (saved messages). It is recommended to forward
    the files to download to "saved messages" and use ``--delete-on-success``.
    Forwarded messages will be removed from the chat after downloading, like a queue.
    """
    setup_logging(level=getattr(logging, log_level.upper()))
    logger = logging.getLogger(__name__)
    logger.debug('Starting download from: %s', from_)

    client = TelegramManagerClient(config or default_config(), proxy=proxy)
    client.start()

    from_ = _resolve_recipient(from_ or None)

    messages = client.find_files(from_)
    messages_cls = DOWNLOAD_SPLIT_FILE_MODES[split_files]
    download_files = messages_cls(reversed(list(messages)))
    client.download_files(from_, download_files, delete_on_success)


upload_cli = catch(upload)
download_cli = catch(download)


if __name__ == '__main__':
    import re
    import sys

    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    commands = {'upload': upload_cli, 'download': download_cli}
    if len(sys.argv) < 2:
        sys.stderr.write(f'A command is required. Available commands: {", ".join(commands)}\n')
        sys.exit(1)
    if sys.argv[1] not in commands:
        sys.stderr.write(f'{sys.argv[1]} is an invalid command. Valid commands: {", ".join(commands)}\n')
        sys.exit(1)
    fn = commands[sys.argv[1]]
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    sys.exit(fn())
