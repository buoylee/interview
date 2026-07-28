#!/usr/bin/env bash
set -euo pipefail

module_root="${1:-consistency-verifier}"
test -f "$module_root/pom.xml"

fail() {
  echo "verifier independence violation: $1" >&2
  exit 1
}

if grep -Fq '<artifactId>search-sync-consumer</artifactId>' "$module_root/pom.xml"; then
  fail 'consumer Maven dependency'
fi
if [[ "${VERIFIER_TEST_CLASSPATH:-}" == *search-sync-consumer* ]]; then
  fail 'consumer module on resolved test classpath'
fi

source_roots=(
  "$module_root/src/main/java"
  "$module_root/src/test/java"
  "$module_root/target/generated-sources"
  "$module_root/target/generated-test-sources"
  "$module_root/target/test-generated-sources"
)
for root in "${source_roots[@]}"; do
  [[ -d "$root" ]] || continue
  while IFS= read -r -d '' source; do
    if grep -Eiq 'consumer|Class[[:space:]]*\.[[:space:]]*forName|\.loadClass[[:space:]]*\(|java[.]lang[.]reflect|MethodHandles|MethodType' "$source"; then
      fail "forbidden implementation/reflection reference in $source"
    fi
  done < <(find "$root" -type f -name '*.java' -print0)
done

for root in "$module_root/target/classes" "$module_root/target/test-classes"; do
  [[ -d "$root" ]] || continue
  while IFS= read -r -d '' class_file; do
    if LC_ALL=C grep -aEiq 'consumer|search-sync-consumer|com/interview/mysqlescdc/consumer|java/lang/reflect' "$class_file"; then
      fail "forbidden implementation/reflection reference in $class_file"
    fi
  done < <(find "$root" -type f -name '*.class' -print0)
done
