#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 META_DAT" >&2
  exit 2
fi

meta_file="$1"

jq -ce --arg path "/home/admin/canal-data/products/meta.dat" '
  (.clientDatas // [] | map(select(.cursor != null)) | first) as $client
  | if .destination != "products" then
      error("unexpected Canal destination")
    elif $client == null then
      error("meta.dat has no acknowledged client cursor")
    elif ($client.cursor.postion.journalName | type) != "string"
         or ($client.cursor.postion.journalName | length) == 0 then
      error("meta.dat cursor has no journal name")
    elif ($client.cursor.postion.position | type) != "number"
         or $client.cursor.postion.position <= 0 then
      error("meta.dat cursor has no positive binlog position")
    else
      {
        contract: "canal-1.1.8-file-mixed-meta-ack-cursor",
        path: $path,
        destination: .destination,
        client: {
          destination: $client.clientIdentity.destination,
          client_id: $client.clientIdentity.clientId,
          filter: ($client.clientIdentity.filter // null)
        },
        journal: $client.cursor.postion.journalName,
        position: $client.cursor.postion.position,
        timestamp: ($client.cursor.postion.timestamp // null),
        server_id: ($client.cursor.postion.serverId // null),
        gtid: ($client.cursor.postion.gtid // null),
        source: ($client.cursor.identity.sourceAddress // null),
        slave_id: ($client.cursor.identity.slaveId // null)
      }
    end
' "$meta_file"
