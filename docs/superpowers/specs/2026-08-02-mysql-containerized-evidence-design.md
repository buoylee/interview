# MySQL Senior Scenario Containerized Evidence Design

**Date:** 2026-08-02

**Status:** APPROVED_DRAFT

## 1. Goal

Run the report/export senior-scenario experiment directly and reproducibly
without installing Python dependencies on macOS, running host Python workload,
or storing experiment runtimes and raw evidence in host `/private/tmp` or the
repository.

Docker still consumes bounded macOS CPU, memory, and disk through its normal
virtualization layer. The isolation guarantee concerns processes, dependencies,
ports used by the harness, runtime files, and evidence ownership; it is not a
claim of zero host resource usage.

## 2. Problem and current state

The original harness placed only MySQL in Docker. Python runner/controller
processes executed on macOS, connected through `127.0.0.1:33306`, and stored
metrics, CSV artifacts, stdout/stderr, manifests, and controller results under
host `/private/tmp/mysql-senior-scenarios.*`.

All six historical host runtimes were later removed by external temporary-file
cleanup. Before the next live experiment began, the ownership gate observed:

- no historical runtime remained under host `/private/tmp`;
- the dedicated `mysql-senior-scenarios-mysql` container was `Exited(255)`;
- `mysql-primary` remained exited and untouched;
- no seventh runtime or measured invocation had been created;
- feature documentation and Git index remained clean.

The authoritative-window runner/controller changes had already passed
canonical and feature static review. This design changes only execution and
evidence lifecycle; it does not redesign their window-history behavior.

## 3. Minimal container architecture

```text
macOS
└─ Docker
   ├─ mysql-senior-scenarios-net
   │  ├─ mysql-senior-scenarios-mysql
   │  └─ mysql-senior-scenarios-harness
   ├─ mysql-senior-scenarios-data
   └─ mysql-senior-scenarios-evidence-v1
```

### 3.1 MySQL container

`mysql-senior-scenarios-mysql` remains the only database server in scope. It
must have the exact experiment scope label, use MySQL `8.0.36`, use only the
dedicated data volume, and join the dedicated network.

The harness connects through Docker DNS:

```text
host=mysql-senior-scenarios-mysql
port=3306
```

It does not use the host-published `127.0.0.1:33306` path. An existing port
mapping may remain as container metadata, but no measured or verification
command uses it.

### 3.2 Harness container

One temporary container named `mysql-senior-scenarios-harness` runs the whole
experiment. It uses `python:3.13-slim`, installs exactly
`mysql-connector-python==9.7.0` inside the container, and is removed after final
review. No Python package is installed on macOS.

The committed scenario Markdown is copied into the container with `docker cp`.
It is not bind-mounted. A fixed reviewed extraction command runs inside the
container and materializes runner/controller/freeze helper under the evidence
volume. Program hashes must equal the committed scenario fences before any
database or measured work.

The harness is the sole owner of runner/controller processes, stdout/stderr,
CSV files, abort signals, manifests, and audit helpers. Host process management
is not part of the experiment.

### 3.3 Dedicated network

The harness and MySQL join only
`mysql-senior-scenarios-net`, labeled for this experiment. Container-to-
container traffic uses the MySQL container name. `mysql-primary` is never
connected to this network, started, or modified.

### 3.4 Evidence named volume

The named volume `mysql-senior-scenarios-evidence-v1` is mounted at
`/private/tmp` inside the harness. Existing runner/controller runtime-path
validation therefore remains unchanged, while `/private/tmp` refers to Docker
volume storage rather than macOS temporary storage.

The volume contains:

```text
/private/tmp/
  historical-evidence-loss.json
  mysql-senior-scenarios.<seventh-suffix>/
    export_runner.py
    scenario_controller.py
    metrics-*.json
    controller-result-*.json
    stdout/stderr evidence
    CSV artifacts and job directories
    phase-manifest-*.json
    evidence-sha256.txt
```

Removing or recreating the harness container does not remove the volume. The
volume is not bind-mounted to a macOS directory and is retained after merge
until the user explicitly requests its deletion.

## 4. Host pollution boundary

