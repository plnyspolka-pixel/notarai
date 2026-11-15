#!/usr/bin/env bash
# Wykonuje zadania z docs/agent-tasks/ZLECENIE.txt: każde w osobnej kopii plików repo (bez
# .git) i osobnym kontenerze bez sekretów, z siecią ograniczoną do bramy modelu. Ocena
# (polecenie "Sprawdzenie:" z zadania) biegnie w świeżym kontenerze bez sieci. Commit powstaje
# w zaufanym klonie poza zasięgiem agenta (bez hooków). Wynik: gałęzie agent/* do przeglądu.
set -uo pipefail
RUN="${GITHUB_RUN_ID:-lokalnie}"; ROOT="$PWD"; TMP="${RUNNER_TEMP:-/tmp}"
OUT="$TMP/wyniki"; mkdir -p "$OUT" "$TMP/work" "$TMP/zaufane"; chmod a+rwx "$OUT"
LIMIT="${KODER_TASK_SECONDS:-900}"
: > "$OUT/wyniki.jsonl"
grep -vE '^\s*(#|$)' docs/agent-tasks/ZLECENIE.txt | tr -d '\r' | while read -r TASK; do
  case "$TASK" in docs/agent-tasks/*.md) ;; *) echo "pomijam $TASK"; continue;; esac
  [ -f "$TASK" ] && [ ! -L "$TASK" ] || { echo "brak $TASK"; continue; }
  ID="$(basename "$TASK" .md | cut -d- -f1)"; W="$TMP/work/$ID"; T="$TMP/zaufane/$ID"; BR="agent/$RUN-$ID"
  git clone -q --no-hardlinks "$ROOT" "$T" && git -C "$T" checkout -q -b "$BR"
  mkdir -p "$W" && git -C "$ROOT" archive HEAD | tar -x -C "$W"; chmod -R a+rwX "$W"
  echo "::group::$ID - agent"
  T0=$(date +%s)
  timeout "$LIMIT" docker run --rm --name "agent-$ID" --network kodernet \
    --cap-drop ALL --security-opt no-new-privileges --memory 6g --pids-limit 512 \
    -u "$(id -u):$(id -g)" -v "$W:/repo" -v "$OUT:/out" \
    -v "$ROOT/tools/agent_factory/koder:/cfg:ro" -w /repo koder-agent \
    mini -c mini.yaml -c /cfg/mini.yaml -y --exit-immediately \
    -t "$(cat "$TASK")" -o "/out/$ID.traj.json" < /dev/null > "$OUT/$ID.agent.log" 2>&1
  RC=$?; T1=$(date +%s)
  docker rm -f "agent-$ID" > /dev/null 2>&1
  tail -n 15 "$OUT/$ID.agent.log"; echo "::endgroup::"
  CHECK="$(grep -m1 '^Sprawdzenie: ' "$TASK" | tr -d '\r' | sed -E 's/^Sprawdzenie: //; s/ - .*$//')"
  case "$CHECK" in "python -m pytest -q "*) ;; *) CHECK="";; esac
  TRC=-1
  if [ -n "$CHECK" ]; then
    timeout 300 docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
      --memory 4g -u "$(id -u):$(id -g)" -v "$W:/repo" -w /repo koder-agent \
      $CHECK -p no:cacheprovider > "$OUT/$ID.test.log" 2>&1 < /dev/null; TRC=$?
    tail -n 3 "$OUT/$ID.test.log"
  fi
  G=(git --git-dir="$T/.git" --work-tree="$W" -c core.hooksPath=/dev/null -c core.fsmonitor=false)
  "${G[@]}" add -A
  CHANGED="$("${G[@]}" diff --cached --name-only | tr '\n' ' ')"
  if [ -n "$CHANGED" ]; then
    "${G[@]}" -c user.name="koder (agent)" -c user.email="koder@users.noreply.github.com" \
      commit -q -m "agent($ID): $(head -n1 "$TASK" | tr -d '\r' | sed 's/^# //')" \
      -m "Model: ${KODER_MODEL:-?} na SaladCloud, mini-swe-agent. Do przeglądu przez człowieka - nie scalać automatycznie."
    git -C "$ROOT" fetch -q "$T" "$BR:$BR" && git -C "$ROOT" push -q origin "$BR" \
      && echo "wypchnięto $BR" || echo "nie wypchnięto $BR"
  fi
  python3 - "$OUT" "$ID" "$TASK" "$RC" "$TRC" "$((T1 - T0))" "$BR" "$CHANGED" >> "$OUT/wyniki.jsonl" <<'PY'
import json, sys
out, tid, task, rc, trc, sec, br, changed = sys.argv[1:9]
info = {}
try:
    info = json.load(open(f"{out}/{tid}.traj.json", encoding="utf-8")).get("info", {})
except Exception:
    pass
print(json.dumps({
    "task": task, "id": tid, "agent_exit": int(rc), "exit_status": info.get("exit_status"),
    "model_calls": (info.get("model_stats") or {}).get("api_calls"), "seconds": int(sec),
    "check_exit": int(trc), "check_passed": trc == "0", "changed": changed.split(),
    "branch": br if changed.strip() else None,
}, ensure_ascii=False))
PY
done
cat "$OUT/wyniki.jsonl"
