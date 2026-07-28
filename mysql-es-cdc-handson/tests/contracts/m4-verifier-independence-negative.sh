#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
checker=tests/contracts/check-verifier-independence.sh
test -x "$checker"

fixture=$(mktemp -d "${TMPDIR:-/tmp}/m4-independence.XXXXXX")
trap 'rm -rf "$fixture"' EXIT

new_fixture() {
  rm -rf "$fixture/module"
  mkdir -p "$fixture/module/src/main/java/example" "$fixture/module/src/test/java/example" \
    "$fixture/module/target/classes" "$fixture/module/target/test-classes"
  printf '%s\n' '<project><dependencies/></project>' >"$fixture/module/pom.xml"
}

must_reject() {
  local label=$1
  if bash "$checker" "$fixture/module" >/dev/null 2>&1; then
    echo "independence checker accepted $label" >&2
    exit 1
  fi
}

new_fixture
printf '%s\n' 'package example; import com.interview.mysqlescdc.consumer.Sync;' \
  >"$fixture/module/src/main/java/example/Direct.java"
must_reject 'direct consumer import'

new_fixture
printf '%s\n' 'package example; class Dynamic { Class<?> load() throws Exception { String n="com.interview.mysqlescdc." + "consumer.Sync"; return Class.forName(n); } }' \
  >"$fixture/module/src/main/java/example/Dynamic.java"
must_reject 'dynamic consumer class-name construction'

new_fixture
printf '%s\n' 'package example; class Reflective { Class<?> c() throws Exception { return Class.forName("example.Safe"); } }' \
  >"$fixture/module/src/main/java/example/Reflective.java"
must_reject 'reflection entrypoint'

new_fixture
mkdir -p "$fixture/compile/com/interview/mysqlescdc/consumer"
printf '%s\n' 'package com.interview.mysqlescdc.consumer; public class Sync {}' \
  >"$fixture/compile/com/interview/mysqlescdc/consumer/Sync.java"
printf '%s\n' 'package example; class TestLeak { com.interview.mysqlescdc.consumer.Sync value; }' \
  >"$fixture/module/src/test/java/example/TestLeak.java"
javac -d "$fixture/module/target/test-classes" \
  "$fixture/compile/com/interview/mysqlescdc/consumer/Sync.java" \
  "$fixture/module/src/test/java/example/TestLeak.java"
rm -rf "$fixture/module/src/test/java/example" "$fixture/compile"
must_reject 'compiled test-class consumer reference'

new_fixture
printf '%s\n' '<project><dependencies><dependency><artifactId>search-sync-consumer</artifactId></dependency></dependencies></project>' \
  >"$fixture/module/pom.xml"
must_reject 'consumer Maven dependency'

new_fixture
if VERIFIER_TEST_CLASSPATH="/tmp/search-sync-consumer/target/classes" \
  bash "$checker" "$fixture/module" >/dev/null 2>&1; then
  echo 'independence checker accepted consumer module on resolved classpath' >&2
  exit 1
fi

new_fixture
printf '%s\n' 'package example; class ConsumerLagReader { String consumerGroup="product-search-sync-v1"; String note="Kafka consumer lag terminology"; }' \
  >"$fixture/module/src/main/java/example/ConsumerLagReader.java"
javac -d "$fixture/module/target/classes" \
  "$fixture/module/src/main/java/example/ConsumerLagReader.java"
bash "$checker" "$fixture/module"
