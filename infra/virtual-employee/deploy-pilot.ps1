#Requires -Version 5.1
<#
.SYNOPSIS
  NotarAI VE pilot - safe CloudFormation validation by default.
.DESCRIPTION
  AWS CLI v2 required. Without -Apply performs read-only identity/key checks
  and validates the template. With -Apply creates billable resources.
  No credential, key material or customer data is printed.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'notarai-admin',
    [string]$Region = 'eu-central-1',
    [string]$ExpectedAccount = '127621462971',
    [string]$TenantId = 'pilot01',
    [Parameter(Mandatory=$true)][string]$KeyPairName,
    [ValidateSet('t3.large', 't3.xlarge', 'm6i.large', 'm6i.xlarge')]
    [string]$InstanceType = 't3.large',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if ($Region -ne 'eu-central-1') { throw 'Only eu-central-1 is allowed for this pilot' }
if ($TenantId -notmatch '^[a-z][a-z0-9]{2,11}$') { throw 'TenantId must be synthetic lowercase' }
$template = Join-Path $PSScriptRoot 'notarai-virtual-employee-pilot.yaml'
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI v2 required' }
$account = (& aws sts get-caller-identity --query Account --output text --region $Region --profile $Profile).Trim()
if ($LASTEXITCODE -ne 0 -or $account -ne $ExpectedAccount) {
    throw 'AWS identity check failed or account differs from ExpectedAccount'
}
$null = & aws ec2 describe-key-pairs --key-names $KeyPairName --query 'KeyPairs[0].KeyName' --output text --region $Region --profile $Profile
if ($LASTEXITCODE -ne 0) { throw 'EC2 key pair not found in this account/region' }
& aws cloudformation validate-template --template-body "file://$template" --region $Region --profile $Profile --query Description --output text
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation template validation failed' }
if (-not $Apply) {
    Write-Host 'VALIDATED ONLY. No resources created. Use -Apply to deploy.'
    exit 0
}
$stackName = "notarai-ve-$TenantId"
Write-Host "APPLY: $stackName in $Region (Windows EC2, 3 paid VPC endpoints, EBS)"
& aws cloudformation deploy --stack-name $stackName --template-file $template --capabilities CAPABILITY_IAM --region $Region --profile $Profile --no-fail-on-empty-changeset --parameter-overrides "TenantId=$TenantId" "KeyPairName=$KeyPairName" "InstanceType=$InstanceType"
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation deployment failed' }
& aws cloudformation describe-stacks --stack-name $stackName --query 'Stacks[0].Outputs' --output table --region $Region --profile $Profile
if ($LASTEXITCODE -ne 0) { throw 'Deployment finished but reading outputs failed' }
Write-Host 'STOP VM after testing: aws ec2 stop-instances --instance-ids <InstanceId> --region eu-central-1 --profile notarai-admin'
