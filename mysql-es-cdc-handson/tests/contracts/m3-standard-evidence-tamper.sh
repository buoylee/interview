#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$root"
source_dir=tests/fixtures/m3/m3-bulk-partial
validator=scenarios/scripts/assert-m3-standard-evidence.sh
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

bash "$validator" "$source_dir"

expect_rejected() {
  local name="$1" filter="$2" target="$3"
  cp -R "$source_dir" "$tmp/$name"
  jq "$filter" "$tmp/$name/$target" >"$tmp/value"
  mv "$tmp/value" "$tmp/$name/$target"
  if bash "$validator" "$tmp/$name" >/dev/null 2>&1; then
    echo "standard validator accepted tamper: $name" >&2; exit 1
  fi
}

expect_rejected missing-batch-row '.raw_batch_record.payload.data|=.[0:1]' result.json
expect_rejected forged-pre-repair-valid-price '.raw_valid_before_repair.raw_body=((.raw_valid_before_repair.raw_body|fromjson)|._source.price_cents=999|tojson)' result.json
expect_rejected extra-dlq-item '.raw_pending += [.raw_pending[0]]' result.json
expect_rejected mismatched-dlq-identity '.raw_pending[0].eventId="forged"' result.json
expect_rejected forged-final-raw-version '.raw_valid_final.raw_body=((.raw_valid_final.raw_body|fromjson)|._version=3|tojson)' result.json
expect_rejected forged-result-version '.final_valid_external_version=3' result.json
