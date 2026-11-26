"""V2 local service IPC: one fixed status probe over a Windows named pipe."""
from threading import Event
from time import monotonic

import ntsecuritycon
import pywintypes
import win32api
import win32con
import win32file
import win32pipe
import win32security
import winerror

PIPE_NAME = r"\\.\pipe\NotarAI.V2.SessionStatus"
STATUS_V1 = b"\x01"
ACK = b"\x02"
CLIENT_ACCESS = win32file.FILE_GENERIC_READ | ntsecuritycon.FILE_WRITE_DATA
PEER_DISCONNECTED = {winerror.ERROR_BROKEN_PIPE, winerror.ERROR_NO_DATA, winerror.ERROR_PIPE_NOT_CONNECTED}


def local_service_sid():
    return win32security.CreateWellKnownSid(win32security.WinLocalServiceSid, None)


def process_identity():
    with win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY) as token:
        return (
            win32security.GetTokenInformation(token, win32security.TokenUser)[0],
            win32security.GetTokenInformation(token, win32security.TokenSessionId),
            win32security.GetTokenInformation(token, win32security.TokenElevation),
        )


def _security_attributes(owner, user):
    acl = win32security.ACL()
    acl.AddAccessAllowedAce(win32security.ACL_REVISION, win32file.FILE_ALL_ACCESS, owner)
    # FILE_GENERIC_WRITE includes FILE_CREATE_PIPE_INSTANCE. Grant the data bit only.
    if user != owner:
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, CLIENT_ACCESS, user)
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR.SetSecurityDescriptorOwner(owner, False)
    attributes.SECURITY_DESCRIPTOR.SetSecurityDescriptorDacl(True, acl, False)
    return attributes


def _read_byte(pipe, stop, deadline):
    while not stop.is_set() and monotonic() < deadline:
        _, available, _ = win32pipe.PeekNamedPipe(pipe, 0)
        if available:
            if available != 1:
                raise ValueError("invalid status frame")
            _, data = win32file.ReadFile(pipe, 1)
            return data
        stop.wait(0.025)
    raise TimeoutError("status exchange timed out")


def _client_matches(pipe, user, session):
    if win32pipe.GetNamedPipeClientSessionId(pipe) != session:
        return False
    win32security.ImpersonateNamedPipeClient(pipe)
    try:
        with win32security.OpenThreadToken(
            win32api.GetCurrentThread(), win32con.TOKEN_QUERY, True
        ) as token:
            return win32security.GetTokenInformation(token, win32security.TokenUser)[0] == user
    finally:
        win32security.RevertToSelf()


def listen_once(name, owner, user, session, stop):
    """Wait for one client or service shutdown. Verify the peer before responding."""
    with win32pipe.CreateNamedPipe(
        name,
        win32pipe.PIPE_ACCESS_DUPLEX | win32pipe.FILE_FLAG_FIRST_PIPE_INSTANCE,
        win32pipe.PIPE_NOWAIT | win32pipe.PIPE_REJECT_REMOTE_CLIENTS,
        1, 0, 0, 0, _security_attributes(owner, user),
    ) as pipe:
        while not stop.is_set():
            try:
                win32pipe.ConnectNamedPipe(pipe)
                break
            except pywintypes.error as error:
                if error.winerror == winerror.ERROR_NO_DATA:
                    break
                if error.winerror != winerror.ERROR_PIPE_LISTENING:
                    raise
                stop.wait(0.025)
        if stop.is_set():
            return False

        try:
            deadline = monotonic() + 2
            if _read_byte(pipe, stop, deadline) != STATUS_V1 or not _client_matches(pipe, user, session):
                return False
            win32file.WriteFile(pipe, STATUS_V1)
            return _read_byte(pipe, stop, deadline) == ACK
        except (ValueError, TimeoutError):
            return False
        except pywintypes.error as error:
            if error.winerror in PEER_DISCONNECTED:
                return False
            raise


def probe(name, owner):
    """Verify the pipe owner, then exchange a fixed protocol marker."""
    with win32file.CreateFile(
        name, CLIENT_ACCESS, 0, None, win32con.OPEN_EXISTING,
        win32con.SECURITY_SQOS_PRESENT | win32file.SECURITY_IDENTIFICATION, None,
    ) as pipe:
        descriptor = win32security.GetSecurityInfo(
            pipe, win32security.SE_KERNEL_OBJECT, win32security.OWNER_SECURITY_INFORMATION
        )
        if descriptor.GetSecurityDescriptorOwner() != owner:
            raise PermissionError("unexpected pipe owner")
        win32file.WriteFile(pipe, STATUS_V1)
        if _read_byte(pipe, Event(), monotonic() + 2) != STATUS_V1:
            raise PermissionError("unexpected status response")
        win32file.WriteFile(pipe, ACK)
