#!/usr/bin/env bash

process_identity_is_unchanged() {
  local before="$1"
  local after="$2"
  local before_pid before_ticks before_extra
  local after_pid after_ticks after_extra

  IFS='|' read -r before_pid before_ticks before_extra <<<"$before"
  IFS='|' read -r after_pid after_ticks after_extra <<<"$after"

  test -z "$before_extra" &&
    test -z "$after_extra" &&
    test -n "$before_pid" &&
    test -n "$before_ticks" &&
    test -n "$after_pid" &&
    test -n "$after_ticks" &&
    test "$before" = "$before_pid|$before_ticks" &&
    test "$after" = "$after_pid|$after_ticks" || return 1

  case "$before_pid$before_ticks$after_pid$after_ticks" in
    *[!0-9]*) return 1 ;;
  esac

  test "$before" = "$after"
}

log_pattern_exists_since() {
  local cutoff="$1"
  local log_file="$2"
  local required_pattern="$3"

  test -r "$log_file" || return 1

  awk -v cutoff="$cutoff" '
    BEGIN {
      required = ARGV[2]
      ARGV[2] = ""
    }
    {
      timestamp = substr($0, 1, 23)
      timestamp_is_valid = \
        length(timestamp) == 23 && \
        substr(timestamp, 5, 1) == "-" && \
        substr(timestamp, 8, 1) == "-" && \
        substr(timestamp, 11, 1) == " " && \
        substr(timestamp, 14, 1) == ":" && \
        substr(timestamp, 17, 1) == ":" && \
        substr(timestamp, 20, 1) == "."
      if (timestamp_is_valid && timestamp >= cutoff && index($0, required)) {
        found = 1
      }
    }
    END {
      exit !found
    }
  ' "$log_file" "$required_pattern"
}

require_log_patterns_since() {
  local cutoff="$1"
  local log_file="$2"
  shift 2

  test "$#" -gt 0 || return 1

  local required_pattern
  for required_pattern in "$@"; do
    log_pattern_exists_since "$cutoff" "$log_file" "$required_pattern" || return 1
  done
}

adapter_mapping_load_is_current() {
  local cutoff="$1"
  local log_file="$2"

  require_log_patterns_since "$cutoff" "$log_file" \
    "## Start loading es mapping config ..." \
    "## ES mapping config loaded"
}
