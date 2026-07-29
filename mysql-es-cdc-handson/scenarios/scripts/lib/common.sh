#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
compose=(docker compose -f "$project_root/infra/compose.yaml")
wait_condition="$project_root/scenarios/scripts/wait-condition.sh"

atomic_json(){ local target="$1" directory tmp;directory="$(dirname "$target")";mkdir -p "$directory";tmp="$(mktemp "$directory/.tmp.XXXXXX")";trap 'rm -f "$tmp"' RETURN;jq -S . >"$tmp";mv "$tmp" "$target";trap - RETURN; }
register_cleanup(){ local command="$1" file="${SCENARIO_CLEANUP_FILE:?SCENARIO_CLEANUP_FILE required before fault apply}";mkdir -p "$(dirname "$file")";printf '%s\n' "$command" >>"$file"; }
require_action(){ case "${1:-}" in apply|remove|status) ;; *) echo 'action must be apply, remove, or status' >&2;exit 64;;esac; }
bounded_curl(){ curl --fail-with-body --silent --show-error --max-time 10 "$@"; }
