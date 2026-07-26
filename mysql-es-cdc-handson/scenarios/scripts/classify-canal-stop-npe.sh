#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 CANAL_STOP_LOG" >&2
  exit 2
fi

jq -Rs '
  split("\n") as $lines
  | [
      range(0; $lines | length) as $index
      | select($lines[$index] | contains("NullPointerException"))
      | {
          known: (
            $index > 0
            and ($index + 2) < ($lines | length)
            and
            $lines[$index] == "java.lang.NullPointerException: null"
            and (($lines[$index - 1] // "") | contains("ServerRunningMonitor - processActiveExit failed"))
            and (($lines[$index + 1] // "") | contains("CanalMQStarter$CanalMQRunnable.stop(CanalMQStarter.java:245)"))
            and (($lines[$index + 2] // "") | contains("CanalMQStarter.stopDestination(CanalMQStarter.java:128)"))
          ),
          excerpt: ($lines[([$index - 1, 0] | max):($index + 8)] | join("\n"))
        }
    ] as $npe
  | {
      known_stop_npe: {
        present: ([$npe[] | select(.known)] | length > 0),
        count: ([$npe[] | select(.known)] | length),
        excerpts: [$npe[] | select(.known) | .excerpt],
        scope: "Canal 1.1.8 static-destination future-null CanalMQRunnable.stop observation only; not a success condition and not a shutdown-safety guarantee."
      },
      unexpected_npe: {
        present: ([$npe[] | select(.known | not)] | length > 0),
        count: ([$npe[] | select(.known | not)] | length),
        excerpts: [$npe[] | select(.known | not) | .excerpt]
      }
    }
' "$1"
