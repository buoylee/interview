#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
scenario="${1:?usage: run.sh SCENARIO}"
if [ "$scenario" = ha-cannot-replace-pitr ]; then
  exec "$ROOT/scenarios/pitr.sh"
fi
case "$scenario" in
  planned-switchover|primary-crash|primary-partition|quorum-loss|slow-member|router-failure|member-rejoin) ;;
  *) echo "unsupported scenario: $scenario" >&2; exit 2 ;;
esac

fault_may_be_active=0
watcher_pid=""
session_pid=""
burst_pid=""

stop_background() {
  local pid
  for pid in "$watcher_pid" "$session_pid" "$burst_pid"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$watcher_pid" "$session_pid" "$burst_pid"; do
    if [ -n "$pid" ]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
}

cleanup() {
  local status=$?
  trap - EXIT
  stop_background
  if [ "$fault_may_be_active" = 1 ] && [ -f "$ROOT/evidence/fault-state.env" ]; then
    make -C "$ROOT" restore || true
  fi
  make -C "$ROOT" workload-stop >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

wait_for_observers_ready() {
  local _
  for _ in $(seq 1 100); do
    if [ -f "$ROOT/evidence/session-ready" ] && [ -f "$ROOT/evidence/timeline-ready" ]; then
      if ! kill -0 "$watcher_pid" 2>/dev/null; then wait "$watcher_pid"; return 1; fi
      if ! kill -0 "$session_pid" 2>/dev/null; then wait "$session_pid"; return 1; fi
      return 0
    fi
    if ! kill -0 "$watcher_pid" 2>/dev/null; then wait "$watcher_pid"; return 1; fi
    if ! kill -0 "$session_pid" 2>/dev/null; then wait "$session_pid"; return 1; fi
    sleep 0.05
  done
  echo "scenario observers did not become ready" >&2
  return 1
}

make -C "$ROOT" reset
make -C "$ROOT" up
"${DC[@]}" build verifier
make -C "$ROOT" workload-start
sleep "${WARMUP_SECONDS:-5}"

if [[ "$scenario" = planned-switchover || "$scenario" = primary-crash || "$scenario" = primary-partition ]]; then
  old_primary="$("${DC[@]}" exec -T db1 mysql -uroot -pha-root -Nse \
    "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'")"
  case "$old_primary" in
    db1|db2|db3) ;;
    *) echo "could not identify exactly one old Primary" >&2; exit 1 ;;
  esac
  "${DC[@]}" run --rm verifier python -m verifier.timeline --old-primary "$old_primary" &
  watcher_pid=$!
  "${DC[@]}" run --rm verifier python -m verifier.session_probe --router router-a &
  session_pid=$!
  wait_for_observers_ready
fi

if [ "$scenario" = slow-member ]; then
  "${DC[@]}" run --rm verifier python -m verifier.metrics --phase before
fi

fault_may_be_active=1
make -C "$ROOT" fault SCENARIO="$scenario"
if [ -n "$watcher_pid" ]; then
  wait "$watcher_pid"
  watcher_pid=""
fi
if [ -n "$session_pid" ]; then
  wait "$session_pid"
  session_pid=""
fi

if [ "$scenario" = slow-member ]; then
  make -C "$ROOT" workload-burst N=2000 &
  burst_pid=$!
  sleep 3
  "${DC[@]}" run --rm verifier python -m verifier.metrics --phase active
  wait "$burst_pid"
  burst_pid=""
fi

fault_seconds="${FAULT_SECONDS:-12}"
if [ "$scenario" = quorum-loss ] && [ -z "${FAULT_SECONDS+x}" ]; then
  fault_seconds=3
fi
sleep "$fault_seconds"
make -C "$ROOT" restore
fault_may_be_active=0
sleep "${RECOVERY_SECONDS:-5}"
make -C "$ROOT" workload-stop
make -C "$ROOT" verify
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse \
  "SELECT written_by, COUNT(*) FROM ha_lab.orders GROUP BY written_by ORDER BY written_by" \
  > "$ROOT/evidence/written-by.txt"
"${DC[@]}" run --rm verifier python -c "
import json
from pathlib import Path
from workload.model import JsonlLedger
from verifier.scenarios import assert_scenario
root = Path('/evidence')
records = JsonlLedger.load(root.glob('ledger-*.jsonl'))
events = [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines() if line.strip()]
metric_path = root / 'metrics.jsonl'
metrics = [json.loads(line) for line in metric_path.read_text().splitlines() if line.strip()] if metric_path.exists() else []
timeline_path = root / 'timeline.jsonl'
timeline = [json.loads(line) for line in timeline_path.read_text().splitlines() if line.strip()] if timeline_path.exists() else []
fencing_path = root / 'fencing.json'
fencing = json.loads(fencing_path.read_text()) if fencing_path.exists() else {}
session_path = root / 'session.json'
session = json.loads(session_path.read_text()) if session_path.exists() else {}
report = assert_scenario('$scenario', records, events, metrics, timeline, fencing, session)
(root / 'scenario-verification.json').write_text(json.dumps(report, indent=2) + '\\n')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['ok'] else 1)
"

archive="$ROOT/evidence/runs/$scenario/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$archive"
find "$ROOT/evidence" -mindepth 1 -maxdepth 1 -type f -exec cp {} "$archive"/ \;
trap - EXIT