Allowed macOS-side effects are limited to:

- normal Git documentation edits;
- Docker images, containers, network, and named volumes with exact experiment
  names and labels;
- `docker cp` reading the one committed scenario file;
- Docker management commands and bounded Docker resource usage.

The experiment must not:

- invoke host Python, `uv`, `pip`, or MySQL clients for live work;
- create a host `/private/tmp/mysql-senior-scenarios.*` runtime;
- store raw evidence under the repository or another host directory;
- bind-mount a writable host path;
- install a macOS package or change a shell profile;
- start or mutate `mysql-primary`;
- operate on unlabeled Docker resources.

Read-only Git commands may independently verify the committed scenario and
documented hashes. Raw-evidence verification runs in containers.

## 5. Resource limits

The experiment is scaled evidence, not a capacity benchmark. Both containers
have explicit limits so the run cannot consume unbounded macOS resources:

```text
MySQL:   2 CPUs, 2 GiB memory, 256 PIDs
Harness: 2 CPUs, 2 GiB memory, 256 PIDs
```

Before live work, the operator applies and verifies these limits on the
dedicated MySQL container and creates the harness with the same bounded class.
OOM, PID exhaustion, or resource-limit termination is a failed experiment and
is never hidden by retrying with larger limits.

All reported performance numbers are scoped to a two-container client/server
experiment on macOS Docker virtualization with these limits. They are not
native-host or production MySQL capacity claims.

## 6. Container recovery and creation

The operator first verifies resource ownership by exact names and labels.

1. Create the dedicated network and evidence volume only when absent.
2. Apply exact experiment labels at creation.
3. Attempt to start the existing owned MySQL container once.
4. Revalidate image/version, data volume, network, limits, restart policy, and
   health.

If the existing container cannot start or its identity is contradictory, the
operator stops before live work. It does not silently delete and replace the
container. A replacement requires a separate explicit user decision.

After successful recovery, old database contents are not trusted. The live
experiment performs the complete drop/recreate/reseed contract.

## 7. Harness bootstrap

The harness bootstrap is deterministic and occurs before a measured runtime is
created:

1. Start one bounded `python:3.13-slim` container on the dedicated network with
   the evidence volume mounted at `/private/tmp`.
2. Install Connector/Python `9.7.0` once inside that container.
3. Record Python, platform, connector, container-image, network, mount, and
   cgroup-limit evidence in the named volume.
4. Copy the committed scenario Markdown into a non-volume container path.
5. Extract runner/controller/freeze-helper fences inside the container.
6. Compare their SHA-256 with hashes independently derived from the committed
   Git object.
7. Compile all extracted Python programs inside the container.

Any version, extraction, hash, compile, mount, DNS, resource-limit, or
connector discrepancy stops before seed or measured invocation. The harness is
not recreated to obtain a different result.

Package download occurs during bootstrap, before measurement. No dependency
installation or external network request occurs during measured phases.

## 8. Historical evidence loss

Inside the evidence volume, bootstrap creates one immutable
`historical-evidence-loss.json`. It lists all six former host runtime paths and
uses:

```text
status=LOST_BY_EXTERNAL_TMP_CLEANUP
current_raw_verification=false
```

Previously reported hashes may be included only as
`historical_report_claim`. The document states that raw files, pre/post tree
comparison, and current manifest verification are unavailable. Historical
controls, calibration values, and budgets cannot become inputs to the new run.

The new experiment remains numbered seventh because six experiments
historically occurred. It becomes the first run whose full raw evidence is
retained in a Docker named volume.

## 9. Append-only phase manifests

Full runtime duplication is unnecessary because the named volume already
persists independently of the harness. Instead, after each phase the harness
writes one atomic append-only manifest:

```text
00-seed-freeze
10-kill-smoke
20-controls-calibration
30-buffered
40-chunked
50-resume-audit
60-final
```

Each manifest records the ordered set of all regular files completed by that
phase, relative paths, sizes, SHA-256, program/container binding, phase status,
timestamp, file count, byte count, and tree hash. The manifest excludes itself.

