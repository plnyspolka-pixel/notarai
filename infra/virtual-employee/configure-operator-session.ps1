#Requires -Version 5.1
<#
.SYNOPSIS
  Run as the dedicated NON-admin interactive VM operator. Stores paths and
  synthetic tenant ID in user environment, never the binary signing key.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[a-z][a-z0-9]{2,11}$')][string]$TenantId = 'pilot01',
    [string]$Root = 'C:\ProgramData\NotarAI\VirtualEmployee'
)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Log in as the dedicated non-admin operator to run the agent'
}
if (-not [Environment]::UserInteractive) { throw 'Interactive desktop required' }

$paths = @{
    NOTARAI_VE_TENANT_ID = $TenantId
    NOTARAI_VE_HMAC_KEY_FILE = (Join-Path $Root "keys\$TenantId.hmac.bin")
    NOTARAI_VE_INBOX_DIR = (Join-Path $Root 'work\inbox')
    NOTARAI_VE_OUTBOX_DIR = (Join-Path $Root 'work\outbox')
    NOTARAI_VE_REPLAY_DIR = (Join-Path $Root 'work\replay')
}
foreach ($entry in $paths.GetEnumerator()) {
    if ($entry.Key -ne 'NOTARAI_VE_TENANT_ID' -and -not (Test-Path -LiteralPath $entry.Value)) {
        throw "Missing prepared operator resource: $($entry.Key)"
    }
}
foreach ($entry in $paths.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'User')
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
}
Write-Host 'Operator configuration written to current-user environment (paths only).'
Write-Host 'Log out/in before testing the Scheduled Task, to refresh user environment.'
Write-Host 'No credentials or signing-key contents were displayed or stored in environment.'
