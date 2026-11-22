#Requires -Version 5.1
<#
.SYNOPSIS
  Create a signed, synthetic diagnostic job on an isolated Windows test VM.
.DESCRIPTION
  Run as the dedicated logged-in operator with the local private test key.
  Does not send anything to the network or include case/document data.
#>
[CmdletBinding()]
param(
    [ValidateSet('probe.session', 'probe.notepad')][string]$Operation = 'probe.session'
)
$ErrorActionPreference = 'Stop'
$tenant = [Environment]::GetEnvironmentVariable('NOTARAI_VE_TENANT_ID', 'User')
$keyPath = [Environment]::GetEnvironmentVariable('NOTARAI_VE_HMAC_KEY_FILE', 'User')
$inbox = [Environment]::GetEnvironmentVariable('NOTARAI_VE_INBOX_DIR', 'User')
if ($tenant -notmatch '^[a-z][a-z0-9]{2,11}$' -or
    [string]::IsNullOrWhiteSpace($keyPath) -or
    [string]::IsNullOrWhiteSpace($inbox)) {
    throw 'Local operator config not ready'
}
if (-not (Test-Path -LiteralPath $inbox -PathType Container)) { throw 'Missing private inbox' }

function New-RandomHex32 {
    $bytes = New-Object byte[] 16
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes); return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant() }
    finally { [Array]::Clear($bytes, 0, $bytes.Length); $rng.Dispose() }
}
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$jobId = New-RandomHex32
$nonce = New-RandomHex32
$payload = @(
    'notarai-ve/v1', '1', $tenant, $jobId,
    $Operation, [string]$now, [string]($now + 120), $nonce
) -join "`n"
$key = [IO.File]::ReadAllBytes($keyPath)
if ($key.Length -lt 32) { throw 'Invalid test key' }
$hmac = [Security.Cryptography.HMACSHA256]::new($key)
try {
    $signature = [BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($payload))).Replace('-', '').ToLowerInvariant()
}
finally {
    $hmac.Dispose()
    [Array]::Clear($key, 0, $key.Length)
}
$job = [ordered]@{
    schema = 1
    tenantId = $tenant
    jobId = $jobId
    operation = $Operation
    issuedAtUnix = $now
    expiresAtUnix = ($now + 120)
    nonce = $nonce
    signature = $signature
}
$final = Join-Path $inbox ($jobId + '.json')
$temp = Join-Path $inbox ($jobId + '.tmp')
if (Test-Path -LiteralPath $final) { throw 'Random job collision' }
try {
    [IO.File]::WriteAllText($temp, ($job | ConvertTo-Json -Compress -Depth 2), [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($temp, $final)
}
finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
Write-Host 'Submitted a signed local-only diagnostic job. No documents or signing keys printed.'
Write-Host 'Inspect a matching .status.json in the private outbox for the result.'
