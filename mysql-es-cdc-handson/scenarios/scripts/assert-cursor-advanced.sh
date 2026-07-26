#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 BEFORE_DECODED_CURSOR AFTER_DECODED_CURSOR" >&2
  exit 2
fi

before="$1"
after="$2"

jq -e -n --slurpfile before "$before" --slurpfile after "$after" '
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

  ($before[0] | ordered_cursor) as $before_cursor
  | ($after[0] | ordered_cursor) as $after_cursor
  | ($before_cursor.position | type) == "number"
    and ($after_cursor.position | type) == "number"
    and $before_cursor.position > 0
    and $after_cursor.position > 0
    and $after_cursor.source == $before_cursor.source
    and $after_cursor.prefix == $before_cursor.prefix
    and (
      $after_cursor.index > $before_cursor.index
      or (
        $after_cursor.index == $before_cursor.index
        and $after_cursor.position > $before_cursor.position
      )
    )
' >/dev/null || {
  echo "decoded Canal cursor did not advance in journal/position order" >&2
  exit 1
}