Before a later phase starts, the verifier recomputes every file named by all
earlier manifests. Later phases may add new files but may not remove or change
previously recorded files. Existing manifest paths, phase reordering, symlinks,
special files, missing files, changed hashes, type-coercing JSON values, or
binding drift fail closed.

No manifest is rewritten. The final manifest covers every regular file except
itself and revalidates every earlier phase.

## 10. Live experiment flow

After bootstrap and ownership gates pass:

1. Create exactly one fresh runtime inside the evidence volume.
2. Drop/recreate/reseed 100,000 orders, 300,000 items, and 10,000 probes.
3. Freeze source, install six triggers, and run six negative probes once.
4. Write and verify `00-seed-freeze`.
5. Run KILL preflight and pure-client smoke once; write `10-kill-smoke`.
6. Run three controls and one calibration once; write
   `20-controls-calibration`.
7. Run buffered trials once; write `30-buffered`.
8. Run chunked trials once; write `40-chunked`.
9. Run interruption/resume and correctness audit once; write
   `50-resume-audit`.
10. Remove triggers, verify source/probes/processes/globals/container identity,
    and write `60-final`.

The already-reviewed authoritative-window, rolling calibration, source,
connector, worker, KILL, drain, heartbeat, disk, artifact, resume, and no-retry
contracts remain unchanged except for container DNS host/port and container-
internal evidence paths.

Any measured failure stops dependent work. The harness performs controlled
teardown, writes a manifest for the completed evidence when possible, and does
not retry the invocation or create a replacement harness/runtime.

## 11. Verification container

Final raw-evidence review uses a separate temporary verifier container with:

- the evidence volume mounted read-only;
- no MySQL data volume;
- no writable host mount;
- the same bounded CPU, memory, and PID limits;
- the committed verifier/extraction logic;
- no ability to modify MySQL or raw evidence.

It recomputes every phase manifest, final tree hash, authoritative histories,
calibration inputs/derivatives, artifact rows/order/SHA, source/probe audits,
and container/program binding. Its stdout report is captured through Docker
management output and summarized in committed documentation; it does not write
back into the read-only volume.

## 12. Offline verification

Before live work, containerized tests cover:

- evidence volume mounted at container `/private/tmp` and absent from host
  `/private/tmp`;
- runtime-prefix validation inside the volume;
- scenario extraction and program hash equality;
- exact Python/Connector versions and pure-client identity;
- Docker DNS resolution to the owned MySQL container;
- exact cgroup CPU/memory/PID limits;
- historical-loss truthfulness;
- phase manifest creation, immutability, ordering, prefix verification, and
  final coverage;
- missing, extra, corrupt, symlink, special-file, and type-alias rejection;
- verifier success on a read-only miniature evidence volume;
- unchanged authoritative-window runner/controller/freeze-helper hashes.

No live test command runs through host Python. Docker CLI inspection is the
host-side orchestration boundary.

## 13. Documentation and cleanup

Successful documentation records:

- exact container images, limits, network, volume names, and program hashes;
- the seventh runtime and every phase manifest;
- full authoritative-window/calibration/export/resume/source/teardown evidence;
- the loss of first-through-sixth raw host runtimes as a limitation;
- containerized-client safety and interference conclusions;
- the boundary that scaled Docker results are not production SLO or capacity.

The scenario becomes `SCALED_REPRODUCED (S=100000)` only when the measured
completion contract, every phase manifest, and read-only verifier pass. An
incomplete run produces no partial performance conclusion or success label.

After final branch review, the temporary harness, verifier, and dedicated
network may be removed. Owned MySQL container/data cleanup follows the
separately approved branch workflow. The named evidence volume is retained
after merge and deleted only after an explicit user request naming it.

## 14. Non-goals

- No host Python, MySQL client, package installation, or host experiment
  runtime.
- No writable bind mount and no repo-local raw evidence archive.
- No APFS clone, `cp -cR`, `clonefile(2)`, hard-link, or `rsync` snapshot
  system.
- No recreation or present-tense verification of six lost raw runtimes.
- No change to authoritative-window semantics beyond Docker DNS/path binding.
- No automatic replacement of an invalid MySQL container.
- No retry with larger resource limits.
- No automatic deletion of the evidence named volume.
