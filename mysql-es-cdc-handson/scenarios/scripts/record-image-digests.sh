#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

registry_refs=(
  mysql:8.4.8
  canal/canal-server:v1.1.8
  apache/kafka:4.1.2
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0
  ghcr.io/shopify/toxiproxy:2.12.0
  eclipse-temurin:21-jre
)
local_services=(product-service search-sync-consumer consistency-verifier)
local_refs=(
  mysql-es-cdc-handson/product-service:0.1.0-local
  mysql-es-cdc-handson/search-sync-consumer:0.1.0-local
  mysql-es-cdc-handson/consistency-verifier:0.1.0-local
)

compose_registry_refs="$(docker compose -f infra/compose.yaml --profile m0-tools \
  config --format json \
  | jq -c '[.services[].image | select(startswith("mysql-es-cdc-handson/") | not)] | unique | sort')"
expected_compose_registry_refs="$(printf '%s\n' "${registry_refs[@]:0:5}" \
  | jq -Rsc 'split("\n")[:-1] | sort')"
if [ "$compose_registry_refs" != "$expected_compose_registry_refs" ]; then
  echo "Compose dependency refs do not match the five pinned registry refs expected by the M0 image manifest" >&2
  echo "Compose:  $compose_registry_refs" >&2
  echo "Expected: $expected_compose_registry_refs" >&2
  exit 1
fi

mkdir -p evidence/m0
output="${M0_VERSION_MANIFEST_OUTPUT:-evidence/m0/version-manifest.json}"
inspect_data="$(mktemp "${TMPDIR:-/tmp}/m0-image-inspect.XXXXXX")"
trap 'rm -f "$inspect_data"' EXIT

if [ -n "${M0_IMAGE_INSPECT_FIXTURE:-}" ]; then
  cp "$M0_IMAGE_INSPECT_FIXTURE" "$inspect_data"
else
  docker compose -f infra/compose.yaml --profile m0-tools build \
    product-service search-sync-consumer consistency-verifier

  printf '[]' >"$inspect_data"
  for ref in "${registry_refs[@]}"; do
    if ! docker image inspect "$ref" >/dev/null 2>&1; then
      docker pull "$ref" >/dev/null
    fi
    inspected="$(docker image inspect "$ref" | jq -c --arg ref "$ref" '
      .[0] | {
        kind: "registry",
        ref: $ref,
        id: .Id,
        repo_digests: (.RepoDigests // [])
      }
    ')"
    jq --argjson inspected "$inspected" '. + [$inspected]' "$inspect_data" \
      >"${inspect_data}.next"
    mv "${inspect_data}.next" "$inspect_data"
  done

  for index in "${!local_services[@]}"; do
    service="${local_services[$index]}"
    ref="${local_refs[$index]}"
    inspected="$(docker image inspect "$ref" | jq -c --arg service "$service" --arg ref "$ref" '
      .[0] | {
        kind: "local-build",
        service: $service,
        ref: $ref,
        id: .Id,
        repo_digests: (.RepoDigests // [])
      }
    ')"
    jq --argjson inspected "$inspected" '. + [$inspected]' "$inspect_data" \
      >"${inspect_data}.next"
    mv "${inspect_data}.next" "$inspect_data"
  done
fi

expected_registry="$(printf '%s\n' "${registry_refs[@]}" | jq -Rsc 'split("\n")[:-1] | sort')"
expected_local="$(printf '%s\n' "${local_refs[@]}" | jq -Rsc 'split("\n")[:-1] | sort')"

jq -e --argjson expected_registry "$expected_registry" --argjson expected_local "$expected_local" '
  def ref_repository:
    split("@")[0]
    | if test(":[^/]+$") then sub(":[^/]+$"; "") else . end;
  def matching_repo_digests:
    . as $image
    | ($image.ref | ref_repository) as $repository
    | [$image.repo_digests[] | select((split("@")[0]) == $repository)];

  (map(select(.kind == "registry") | .ref) | sort) == $expected_registry and
  (map(select(.kind == "local-build") | .ref) | sort) == $expected_local and
  all(.[]; (.ref | contains(":latest") | not)) and
  all(.[]; (.id | type) == "string" and (.id | startswith("sha256:"))) and
  all(.[] | select(.kind == "registry");
    (matching_repo_digests | length) == 1 and
    (matching_repo_digests[0] | test("@sha256:[0-9a-f]{64}$")))
' "$inspect_data" >/dev/null || {
  echo "image identity input is incomplete: every pinned registry ref, including eclipse-temurin:21-jre, needs a real RepoDigest; every app image needs a local image ID" >&2
  exit 1
}

jq -n \
  --arg captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --slurpfile inspected "$inspect_data" '
  def ref_repository:
    split("@")[0]
    | if test(":[^/]+$") then sub(":[^/]+$"; "") else . end;
  def matching_repo_digests:
    . as $image
    | ($image.ref | ref_repository) as $repository
    | [$image.repo_digests[] | select((split("@")[0]) == $repository)];

  {
    milestone: "M0",
    captured_at: $captured_at,
    contract: "pinned-registry-digest-and-local-build-id-v1",
    images: ($inspected[0] | map(
      if .kind == "registry" then
        {
          kind: .kind,
          ref: .ref,
          id: .id,
          repo_digest: (matching_repo_digests[0])
        }
      else
        {
          kind: .kind,
          service: .service,
          ref: .ref,
          id: .id,
          repo_digest: null,
          repo_digest_status: "unavailable/local-build"
        }
      end
    ))
  }
' >"$output"

echo "wrote $output"
