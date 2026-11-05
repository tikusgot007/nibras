"""Single-instance lock and clean-shutdown marker (D-08).

An exclusive OS file lock on ``Data/nibras.lock`` guarantees one running
instance. The ``clean_shutdown`` session marker in ``core.db`` tells the
next startup whether the previous session ended cleanly.
"""

from __future__ import annotations

import os
from pathlib import Path

LOCK_FILENAME = "nibras.lock"


class SingleInstanceLock:
    """Exclusive lock file. On Windows uses ``msvcrt.locking``; elsewhere
    ``fcntl.flock`` (used by the Linux test/dev environment)."""

    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / LOCK_FILENAME
        self._fh = None
        self._locked = False

    def acquire(self) -> bool:
        """Try to take the lock. Returns False when another instance holds it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
            return False
        try:
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(f"{os.getpid()}\n".encode())
            self._fh.flush()
        except OSError:
            pass
        self._locked = True
        return True

    def release(self) -> None:
        if not self._locked or self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
        except OSError:
            pass
        self._fh = None
        self._locked = False


def read_clean_shutdown(conn) -> bool:
    row = conn.execute(
        "SELECT value FROM session WHERE key = 'clean_shutdown'"
    ).fetchone()
    return bool(row and row[0] == "1")


def write_clean_shutdown(conn, clean: bool) -> None:
    conn.execute(
        "INSERT INTO session (key, value) VALUES ('clean_shutdown', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("1" if clean else "0",),
    )
    conn.commit()
