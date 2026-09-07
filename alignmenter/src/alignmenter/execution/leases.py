"""Process-held coordinator leases for local run directories."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class RunBusyError(RuntimeError):
    """Another coordinator holds this run's lease."""


@contextmanager
def coordinator_lease(run_dir: Path) -> Iterator[None]:
    """Hold one nonblocking OS lock through dispatch, capture, and finalization.

    Lock files must remain in place: unlinking one can create two locked inodes.
    The OS releases the lock on process death. This is a local-filesystem lease,
    not a distributed lease or a lock on a physical application/device.
    """
    path = Path(run_dir) / "coordinator.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RunBusyError("Run already has an active coordinator") from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunBusyError("Run already has an active coordinator") from exc
        yield
    finally:
        os.close(fd)
