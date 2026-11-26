#!/usr/bin/env bash
set -Eeuo pipefail
export AWS_DEFAULT_REGION=eu-central-1 AWS_PAGER=""
cd "$(dirname "$0")/.."
for key in BROWSER_HOSTNAME BROWSER_CERT_ARN BROWSER_POOL_ARN BROWSER_POOL_CLIENT BROWSER_POOL_DOMAIN BROWSER_PUBLIC_SUBNETS BROWSER_CLIENT_CIDR BROWSER_IMAGE; do
  [[ -n "${!key:-}" ]] || { echo "Missing configuration: $key" >&2; exit 2; }
done
command -v jq >/dev/null
# Read-only access to existing egress infrastructure. Do not allocate or move EIPs.
stack=$(aws cloudformation describe-stacks --stack-name notarai-egress --output json)
out() { jq -er --arg key "$1" '.Stacks[0].Outputs[] | select(.OutputKey==$key) | .OutputValue' <<< "$stack"; }
param() { jq -er --arg key "$1" '.Stacks[0].Parameters[] | select(.ParameterKey==$key) | .ParameterValue' <<< "$stack"; }
[[ $(param NatWlaczony) == true ]] || { echo 'Existing NAT is off; enable it explicitly before deploying.' >&2; exit 1; }
expected=$(out AdresEgress)
subnet=$(out PodsiecWyjscia)
vpc=$(param VpcId)
nat=$(aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$subnet" --query "RouteTables[].Routes[?DestinationCidrBlock=='0.0.0.0/0' && State=='active'].NatGatewayId | []" --output text)
[[ $nat == nat-* && $nat != *$'\t'* && $nat != *$'\n'* ]] || { echo 'No unique active NAT route.' >&2; exit 1; }
actual=$(aws ec2 describe-nat-gateways --nat-gateway-ids "$nat" --query 'NatGateways[?State==`available`].NatGatewayAddresses[].PublicIp' --output text)
[[ $actual == "$expected" ]] || { echo 'NAT IP mismatch or multiple IPs.' >&2; exit 1; }
cidrs=$(aws ec2 describe-vpcs --vpc-ids "$vpc" --query 'Vpcs[0].CidrBlockAssociationSet[?CidrBlockState.State==`associated`].CidrBlock' --output text)
cidrs=$(tr '\t\n' '  ' <<< "$cidrs" | xargs)
[[ -n $cidrs ]] || exit 1
# Only a dedicated pool with administrator-created accounts; no self-registration.
pool=${BROWSER_POOL_ARN##*/}
[[ $(aws cognito-idp describe-user-pool --user-pool-id "$pool" --query 'UserPool.AdminCreateUserConfig.AllowAdminCreateUserOnly' --output text) == True ]] || { echo 'Dedicated admin-only Cognito pool required.' >&2; exit 1; }
[[ $(aws cognito-idp describe-user-pool --user-pool-id "$pool" --query 'UserPool.MfaConfiguration' --output text) == ON ]] || { echo 'MFA required for browser pool.' >&2; exit 1; }
[[ $(aws cognito-idp list-users --user-pool-id "$pool" --query 'length(Users[?Enabled==`true`])' --output text) == 1 ]] || { echo 'Exactly one enabled account required.' >&2; exit 1; }
aws cloudformation validate-template --template-body file://infra/notarai-private-browser.yaml >/dev/null
aws cloudformation deploy --stack-name notarai-private-browser --template-file infra/notarai-private-browser.yaml --no-fail-on-empty-changeset --parameter-overrides \
  "VpcId=$vpc" "PrivateSubnet=$subnet" "PublicSubnets=$BROWSER_PUBLIC_SUBNETS" "ExpectedIP=$expected" "VpcCidrs=$cidrs" \
  "Hostname=$BROWSER_HOSTNAME" "CertificateArn=$BROWSER_CERT_ARN" "UserPoolArn=$BROWSER_POOL_ARN" \
  "UserPoolClientId=$BROWSER_POOL_CLIENT" "UserPoolDomain=$BROWSER_POOL_DOMAIN" "ClientCidr=$BROWSER_CLIENT_CIDR" "BrowserImage=$BROWSER_IMAGE" >/dev/null
target=$(aws cloudformation describe-stacks --stack-name notarai-private-browser --query "Stacks[0].Outputs[?OutputKey=='TargetGroup'].OutputValue | [0]" --output text)
aws elbv2 wait target-in-service --target-group-arn "$target"
# DNS must already point at this ALB; test TLS and anonymous auth redirect.
code=$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "https://$BROWSER_HOSTNAME/")
[[ $code == 302 ]] || { echo 'Expected anonymous login redirect; check DNS, TLS and authentication.' >&2; exit 1; }
echo 'Infrastructure, browser startup IP check, target health and anonymous login gate passed. Verify login and in-browser IP manually.'
