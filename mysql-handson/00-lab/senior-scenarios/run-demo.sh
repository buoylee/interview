#!/bin/sh
set -eu

SCOPE_KEY='com.openai.codex.scope'
SCOPE_VALUE='mysql-senior-demo'
SCOPE_LABEL="$SCOPE_KEY=$SCOPE_VALUE"
MYSQL_CONTAINER='mysql-senior-demo-mysql'
RUNNER_CONTAINER='mysql-senior-demo-runner'
TEST_CONTAINER='mysql-senior-demo-test'
NETWORK='mysql-senior-demo-net'
DATA_VOLUME='mysql-senior-demo-data'
MYSQL_IMAGE='mysql:8.0.36'
PYTHON_IMAGE='python:3.13-slim'
DEMO_PASSWORD='demo-only-password'
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
SCENARIO_SOURCE="$REPO_ROOT/mysql-handson/13-senior-scenarios/04-report-export-isolation.md"
ROUTING_SOURCE="$REPO_ROOT/mysql-handson/13-senior-scenarios/README.md"

container_exists() {
  docker container inspect "$1" >/dev/null 2>&1
}

network_exists() {
  docker network inspect "$1" >/dev/null 2>&1
}

volume_exists() {
  docker volume inspect "$1" >/dev/null 2>&1
}

require_owned_container() {
  actual=$(docker inspect --format "{{ index .Config.Labels \"$SCOPE_KEY\" }}" "$1")
  test "$actual" = "$SCOPE_VALUE" || {
    printf 'refusing unowned container: %s\n' "$1" >&2
    exit 1
  }
}

require_owned_network() {
  actual=$(docker inspect --format "{{ index .Labels \"$SCOPE_KEY\" }}" "$1")
  test "$actual" = "$SCOPE_VALUE" || {
    printf 'refusing unowned network: %s\n' "$1" >&2
    exit 1
  }
}

require_owned_volume() {
  actual=$(docker inspect --format "{{ index .Labels \"$SCOPE_KEY\" }}" "$1")
  test "$actual" = "$SCOPE_VALUE" || {
    printf 'refusing unowned volume: %s\n' "$1" >&2
    exit 1
  }
}

remove_owned_container() {
  if container_exists "$1"; then
    require_owned_container "$1"
    docker rm -f "$1" >/dev/null
  fi
}

run_tests() {
  remove_owned_container "$TEST_CONTAINER"
  docker create --name "$TEST_CONTAINER" --label "$SCOPE_LABEL" --network none --cpus 2 --memory 2g --pids-limit 256 "$PYTHON_IMAGE" sh -c 'cd /opt && python -m unittest -v test_demo.py && python -m py_compile demo.py test_demo.py && sh -n run-demo.sh'
  docker cp "$SCRIPT_DIR/demo.py" "$TEST_CONTAINER:/opt/demo.py"
  docker cp "$SCRIPT_DIR/test_demo.py" "$TEST_CONTAINER:/opt/test_demo.py"
  docker cp "$SCRIPT_DIR/run-demo.sh" "$TEST_CONTAINER:/opt/run-demo.sh"
  docker cp "$SCENARIO_SOURCE" "$TEST_CONTAINER:/opt/04-report-export-isolation.md"
  docker cp "$ROUTING_SOURCE" "$TEST_CONTAINER:/opt/senior-scenarios-README.md"
  docker start -a "$TEST_CONTAINER"
}

require_fresh_demo_resources() {
  for name in "$MYSQL_CONTAINER" "$RUNNER_CONTAINER"; do
    if container_exists "$name"; then
      printf 'demo resource already exists; run ./run-demo.sh cleanup: %s\n' "$name" >&2
      exit 1
    fi
  done
  if network_exists "$NETWORK"; then
    printf 'demo resource already exists; run ./run-demo.sh cleanup: %s\n' "$NETWORK" >&2
    exit 1
  fi
  if volume_exists "$DATA_VOLUME"; then
    printf 'demo resource already exists; run ./run-demo.sh cleanup: %s\n' "$DATA_VOLUME" >&2
    exit 1
  fi
}

