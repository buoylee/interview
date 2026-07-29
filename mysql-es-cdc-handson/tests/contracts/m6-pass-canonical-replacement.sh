#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
tmp="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$tmp"' EXIT
scenario=canal-normal-restart
old=11111111-1111-4111-8111-111111111111
new=22222222-2222-4222-8222-222222222222
mkdir -p "$tmp/.runs/$scenario/$old" "$tmp/.runs/$scenario/$new"
ln -s ".runs/$scenario/$old" "$tmp/$scenario"

python3 scenarios/scripts/publish-evidence.py replace "$tmp" "$scenario" "$new" "$old" >/dev/null
test "$(readlink "$tmp/$scenario")" = ".runs/$scenario/$new"
test -d "$tmp/.runs/$scenario/$old"
test -d "$tmp/.runs/$scenario/$new"
test ! -e "$tmp/.link.$scenario.$new"

echo 'M6 validated PASS atomically replaces prior canonical without deleting attempts'
