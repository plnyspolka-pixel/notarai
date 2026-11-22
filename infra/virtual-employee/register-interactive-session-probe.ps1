#Requires -Version 5.1
<#
.SYNOPSIS
  Register a restricted NotarAI diagnostic task in the current user's Windows session.
.DESCRIPTION
  Uses Task Scheduler interactive logon. Does not create an automatic Windows
  logon, store account passwords or run as Session 0/service administrator.
  -StartWorker enables the synthetic local inbox only.
  -StartSqsWorker enables the synthetic private SQS consumer only.
  Defaults to a one-shot session health check at next login.
#>
[CmdletBinding()]
param(
    [string]$ExecutablePath,
    [string]$ExpectedSha256,
    [switch]$StartWorker,
    [switch]$StartSqsWorker,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$taskName = 'NotarAI-VE-SessionHealth'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($null -eq $identity -or [string]::IsNullOrWhiteSpace($identity.Name)) {
    throw 'Cannot determine current Windows identity'
}
$principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
if ($principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Register only from the dedicated non-admin Windows operator'
}
if (-not [Environment]::UserInteractive) {
    throw 'An authenticated interactive Windows logon is required'
}
if ($StartWorker -and $StartSqsWorker) {
    throw 'Choose one worker type, never both'
}

if ($Remove) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    }
    Write-Host 'NotarAI interactive diagnostic task removed, if present'
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ExecutablePath) -or
    $ExpectedSha256 -notmatch '^[a-fA-F0-9]{64}$') {
    throw 'Provide ExecutablePath and a 64-hex-character SHA256 checksum'
}
$exe = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
if (-not [string]::Equals([IO.Path]::GetExtension($exe), '.exe',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'ExecutablePath must point to a compiled .exe'
}
$actualSha = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if (-not [string]::Equals($actualSha, $ExpectedSha256,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Executable hash mismatch; task will not be created'
}

$mode = '--session-health'
$requiredVariables = @()
if ($StartWorker -or $StartSqsWorker) {
    $requiredVariables = @('NOTARAI_VE_TENANT_ID', 'NOTARAI_VE_HMAC_KEY_FILE',
                           'NOTARAI_VE_OUTBOX_DIR', 'NOTARAI_VE_REPLAY_DIR')
    if ($StartWorker) {
        $mode = '--serve-local-inbox'
        $requiredVariables += 'NOTARAI_VE_INBOX_DIR'
    } else {
        $mode = '--serve-sqs'
        $requiredVariables += 'NOTARAI_VE_SQS_QUEUE_URL'
    }
}
foreach ($variable in $requiredVariables) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable(
            $variable, 'User'))) {
        throw "Operator setting missing: $variable"
    }
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$operator = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $exe -Argument $mode
$limit = if ($StartWorker -or $StartSqsWorker) {
    New-TimeSpan -Seconds 0
} else {
    New-TimeSpan -Minutes 1
}
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit $limit -RestartCount 0
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Principal $operator -Action $action -Settings $settings -Description 'NotarAI synthetic diagnostics in interactive user session' -Force | Out-Null

Write-Host "Registered $mode for the current operator at interactive logon."
Write-Host 'No auto-logon, credentials, or elevated task permissions configured.'
