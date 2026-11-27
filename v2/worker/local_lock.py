"""One process at a time may serve or re-key a vault. An OS lock, released when the process dies."""
import os
from pathlib import Path


class Busy(Exception):
    pass


def acquire(home: Path):
    """Return an open handle holding the lock; close it to release. Raises Busy if someone else holds it."""
    handle = open(Path(home) / "worker.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise Busy() from None
    return handle
