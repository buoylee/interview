#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";script="$root/scenarios/scripts/fault-retention.sh";tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
cat >"$tmp/bin/docker" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${FAKE_DOCKER_LOG:?}"
case "$*" in
  *' ps -q mysql') printf 'mysql-id\n' ;;
  *' ps -q kafka') printf 'kafka-id\n' ;;
  'inspect -f '*'mysql-id'|'inspect -f '*'kafka-id') printf '%s\n' "${FAKE_COMPOSE_LABEL:-wrong-project}" ;;
  *) echo 'unexpected mutating docker call' >&2;exit 99 ;;
esac
FAKE
chmod +x "$tmp/bin/docker"
export PATH="$tmp/bin:$PATH" FAKE_DOCKER_LOG="$tmp/docker.log" MYSQL_PWD="${MYSQL_PWD:-unused-variable-reference}"

reject_without_side_effects(){
  local name="$1" project="$2" ack="$3" marker="$4" state cleanup
  state="$tmp/state-$name";cleanup="$tmp/cleanup-$name"
  : >"$FAKE_DOCKER_LOG"
  set +e
  COMPOSE_PROJECT_NAME="$project" M6_RETENTION_DESTRUCTIVE_ACK="$ack" SCENARIO_PROVENANCE_FILE="$marker" SCENARIO_STATE_DIR="$state" SCENARIO_CLEANUP_FILE="$cleanup" bash "$script" apply mysql >"$tmp/$name.out" 2>"$tmp/$name.err"
  rc=$?
  set -e
  test "$rc" -eq 64
  test ! -e "$state";test ! -e "$cleanup"
  ! grep -Eq ' stop | alter |FLUSH|PURGE|delete-records' "$FAKE_DOCKER_LOG"
}

valid_project=mysql-es-cdc-handson-m6-negative
valid_marker="$tmp/provenance.json"
jq -n --arg project "$valid_project" '{purpose:"m6-dedicated-retention",compose_project:$project}' >"$valid_marker"
reject_without_side_effects no-ack "$valid_project" '' "$valid_marker"
reject_without_side_effects wrong-project shared-project I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS "$valid_marker"
reject_without_side_effects no-marker "$valid_project" I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS "$tmp/missing.json"
FAKE_COMPOSE_LABEL=wrong-project reject_without_side_effects wrong-label "$valid_project" I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS "$valid_marker"

printf 'M6 destructive guard zero-side-effect negatives passed\n'
