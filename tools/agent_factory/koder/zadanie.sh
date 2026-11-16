#!/usr/bin/env bash
# Jedno zadanie: karta -> agent w kontenerze -> ocena -> kontrola zakresu -> gałąź agent/*.
# Wywoływane przez przebieg.sh (równolegle). Wymaga: ROOT, OUT, TMP, RUN w środowisku.
set -uo pipefail
KARTA="$1"
J="$(python3 "$ROOT/tools/agent_factory/koder/karta.py" json "$ROOT/$KARTA")" || { echo "odrzucona karta $KARTA"; exit 0; }
pole() { python3 -c 'import json,sys; v=json.loads(sys.argv[1])[sys.argv[2]]; print(" ".join(v) if isinstance(v, list) else v)' "$J" "$1"; }
[ "$(pole tor)" = "koder" ] || exit 0
ID="$(pole id)"; CHECK="$(pole sprawdzenie)"; KROKI="$(pole kroki)"
W="$TMP/work/$ID"; T="$TMP/zaufane/$ID"; BR="agent/$RUN-$ID"; LIMIT="${KODER_TASK_SECONDS:-900}"

git clone -q --no-hardlinks "$ROOT" "$T" && git -C "$T" checkout -q -b "$BR"
mkdir -p "$W" && git -C "$ROOT" archive HEAD | tar -x -C "$W"; chmod -R a+rwX "$W"

T0=$(date +%s)
timeout "$LIMIT" docker run --rm --name "agent-$ID" --network kodernet \
  --cap-drop ALL --security-opt no-new-privileges --memory 4g --pids-limit 512 \
  -u "$(id -u):$(id -g)" -v "$W:/repo" -v "$OUT:/out" \
  -v "$ROOT/tools/agent_factory/koder:/cfg:ro" -w /repo koder-agent \
  mini -c mini.yaml -c /cfg/mini.yaml -c "agent.step_limit=$KROKI" -y --exit-immediately \
  -t "$(pole polecenie)" -o "/out/$ID.traj.json" < /dev/null > "$OUT/$ID.agent.log" 2>&1
RC=$?; T1=$(date +%s)
docker rm -f "agent-$ID" > /dev/null 2>&1

# Ocena poza zasięgiem agenta: świeży kontener bez sieci.
timeout 300 docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  --memory 4g -u "$(id -u):$(id -g)" -v "$W:/repo" -w /repo koder-agent \
  $CHECK -p no:cacheprovider > "$OUT/$ID.test.log" 2>&1 < /dev/null
TRC=$?

# Commit w zaufanym klonie (agent nie miał dostępu do .git), bez hooków.
G=(git --git-dir="$T/.git" --work-tree="$W" -c core.hooksPath=/dev/null -c core.fsmonitor=false)
"${G[@]}" add -A
mapfile -t ZM < <("${G[@]}" diff --cached --name-only)
POZA="$(python3 "$ROOT/tools/agent_factory/koder/karta.py" zakres "$ROOT/$KARTA" "${ZM[@]}" | tr '\n' ' ')"
if [ "${#ZM[@]}" -gt 0 ]; then
  "${G[@]}" -c user.name="koder (agent)" -c user.email="koder@users.noreply.github.com" \
    commit -q -m "agent($ID): $(pole tytul)" \
    -m "Model: ${KODER_MODEL:-?} na SaladCloud, mini-swe-agent. Do przeglądu przez człowieka - nie scalać automatycznie."
  flock "$TMP/push.lock" bash -c "git -C '$ROOT' fetch -q '$T' '$BR:$BR' && git -C '$ROOT' push -q origin '$BR'" \
    || echo "nie wypchnięto $BR"
fi

python3 - "$OUT" "$ID" "$KARTA" "$RC" "$TRC" "$((T1 - T0))" "$BR" "$POZA" "${ZM[@]}" > "$OUT/$ID.json" <<'PY'
import json, sys
out, tid, karta, rc, trc, sec, br, poza = sys.argv[1:9]
zm = sys.argv[9:]
info = {}
try:
    info = json.load(open(f"{out}/{tid}.traj.json", encoding="utf-8")).get("info", {})
except Exception:
    pass
status = info.get("exit_status")
wynik = {
    "id": tid, "karta": karta, "exit_status": status, "agent_exit": int(rc),
    "kroki": (info.get("model_stats") or {}).get("api_calls"), "sekundy": int(sec),
    "test_zaliczony": trc == "0", "poza_zakresem": poza.split(), "zmienione": zm,
    "galaz": br if zm else None,
}
wynik["zaliczone"] = bool(status == "Submitted" and wynik["test_zaliczony"] and zm and not wynik["poza_zakresem"])
print(json.dumps(wynik, ensure_ascii=False))
PY
echo "$ID: $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("ZALICZONE" if d["zaliczone"] else "do Claude", "|", d["exit_status"], "| test", d["test_zaliczony"], "| poza zakresem", d["poza_zakresem"], "|", d["sekundy"], "s")' "$OUT/$ID.json")"
