#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
files=(manifest.json input-commands.json fault.json mysql-snapshot.json es-snapshot.json kafka-offsets.json differences.json recovery-actions.json result.json)

cd "$project_root"
for name in "${files[@]}"; do
  path="evidence/canal-normal-restart/$name"
  if git check-ignore -q --no-index "$path"; then
    echo "committed M6 evidence is ignored: $path" >&2
    exit 1
  fi
done
git check-ignore -q --no-index evidence/.raw/canal-normal-restart/service.log || { echo 'raw evidence logs must be ignored' >&2; exit 1; }
git check-ignore -q --no-index evidence/.raw/canal-normal-restart/debug.json || { echo 'raw evidence JSON must be ignored' >&2; exit 1; }

printf 'M6 evidence gitignore contract passed\n'
