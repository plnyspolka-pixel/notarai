"""Single interactive desktop lock across processes on the same Windows VM.

A Python threading.Lock only protects one instance. Named Win32 mutex adds
cross-process protection inside the dedicated tenant user's logon session.
"""
import hashlib
import os
import threading


class SessionMutex:
    def __init__(self, tenant_id: str):
        self._local = threading.Lock()
        self._handle = None
        self._name = "Local\\NotarAI-" + hashlib.sha256(tenant_id.encode()).hexdigest()[:32]

    def acquire(self, blocking: bool = False) -> bool:
        if not self._local.acquire(blocking=blocking):
            return False
        if os.name != "nt":
            return True
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateMutexW(None, False, self._name)
        if not handle:
            self._local.release()
            raise RuntimeError("desktop_mutex_unavailable")
        # WAIT_OBJECT_0 or WAIT_ABANDONED: both represent acquired ownership.
        status = kernel.WaitForSingleObject(handle, 0 if not blocking else 15000)
        if status not in (0x00000000, 0x00000080):
            kernel.CloseHandle(handle)
            self._local.release()
            return False
        self._handle = (kernel, handle)
        return True

    def release(self) -> None:
        if os.name == "nt" and self._handle is not None:
            kernel, handle = self._handle
            from ctypes import wintypes
            kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
            self._handle = None
        self._local.release()
