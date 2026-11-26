# Windows session prototype

`worker.windows_service` is a Windows Service Control Manager entry point. It accepts only LocalService in session 0. The service reads the intended user SID and the numeric logon session from the admin-controlled service registry key. `worker.windows_agent` runs from a non-elevated interactive session. It verifies the named pipe ownership, then sends a fixed status request. The service accepts local clients on a DACL-restricted named pipe, verifies the client token SID and session, and returns a single protocol marker. The service hosts no HTTP listener, reads no development vault files, and has no automation or inference capability.

The service name is `NotarAIV2SessionStatus`. A future signed installer must register the service from an admin-owned installation directory and configure `UserSid` (REG_SZ) and `SessionId` (REG_DWORD) under its `Parameters` registry key. Changing sessions requires explicit reconfiguration and restart. Any future UI work also needs to verify that the session is unlocked and owns the target window. Signed installation and updates and failure drills across logon sessions remain release gates.

The Windows tests use real pipes between disposable processes in the runner's session and real DPAPI in the runner's user profile. New Windows development workspaces store `vault.key.dpapi` and `api.token.dpapi` using user-scoped DPAPI. Existing installations with both legacy plaintext files remain readable. Initialization refuses to replace existing files. Keep the workspace in the user's private local profile. A copied ciphertext file alone cannot serve as an independent recovery backup.

## Reproduce the SCM check

GitHub Actions runs the check on a disposable hosted Windows runner. To reproduce on a disposable Windows VM, install the pinned V2 dependencies and run from an elevated PowerShell in `v2`.

```powershell
$env:NOTARAI_V2_TEST_SCM = '1'
python -m pytest -q -rP tests/test_windows_scm.py
Remove-Item Env:NOTARAI_V2_TEST_SCM
```

The test registers the service for demand start, sets the calling user SID and session number, and starts the service as LocalService. It runs the normal `worker.windows_agent` entry point with a non-elevated Windows token and checks that it receives the protocol marker. It then stops and deletes the service and checks that it can no longer be opened in SCM.
