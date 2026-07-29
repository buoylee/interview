#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";script="$root/scenarios/scripts/fault-retention.sh"
grep -Fq 'I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS' "$script" || { echo 'missing one-time destructive ACK' >&2;exit 1; }
grep -Fq 'com.docker.compose.project' "$script" || { echo 'missing exact Compose label guard' >&2;exit 1; }
grep -Fq 'SCENARIO_PROVENANCE_FILE' "$script" || { echo 'missing dedicated-project provenance marker guard' >&2;exit 1; }
! grep -Eq 'register_cleanup .*MYSQL_PWD|register_cleanup .*_PWD|register_cleanup .*rootpass' "$script"
printf 'M6 destructive guard and credential-free cleanup contract passed\n'
