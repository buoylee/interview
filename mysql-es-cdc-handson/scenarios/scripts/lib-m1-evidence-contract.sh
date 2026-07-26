#!/usr/bin/env bash

m1_require_evidence_files() {
  local out="$1"
  shift
  local required
  for required in "$@"; do
    test -s "$out/$required" || return 1
  done
}

m1_assert_current_mapping_evidence() {
  local out="$1"
  grep -Fq '## Start loading es mapping config ...' "$out/adapter.log" &&
    grep -Fq '## ES mapping config loaded' "$out/adapter.log" &&
    grep -Fxq -- \
      '- formal es8 products mapping: exact image file plus current-Java-run load evidence' \
      "$out/current-run-topology-proof.txt"
}

m1_assert_derived_result() {
  local derive_script="$1"
  local out="$2"
  local expected_result
  expected_result=$(mktemp "${TMPDIR:-/tmp}/m1-derived-result.XXXXXX") || return 1
  if ! bash "$derive_script" "$out" >"$expected_result"; then
    rm -f "$expected_result"
    return 1
  fi
  diff -u <(jq -S . "$expected_result") <(jq -S . "$out/result.json")
  local status=$?
  rm -f "$expected_result"
  return "$status"
}
