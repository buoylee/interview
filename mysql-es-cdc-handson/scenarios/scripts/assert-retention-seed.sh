#!/usr/bin/env bash
set -euo pipefail
ack="${1:?ACK JSON required}";record="${2:?record JSON required}"
jq -e '
  type=="object" and keys==["offset","partition","topic"] and
  .topic=="product-search-revisions" and .partition==0 and
  (.offset|type)=="number" and (.offset|floor)==.offset and .offset>=0
' "$ack" >/dev/null
jq -e '
  type=="object" and
  .database=="product_catalog" and .table=="product_search_revision" and
  .isDdl==false and .type=="UPDATE" and
  (.data|type)=="array" and (.data|length)==1 and
  (.data[0]|keys)==["active","product_id","revision"] and
  .data[0].product_id=="900001" and .data[0].revision=="1" and .data[0].active=="1"
' "$record" >/dev/null
