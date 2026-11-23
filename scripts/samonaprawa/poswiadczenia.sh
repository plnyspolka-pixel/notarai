#!/usr/bin/env bash
# Poswiadczenia AWS dla samonaprawy przez OIDC GitHuba (bez kluczy).
#
#   eval "$(bash scripts/samonaprawa/poswiadczenia.sh pelne)"  - rola samonaprawy
#   eval "$(bash scripts/samonaprawa/poswiadczenia.sh agent)"  - ta sama rola, ale
#        sesja zawezona polityka sesji do samego wywolywania modeli Bedrock:
#        agent nie przeczyta sekretu, logow ani nie wysle powiadomienia.
#
# Wypisuje linie export ...; tajne wartosci sa maskowane w logu Actions.
set -euo pipefail
zakres="${1:-pelne}"
rola="${ROLA_SAMONAPRAWY:?brak ROLA_SAMONAPRAWY}"

token=$(curl -sSf -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r .value)
# Maskowanie przez echo w poleceniach do eval (komendy Actions czyta ze stdout kroku).
printf 'echo "::add-mask::%s"\n' "$token"

polityka=()
if [ "$zakres" = "agent" ]; then
  polityka=(--policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream","bedrock:GetInferenceProfile","bedrock:ListInferenceProfiles"],"Resource":"*"}]}')
fi

dane=$(aws sts assume-role-with-web-identity \
  --role-arn "$rola" \
  --role-session-name "samonaprawa-${zakres}-${GITHUB_RUN_ID}" \
  --web-identity-token "$token" \
  --duration-seconds 3600 \
  "${polityka[@]}" \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text) || {
  echo "::error::Brak dostepu do roli $rola. Zaktualizuj stos notarai-github: powershell -ExecutionPolicy Bypass -File infra\\4-polacz-github.ps1" >&2
  exit 1
}
read -r kid ksec ksesja <<< "$dane"
printf 'echo "::add-mask::%s"\n' "$ksec" "$ksesja"
printf 'export AWS_ACCESS_KEY_ID=%q\nexport AWS_SECRET_ACCESS_KEY=%q\nexport AWS_SESSION_TOKEN=%q\n' "$kid" "$ksec" "$ksesja"
