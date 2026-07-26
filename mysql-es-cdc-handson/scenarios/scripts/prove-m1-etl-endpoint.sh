#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
output="${1:?usage: prove-m1-etl-endpoint.sh OUTPUT}"
archive=infra/canal-adapter/artifacts/canal.adapter-1.1.8.tar.gz
official_sha=e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340
actual_sha=$(sha256sum "$archive" | awk '{print $1}')
test "$actual_sha" = "$official_sha"

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/m1-task4-etl.XXXXXX")
trap 'rm -rf "$temp_dir"' EXIT
launcher="$temp_dir/client-adapter.launcher-1.1.8.jar"
tar -xOf "$archive" lib/client-adapter.launcher-1.1.8.jar >"$launcher"
launcher_sha=$(sha256sum "$launcher" | awk '{print $1}')
javap_output="$temp_dir/CommonRest.javap"
javap -classpath "$launcher" -p -v \
  com.alibaba.otter.canal.adapter.launcher.rest.CommonRest >"$javap_output"
grep -Fq 'value=["/etl/{type}/{task}"]' "$javap_output"
grep -Fq 'name="params"' "$javap_output"

temporary=$(mktemp "${output}.tmp.XXXXXX")
trap 'rm -rf "$temp_dir"; rm -f "$temporary"' EXIT
jq -n --arg archive_sha "$actual_sha" --arg launcher_sha "$launcher_sha" '
  {
    official_archive_sha256:$archive_sha,
    launcher_jar_sha256:$launcher_sha,
    source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
    post_mapping:"/etl/{type}/{task}",request_param_name:"params",
    instantiated_endpoint:"/etl/es8/products.yml",request_param_value:"1401"
  }
' >"$temporary"
mv "$temporary" "$output"
rm -rf "$temp_dir"
trap - EXIT
