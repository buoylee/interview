#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

decoded="$(./scenarios/scripts/decode-canal-meta.sh tests/fixtures/canal-meta.dat)"
jq -e '
  .contract == "canal-1.1.8-file-mixed-meta-ack-cursor" and
  .path == "/home/admin/canal-data/products/meta.dat" and
  .destination == "products" and
  .journal == "mysql-bin.000002" and
  .position == 4096 and
  .source.address == "toxiproxy" and
  .source.port == 8668
' <<<"$decoded" >/dev/null

./scenarios/scripts/assert-m0-evidence.sh tests/fixtures/canal-position.json
./scenarios/scripts/verify-product-transactions.sh \
  --validate-report tests/fixtures/product-it-pass.xml

manifest="$(mktemp "${TMPDIR:-/tmp}/m0-version-manifest.XXXXXX")"
trap 'rm -f "$manifest"' EXIT
M0_IMAGE_INSPECT_FIXTURE=tests/fixtures/image-inspect-pass.json \
M0_VERSION_MANIFEST_OUTPUT="$manifest" \
  ./scenarios/scripts/record-image-digests.sh >/dev/null
jq -e '
  .contract == "pinned-registry-digest-and-local-build-id-v1" and
  (.images | length) == 9 and
  ([.images[] | select(.kind == "registry") | .repo_digest] | all(test("@sha256:[0-9a-f]{64}$"))) and
  ([.images[] | select(.kind == "local-build") | .repo_digest_status] | all(. == "unavailable/local-build"))
' "$manifest" >/dev/null

if M0_IMAGE_INSPECT_FIXTURE=tests/fixtures/image-inspect-missing-digest.json \
    M0_VERSION_MANIFEST_OUTPUT="$manifest" \
    ./scenarios/scripts/record-image-digests.sh >/dev/null 2>&1; then
  echo "record-image-digests accepted a registry image without RepoDigest" >&2
  exit 1
fi

if ./scenarios/scripts/verify-product-transactions.sh \
    --validate-report tests/fixtures/product-it-fail.xml >/dev/null 2>&1; then
  echo "verify-product-transactions accepted an incomplete ProductMutationServiceIT report" >&2
  exit 1
fi

echo "M0 evidence fixtures: cursor, image digest, and verify failure contracts pass"
