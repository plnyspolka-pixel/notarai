#!/usr/bin/env bash
# notarai - AWS w sesji chmurowej Claude (claude.ai/code) bez logowania.
#
# Srodowisko Claude trzyma staly klucz uzytkownika IAM notarai-claude w
# zmiennych NOTARAI_AWS_ACCESS_KEY_ID i NOTARAI_AWS_SECRET_ACCESS_KEY
# (zaklada go infra\USTAW_DOSTEP_CLAUDE.bat na komputerze). Ten skrypt:
#   1. instaluje AWS CLI v2, jesli go nie ma,
#   2. zapisuje klucz jako profil notarai-admin i default w ~/.aws,
#   3. wylacza atrapy AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, ktore
#      srodowisko chmurowe ustawia samo (sa nieprawidlowe i mialyby
#      pierwszenstwo przed profilem).
# Uzycie na poczatku sesji:   source infra/aws-z-env.sh
# (zwykle `bash infra/aws-z-env.sh` tez zapisze profile, ale nie zmieni
#  zmiennych biezacej powloki - wtedy dodawaj --profile notarai-admin).
# Nazwy zmiennych sa celowo inne niz AWS_*, zeby nie zderzac sie z atrapami.

_notarai_aws_z_env() {
  local kid="${NOTARAI_AWS_ACCESS_KEY_ID:-}" ksec="${NOTARAI_AWS_SECRET_ACCESS_KEY:-}"
  local region="${NOTARAI_AWS_REGION:-eu-central-1}"
  if [ -z "$kid" ] || [ -z "$ksec" ]; then
    echo "aws-z-env: brak NOTARAI_AWS_ACCESS_KEY_ID / NOTARAI_AWS_SECRET_ACCESS_KEY w srodowisku." >&2
    echo "aws-z-env: dodaj je w claude.ai -> Code -> Settings -> Environments -> Edit (patrz infra/USTAW_DOSTEP_CLAUDE.bat)." >&2
    return 1
  fi
  if ! command -v aws >/dev/null 2>&1; then
    echo "aws-z-env: instaluje AWS CLI v2..." >&2
    local tmp
    tmp="$(mktemp -d)"
    curl -sSfL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$tmp/awscliv2.zip" \
      && (cd "$tmp" && unzip -q awscliv2.zip && ./aws/install --update >/dev/null) \
      || { echo "aws-z-env: instalacja AWS CLI nie powiodla sie" >&2; rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
  fi
  local p
  for p in notarai-admin notarai-claude default; do
    aws configure set aws_access_key_id "$kid" --profile "$p"
    aws configure set aws_secret_access_key "$ksec" --profile "$p"
    aws configure set region "$region" --profile "$p"
  done
  # Atrapy ze srodowiska chmurowego mialyby pierwszenstwo przed profilem.
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
  export AWS_PROFILE=notarai-admin AWS_REGION="$region" AWS_DEFAULT_REGION="$region"
  export AWS_EC2_METADATA_DISABLED=true
  if aws sts get-caller-identity --query Arn --output text; then
    echo "aws-z-env: AWS CLI gotowe (profil notarai-admin, region $region), bez logowania." >&2
  else
    echo "aws-z-env: klucz odrzucony - sprawdz zmienne NOTARAI_AWS_* w srodowisku Claude." >&2
    return 1
  fi
}
_notarai_aws_z_env
