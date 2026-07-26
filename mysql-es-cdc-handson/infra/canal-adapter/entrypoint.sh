#!/usr/bin/env bash
set -euo pipefail

cd /opt/canal-adapter

pid_file="bin/adapter.pid"
if test -f "$pid_file"; then
  recorded_pid="$(cat "$pid_file")"
  if kill -0 "$recorded_pid" 2>/dev/null; then
    echo "Canal Adapter process $recorded_pid is already running" >&2
    exit 1
  fi
  rm -f "$pid_file"
fi

./bin/startup.sh

for attempt in $(seq 1 60); do
  if test -f logs/adapter/adapter.log; then
    exec tail -n +1 -F logs/adapter/adapter.log
  fi
  sleep 1
done

echo "Canal Adapter log did not appear" >&2
exit 1
