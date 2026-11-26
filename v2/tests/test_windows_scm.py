"""Opt-in integration test for SCM on a disposable Windows machine."""
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep

import pytest


@pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("NOTARAI_V2_TEST_SCM") != "1",
    reason="requires a disposable Windows machine and permission to register a temporary service",
)
def test_scm_starts_local_service_and_answers_session_probe():
    import pywintypes
    import win32con
    import win32pipe
    import win32security
    import win32service
    import win32serviceutil
    import winerror
    import winreg

    from worker.windows_ipc import PIPE_NAME, local_service_sid, probe, process_identity
    from worker.windows_service import SessionStatusService

    sid, session, elevated = process_identity()
    assert session > 0, "the client must run in a Windows user session"
    service_name = SessionStatusService._svc_name_
    root = Path(__file__).resolve().parents[1]
    command = subprocess.list2cmdline([
        sys.executable, "-I", "-c",
        "import runpy,sys; sys.path.insert(0,sys.argv[1]); "
        "runpy.run_module('worker.windows_service', run_name='__main__')",
        str(root),
    ])

    scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_CONNECT | win32service.SC_MANAGER_CREATE_SERVICE
    )
    try:
        service = win32service.CreateService(
            scm, service_name, SessionStatusService._svc_display_name_,
            win32service.SERVICE_QUERY_STATUS | win32service.SERVICE_START
            | win32service.SERVICE_STOP | win32con.DELETE,
            win32service.SERVICE_WIN32_OWN_PROCESS,
            win32service.SERVICE_DEMAND_START,
            win32service.SERVICE_ERROR_NORMAL,
            command, None, 0, None, r"NT AUTHORITY\LocalService", None,
        )
        try:
            registry_path = rf"SYSTEM\CurrentControlSet\Services\{service_name}\Parameters"
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                winreg.SetValueEx(key, "UserSid", 0, winreg.REG_SZ, win32security.ConvertSidToStringSid(sid))
                winreg.SetValueEx(key, "SessionId", 0, winreg.REG_DWORD, session)

            win32service.StartService(service, None)
            win32serviceutil.WaitForServiceStatus(service_name, win32service.SERVICE_RUNNING, 15)
            deadline = monotonic() + 10
            while True:
                try:
                    win32pipe.WaitNamedPipe(PIPE_NAME, 200)
                    break
                except pywintypes.error as error:
                    if error.winerror not in {winerror.ERROR_FILE_NOT_FOUND, winerror.ERROR_SEM_TIMEOUT}:
                        raise
                    status = win32service.QueryServiceStatus(service)
                    assert status[1] == win32service.SERVICE_RUNNING, f"service stopped during startup: {status}"
                    if monotonic() >= deadline:
                        pytest.fail("the registered service did not open its local pipe")
                    sleep(0.05)

            if elevated:
                probe(PIPE_NAME, local_service_sid())
                print("SCM started LocalService in session 0 and the registered user-session probe succeeded.")
            else:
                result = subprocess.run(
                    [sys.executable, "-m", "worker.windows_agent"],
                    cwd=root, capture_output=True, text=True, check=True, timeout=10,
                )
                assert "V2 local status protocol v1 verified." in result.stdout
                print("SCM started LocalService in session 0 and the non-elevated agent succeeded.")
        finally:
            try:
                if win32service.QueryServiceStatus(service)[1] != win32service.SERVICE_STOPPED:
                    win32service.ControlService(service, win32service.SERVICE_CONTROL_STOP)
                    win32serviceutil.WaitForServiceStatus(service_name, win32service.SERVICE_STOPPED, 15)
            finally:
                try:
                    win32service.DeleteService(service)
                finally:
                    win32service.CloseServiceHandle(service)

        with pytest.raises(pywintypes.error) as deleted:
            remaining = win32service.OpenService(scm, service_name, win32service.SERVICE_QUERY_STATUS)
            win32service.CloseServiceHandle(remaining)
        assert deleted.value.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST
        print("SCM confirmed the temporary service was removed.")
    finally:
        win32service.CloseServiceHandle(scm)
