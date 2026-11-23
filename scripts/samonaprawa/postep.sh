#!/usr/bin/env bash
# Postep naprawy dla notariusza: bash postep.sh <etap> [opis]
# Zapis do Parameter Store /notarai/samonaprawa/<ODCISK> (bez danych klientow);
# aplikacja czyta go i asystent kancelarii pokazuje pasek postepu i czas.
# Wymaga poswiadczen roli samonaprawy (poswiadczenia.sh pelne). Nigdy nie przerywa naprawy.
set -uo pipefail
etap="${1:?etap}"
opis="${2:-}"
[ -n "${ODCISK:-}" ] || exit 0
wartosc=$(jq -nc --arg e "$etap" --arg o "$opis" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg r "${GITHUB_RUN_ID:-}" '{etap: $e, opis: $o, czas: $t, przebieg: $r}')
aws ssm put-parameter --name "/notarai/samonaprawa/${ODCISK}" --type String --overwrite \
  --value "$wartosc" >/dev/null 2>&1 || echo "::warning::nie zapisano postepu ($etap)"
exit 0
