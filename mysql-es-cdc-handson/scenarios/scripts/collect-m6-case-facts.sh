#!/usr/bin/env bash
set -euo pipefail

scenario_id="${1:?scenario required}"
raw="${2:?raw directory required}"
test -d "$raw"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf '[]\n' >"$tmp/facts.json"

while IFS= read -r file; do
  relative="${file#"$raw"/}"
  if jq -e . "$file" >/dev/null 2>&1; then
    sha256="$(jq -cS . "$file" | shasum -a 256 | awk '{print $1}')"
    jq --arg path "$relative" --arg sha "$sha256" --slurpfile value "$file" \
      '.+[{path:$path,sha256:$sha,json:$value[0]}]' "$tmp/facts.json" >"$tmp/next.json"
  else
    sha256="$(shasum -a 256 "$file" | awk '{print $1}')"
    jq --arg path "$relative" --arg sha "$sha256" --rawfile value "$file" \
      '.+[{path:$path,sha256:$sha,text:$value}]' "$tmp/facts.json" >"$tmp/next.json"
  fi
  mv "$tmp/next.json" "$tmp/facts.json"
done < <(find "$raw" -type f \( -name '*.json' -o -name 'generation-before' -o -name 'generation-after' -o -name 'rebuild-run-id' -o -name 'old-alias' -o -name 'alias-after-*' -o -name 'promoted-*' \) | LC_ALL=C sort)

jq -n --arg scenario "$scenario_id" --slurpfile facts "$tmp/facts.json" \
  '{scenario_id:$scenario,artifacts:$facts[0]}'
