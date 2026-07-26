#!/usr/bin/env bash
set -euo pipefail

base_dir="$(cd "$(dirname "$0")" && pwd)"
artifact_dir="$base_dir/artifacts"
archive="$artifact_dir/canal.adapter-1.1.8.tar.gz"
partial="$archive.partial"
expected_size=291072978
expected_sha256="$(awk 'NR == 1 { print $1 }' "$base_dir/SHA256SUMS")"
mkdir -p "$artifact_dir"

file_size() {
  stat -f '%z' "$1" 2>/dev/null || stat -c '%s' "$1"
}

file_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{ print $1 }'
  else
    shasum -a 256 "$1" | awk '{ print $1 }'
  fi
}

verify_archive() {
  local candidate="$1"
  test -f "$candidate" &&
    test "$(file_size "$candidate")" = "$expected_size" &&
    test "$(file_sha256 "$candidate")" = "$expected_sha256"
}

if verify_archive "$archive"; then
  exit 0
fi

rm -f "$archive" "$partial"
curl -fL \
  https://github.com/alibaba/canal/releases/download/canal-1.1.8/canal.adapter-1.1.8.tar.gz \
  -o "$partial"
verify_archive "$partial"
mv "$partial" "$archive"
verify_archive "$archive"
