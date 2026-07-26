#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 CANAL_POSITION_JSON" >&2
  exit 2
fi

jq -e '
  def ordered_cursor:
    . as $cursor
    | ($cursor.journal
       | capture("^(?<prefix>.*[^0-9])(?<index>[0-9]+)$")) as $journal
    | {
        prefix: $journal.prefix,
        index: ($journal.index | tonumber),
        position: $cursor.position,
        source: $cursor.source
      };
  def cursor_advanced($before; $after):
    ($before | ordered_cursor) as $before_cursor
    | ($after | ordered_cursor) as $after_cursor
    | $after_cursor.source == $before_cursor.source
      and $after_cursor.prefix == $before_cursor.prefix
      and (
        $after_cursor.index > $before_cursor.index
        or (
          $after_cursor.index == $before_cursor.index
          and $after_cursor.position > $before_cursor.position
        )
      );

  .milestone == "M0" and
  .contract == "mysql-canal-kafka-capture-restart-v1" and
  .topic == "product-search-revisions" and
  .topic_partition_count == 3 and
  .revision1.kafka.key == null and
  (.revision1.kafka.partition | type) == "number" and
  (.revision1.kafka.offset | type) == "number" and
  .revision1.raw.database == "product_catalog" and
  .revision1.raw.table == "product_search_revision" and
  (.revision1.raw.data | any(.product_id == "1001" and .revision == "1")) and
  .pre_restart.meta.contract == "canal-1.1.8-file-mixed-meta-ack-cursor" and
  (.pre_restart.meta_sha256 | test("^[0-9a-f]{64}$")) and
  (.pre_restart.kafka_end_offsets | length) == 3 and
  .post_restart.meta_sha256 == .pre_restart.meta_sha256 and
  .post_restart.meta.journal == .pre_restart.meta.journal and
  .post_restart.meta.position == .pre_restart.meta.position and
  .post_restart.kafka_end_offsets == .pre_restart.kafka_end_offsets and
  .post_restart.startup_exact_resume.matched == true and
  (.post_restart.known_stop_npe.present | type) == "boolean" and
  (.post_restart.known_stop_npe.count | type) == "number" and
  (.post_restart.known_stop_npe.excerpts | type) == "array" and
  (.post_restart.known_stop_npe.excerpts | length) == .post_restart.known_stop_npe.count and
  ((.post_restart.known_stop_npe.present and .post_restart.known_stop_npe.count > 0)
   or ((.post_restart.known_stop_npe.present | not) and .post_restart.known_stop_npe.count == 0)) and
  (.post_restart.known_stop_npe.scope | contains("not a success condition")) and
  .post_restart.unexpected_npe.present == false and
  .post_restart.unexpected_npe.count == 0 and
  .post_restart.unexpected_npe.excerpts == [] and
  .revision2.kafka.partition == .revision1.kafka.partition and
  .revision2.kafka.offset == (.revision1.kafka.offset + 1) and
  .revision2.kafka.key == null and
  (.revision2.raw.data | any(.product_id == "1001" and .revision == "2")) and
  (.revision2.raw.old | any(.revision == "1")) and
  .revision2.exactly_once_at_expected_next_offset == true and
  .revision2.post_ack_cursor_advanced == true and
  cursor_advanced(.post_restart.meta; .revision2.post_ack_meta) and
  (.revision2.kafka_end_offset_delta | map(.delta) | add) == 1 and
  (.revision2.kafka_end_offset_delta | map(select(.delta == 1) | .partition)) ==
    [.revision1.kafka.partition]
' "$1" >/dev/null
