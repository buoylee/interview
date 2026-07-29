#!/usr/bin/env bash
set -euo pipefail

[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'formal M5 gate requires latest clean HEAD' >&2; exit 1; }
head="$(git rev-parse HEAD)"
root="${M5_FORMAL_ROOT:-evidence/m5}"
compose=(docker compose -f infra/compose.yaml)

round(){
  local number="$1" evidence="$root/formal-final-$1"
  make reset
  make up
  "${compose[@]}" --profile m0-tools up -d --build search-sync-consumer consistency-verifier
  bash infra/mysql/apply-reconciliation-control.sh
  make bootstrap-index
  mkdir -p "$evidence"
  jq -n --arg head "$head" --arg round "$number" \
    --arg mysqlVolume "$(docker volume inspect mysql-es-cdc-handson_mysql-data --format '{{.Name}}:{{.CreatedAt}}')" \
    --arg kafkaVolume "$(docker volume inspect mysql-es-cdc-handson_kafka-data --format '{{.Name}}:{{.CreatedAt}}')" \
    --arg canalVolume "$(docker volume inspect mysql-es-cdc-handson_canal-data --format '{{.Name}}:{{.CreatedAt}}')" \
    --arg clusterId "$("${compose[@]}" exec -T kafka sh -lc "grep '^cluster.id=' /tmp/kafka-logs/meta.properties|cut -d= -f2")" \
    '{head:$head,round:($round|tonumber),mysqlVolume:$mysqlVolume,kafkaVolume:$kafkaVolume,canalVolume:$canalVolume,kafkaClusterId:$clusterId}' >"$evidence/reset-provenance.json"
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -2 >"$evidence/initial-beginning-offsets.txt"
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 >"$evidence/initial-end-offsets.txt"
  M5_GATE_RUN="formal-final-$number" M5_EVIDENCE_DIR="$evidence" bash tests/end-to-end/m5-rebuild.sh
  jq '[.[]|del(.runId,.authoritative,.failedGeneration)]' "$evidence/terminal-classifications.json" >"$evidence/terminal-normalized.json"
}

round 1
round 2
diff -u "$root/formal-final-1/terminal-normalized.json" "$root/formal-final-2/terminal-normalized.json"
jq -n --slurpfile first "$root/formal-final-1/terminal-normalized.json" --slurpfile second "$root/formal-final-2/terminal-normalized.json" \
  --slurpfile p1 "$root/formal-final-1/reset-provenance.json" --slurpfile p2 "$root/formal-final-2/reset-provenance.json" \
  '{rounds:2,matching:($first[0]==$second[0]),freshKafkaVolumes:($p1[0].kafkaVolume!=$p2[0].kafkaVolume),fixedConfiguredClusterId:($p1[0].kafkaClusterId==$p2[0].kafkaClusterId),terminal:$second[0]}' >"$root/formal-final-truth.json"
jq -e '.matching and .freshKafkaVolumes and .fixedConfiguredClusterId and .rounds==2' "$root/formal-final-truth.json" >/dev/null
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo 'tracked worktree changed during formal M5 gate' >&2; exit 1; }
echo "M5 two-fresh-round formal gate passed: $root/formal-final-truth.json"
