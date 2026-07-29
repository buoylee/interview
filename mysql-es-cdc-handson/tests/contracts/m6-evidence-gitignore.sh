#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
files=(manifest.json input-commands.json fault.json mysql-snapshot.json es-snapshot.json kafka-offsets.json differences.json recovery-actions.json result.json)
probe="$(mktemp -d)"
trap 'rm -rf "$probe"' EXIT

cp "$project_root/.gitignore" "$probe/.gitignore"
git -C "$probe" init -q
mkdir -p "$probe/evidence/canal-normal-restart" "$probe/evidence/.raw/canal-normal-restart" \
  "$probe/evidence/.attempts/.runs/canal-normal-restart/run"
touch "$probe/evidence/index.json"

if git -C "$probe" check-ignore -q --no-index evidence/index.json; then
  echo 'committed M6 evidence index is ignored' >&2
  exit 1
fi
for name in "${files[@]}"; do
  path="evidence/canal-normal-restart/$name"
  touch "$probe/$path"
  if git -C "$probe" check-ignore -q --no-index "$path"; then
    echo "committed M6 evidence is ignored: $path" >&2
    exit 1
  fi
done
git -C "$probe" check-ignore -q --no-index evidence/.raw/canal-normal-restart/service.log || { echo 'raw evidence logs must be ignored' >&2; exit 1; }
git -C "$probe" check-ignore -q --no-index evidence/.raw/canal-normal-restart/debug.json || { echo 'raw evidence JSON must be ignored' >&2; exit 1; }
git -C "$probe" check-ignore -q --no-index evidence/.attempts/.runs/canal-normal-restart/run/result.json || { echo 'runtime attempts must be ignored' >&2; exit 1; }

printf 'M6 evidence gitignore contract passed\n'
