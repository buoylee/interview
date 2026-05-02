#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql

for attempt in {1..60}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 60 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

mvn -f "$SERVICE_DIR/pom.xml" spring-boot:run
