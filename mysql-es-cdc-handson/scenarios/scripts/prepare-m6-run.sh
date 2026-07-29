#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
run_dir="${1:?private run directory required}"
source "$root/scenarios/scripts/lib/m6-compose-project.sh"
project="$(m6_compose_project "${COMPOSE_PROJECT_NAME:-}")" || { echo "locked dedicated M6 project required" >&2; exit 64; }
cd "$root"

marker="$root/evidence/$(m6_compose_marker_name "$project")"
existing="$(docker ps -a -q --filter "label=com.docker.compose.project=$project")"
if test -n "$existing" && test ! -f "$marker"; then
  echo "refusing to touch unowned Compose project $project" >&2
  exit 74
fi
jq -n --arg project "$project" '{purpose:"m6-real-matrix",compose_project:$project}' >"$marker"

compose=(docker compose -f infra/compose.yaml)
"${compose[@]}" --profile m0-tools down --volumes --remove-orphans >"$run_dir/setup-down.log" 2>&1

java21=/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home
test -x "$java21/bin/java" || { echo 'Temurin Java 21 is required' >&2; exit 69; }
JAVA_HOME="$java21" PATH="$java21/bin:$PATH" make up >"$run_dir/setup-up.log" 2>&1
bash infra/mysql/apply-pipeline-control.sh >"$run_dir/setup-pipeline-control.log" 2>&1
bash infra/mysql/apply-reconciliation-control.sh >"$run_dir/setup-reconciliation-control.log" 2>&1
bash infra/elasticsearch/bootstrap-products-v2.sh >"$run_dir/setup-index.log" 2>&1
"${compose[@]}" --profile m0-tools up -d --build search-sync-consumer consistency-verifier >"$run_dir/setup-tools.log" 2>&1

waiter=scenarios/scripts/wait-condition.sh
"$waiter" 'consumer ready' 180 0.2 curl -fsS http://127.0.0.1:8082/actuator/health >/dev/null
"$waiter" 'verifier ready' 180 0.2 curl -fsS http://127.0.0.1:8083/actuator/health >/dev/null
"$waiter" 'three primary partitions settled' 180 0.2 bash -c '
  docker compose -f "$1" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null |
    awk '\''$2=="product-search-revisions"&&$3~/^[0-9]+$/{seen++;lag=$6;if($4=="-"&&$5==0&&lag=="-")lag=0;if(lag!~/^[0-9]+$/||lag!=0)bad=1} END{exit !(seen==3&&!bad)}'\''
' _ "$root/infra/compose.yaml" >/dev/null

jq -n --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{consistency_preconditions:[
  {name:"dedicated-compose-project",satisfied:true,observed_at:$now},
  {name:"pinned-stack-ready",satisfied:true,observed_at:$now},
  {name:"baseline-lag-zero",satisfied:true,observed_at:$now}
]}' >"$run_dir/setup-observation.json"
