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

./scenarios/scripts/assert-cursor-advanced.sh \
  tests/fixtures/cursor-before.json tests/fixtures/cursor-after-position.json
./scenarios/scripts/assert-cursor-advanced.sh \
  tests/fixtures/cursor-before.json tests/fixtures/cursor-after-rotation.json
if ./scenarios/scripts/assert-cursor-advanced.sh \
    tests/fixtures/cursor-before.json tests/fixtures/cursor-after-same.json \
    >/dev/null 2>&1; then
  echo "cursor comparator accepted an unchanged decoded cursor" >&2
  exit 1
fi

known_npe="$(./scenarios/scripts/classify-canal-stop-npe.sh \
  tests/fixtures/canal-stop-known-npe.log)"
jq -e '
  .known_stop_npe.present == true and .known_stop_npe.count == 1 and
  (.known_stop_npe.excerpts | length) == 1 and
  .unexpected_npe.present == false and .unexpected_npe.count == 0
' <<<"$known_npe" >/dev/null

unexpected_npe="$(./scenarios/scripts/classify-canal-stop-npe.sh \
  tests/fixtures/canal-stop-unexpected-npe.log)"
jq -e '
  .known_stop_npe.present == false and .known_stop_npe.count == 0 and
  .unexpected_npe.present == true and .unexpected_npe.count == 1 and
  (.unexpected_npe.excerpts | length) == 1
' <<<"$unexpected_npe" >/dev/null

./scenarios/scripts/assert-m0-evidence.sh tests/fixtures/canal-position.json

unexpected_evidence="$(mktemp "${TMPDIR:-/tmp}/m0-unexpected-npe-evidence.XXXXXX")"
jq '
  .post_restart.unexpected_npe = {
    present:true,
    count:1,
    excerpts:["java.lang.NullPointerException: unrelated"]
  }
' tests/fixtures/canal-position.json >"$unexpected_evidence"
if ./scenarios/scripts/assert-m0-evidence.sh "$unexpected_evidence" >/dev/null 2>&1; then
  echo "M0 evidence assertion accepted an unexpected stop NPE" >&2
  exit 1
fi
./scenarios/scripts/verify-product-transactions.sh \
  --validate-report tests/fixtures/product-it-pass.xml

manifest="$(mktemp "${TMPDIR:-/tmp}/m0-version-manifest.XXXXXX")"
trap 'rm -f "$manifest" "$unexpected_evidence"' EXIT
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

if M0_IMAGE_INSPECT_FIXTURE=tests/fixtures/image-inspect-wrong-repository.json \
    M0_VERSION_MANIFEST_OUTPUT="$manifest" \
    ./scenarios/scripts/record-image-digests.sh >/dev/null 2>&1; then
  echo "record-image-digests accepted a digest from the wrong repository" >&2
  exit 1
fi

if ./scenarios/scripts/verify-product-transactions.sh \
    --validate-report tests/fixtures/product-it-fail.xml >/dev/null 2>&1; then
  echo "verify-product-transactions accepted an incomplete ProductMutationServiceIT report" >&2
  exit 1
fi

echo "M0 evidence fixtures: cursor, image digest, and verify failure contracts pass"
