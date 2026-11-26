"""Windows SCM entry point for the synthetic V2 session-status service."""
from threading import Event
import winreg

import servicemanager
import win32security
import win32service
import win32serviceutil

from .windows_ipc import PIPE_NAME, listen_once, local_service_sid, process_identity


class SessionStatusService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NotarAIV2SessionStatus"
    _svc_display_name_ = "NotarAI V2 Session Status (synthetic)"

    def __init__(self, args):
        super().__init__(args)
        self.stop = Event()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop.set()

    def SvcDoRun(self):
        owner, session, _ = process_identity()
        if owner != local_service_sid() or session != 0:
            raise PermissionError("requires LocalService in session 0")
        path = rf"SYSTEM\CurrentControlSet\Services\{self._svc_name_}\Parameters"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as registry:
            sid, sid_type = winreg.QueryValueEx(registry, "UserSid")
            session, session_type = winreg.QueryValueEx(registry, "SessionId")
        if sid_type != winreg.REG_SZ or session_type != winreg.REG_DWORD or not 0 < session < 0xFFFFFFFF:
            raise ValueError("explicit user SID and interactive session required")
        user = win32security.ConvertStringSidToSid(sid)
        if win32security.LookupAccountSid(None, user)[2] != win32security.SidTypeUser:
            raise ValueError("session owner must be a user account")
        while not self.stop.is_set():
            listen_once(PIPE_NAME, owner, user, session, self.stop)


if __name__ == "__main__":
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(SessionStatusService)
    servicemanager.StartServiceCtrlDispatcher()
