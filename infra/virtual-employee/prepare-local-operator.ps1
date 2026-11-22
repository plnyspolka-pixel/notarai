#Requires -Version 5.1
<#
.SYNOPSIS
  Provision a synthetic local-only VM operator workspace (admin-only setup).
.DESCRIPTION
  Creates an isolated test key and directories. Must run elevated on the
  Windows VM; never commit keys or copy them to chat. Does not change passwords,
  authorize RDP, configure unattended logon, or connect to production.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OperatorAccount,
    [ValidatePattern('^[a-z][a-z0-9]{2,11}$')][string]$TenantId = 'pilot01',
    [string]$Root = 'C:\ProgramData\NotarAI\VirtualEmployee'
)
$ErrorActionPreference = 'Stop'
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($me)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run elevated as local VM administrator'
}
$operatorSid = (New-Object Security.Principal.NTAccount($OperatorAccount)).Translate([Security.Principal.SecurityIdentifier]).Value
if ([string]::IsNullOrWhiteSpace($operatorSid)) { throw 'Cannot resolve operator SID' }

function Set-PrivateAcl([string]$Path, [string]$OperatorRights, [bool]$Directory) {
    $aclOperator = if ($Directory) { "*${operatorSid}:(OI)(CI)$OperatorRights" } else { "*${operatorSid}:$OperatorRights" }
    & icacls.exe $Path /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' $aclOperator | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to initialize private ACL for $Path" }
}

New-Item -ItemType Directory -Path $Root -Force | Out-Null
Set-PrivateAcl $Root 'RX' $true
$bin = Join-Path $Root 'bin'
$work = Join-Path $Root 'work'
$keys = Join-Path $Root 'keys'
$inbox = Join-Path $work 'inbox'
$outbox = Join-Path $work 'outbox'
$replay = Join-Path $work 'replay'
New-Item -ItemType Directory -Path $bin -Force | Out-Null
Set-PrivateAcl $bin 'RX' $true
New-Item -ItemType Directory -Path $work -Force | Out-Null
Set-PrivateAcl $work 'M' $true
foreach ($path in @($inbox, $outbox, $replay)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    Set-PrivateAcl $path 'M' $true
}
New-Item -ItemType Directory -Path $keys -Force | Out-Null
Set-PrivateAcl $keys 'RX' $true

$keyPath = Join-Path $keys ($TenantId + '.hmac.bin')
if (-not (Test-Path -LiteralPath $keyPath)) {
    $key = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($key); [System.IO.File]::WriteAllBytes($keyPath, $key) }
    finally { [Array]::Clear($key, 0, $key.Length); $rng.Dispose() }
}
& icacls.exe $keyPath /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' ("*${operatorSid}:R") | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict test key ACL' }
Write-Host 'Private synthetic-only operator directories prepared. Key content was not printed.'
Write-Host 'Operator must log in interactively and set USER-scope environment variables:'
Write-Host 'NOTARAI_VE_TENANT_ID; NOTARAI_VE_HMAC_KEY_FILE; NOTARAI_VE_INBOX_DIR; NOTARAI_VE_OUTBOX_DIR; NOTARAI_VE_REPLAY_DIR.'
Write-Host 'A real tenant requires separate reviewed key-management and operator-access procedures.'
