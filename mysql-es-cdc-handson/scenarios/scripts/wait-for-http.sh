#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 URL DEADLINE_SECONDS" >&2
  exit 2
fi

url="$1"
deadline="$2"
start="$(date +%s)"

while ! curl -fsS "$url" >/dev/null; do
  now="$(date +%s)"
  if [ "$((now - start))" -ge "$deadline" ]; then
    echo "timeout waiting for $url after ${deadline}s" >&2
    exit 1
  fi
  sleep 1
done
