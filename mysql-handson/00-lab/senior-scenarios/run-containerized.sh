#!/bin/sh
set -eu

SCOPE_LABEL='com.openai.codex.scope=mysql-senior-scenarios'
MYSQL_CONTAINER='mysql-senior-scenarios-mysql'
HARNESS_CONTAINER='mysql-senior-scenarios-harness'
VERIFIER_CONTAINER='mysql-senior-scenarios-verifier'
OFFLINE_TEST_CONTAINER='mysql-senior-scenarios-offline-test'
NETWORK='mysql-senior-scenarios-net'
DATA_VOLUME='mysql-senior-scenarios-data'
EVIDENCE_VOLUME='mysql-senior-scenarios-evidence-v1'
PYTHON_IMAGE='python:3.13-slim'
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
SCENARIO_SOURCE="$REPO_ROOT/mysql-handson/13-senior-scenarios/04-report-export-isolation.md"

require_scope_label() {
  kind=$1
  name=$2
  actual=$(docker inspect --format "{{ index .Config.Labels \"com.openai.codex.scope\" }}" "$name")
  test "$actual" = 'mysql-senior-scenarios' || {
    printf '%s %s has unexpected scope label: %s\n' "$kind" "$name" "$actual" >&2
    exit 1
  }
}

require_resource_scope_label() {
  kind=$1
  name=$2
  actual=$(docker inspect --format "{{ index .Labels \"com.openai.codex.scope\" }}" "$name")
  test "$actual" = 'mysql-senior-scenarios' || {
    printf '%s %s has unexpected scope label: %s\n' "$kind" "$name" "$actual" >&2
    exit 1
  }
}

container_exists() {
  docker container inspect "$1" >/dev/null 2>&1
}

network_exists() {
  docker network inspect "$1" >/dev/null 2>&1
}

volume_exists() {
  docker volume inspect "$1" >/dev/null 2>&1
}

require_owned_network() {
  if network_exists "$NETWORK"; then
    require_resource_scope_label network "$NETWORK"
  else
    docker network create --label "$SCOPE_LABEL" "$NETWORK"
  fi
}

require_owned_evidence_volume() {
  if volume_exists "$EVIDENCE_VOLUME"; then
    require_resource_scope_label volume "$EVIDENCE_VOLUME"
  else
    docker volume create --label "$SCOPE_LABEL" "$EVIDENCE_VOLUME"
  fi
}

mysql_guard() {
  docker inspect --format '{{.Image}}|{{.Config.Image}}|{{.HostConfig.RestartPolicy.Name}}|{{range .Mounts}}{{.Type}}:{{.Name}}:{{.Destination}}{{end}}' "$MYSQL_CONTAINER"
}

primary_state() {
  docker inspect --format '{{json .State}}' mysql-primary
}

require_owned_mysql() {
  require_scope_label container "$MYSQL_CONTAINER"
  image=$(docker inspect --format '{{.Config.Image}}' "$MYSQL_CONTAINER")
  test "$image" = 'mysql:8.0.36' || {
    printf '%s has unexpected image reference: %s\n' "$MYSQL_CONTAINER" "$image" >&2
    exit 1
  }
  mount=$(docker inspect --format '{{range .Mounts}}{{.Type}}:{{.Name}}:{{.Destination}}{{end}}' "$MYSQL_CONTAINER")
  test "$mount" = "volume:$DATA_VOLUME:/var/lib/mysql" || {
    printf '%s has unexpected data mount: %s\n' "$MYSQL_CONTAINER" "$mount" >&2
    exit 1
  }
}

require_limits() {
  limits=$(docker inspect --format '{{.HostConfig.NanoCpus}}|{{.HostConfig.Memory}}|{{.HostConfig.PidsLimit}}' "$MYSQL_CONTAINER")
  test "$limits" = '2000000000|2147483648|256' || {
    printf '%s has unexpected limits: %s\n' "$MYSQL_CONTAINER" "$limits" >&2
    exit 1
  }
}

print_inspection() {
  docker inspect --format 'state={{json .State}} image={{.Config.Image}} image_id={{.Image}} labels={{json .Config.Labels}} mounts={{json .Mounts}} network={{json .NetworkSettings.Networks}} restart={{json .HostConfig.RestartPolicy}} health={{json .State.Health}} cpu={{.HostConfig.NanoCpus}} memory={{.HostConfig.Memory}} pids={{.HostConfig.PidsLimit}}' "$MYSQL_CONTAINER"
  docker inspect --format 'mysql-primary state={{json .State}}' mysql-primary
}

remove_owned_transient() {
  name=$1
  if container_exists "$name"; then
    require_scope_label container "$name"
    docker rm "$name"
  fi
}

