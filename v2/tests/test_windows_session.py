"""Run the IPC and DPAPI tests on the Windows Python process."""
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest

from worker.local_secrets import read_secret


def test_ambiguous_secret_fails_closed(tmp_path):
    (tmp_path / "vault.key").write_bytes(b"legacy")
    (tmp_path / "vault.key.dpapi").write_bytes(b"protected")
    with pytest.raises(ValueError, match="ambiguous"):
        read_secret(tmp_path, "vault.key")


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows DPAPI")
def test_new_vault_can_be_read_by_a_second_windows_process(tmp_path):
    from fastapi.testclient import TestClient
    import pywintypes
    from worker.api import create_app

    completed = subprocess.run(
        [sys.executable, "-m", "worker.init_vault"],
        env={**os.environ, "NOTARAI_V2_HOME": str(tmp_path)},
        capture_output=True, check=True, timeout=10,
    )
    token = completed.stdout.decode().split()[-1]
    assert not (tmp_path / "vault.key").exists()
    assert not (tmp_path / "api.token").exists()
    assert token.encode() not in (tmp_path / "api.token.dpapi").read_bytes()
    client = TestClient(create_app(tmp_path))
    assert client.get("/v2/health", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    with pytest.raises(pywintypes.error):
        # DPAPI entropy binds each protected file to its purpose.
        (tmp_path / "vault.key.dpapi").write_bytes((tmp_path / "api.token.dpapi").read_bytes())
        read_secret(tmp_path, "vault.key")


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows named pipes")
@pytest.mark.parametrize("allowed", [True, False])
def test_windows_ipc_checks_session_across_processes(allowed):
    import pywintypes
    import win32pipe
    import winerror
    from worker.windows_ipc import listen_once, process_identity

    name = rf"\\.\pipe\NotarAI.V2.Test.{uuid4()}"
    sid, session, _ = process_identity()
    stop = Event()
    command = (
        "import sys, win32security;"
        "from worker.windows_ipc import probe;"
        "probe(sys.argv[1], win32security.ConvertStringSidToSid(sys.argv[2]))"
    )
    import win32security

    with ThreadPoolExecutor() as executor:
        result = executor.submit(listen_once, name, sid, sid, session + (not allowed), stop)
        try:
            deadline = monotonic() + 5
            while True:
                try:
                    win32pipe.WaitNamedPipe(name, 100)
                    break
                except pywintypes.error as error:
                    if error.winerror not in {winerror.ERROR_FILE_NOT_FOUND, winerror.ERROR_SEM_TIMEOUT}:
                        raise
                    if result.done():
                        result.result()
                        pytest.fail("named pipe closed before the client connected")
                    if monotonic() >= deadline:
                        raise TimeoutError("test pipe did not start")
                    sleep(0.025)
            completed = subprocess.run(
                [sys.executable, "-c", command, name, win32security.ConvertSidToStringSid(sid)],
                capture_output=True, timeout=10,
            )
            assert result.result(timeout=5) is allowed, completed.stderr.decode(errors="replace")
            assert (completed.returncode == 0) is allowed, completed.stderr.decode(errors="replace")
        finally:
            stop.set()
