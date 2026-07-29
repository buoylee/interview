#!/usr/bin/env bash
set -euo pipefail

# The M6 normal verify contract names representative end-to-end checks together.
exec bash "$(cd "$(dirname "$0")/../.." && pwd)/scenarios/scripts/smoke-m0.sh"
