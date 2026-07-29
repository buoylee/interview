#!/usr/bin/env bash
set -euo pipefail

target="${1:?gap target required}"
evidence="${2:?gap evidence required}"
jq -e 'type=="object"' "$evidence" >/dev/null

case "$target" in
  mysql-binlog)
    jq -e '
      keys|sort==["canal_missing_position_observed","journal","position","recorded_present","retained_files","target"]
    ' "$evidence" >/dev/null
    jq -e '
      .target=="mysql-binlog" and
      (.journal|type=="string" and length>0) and
      (.position|type=="number" and .>=0) and
      (.journal as $journal | .retained_files|type=="array") and
      .recorded_present==false and
      .canal_missing_position_observed==true and
      (.journal as $journal | .retained_files|index($journal)==null)
    ' "$evidence" >/dev/null
    ;;
  kafka)
    jq -e '
      keys|sort==["beginning_offset","committed_offset","partition","target","topic"]
    ' "$evidence" >/dev/null
    jq -e '
      .target=="kafka" and .topic=="product-search-revisions" and
      (.partition|type=="number" and .>=0) and
      (.committed_offset|type=="number" and .>=0) and
      (.beginning_offset|type=="number") and
      .beginning_offset>.committed_offset
    ' "$evidence" >/dev/null
    ;;
  *) echo "unknown gap target: $target" >&2; exit 64 ;;
esac
