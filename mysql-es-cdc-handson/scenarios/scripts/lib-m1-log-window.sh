#!/usr/bin/env bash

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
