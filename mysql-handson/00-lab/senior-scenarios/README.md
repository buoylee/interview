# Report/export container lab

Status: `READY_UNRUN`. This lab defines execution and verification only; it does not publish a completed evidence status or an S-scale result.

## Container lab entry from macOS

```bash
cd mysql-handson/00-lab/senior-scenarios
./run-containerized.sh inspect
./run-containerized.sh offline-test
./run-containerized.sh run
./run-containerized.sh verify
```

The macOS side-effect boundary is Docker CLI only: no host Python, package installer, MySQL client, host runtime directory, or host artifact path. `inspect` is read-only; `offline-test` is the existing network-none copy-based suite; `run` is one-shot with no retry path; and `verify` is read-only evidence verification. `run` mutates only dedicated Docker resources and the owned MySQL schema, starts the owned MySQL container at most once, never touches `mysql-primary`, and does not imply production capacity.

## Exact owned Docker resources

The scope label is `com.openai.codex.scope=mysql-senior-scenarios`. The owned names are `mysql-senior-scenarios-mysql`, `mysql-senior-scenarios-harness`, `mysql-senior-scenarios-verifier`, `mysql-senior-scenarios-offline-test`, `mysql-senior-scenarios-net`, `mysql-senior-scenarios-data`, and `mysql-senior-scenarios-evidence-v1`. Every harness/verifier/offline-test container is limited to `--cpus 2`, `--memory 2g`, and `--pids-limit 256`.

`/private/tmp` in harness/verifier arguments is the mount destination of named volume `mysql-senior-scenarios-evidence-v1` inside the container, never a macOS execution/artifact directory. The harness reaches the owned MySQL container through Docker DNS `mysql-senior-scenarios-mysql:3306` on `mysql-senior-scenarios-net`.

## Read-only inspection

This prints the owned MySQL container's state, image, labels, mounts, network, restart policy, health, and limits, plus read-only `mysql-primary` state.

## Offline test

This creates a labeled disposable Python container, copies the scenario and tests into it, and runs the contract tests without a bind mount or MySQL connection.

## One-shot live run

Use this only after inspection. It fails closed on an unexpected label, image, data mount, limits, or `mysql-primary` state; its evidence and harness traffic stay on the dedicated Docker resources.

## Read-only verification

The verifier mounts the evidence volume read-only, uses `--network none`, and fails if the retained named volume is absent or out of scope.

## Controlled stop

The script intentionally has no stop command. If an operator must stop the owned container, use Docker's exact container name after a fresh `inspect`; never use this lab to stop `mysql-primary`.

## Transient cleanup

`cleanup-transient` is intentionally outside the four-step lab entry. It removes only exact-name, scope-labeled harness, verifier, and offline-test containers.

## Retained evidence volume

`mysql-senior-scenarios-evidence-v1` is a retained evidence volume for append-only audit. Deleting it is deliberately absent from the script and never an operator instruction in this lab.