copy_common_inputs() {
  name=$1
  docker cp "$SCENARIO_SOURCE" "$name:/opt/scenario.md"
  docker cp "$SCRIPT_DIR/evidence_contract.py" "$name:/opt/evidence_contract.py"
  docker cp "$SCRIPT_DIR/test_evidence_contract.py" "$name:/opt/test_evidence_contract.py"
  docker cp "$SCRIPT_DIR/run-containerized.sh" "$name:/opt/run-containerized.sh"
}

copy_harness_inputs() {
  name=$1
  copy_common_inputs "$name"
  docker cp "$SCRIPT_DIR/container_harness.py" "$name:/opt/container_harness.py"
}

copy_verifier_inputs() {
  name=$1
  copy_common_inputs "$name"
  docker cp "$SCRIPT_DIR/container_verifier.py" "$name:/opt/container_verifier.py"
}

offline_test() {
  remove_owned_transient "$OFFLINE_TEST_CONTAINER"
  docker create --name "$OFFLINE_TEST_CONTAINER" --label "$SCOPE_LABEL" --cpus 2 --memory 2g --pids-limit 256 "$PYTHON_IMAGE" python -m unittest -v /opt/test_evidence_contract.py
  copy_common_inputs "$OFFLINE_TEST_CONTAINER"
  docker start -a "$OFFLINE_TEST_CONTAINER"
}

wait_for_healthy() {
  seconds=0
  while test "$seconds" -lt 60; do
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$MYSQL_CONTAINER")
    if test "$health" = 'healthy'; then
      return 0
    fi
    seconds=$((seconds + 1))
    sleep 1
  done
  printf '%s did not become healthy within 60 seconds\n' "$MYSQL_CONTAINER" >&2
  exit 1
}

run_live_harness() {
  require_owned_network
  require_owned_evidence_volume
  require_owned_mysql
  before_mysql_guard=$(mysql_guard)
  before_mysql_state=$(docker inspect --format '{{json .State}}' "$MYSQL_CONTAINER")
  before_primary_state=$(primary_state)
  docker update --cpus 2 --memory 2g --pids-limit 256 mysql-senior-scenarios-mysql
  attached=$(docker inspect --format '{{with index .NetworkSettings.Networks "mysql-senior-scenarios-net"}}{{.NetworkID}}{{end}}' "$MYSQL_CONTAINER")
  if test -z "$attached"; then
    docker network connect "$NETWORK" "$MYSQL_CONTAINER"
  fi
  running=$(docker inspect --format '{{.State.Running}}' "$MYSQL_CONTAINER")
  if test "$running" != 'true'; then
    docker start mysql-senior-scenarios-mysql
  fi
  wait_for_healthy
  require_limits
  after_mysql_guard=$(mysql_guard)
  after_primary_state=$(primary_state)
  test "$before_mysql_guard" = "$after_mysql_guard" || {
    printf '%s image, data mount, or restart policy changed\n' "$MYSQL_CONTAINER" >&2
    exit 1
  }
  test "$before_primary_state" = "$after_primary_state" || {
    printf 'mysql-primary state changed during owned run gate\n' >&2
    exit 1
  }
  remove_owned_transient "$HARNESS_CONTAINER"
  scenario_commit=$(git -C "$REPO_ROOT" rev-parse HEAD)
  docker create --name "$HARNESS_CONTAINER" --label "$SCOPE_LABEL" --network "$NETWORK" --cpus 2 --memory 2g --pids-limit 256 --mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp "$PYTHON_IMAGE" sh -c 'python -m pip install --no-cache-dir mysql-connector-python==9.7.0 && exec python /opt/container_harness.py run-all --scenario /opt/scenario.md --expected-commit "$1"' sh "$scenario_commit"
  copy_harness_inputs "$HARNESS_CONTAINER"
  docker start -a "$HARNESS_CONTAINER"
}

verify_evidence() {
  require_owned_evidence_volume
  remove_owned_transient "$VERIFIER_CONTAINER"
  docker create --name "$VERIFIER_CONTAINER" --label "$SCOPE_LABEL" --cpus 2 --memory 2g --pids-limit 256 --mount type=volume,src=mysql-senior-scenarios-evidence-v1,dst=/private/tmp,readonly "$PYTHON_IMAGE" python /opt/container_verifier.py verify --scenario /opt/scenario.md
  copy_verifier_inputs "$VERIFIER_CONTAINER"
  docker start -a "$VERIFIER_CONTAINER"
}

usage() {
  printf '%s\n' 'usage: run-containerized.sh {inspect|offline-test|run|verify|cleanup-transient}' >&2
  exit 64
}

case "${1-}" in
  inspect) print_inspection ;;
  offline-test) offline_test ;;
  run) run_live_harness ;;
  verify) verify_evidence ;;
  cleanup-transient)
    remove_owned_transient "$HARNESS_CONTAINER"
    remove_owned_transient "$VERIFIER_CONTAINER"
    remove_owned_transient "$OFFLINE_TEST_CONTAINER"
    ;;
  *) usage ;;
esac
