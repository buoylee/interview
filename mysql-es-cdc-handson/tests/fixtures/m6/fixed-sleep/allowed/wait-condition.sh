#!/usr/bin/env bash
deadline_epoch=100
attempt=0
poll_seconds=1
while (( attempt < deadline_epoch )); do
  attempt=$((attempt + 1))
  sleep "$poll_seconds"
done
