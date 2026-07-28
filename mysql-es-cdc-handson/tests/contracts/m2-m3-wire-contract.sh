#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

test_file=search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/canal/CanalPartitionContractIT.java

grep -Fq 'awaitCleanupBarrier' "$test_file"
grep -Fq 'captureBaselineOffsets' "$test_file"
grep -Fq 'consumer.endOffsets(consumer.assignment())' "$test_file"
grep -Fq 'consumer.seek(partition, endOffset)' "$test_file"
grep -Fq 'assertThat(baselineOffsets).hasSize(3)' "$test_file"
grep -Fq 'isGreaterThanOrEqualTo(baselineOffsets.get' "$test_file"
grep -Fq 'new ExpectedSignal(2101L, 1L, "INSERT", true)' "$test_file"
grep -Fq 'new ExpectedSignal(2101L, 2L, "UPDATE", true)' "$test_file"
grep -Fq 'new ExpectedSignal(2101L, 3L, "UPDATE", true)' "$test_file"
grep -Fq 'new ExpectedSignal(2102L, 1L, "INSERT", true)' "$test_file"
grep -Fq 'new ExpectedSignal(2103L, 1L, "INSERT", true)' "$test_file"
