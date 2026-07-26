#!/usr/bin/env bash
set -euo pipefail

topic=product-search-revisions
expected_partitions=3

/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists \
  --topic "$topic" \
  --partitions "$expected_partitions" \
  --replication-factor 1

description=$(/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic "$topic")

printf '%s\n' "$description"

partition_count=$(printf '%s\n' "$description" | awk '
  NR == 1 {
    for (field = 1; field <= NF; field++) {
      if ($field == "PartitionCount:") {
        print $(field + 1)
        exit
      }
    }
  }
')

if [ "$partition_count" != "$expected_partitions" ]; then
  printf '%s\n' \
    "ERROR: topic $topic has PartitionCount: ${partition_count:-unknown}; expected $expected_partitions. Explicitly reset or migrate the Kafka volume; this script will not alter an existing topic." \
    >&2
  exit 1
fi