wait_for_mysql() {
  if test "${DEMO_NO_WAIT-}" = 1; then
    return
  fi
  seconds=0
  while test "$seconds" -lt 60; do
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$MYSQL_CONTAINER")
    if test "$health" = healthy; then
      return
    fi
    seconds=$((seconds + 1))
    sleep 1
  done
  printf 'demo MySQL did not become healthy within 60 seconds\n' >&2
  exit 1
}

run_demo() {
  test -f "$SCRIPT_DIR/demo.py" || {
    printf 'missing demo.py\n' >&2
    exit 1
  }
  require_fresh_demo_resources
  docker network create --label "$SCOPE_LABEL" "$NETWORK" >/dev/null
  docker volume create --label "$SCOPE_LABEL" "$DATA_VOLUME" >/dev/null
  MYSQL_ROOT_PASSWORD=$DEMO_PASSWORD
  export MYSQL_ROOT_PASSWORD
  docker create --name "$MYSQL_CONTAINER" --label "$SCOPE_LABEL" --network "$NETWORK" --cpus 2 --memory 2g --pids-limit 256 --mount "type=volume,src=$DATA_VOLUME,dst=/var/lib/mysql" --env MYSQL_ROOT_PASSWORD --health-cmd='mysqladmin ping -h 127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent' --health-interval=1s --health-timeout=3s --health-retries=60 "$MYSQL_IMAGE" >/dev/null
  docker start "$MYSQL_CONTAINER" >/dev/null
  wait_for_mysql
  MYSQL_PASSWORD=$DEMO_PASSWORD
  export MYSQL_PASSWORD
  docker create --name "$RUNNER_CONTAINER" --label "$SCOPE_LABEL" --network "$NETWORK" --cpus 2 --memory 2g --pids-limit 256 --env MYSQL_PASSWORD --env MYSQL_HOST="$MYSQL_CONTAINER" --workdir /work "$PYTHON_IMAGE" sh -c 'python -m pip install --no-cache-dir mysql-connector-python==9.7.0 >/dev/null && exec python /opt/demo.py run'
  docker cp "$SCRIPT_DIR/demo.py" "$RUNNER_CONTAINER:/opt/demo.py"
  docker start -a "$RUNNER_CONTAINER"
}

inspect_demo() {
  for name in "$MYSQL_CONTAINER" "$RUNNER_CONTAINER" "$TEST_CONTAINER"; do
    if container_exists "$name"; then
      require_owned_container "$name"
      docker inspect --format 'container={{.Name}} state={{.State.Status}} exit={{.State.ExitCode}} image={{.Config.Image}} cpu={{.HostConfig.NanoCpus}} memory={{.HostConfig.Memory}} pids={{.HostConfig.PidsLimit}}' "$name"
    else
      printf 'container=%s state=absent\n' "$name"
    fi
  done
  for name in "$NETWORK" "$DATA_VOLUME"; do
    if docker inspect "$name" >/dev/null 2>&1; then
      printf 'resource=%s state=present\n' "$name"
    else
      printf 'resource=%s state=absent\n' "$name"
    fi
  done
}

cleanup_demo() {
  remove_owned_container "$RUNNER_CONTAINER"
  remove_owned_container "$TEST_CONTAINER"
  remove_owned_container "$MYSQL_CONTAINER"
  if network_exists "$NETWORK"; then
    require_owned_network "$NETWORK"
    docker network rm "$NETWORK" >/dev/null
  fi
  if volume_exists "$DATA_VOLUME"; then
    require_owned_volume "$DATA_VOLUME"
    docker volume rm "$DATA_VOLUME" >/dev/null
  fi
}

case "${1-}" in
  test) run_tests ;;
  run) run_demo ;;
  inspect) inspect_demo ;;
  cleanup) cleanup_demo ;;
  *) printf '%s\n' 'usage: run-demo.sh {test|run|inspect|cleanup}' >&2; exit 64 ;;
esac
