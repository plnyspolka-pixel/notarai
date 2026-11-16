#!/usr/bin/env bash
# Wykonuje wszystkie karty z docs/agent-tasks/kolejka/ o torze `koder` (kilka naraz),
# każdą w osobnej kopii plików i osobnym kontenerze - patrz zadanie.sh. Na koniec składa
# wyniki.jsonl i tabelę WYNIKI.md (zaliczone -> do przeglądu, reszta -> do Claude).
set -uo pipefail
export RUN="${GITHUB_RUN_ID:-lokalnie}" ROOT="$PWD" TMP="${RUNNER_TEMP:-/tmp}"
export OUT="$TMP/wyniki"
mkdir -p "$OUT" "$TMP/work" "$TMP/zaufane"; chmod a+rwx "$OUT"
python3 tools/agent_factory/koder/karta.py lint || echo "::warning::część kart odrzucona przez kontrolę - zostaną pominięte"
ls docs/agent-tasks/kolejka/*.md 2>/dev/null \
  | xargs -r -P "${KODER_PARALLEL:-3}" -n 1 bash tools/agent_factory/koder/zadanie.sh
cat "$OUT"/*.json > "$OUT/wyniki.jsonl" 2>/dev/null || true
python3 - "$OUT" "$RUN" "${KODER_MODEL:-?}" <<'PY' | tee "$OUT/WYNIKI.md"
import json, sys
out, run, model = sys.argv[1:4]
w = [json.loads(x) for x in open(f"{out}/wyniki.jsonl", encoding="utf-8") if x.strip()]
ok = [x for x in w if x["zaliczone"]]
print(f"# Koder - przebieg {run}\n\nModel: {model}. Zaliczone {len(ok)} z {len(w)}; "
      f"łączny czas pracy agentów {sum(x['sekundy'] for x in w) // 60} min.\n")
print("| Zadanie | Wynik | Kroki | Czas | Test | Poza zakresem | Gałąź |\n|---|---|---|---|---|---|---|")
for x in sorted(w, key=lambda x: (not x["zaliczone"], x["id"])):
    print(f"| {x['id']} | {'zaliczone' if x['zaliczone'] else 'do Claude'} | {x['kroki']} | {x['sekundy']} s | "
          f"{'tak' if x['test_zaliczony'] else 'nie'} | {' '.join(x['poza_zakresem']) or '-'} | {x['galaz'] or '-'} |")
PY
