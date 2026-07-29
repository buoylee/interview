#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
fixture=tests/fixtures/m6/case-semantics.json
assertion=scenarios/scripts/assert-m6-case-semantics.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

build_fault() {
  local scenario="$1" destination="$2"
  jq -n --arg scenario "$scenario" --slurpfile fixture "$fixture" '
    {scenario_id:$scenario,case_observations:{scenario_id:$scenario,
      artifacts:($fixture[0][$scenario]|to_entries|map({path:.key,sha256:("a"*64),json:.value}))}}
  ' >"$destination"
}

while IFS= read -r scenario; do
  build_fault "$scenario" "$tmp/$scenario.json"
  bash "$assertion" "$tmp/$scenario.json"
done < <(jq -r '.scenarios[].scenario_id' scenarios/catalog.json)

expect_rejected() {
  local scenario="$1" filter="$2" name="$3"
  local source="$tmp/$scenario.json" target="$tmp/tamper-$name.json"
  jq "$filter" "$source" >"$target"
  if bash "$assertion" "$target" >/dev/null 2>&1; then
    echo "semantic tamper accepted: $name" >&2
    exit 1
  fi
  tamper_count=$((tamper_count+1))
}

tamper_count=0
expect_rejected canal-normal-restart '(.case_observations.artifacts[]|select(.path=="meta-after-restart.json").json.position)=5' case1-cursor-changed
expect_rejected canal-outage-within-binlog-retention '(.case_observations.artifacts[]|select(.path=="es-final.json").json._source.source_revision)=1' case2-not-caught-up
expect_rejected canal-outage-beyond-binlog-retention '(.case_observations.artifacts[]|select(.path=="gap-proof.json").json.canal_missing_position_observed)=false' case3-missing-gap
expect_rejected kafka-temporary-unavailable '(.case_observations.artifacts[]|select(.path=="toxic-removed.json").json.active)=true' case4-fault-not-removed
expect_rejected consumer-offset-beyond-kafka-retention '(.case_observations.artifacts[]|select(.path=="kafka-gap-status.json").json.gap)=false' case5-no-gap
expect_rejected consumer-crash-before-elasticsearch '(.case_observations.artifacts[]|select(.path=="crashed.json").json.exit_code)=0' case6-no-crash
expect_rejected consumer-crash-after-elasticsearch-before-offset '(.case_observations.artifacts[]|select(.path=="es-after-restart.json").json._seq_no)=9' case7-duplicate-write
expect_rejected elasticsearch-bulk-partial-failure '(.case_observations.artifacts[]|select(.path=="replay.json").json.status)="PENDING"' case8-unresolved
expect_rejected duplicate-event '(.case_observations.artifacts[]|select(.path=="injected-event.json").json.normalized_payload.data[0].revision)="2"' case9-payload-mismatch
expect_rejected late-old-revision '(.case_observations.artifacts[]|select(.path=="injected-event.json").json.normalized_payload.data[0].revision)="2"' case10-payload-mismatch
expect_rejected mapping-conflict '(.case_observations.artifacts[]|select(.path=="generation-after").json)="invented"' case11-generation
expect_rejected manual-elasticsearch-drift '(.case_observations.artifacts[]|select(.path=="fresh-pass.json").json.differenceCount)=1' case12-still-different
expect_rejected category-rename-multi-product '(.case_observations.artifacts[]|select(.path=="three-row-record.json").json)=false' case13-not-atomic
expect_rejected delete-then-old-event-replay '(.case_observations.artifacts[]|select(.path=="injected-event.json").json.normalized_payload.data[0].revision)="2"' case14-payload-mismatch
expect_rejected rebuild-with-concurrent-writes '(.case_observations.artifacts[]|select(.path=="http-codes.json").json.gated_write)=200' case15-gate-open
expect_rejected rebuild-crash-and-restart '(.case_observations.artifacts[]|select(.path=="alias-after-restart").json)="invented"' case16-alias
expect_rejected consumer-systematic-mapping-bug '(.case_observations.artifacts[]|select(.path=="fresh-pass.json").json.differenceCount)=1' case17-still-different
expect_rejected dlq-replay-fails-then-succeeds '(.case_observations.artifacts[]|select(.path=="pending-after-failed-replay.json").json[0].attempts)=1' case18-attempt

test "$tamper_count" -eq 18

echo 'M6 18-case semantic tamper contract passed'
