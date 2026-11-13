#!/usr/bin/env bash
# Wersja bash skryptu 5-budzet-i-limit-gpu.ps1 (ten sam efekt: budzet Bedrock + wniosek o limit GPU spot).
# Uzycie: bash infra/5-budzet-i-limit-gpu.sh twoj@email.pl [limit_usd=60] [gpu_vcpu=8]
set -euo pipefail
EMAIL=${1:?podaj e-mail na alarmy}; LIMIT=${2:-60}; VCPU=${3:-8}; REGION=${AWS_REGION:-eu-central-1}
TU=$(cd "$(dirname "$0")" && pwd)
aws sts get-caller-identity --output table
aws cloudformation deploy --stack-name notarai-budzet --template-file "$TU/notarai-budzet.yaml" \
  --parameter-overrides "Email=$EMAIL" "LimitUsd=$LIMIT" --region "$REGION"
KOD=L-3819A6DF  # All G and VT Spot Instance Requests
OBECNY=$(aws service-quotas get-service-quota --service-code ec2 --quota-code $KOD --region "$REGION" --query Quota.Value --output text)
echo "obecny limit GPU spot: $OBECNY vCPU"
if awk "BEGIN{exit !($OBECNY < $VCPU)}"; then
  aws service-quotas request-service-quota-increase --service-code ec2 --quota-code $KOD --desired-value "$VCPU" --region "$REGION" --output table
  echo "wniosek zlozony; AWS odpowiada zwykle w 1-2 dni"
else
  echo "limit wystarcza"
fi
echo "Potwierdz subskrypcje alarmu w mailu od AWS Notifications."
