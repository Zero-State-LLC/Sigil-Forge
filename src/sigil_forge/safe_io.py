"""Read files that someone else may have written, without trusting them.

Every command that opens a glyph, wallpaper, index or manifest goes through
``read_regular``. It refuses symlinks, FIFOs and devices, and anything larger
than the caller's limit. The checks are made on the opened file, so nothing
can be swapped in between the check and the read, and a FIFO cannot block.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

# Generous for real files, small enough that a crafted one cannot exhaust memory.
MAX_SVG_BYTES = 4 * 1024 * 1024
MAX_PNG_FILE_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024


class UnsafeFile(OSError):
    """The path is not a plain file within the size limit."""


def read_regular(path: Path | str, limit: int) -> bytes:
    """Read at most ``limit`` bytes of a regular file, without following a link."""
    path = Path(path)
    if path.is_symlink():
        raise UnsafeFile("symlink")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise UnsafeFile("not a regular file")
        if info.st_size > limit:
            raise UnsafeFile("larger than the limit")
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, min(1 << 16, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > limit:
            raise UnsafeFile("larger than the limit")
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_head(path: Path | str, n: int) -> bytes:
    """First ``n`` bytes of a regular file, whatever its size; b"" if unsafe.

    For sniffing a file's type. Never reads more than ``n`` bytes, so a huge
    file costs nothing, and never raises: a link, pipe, directory or missing
    file just does not look like anything.
    """
    path = Path(path)
    try:
        if path.is_symlink():
            return b""
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except OSError:
        return b""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return b""
        return os.read(fd, n)
    except OSError:
        return b""
    finally:
        os.close(fd)


def read_text(path: Path | str, limit: int) -> str:
    """``read_regular`` decoded as UTF-8; raises ValueError if it is not text."""
    return read_regular(path, limit).decode("utf-8")
