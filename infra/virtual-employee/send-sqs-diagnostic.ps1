#Requires -Version 5.1
<#
.SYNOPSIS
  Send a pre-signed, synthetic diagnostic envelope to a tenant's pilot FIFO queue.
.DESCRIPTION
  Run as an explicitly authorized AWS account operator, not the Windows VM agent.
  No key, password, script, document text or customer data is sent or logged.
  Default is a dry run. -Apply creates one SQS message only (no cloud resources).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$JobFile,
    [Parameter(Mandatory=$true)][string]$QueueUrl,
    [string]$Profile = 'notarai-admin',
    [ValidateSet('eu-central-1')][string]$Region = 'eu-central-1',
    [string]$ExpectedAccount = '127621462971',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 required' }
$absolute = (Resolve-Path -LiteralPath $JobFile -ErrorAction Stop).Path
$fileSize = (Get-Item -LiteralPath $absolute).Length
if ($fileSize -lt 80 -or $fileSize -gt 4096) { throw 'Synthetic signed job size out of bounds' }
$job = Get-Content -LiteralPath $absolute -Raw -Encoding UTF8 | ConvertFrom-Json
$keys = @($job.PSObject.Properties.Name | Sort-Object)
$expectedKeys = @('expiresAtUnix','issuedAtUnix','jobId','nonce','operation','schema','signature','tenantId')
if ((Compare-Object -ReferenceObject $expectedKeys -DifferenceObject $keys)) {
    throw 'Unexpected signed job fields'
}
if ($job.schema -ne 1 -or $job.tenantId -cnotmatch '^[a-z][a-z0-9]{2,11}$' -or
    $job.jobId -cnotmatch '^[a-f0-9]{32}$' -or $job.nonce -cnotmatch '^[a-f0-9]{32}$' -or
    $job.signature -cnotmatch '^[a-f0-9]{64}$' -or
    $job.operation -cnotin @('probe.session', 'probe.notepad')) {
    throw 'Only signed schema-v1 diagnostic envelopes can be sent'
}
$expectedUrl = "^https://sqs\.eu-central-1\.amazonaws\.com/[0-9]{12}/notarai-ve-$($job.tenantId)-jobs\.fifo$"
if ($QueueUrl -cnotmatch $expectedUrl) { throw 'Queue URL is not this synthetic tenant queue' }
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
if ($job.expiresAtUnix -le $now -or $job.issuedAtUnix -gt ($now + 60) -or
    ($job.expiresAtUnix - $job.issuedAtUnix) -gt 300) {
    throw 'Signed job already expired or outside permitted issue window'
}
$identity = (& aws sts get-caller-identity --region $Region --profile $Profile --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0 -or $identity -ne $ExpectedAccount) {
    throw 'AWS account check failed'
}
if (-not $Apply) {
    Write-Host 'VALIDATED ONLY. No message sent. Add -Apply to send ONE synthetic signed diagnostic.'
    exit 0
}

Write-Host 'Sending one synthetic diagnostic via SQS FIFO (no key material or documents).'
& aws sqs send-message --queue-url $QueueUrl --message-body "file://$absolute" --message-group-id $job.tenantId --message-deduplication-id $job.jobId --region $Region --profile $Profile --query MessageId --output text | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Sending signed synthetic diagnostic failed' }
Write-Host 'Synthetic diagnostic submitted. Check VM private metadata-only outbox.'
