#!/usr/bin/env bash
set -euo pipefail

cd /opt/canal-adapter
./bin/startup.sh

for attempt in $(seq 1 60); do
  if test -f logs/adapter/adapter.log; then
    exec tail -n +1 -F logs/adapter/adapter.log
  fi
  sleep 1
done

echo "Canal Adapter log did not appear" >&2
exit 1
