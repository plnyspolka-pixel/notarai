#Requires -Version 5.1
<#
.SYNOPSIS
  Validate an optional SQS FIFO transport for the existing synthetic EC2 VM.
.DESCRIPTION
  Default: read-only CloudFormation validation and account/stack checks.
  -Apply explicitly authorizes an additional billed SQS VPC Endpoint and queues.
  Never mutates the production NotarAI ECS stack or logs secrets/customer data.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'notarai-admin',
    [ValidateSet('eu-central-1')][string]$Region = 'eu-central-1',
    [string]$ExpectedAccount = '127621462971',
    [ValidatePattern('^[a-z][a-z0-9]{2,11}$')][string]$TenantId = 'pilot01',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 required' }
$account = (& aws sts get-caller-identity --query Account --output text --region $Region --profile $Profile).Trim()
if ($LASTEXITCODE -ne 0 -or $account -ne $ExpectedAccount) { throw 'Unexpected AWS account' }

$template = Join-Path $PSScriptRoot 'notarai-ve-sqs-pilot.yaml'
& aws cloudformation validate-template --template-body "file://$template" --region $Region --profile $Profile --query Description --output text
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation validation failed' }

$vmStack = "notarai-ve-$TenantId"
$outputJson = & aws cloudformation describe-stacks --stack-name $vmStack --query 'Stacks[0].Outputs' --output json --region $Region --profile $Profile
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($outputJson)) {
    throw 'Existing Windows pilot stack unavailable. SQS bridge cannot deploy alone.'
}
$outputs = @{}
foreach ($entry in ($outputJson | ConvertFrom-Json)) {
    $outputs[[string]$entry.OutputKey] = [string]$entry.OutputValue
}
foreach ($needed in @('VpcId','PrivateSubnetId','EndpointSecurityGroupId','WindowsRoleName')) {
    if ([string]::IsNullOrWhiteSpace($outputs[$needed])) {
        throw "Missing expected Windows stack output: $needed"
    }
}

if (-not $Apply) {
    Write-Host 'VALIDATED ONLY: no resources created or changed.'
    Write-Host 'Apply later only after approving charges for another private VPC endpoint.'
    exit 0
}

$stack = "notarai-ve-$TenantId-sqs"
Write-Host "APPLY: synthetic-only SQS queues, IAM consumer policy and paid private endpoint in $Region"
& aws cloudformation deploy --stack-name $stack --template-file $template --region $Region --profile $Profile --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --parameter-overrides "TenantId=$TenantId" "VpcId=$($outputs['VpcId'])" "PrivateSubnetId=$($outputs['PrivateSubnetId'])" "EndpointSecurityGroupId=$($outputs['EndpointSecurityGroupId'])" "WindowsRoleName=$($outputs['WindowsRoleName'])"
if ($LASTEXITCODE -ne 0) { throw 'SQS transport deployment failed' }
& aws cloudformation describe-stacks --stack-name $stack --query 'Stacks[0].Outputs' --output table --region $Region --profile $Profile
if ($LASTEXITCODE -ne 0) { throw 'SQS resources created but output lookup failed' }
Write-Host 'Queue is empty and no task sender is configured. Use only signed synthetic jobs.'
