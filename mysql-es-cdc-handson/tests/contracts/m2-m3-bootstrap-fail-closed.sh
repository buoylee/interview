#!/usr/bin/env bash
set -euo pipefail

tmp_dir="$(mktemp -d)"
pids=()
cleanup() {
  local pid
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

for mode in \
  incompatible-template malicious-composed-of unexpected-data-stream \
  extra-template-setting extra-template-alias incompatible-index incompatible-alias; do
  port_file="${tmp_dir}/${mode}.port"
  log_file="${tmp_dir}/${mode}.log"
  : >"$log_file"
  python3 tests/fixtures/fake-es-bootstrap-server.py "$mode" "$port_file" "$log_file" &
  pid=$!
  pids+=("$pid")
  for _ in $(seq 1 50); do
    [[ -s "$port_file" ]] && break
    sleep 0.02
  done
  [[ -s "$port_file" ]]
  port="$(cat "$port_file")"

  if ELASTICSEARCH_URL="http://127.0.0.1:${port}" bash infra/elasticsearch/bootstrap-products-v2.sh \
      >"${tmp_dir}/${mode}.out" 2>&1; then
    echo "bootstrap accepted ${mode}" >&2
    exit 1
  fi
  if grep -Eq '^(PUT|POST) ' "$log_file"; then
    echo "bootstrap mutated Elasticsearch before rejecting ${mode}:" >&2
    cat "$log_file" >&2
    exit 1
  fi
  kill "$pid"
  wait "$pid" 2>/dev/null || true
done

echo "M2-M3 bootstrap incompatible-state zero-mutation contracts passed"
