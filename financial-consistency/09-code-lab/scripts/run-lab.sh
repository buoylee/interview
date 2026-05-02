#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/out/main"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

find "$ROOT_DIR/src/main/java" -name '*.java' > "$ROOT_DIR/out-main-sources.txt"

javac --release 17 -encoding UTF-8 -d "$OUT_DIR" @"$ROOT_DIR/out-main-sources.txt"

java -cp "$OUT_DIR" com.interview.financialconsistency.codelab.runner.CodeLabRunner "$@"
