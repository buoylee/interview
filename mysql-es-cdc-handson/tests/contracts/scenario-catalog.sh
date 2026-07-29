#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
catalog="${1:-$project_root/scenarios/catalog.json}"
scenario_schema="$project_root/scenarios/schema/scenario.schema.json"
validator="$project_root/tests/contracts/validate-json-schema.py"

for asset in "$catalog" "$scenario_schema" "$validator"; do
  test -f "$asset" || { printf 'missing M6 contract asset: %s\n' "${asset#"$project_root/"}" >&2; exit 1; }
done

uv run --quiet --with 'jsonschema[format]==4.25.1' python "$validator" \
  "$scenario_schema" "$catalog" --array-property scenarios

jq -e '
  . as $catalog |
  (keys == ["scenarios","schema_version"]) and
  .schema_version == 1 and
  (.scenarios | length) == 18 and
  ([$catalog.scenarios[].scenario_id] | . as $values | length == ($values | unique | length)) and
  ([$catalog.scenarios[].design_case] | . as $values | length == ($values | unique | length)) and
  all(.scenarios[];
    (.scenario_id | test("^[a-z0-9]+(-[a-z0-9]+)*$")) and
    (.expected_intermediate_states | length >= 1) and
    (.expected_terminal_state | IN("HEALTHY","DEGRADED","REBUILD_REQUIRED")) and
    (.recovery_action | length > 0)
  )
' "$catalog" >/dev/null

jq -r '.scenarios[].design_case' "$catalog" | sort -n | diff -u <(seq 1 18) -

expected_ids='canal-normal-restart
canal-outage-within-binlog-retention
canal-outage-beyond-binlog-retention
kafka-temporary-unavailable
consumer-offset-beyond-kafka-retention
consumer-crash-before-elasticsearch
consumer-crash-after-elasticsearch-before-offset
elasticsearch-bulk-partial-failure
duplicate-event
late-old-revision
mapping-conflict
manual-elasticsearch-drift
category-rename-multi-product
delete-then-old-event-replay
rebuild-with-concurrent-writes
rebuild-crash-and-restart
consumer-systematic-mapping-bug
dlq-replay-fails-then-succeeds'
diff -u <(printf '%s\n' "$expected_ids") <(jq -r '.scenarios | sort_by(.design_case)[] | .scenario_id' "$catalog")

actual_semantics="$(jq -r '.scenarios | sort_by(.design_case)[] | [.design_case,.scenario_id,.milestone,.seed,.fault.type,.fault.target,.fault.action,(.expected_intermediate_states|join(",")),.expected_terminal_state,.recovery_action,(.requires_rebuild|tostring),(.timeout_seconds|tostring)] | @tsv' "$catalog")"
expected_semantics='1	canal-normal-restart	M6	baseline-active-products	PROCESS	canal	restart after acknowledged cursor capture	CATCHING_UP	HEALTHY	restart Canal and prove automatic resume from the persisted cursor	false	300
2	canal-outage-within-binlog-retention	M6	baseline-active-products	PROCESS	canal	stop while retained binlog receives mutations	CATCHING_UP	HEALTHY	restore Canal before the acknowledged binlog file is purged	false	300
3	canal-outage-beyond-binlog-retention	M5	baseline-active-products	RETENTION	mysql-binlog	purge the Canal acknowledged binlog while Canal is stopped	REBUILD_REQUIRED	HEALTHY	perform evidenced Canal cursor rebootstrap and then the M5 full rebuild	true	900
4	kafka-temporary-unavailable	M6	baseline-active-products	NETWORK	kafka	apply and remove the named timeout toxic	CATCHING_UP	HEALTHY	remove the Kafka toxic and prove automatic convergence	false	300
5	consumer-offset-beyond-kafka-retention	M5	baseline-active-products	RETENTION	kafka-product-search-revisions	advance beginning offset beyond the committed consumer offset	REBUILD_REQUIRED	HEALTHY	restore retention and run the M5 full rebuild	true	900
6	consumer-crash-before-elasticsearch	M3	baseline-active-products	PROCESS	search-sync-consumer	arm BEFORE_ES_BULK and process one mutation	CATCHING_UP	HEALTHY	restart the consumer and converge from the uncommitted offset	false	300
7	consumer-crash-after-elasticsearch-before-offset	M3	baseline-active-products	PROCESS	search-sync-consumer	arm AFTER_ES_BULK_SUCCESS and process one mutation	CATCHING_UP	HEALTHY	restart the consumer and prove idempotent replay settlement	false	300
8	elasticsearch-bulk-partial-failure	M3	two-item-canal-record	DATA	one-elasticsearch-bulk-item	project one invalid field type without changing the mapping	DEGRADED	HEALTHY	disarm the one-item fault and replay the durable DLQ from current MySQL state	false	300
9	duplicate-event	M3	captured-flat-product-event	DATA	same-kafka-partition	inject the captured event a second time	HEALTHY	HEALTHY	settle through the per-product external-version fence	false	180
10	late-old-revision	M3	product-at-revision-three-with-recorded-revision-one-event	DATA	same-kafka-partition	inject the recorded revision-one signal after revision three	HEALTHY	HEALTHY	rehydrate current MySQL state and apply the external-version fence	false	180
11	mapping-conflict	M3	baseline-active-products	MAPPING	one-consumer-projection	emit an invalid type against the unchanged correct mapping	DEGRADED	HEALTHY	fix the lab-only projection and replay the durable DLQ into the same generation	false	300
12	manual-elasticsearch-drift	M4	two-converged-products	DATA	products-write	delete one document and corrupt one same-revision document	DEGRADED	HEALTHY	run M4 independent detection and bounded repair	false	300
13	category-rename-multi-product	M6	three-active-products-in-one-category	DATA	mysql-category	rename the category in one source transaction	CATCHING_UP	HEALTHY	allow automatic fan-out revisions and projection convergence	false	300
14	delete-then-old-event-replay	M3	active-product-with-recorded-old-event	DATA	same-kafka-partition	deactivate the product then replay its older active signal	HEALTHY	HEALTHY	preserve the latest tombstone through current-state rehydrate and version fencing	false	180
15	rebuild-with-concurrent-writes	M5	multi-page-product-catalog	REBUILD	m5-rebuild	mutate active inventory delete and create while snapshot pages advance	REBUILDING	HEALTHY	complete the M5 shadow barrier gated atomic-alias cutover	true	900
16	rebuild-crash-and-restart	M5	multi-page-product-catalog	REBUILD	m5-rebuild	arm BEFORE_ALIAS_SWITCH and restart the verifier	REBUILDING,DEGRADED	HEALTHY	recover persisted pre-cutover state and rerun the rebuild without the failpoint	true	900
17	consumer-systematic-mapping-bug	M4	baseline-active-products	MAPPING	consumer-category-projector	emit category ID as the same-revision category name	DEGRADED	HEALTHY	use independent M4 detection and controlled equal-revision repair after fixing the projector	false	300
18	dlq-replay-fails-then-succeeds	M3	one-mapping-poison-record	MAPPING	durable-dlq-replay	replay once while poison remains and again after the mapping fault is fixed	DEGRADED	HEALTHY	retain the failed replay then fix the fault and replay to RESOLVED	false	300'
diff -u <(printf '%s\n' "$expected_semantics") <(printf '%s\n' "$actual_semantics")

printf 'M6 scenario catalog contract passed\n'
