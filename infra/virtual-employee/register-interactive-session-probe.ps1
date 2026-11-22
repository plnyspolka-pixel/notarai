#Requires -Version 5.1
<#
.SYNOPSIS
  Register a one-time interactive NotarAI session health probe at operator logon.
.DESCRIPTION
  Run as the intended Windows user. This script does NOT enable auto-logon,
  store passwords, grant elevated privileges, start background surveillance,
  or create a Windows service in Session 0.
#>
[CmdletBinding()]
param(
    [string]$ExecutablePath,
    [string]$ExpectedSha256,
    [switch]$StartWorker,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$taskName = 'NotarAI-VE-SessionHealth'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if ($null -eq $identity -or [string]::IsNullOrWhiteSpace($identity.Name)) {
    throw 'Cannot determine current interactive Windows user'
}
if (-not [Environment]::UserInteractive) {
    throw 'Register this task from an interactive Windows logon'
}
if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    Write-Host 'Removed NotarAI interactive session health probe'
    exit 0
}
if ([string]::IsNullOrWhiteSpace($ExecutablePath) -or
    $ExpectedSha256 -notmatch '^[a-fA-F0-9]{64}
if (-not [string]::Equals([IO.Path]::GetExtension($exe), '.exe', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'ExecutablePath must point to a built .exe, not a script'
}
$actualSha = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if (-not [string]::Equals($actualSha, $ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Executable hash mismatch; refusing to register a different binary'
}
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$mode = if ($StartWorker) { '--serve-local-inbox' } else { '--session-health' }
$limit = if ($StartWorker) { New-TimeSpan -Seconds 0 } else { New-TimeSpan -Minutes 1 }
$action = New-ScheduledTaskAction -Execute $exe -Argument $mode
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit $limit -RestartCount 0
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Principal $principal -Action $action -Settings $settings -Description 'Read-only interactive desktop readiness; no auto-logon' -Force | Out-Null
Write-Host "Registered interactive task for $mode. No credentials stored or auto-logon enabled."
if ($StartWorker) { Write-Host 'Local diagnostic inbox only - no external queue or RejNET automation.' }
) {
    throw 'Provide ExecutablePath and the 64-hex-digit expected SHA256'
}
if ($StartWorker) {
    foreach ($variable in @('NOTARAI_VE_TENANT_ID', 'NOTARAI_VE_HMAC_KEY_FILE',
                             'NOTARAI_VE_INBOX_DIR', 'NOTARAI_VE_OUTBOX_DIR',
                             'NOTARAI_VE_REPLAY_DIR')) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($variable, 'User'))) {
            throw "Missing per-user operator setting: $variable"
        }
    }
}
$exe = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
if (-not [string]::Equals([IO.Path]::GetExtension($exe), '.exe', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'ExecutablePath must point to a built .exe, not a script'
}
$actualSha = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if (-not [string]::Equals($actualSha, $ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Executable hash mismatch; refusing to register a different binary'
}
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $exe -Argument '--session-health'
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -RestartCount 0
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Principal $principal -Action $action -Settings $settings -Description 'Read-only interactive desktop readiness; no auto-logon' -Force | Out-Null
Write-Host 'Registered user-session probe on interactive logon. No credentials stored.'
Write-Host 'This is a one-shot readiness test, not a persistent RejNET agent.'
