"""Fail-closed plaintext lifetime controls for a ONE-JOB Nitro guest.

This module never certifies secure RAM erasure. Python strings, Playwright and
browser subprocesses may retain copies until the isolated task is destroyed.
All functions are guest-only; they must not run in the web/API process.
"""
from __future__ import annotations

import contextlib
import ctypes
import faulthandler
import os
import resource
import shutil
import sys
import tempfile
from pathlib import Path


class UnsafeGuestRuntime(RuntimeError):
    """Constant safe errors; never interpolate customer-supplied values."""


def assert_tmpfs(*, path: str = "/tmp", mountinfo: str = "/proc/self/mountinfo") -> None:
    """Reject overlay/bind/persistent storage for the browser scratch directory.

    Require an explicit /tmp tmpfs mount, rather than trusting /tmp's name.
    """
    target = os.path.realpath(path)
    try:
        lines = Path(mountinfo).read_text(encoding="utf-8").splitlines()
        mounted = [
            line.split(" - ", 1)[1].split()[0]
            for line in lines
            if " - " in line and line.split(" - ", 1)[0].split()[4] == target
        ]
    except (OSError, ValueError, IndexError):
        raise UnsafeGuestRuntime("ephemeral storage verification failed") from None
    if mounted != ["tmpfs"]:
        raise UnsafeGuestRuntime("tmpfs required for confidential browser")


def harden_guest_process() -> None:
    """Disable Linux core dumps and ptrace-able process dumps, or refuse work."""
    if not sys.platform.startswith("linux"):
        raise UnsafeGuestRuntime("Linux guest required")
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
            raise UnsafeGuestRuntime("core dump limit not enforced")
        # PR_SET_DUMPABLE = 4; 0 prevents ptrace and core dumping for
        # normal unprivileged processes. This is defense in depth, NOT a
        # protection against the Nitro guest's own compromised code.
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong,
                              ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        libc.prctl.restype = ctypes.c_int
        if libc.prctl(4, 0, 0, 0, 0) != 0:
            raise UnsafeGuestRuntime("dumpable process could not be disabled")
        faulthandler.disable()
        os.umask(0o077)
        assert_tmpfs()
    except (OSError, ValueError, AttributeError):
        raise UnsafeGuestRuntime("guest process hardening failed") from None


@contextlib.contextmanager
def ephemeral_browser_home():
    """Keep Chromium HOME, XDG state and crash/cache files on guest tmpfs.

    A unique temp directory is removed on normal/exceptional Python exits;
    crash recovery relies on termination of the whole Nitro task. This is
    NOT cryptographic deletion nor a guarantee against RAM snapshots.
    """
    assert_tmpfs()
    with tempfile.TemporaryDirectory(prefix="notarai-guest-", dir="/tmp") as folder:
        keys = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR")
        prior = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ[key] = folder
            yield folder
        finally:
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def audit_no_plaintext_markers(root: Path, markers: tuple[bytes, ...]) -> int:
    """Offline synthetic-test helper; NEVER scan customer data or real DEKs.

    Returns count of files inspected, raises a constant-message failure on a
    detected marker or inaccessible file. No file content enters logs.
    """
    if not markers or any(not isinstance(x, bytes) or not x for x in markers):
        raise ValueError("synthetic marker set required")
    count = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise UnsafeGuestRuntime("artifact symlink not allowed")
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            raise UnsafeGuestRuntime("artifact inspection unavailable") from None
        count += 1
        if any(marker in data for marker in markers):
            raise UnsafeGuestRuntime("plaintext persisted in artifact")
    return count
