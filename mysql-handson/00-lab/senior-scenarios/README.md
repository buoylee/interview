# Report/export container lab

## macOS side-effect boundary

Run the five commands below from macOS with `sh run-containerized.sh ...`.
Their only live-system boundary is the Docker CLI: no host Python, package installer, or MySQL client is used. `run` mutates the dedicated Docker resources and the owned MySQL schema; it starts the owned MySQL container at most once, never touches `mysql-primary`, and does not imply production capacity.

## Exact owned Docker resources

The scope label is `com.openai.codex.scope=mysql-senior-scenarios`. The owned names are `mysql-senior-scenarios-mysql`, `mysql-senior-scenarios-harness`, `mysql-senior-scenarios-verifier`, `mysql-senior-scenarios-offline-test`, `mysql-senior-scenarios-net`, `mysql-senior-scenarios-data`, and `mysql-senior-scenarios-evidence-v1`.

## Read-only inspection

```sh
sh mysql-handson/00-lab/senior-scenarios/run-containerized.sh inspect
```

This prints the owned MySQL container's state, image, labels, mounts, network, restart policy, health, and limits, plus read-only `mysql-primary` state.

## Offline test

```sh
sh mysql-handson/00-lab/senior-scenarios/run-containerized.sh offline-test
```

This creates a labeled disposable Python container, copies the scenario and tests into it, and runs the contract tests without a bind mount or MySQL connection.

## One-shot live run

```sh
sh mysql-handson/00-lab/senior-scenarios/run-containerized.sh run
```

Use this only after inspection. It fails closed on an unexpected label, image, data mount, limits, or `mysql-primary` state; its evidence and harness traffic stay on the dedicated Docker resources.

## Read-only verification

```sh
sh mysql-handson/00-lab/senior-scenarios/run-containerized.sh verify
```

The verifier mounts the evidence volume read-only and uses a disposable labeled container.

## Controlled stop

The script intentionally has no stop command. If an operator must stop the owned container, use Docker's exact container name after a fresh `inspect`; never use this lab to stop `mysql-primary`.

## Transient cleanup

```sh
sh mysql-handson/00-lab/senior-scenarios/run-containerized.sh cleanup-transient
```

This removes only exact-name, scope-labeled harness, verifier, and offline-test containers.

## Retained evidence volume

`mysql-senior-scenarios-evidence-v1` is retained for audit. Deleting it is deliberately absent from the script.
