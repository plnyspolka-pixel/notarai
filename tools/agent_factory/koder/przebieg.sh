#!/usr/bin/env bash
# Wykonuje wszystkie karty z docs/agent-tasks/kolejka/ o torze `koder` (kilka naraz),
# każdą w osobnej kopii plików i osobnym kontenerze - patrz zadanie.sh. Na koniec składa
# wyniki.jsonl i tabelę WYNIKI.md (zaliczone -> do przeglądu, reszta -> do Claude).
set -uo pipefail
# KODER_TRYB=wezel: przebieg na samym węźle GPU (wezel.py, uruchamiany przez Worker Cloudflare
# notarai-koder) - agenci jako osobni użytkownicy zamiast kontenerów Dockera.
export RUN="${KODER_RUN:-${GITHUB_RUN_ID:-lokalnie}}" ROOT="$PWD" TMP="${KODER_TMP:-${RUNNER_TEMP:-/tmp}}"
export OUT="$TMP/wyniki"
mkdir -p "$OUT" "$TMP/work" "$TMP/zaufane"
if [ "${KODER_TRYB:-docker}" = "wezel" ]; then chmod 700 "$OUT" "$TMP/zaufane"; else chmod a+rwx "$OUT"; fi
python3 tools/agent_factory/koder/karta.py lint || echo "::warning::część kart odrzucona przez kontrolę - zostaną pominięte"
# KODER_KARTY=id1,id2 zawęża przebieg do wskazanych kart (np. przebieg próbny).
ls docs/agent-tasks/kolejka/*.md 2>/dev/null \
  | { if [ -n "${KODER_KARTY:-}" ]; then grep -E "/($(echo "$KODER_KARTY" | tr ',' '|'))\.md$"; else cat; fi; } \
  | xargs -r -P "${KODER_PARALLEL:-3}" -n 1 bash tools/agent_factory/koder/zadanie.sh
# Tylko wyniki zadań (<id>.json); <id>.przed.json, .ukryte.json, .traj.json itd. to pliki pomocnicze.
for f in "$OUT"/*.json; do case "${f##*/}" in *.*.json) ;; *) cat "$f" ;; esac; done > "$OUT/wyniki.jsonl" 2>/dev/null || true
python3 - "$OUT" "$RUN" "${KODER_MODEL:-?}" <<'PY' | tee "$OUT/WYNIKI.md"
import json, sys
out, run, model = sys.argv[1:4]
w = [json.loads(x) for x in open(f"{out}/wyniki.jsonl", encoding="utf-8") if x.strip()]
ok = [x for x in w if x["zaliczone"]]
wadliwe = [x for x in w if x.get("karta_wadliwa")]
zgloszone = [x for x in w if x.get("exit_status") == "Submitted" and x["test_zaliczony"]]
falszywe = [x for x in w if x.get("falszywy_sukces")]
print(f"# Koder - przebieg {run}\n\nModel: {model}. Zaliczone {len(ok)} z {len(w)}; "
      f"łączny czas pracy agentów {sum(x['sekundy'] for x in w) // 60} min.\n")
print(f"**Fałszywe sukcesy (W6):** {len(falszywe)} z {len(zgloszone)} zgłoszonych jako gotowe "
      f"z zielonym widocznym testem odrzuciły ukryte testy. Karty wadliwe (agent nie startował): {len(wadliwe)}.\n")
nowe = sorted({m for x in w for m in (x.get("nowe_zaleznosci") or [])})
print(f"**Nowe zależności (K5):** {sum(len(x.get('nowe_zaleznosci') or []) for x in w)} w {len(w)} zadaniach"
      + (f" - {', '.join(nowe)}" if nowe else "") + chr(10))
print("| Zadanie | Wynik | Kroki | Czas | Test | Ukryte | Poza zakresem | Gałąź |\n|---|---|---|---|---|---|---|---|")
def wynik(x):
    if x.get("karta_wadliwa"):
        return "karta wadliwa"
    return "zaliczone" if x["zaliczone"] else ("fałszywy sukces" if x.get("falszywy_sukces") else "do Claude")
def ukryte(x):
    if x.get("karta_wadliwa"):
        return x["karta_wadliwa"]
    return ("tak" if x.get("ukryte_zaliczone") else "nie") + (f" ({x['wykryte']})" if x.get("wykryte") else "")
for x in sorted(w, key=lambda x: (not x["zaliczone"], x["id"])):
    print(f"| {x['id']} | {wynik(x)} | {x['kroki']} | {x['sekundy']} s | "
          f"{'tak' if x['test_zaliczony'] else 'nie'} | {ukryte(x)} | {' '.join(x['poza_zakresem']) or '-'} | {x['galaz'] or '-'} |")
PY
