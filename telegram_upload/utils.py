import asyncio
import itertools
import os
import shutil
from telegram_upload._compat import scandir
from telegram_upload.exceptions import TelegramEnvironmentError


def free_disk_usage(directory='.'):
    return shutil.disk_usage(directory)[2]


def truncate(text, max_length):
    return (text[:max_length - 3] + '...') if len(text) > max_length else text


def grouper(n, iterable):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def scantree(path, follow_symlinks=False):
    """Recursively yield DirEntry objects for given directory."""
    for entry in scandir(path):
        if entry.is_dir(follow_symlinks=follow_symlinks):
            yield from scantree(entry.path, follow_symlinks)  # see below for Python 2.x
        else:
            yield entry


def async_to_sync(coro):
    """
    Convert an async coroutine to sync execution.

    If an event loop is already running, this will raise a RuntimeError.
    For proper handling of nested event loops, consider using asyncio.run()
    or running in a separate thread.
    """
    try:
        # Check if there's already a running event loop
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # If we get here, we're already in an async context
        raise RuntimeError(
            "async_to_sync() cannot be called from a running event loop. "
            "Use 'await' instead or run in a separate thread."
        )


async def aislice(iterator, limit):
    items = []
    i = 0
    async for value in iterator:
        if i >= limit:
            break
        i += 1
        items.append(value)
    return items


async def amap(fn, iterator):
    async for value in iterator:
        yield fn(value)


async def sync_to_async_iterator(iterator):
    for value in iterator:
        yield value


def get_environment_integer(environment_name: str, default_value: int) -> int:
    """Get an integer from an environment variable.

    Args:
        environment_name: Name of the environment variable
        default_value: Default value if the environment variable is not set

    Returns:
        Integer value from environment or default

    Raises:
        TelegramEnvironmentError: If the value cannot be converted to integer
    """
    value = os.environ.get(environment_name)
    if value is None:
        return default_value

    try:
        return int(value)
    except ValueError:
        raise TelegramEnvironmentError(
            f"Environment variable {environment_name} must be an integer, got: '{value}'"
        )
