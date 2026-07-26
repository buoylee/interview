#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

validate_report() {
  local report="$1"
  local tests errors failures skipped summary suite_line
  suite_line="$(grep -m 1 '<testsuite ' "$report")"
  tests="$(sed -n 's/.* tests="\([0-9][0-9]*\)".*/\1/p' <<<"$suite_line")"
  errors="$(sed -n 's/.* errors="\([0-9][0-9]*\)".*/\1/p' <<<"$suite_line")"
  failures="$(sed -n 's/.* failures="\([0-9][0-9]*\)".*/\1/p' <<<"$suite_line")"
  skipped="$(sed -n 's/.* skipped="\([0-9][0-9]*\)".*/\1/p' <<<"$suite_line")"
  summary="$tests $errors $failures $skipped"
  if [ "$summary" != "3 0 0 0" ]; then
    echo "ProductMutationServiceIT report must prove tests=3, errors=0, failures=0, skipped=0; got: ${summary:-unreadable}" >&2
    return 1
  fi

  for test_name in \
    all_search_relevant_changes_advance_one_revision \
    a_failed_business_write_rolls_back_its_revision \
    inventory_mutation_after_delete_rolls_back_without_advancing_revision
  do
    grep -Fq "name=\"$test_name\"" "$report" || {
      echo "ProductMutationServiceIT report missing $test_name" >&2
      return 1
    }
  done
}

if [ "${1:-}" = "--validate-report" ]; then
  test "$#" -eq 2
  validate_report "$2"
  exit
fi

mysql_image="mysql:8.4.8"
container="m0-product-it-$RANDOM-$$"
dependency_tree="$(mktemp "${TMPDIR:-/tmp}/m0-product-dependencies.XXXXXX")"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -f "$dependency_tree"
}
trap cleanup EXIT

docker run -d --name "$container" \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=product_catalog \
  -e MYSQL_USER=product \
  -e MYSQL_PASSWORD=productpass \
  -p 127.0.0.1::3306 \
  -v "$PWD/infra/mysql/init:/docker-entrypoint-initdb.d:ro" \
  "$mysql_image" >/dev/null

deadline=$((SECONDS + 90))
until docker exec "$container" mysqladmin ping -h 127.0.0.1 -uproduct -pproductpass --silent >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "timeout waiting for isolated $mysql_image used by ProductMutationServiceIT" >&2
    docker logs "$container" >&2 || true
    exit 1
  fi
  sleep 1
done

host_port="$(docker inspect -f '{{(index (index .NetworkSettings.Ports "3306/tcp") 0).HostPort}}' "$container")"
SPRING_DATASOURCE_URL="jdbc:mysql://127.0.0.1:${host_port}/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC" \
SPRING_DATASOURCE_USERNAME=product \
SPRING_DATASOURCE_PASSWORD=productpass \
  ./mvnw -pl product-service -Dtest=ProductMutationServiceIT test

report="product-service/target/surefire-reports/TEST-com.interview.mysqlescdc.product.application.ProductMutationServiceIT.xml"
validate_report "$report"
echo "ProductMutationServiceIT: 3/3 tests executed against isolated mysql:8.4.8"

./mvnw -q -pl product-service dependency:tree \
  -Dscope=runtime -DoutputFile="$dependency_tree"

if grep -Eiq '(^|:)(spring-kafka|kafka-clients|elasticsearch-java|elasticsearch-rest-client)(:|$)' "$dependency_tree"; then
  echo "product-service runtime dependency tree contains a forbidden Kafka or Elasticsearch client" >&2
  grep -Ei 'spring-kafka|kafka-clients|elasticsearch' "$dependency_tree" >&2
  exit 1
fi

echo "product-service dependency tree: no Kafka or Elasticsearch client"
