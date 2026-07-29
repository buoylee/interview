#!/usr/bin/env bash
set -euo pipefail

mode="${1:?validation mode required}"

validate='def exact_keys($required; $optional):
  . as $value |
  (($required - ($value|keys_unsorted))|length)==0 and
  (((($value|keys_unsorted) - ($required + $optional)))|length)==0;
def integer: type=="number" and floor==.;
def timestamp: type=="string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$");
def sha256: type=="string" and test("^[a-f0-9]{64}$");
def safe_command:
  exact_keys(
    ["sequence","kind","target","method","path","started_at","finished_at","exit_code"];
    ["body_sha256","fixture_path","fixture_sha256"]
  ) and
  (.sequence|integer and .>=1) and
  (.exit_code|integer and .>=0 and .<=255) and
  (.kind|IN("HTTP","SQL_FIXTURE","CONTROL")) and
  (.target|type=="string" and length>0 and test("^[A-Za-z0-9._:-]+$")) and
  (.method|IN("GET","POST","PUT","PATCH","DELETE","EXECUTE")) and
  (.path|type=="string" and startswith("/") and (contains("..")|not) and test("^[A-Za-z0-9._~!$&()*+,;=:@%/-]+$")) and
  (.started_at|timestamp) and (.finished_at|timestamp) and
  ((has("body_sha256")|not) or (.body_sha256|sha256)) and
  ((has("fixture_path")==has("fixture_sha256")) and
    ((has("fixture_path")|not) or
      ((.fixture_path|type=="string" and startswith("/")|not) and
       (.fixture_path|contains("..")|not) and
       (.fixture_path|test("^[A-Za-z0-9._/-]+$")) and
       (.fixture_sha256|sha256))));
def safe_commands: type=="array" and all(.[]; safe_command);'

case "$mode" in
  commands)
    file="${2:?observations file required}"
    jq -e "$validate
      type==\"object\" and (.commands|safe_commands) and (.recovery_commands|safe_commands)
    " "$file" >/dev/null
    ;;
  recovery)
    scenario="${2:?scenario required}"
    token="${3:?owner token required}"
    external_clear="${4:?external status required}"
    dispatch_rc="${5:?dispatcher exit status required}"
    file="${6:?recovery output required}"
    jq -e \
      --arg scenario "$scenario" \
      --arg token "$token" \
      --argjson external_clear "$external_clear" \
      --argjson dispatch_rc "$dispatch_rc" \
      "$validate
      type==\"object\" and
      exact_keys(
        [\"scenario_id\",\"owner_token\",\"recovery_action_observed\",\"external_status\",\"cleanup_actions\",\"commands\"];
        []
      ) and
      .scenario_id==\$scenario and .owner_token==\$token and
      (.recovery_action_observed|type)==\"boolean\" and
      .recovery_action_observed==\$external_clear and
      (.external_status|type)==\"object\" and
      (.external_status|exact_keys([\"resource\",\"active\",\"observed\"]; [])) and
      .external_status.resource==\"fixture-fault\" and
      (.external_status.active|type)==\"boolean\" and
      (.external_status.observed|type)==\"boolean\" and
      .external_status.active==(\$external_clear|not) and
      .external_status.observed==\$external_clear and
      (.cleanup_actions|type)==\"array\" and (.cleanup_actions|length)==1 and
      (.cleanup_actions[0]|exact_keys([\"name\",\"success\",\"finished_at\"]; [])) and
      .cleanup_actions[0].name==\"dispatch-owned-fixture-fault\" and
      (.cleanup_actions[0].success|type)==\"boolean\" and
      .cleanup_actions[0].success==\$external_clear and
      (.cleanup_actions[0].finished_at|timestamp) and
      (.commands|safe_commands) and (.commands|length)==1 and
      .commands[0].sequence==1 and .commands[0].kind==\"CONTROL\" and
      .commands[0].target==\"fixture-fault-status\" and
      .commands[0].method==\"DELETE\" and
      .commands[0].path==\"/owned/fixture-fault\" and
      .commands[0].exit_code==\$dispatch_rc and
      ((\$dispatch_rc==0)==\$external_clear)
      " "$file" >/dev/null
    ;;
  *)
    echo 'unknown runner JSON validation mode' >&2
    exit 64
    ;;
esac
