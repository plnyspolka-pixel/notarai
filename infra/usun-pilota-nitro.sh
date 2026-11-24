#!/usr/bin/env bash
# Usuwa pozostalosci pilota Nitro / Confidential (stosy notarai-confidential-*),
# zastapionego przez minimalne 3 x ZERO (docs/3zero-minimum.md).
# Produkcji (notarai-aplikacja, notarai-s3, notarai-kopia, ...) NIE dotyka.
#
#   bash infra/usun-pilota-nitro.sh            # tylko pokazuje, co usunie
#   bash infra/usun-pilota-nitro.sh --tak      # usuwa
#
# Sprawdzone 23.11.2026: osobne VPC (produkcja: vpc-0bc344eeb87973516),
# brak eksportow/importow CloudFormation, 0 zadan ECS, w bucketach tylko
# pliki synthetic01. Klucze KMS przechodza w stan "zaplanowane usuniecie"
# (7-30 dni) - to normalne.
set -euo pipefail
export AWS_REGION="${AWS_REGION:-eu-central-1}"
KONTO=127621462971
TAK="${1:-}"

[ "$(aws sts get-caller-identity --query Account --output text)" = "$KONTO" ] \
  || { echo "To nie konto $KONTO - przerywam."; exit 1; }

BUCKETY="ntr-cf-pilot01 ntr-cf-pilot02 ntr-cf-pilot03 ntr-cf-code-pilot01 ntr-cf-code-pilot02 ntr-cf-code-pilot03"
REPOZYTORIA="notarai-confidential-shared notarai-confidential-pilot01"
# Kolejnosc: najpierw to, co korzysta z innych, na koncu siec.
STOSY="notarai-confidential-fabric-scaler
notarai-confidential-task-pilot03 notarai-confidential-task-pilot02 notarai-confidential-task
notarai-confidential-artifacts-pilot03 notarai-confidential-artifacts-pilot02 notarai-confidential-artifacts
notarai-confidential-staging-pilot03 notarai-confidential-staging-pilot02 notarai-confidential-staging
notarai-confidential-job-ledger-pilot03 notarai-confidential-job-ledger-pilot02 notarai-confidential-job-ledger
notarai-confidential-shared-capacity notarai-confidential-capacity-base
notarai-confidential-github notarai-confidential-shared-ecr notarai-confidential-ecr
notarai-confidential-demo-kms-pilot03 notarai-confidential-demo-kms-pilot02 notarai-confidential-demo-kms
notarai-confidential-shared-fabric notarai-confidential-network-base"

for s in $STOSY; do
  case "$s" in notarai-confidential-*) ;; *) echo "Odmowa: $s"; exit 1;; esac
done

if [ "$TAK" != "--tak" ]; then
  echo "Do usuniecia (bez --tak nic sie nie dzieje):"
  for b in $BUCKETY; do echo "  bucket  $b-$KONTO-$AWS_REGION (z wszystkimi wersjami)"; done
  for r in $REPOZYTORIA; do echo "  ECR     $r (obrazy)"; done
  for s in $STOSY; do echo "  stos    $s"; done
  exit 0
fi

for b in $BUCKETY; do
  B="$b-$KONTO-$AWS_REGION"
  aws s3api head-bucket --bucket "$B" 2>/dev/null || continue
  while :; do
    J=$(aws s3api list-object-versions --bucket "$B" --max-items 1000 --output json \
        --query "{Objects: [Versions[].{Key:Key,VersionId:VersionId}, DeleteMarkers[].{Key:Key,VersionId:VersionId}][]}")
    N=$(echo "$J" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["Objects"] or []))')
    [ "$N" = "0" ] && break
    aws s3api delete-objects --bucket "$B" --delete "$J" >/dev/null
    echo "bucket $b: usunieto $N wersji"
  done
done

for r in $REPOZYTORIA; do
  ids=$(aws ecr list-images --repository-name "$r" --output json --query imageIds 2>/dev/null || echo "[]")
  [ "$ids" = "[]" ] || aws ecr batch-delete-image --repository-name "$r" --image-ids "$ids" >/dev/null
  echo "ECR $r: oproznione"
done

for s in $STOSY; do
  aws cloudformation describe-stacks --stack-name "$s" >/dev/null 2>&1 || { echo "stos $s: juz nie ma"; continue; }
  echo -n "stos $s: usuwam... "
  aws cloudformation delete-stack --stack-name "$s"
  if aws cloudformation wait stack-delete-complete --stack-name "$s" 2>/dev/null; then
    echo "ok"
  else
    echo "BLAD - sprawdz w konsoli CloudFormation (zakladka Events)"
  fi
done
echo "Gotowe. Pozostale stosy:"
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE DELETE_FAILED \
  --query "StackSummaries[?starts_with(StackName,'notarai-confidential')].[StackName,StackStatus]" --output text
