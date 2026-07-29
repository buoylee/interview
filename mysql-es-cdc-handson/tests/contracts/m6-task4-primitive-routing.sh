#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
runtime=scenarios/scripts/m6-case-runtime.sh

if rg -n 'kafka-console-producer[.]sh' \
  scenarios/scripts/m6-case-runtime.sh \
  scenarios/scripts/lib-m3-crash.sh \
  scenarios/scripts/inject-scenario-event.sh; then
  echo 'M6 replay dependency closure bypasses the locked injection primitive' >&2
  exit 1
fi

section() { sed -n "/^case_$1()/,/^case_$2()/p" "$runtime"; }

case3="$(section 3 4)"
grep -Fq 'fault-retention.sh apply mysql' <<<"$case3"
grep -Fq 'MYSQL_PWD=rootpass MYSQL_USER=root' <<<"$case3"
! grep -Eq "mysql_root ['\"](FLUSH|PURGE) BINARY LOGS" <<<"$case3"

for pair in '6 7' '7 8'; do
  set -- $pair
  crash_case="$(section "$1" "$2")"
  grep -Fq 'fault-process.sh apply' <<<"$crash_case"
  grep -Fq 'process-fault.json' <<<"$crash_case"
  ! grep -Fq 'arm_failpoint ' <<<"$crash_case"
done

! grep -Fq 'produce_with_key' "$runtime"

for pair in '9 10' '10 11' '14 15'; do
  set -- $pair
  replay_case="$(section "$1" "$2")"
  grep -Fq 'inject_scenario_event ' <<<"$replay_case"
  grep -Fq 'injected-event.json' <<<"$replay_case"
  ! grep -Fq 'produce_with_key "$id" "$payload"' <<<"$replay_case"
done

grep -Fq 'capture-manifest.sh' scenarios/scripts/build-m6-real-bundle.sh
grep -Fq 'collect-m6-case-facts.sh' scenarios/scripts/build-m6-real-bundle.sh
grep -Fq '.data |= map({product_id,revision,active})' scenarios/scripts/inject-scenario-event.sh

if bash scenarios/scripts/inject-scenario-event.sh 3 '{}' >/dev/null 2>&1; then
  echo 'scenario event primitive accepted an invalid partition' >&2
  exit 1
fi
echo 'M6 Task4 primitive routing contract passed'
