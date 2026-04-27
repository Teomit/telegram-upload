import shutil
from os import scandir


def free_disk_usage(directory: str = '.') -> int:
    return shutil.disk_usage(directory)[2]


def truncate(text: str, max_length: int) -> str:
    return (text[:max_length - 3] + '...') if len(text) > max_length else text


def sizeof_fmt(num: float, suffix: str = 'B') -> str:
    for unit in ('', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi'):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def scantree(path: str, follow_symlinks: bool = False):
    """Recursively yield DirEntry objects for the given directory."""
    for entry in scandir(path):
        if entry.is_dir(follow_symlinks=follow_symlinks):
            yield from scantree(entry.path, follow_symlinks)
        else:
            yield entry
