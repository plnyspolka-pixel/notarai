#!/usr/bin/env bash
# Postep naprawy dla notariusza: bash postep.sh <etap> [opis]
# Zapis do Parameter Store /notarai/samonaprawa/<ODCISK> (bez danych klientow);
# aplikacja czyta go i asystent kancelarii pokazuje pasek postepu i czas.
# Wymaga poswiadczen roli samonaprawy (poswiadczenia.sh pelne). Nigdy nie przerywa naprawy.
set -uo pipefail
etap="${1:?etap}"
opis="${2:-}"
[ -n "${ODCISK:-}" ] || exit 0
# WLACZ = {"klucz","wartosc"} z raportu agenta: ustawienie, ktore aplikacja sama
# wlaczy u kancelarii, ktora prosila, gdy zmiana jest juz na produkcji.
wlacz="${WLACZ:-}"
echo "$wlacz" | jq -e 'type=="object"' >/dev/null 2>&1 || wlacz="null"
wartosc=$(jq -nc --arg e "$etap" --arg o "$opis" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg r "${PRZEBIEG:-${CODEBUILD_BUILD_ID:-${GITHUB_RUN_ID:-}}}" --argjson w "$wlacz" \
  '{etap: $e, opis: $o, czas: $t, przebieg: $r} + (if $w then {wlacz: $w} else {} end)')
aws ssm put-parameter --name "/notarai/samonaprawa/${ODCISK}" --type String --overwrite \
  --value "$wartosc" >/dev/null 2>&1 || echo "::warning::nie zapisano postepu ($etap)"
exit 0
