# MySQL Senior Scenarios Scope Reset Design

## Decision

Return this track to its original purpose: a senior-engineer-level MySQL tutorial that is easy to read, explain in an interview, and reproduce locally without polluting macOS.

This design supersedes the proposed eighth-runtime heartbeat/evidence work. There will be no new liveness pipe, durable-evidence protocol, one-shot runtime, manifest chain, calibration matrix, or independent production-style verifier.

## Reader-facing deliverable

Keep the four senior scenarios as the learning spine:

1. derive schema and indexes from access patterns;
2. import ten million rows through a scaled local reproduction;
3. archive/delete data and explain space reclamation;
4. export a report without unnecessarily harming OLTP traffic.

Each scenario must lead with the engineering decision, then explain mechanism, failure modes, measurement boundaries, and the interview answer. Existing verified facts remain; unverified performance claims must not be introduced.

## Simplified report/export lab

Replace the reader-facing audit platform with one retryable Docker-only demonstration:

- default to exactly 10,000 orders and 30,000 items so the demonstration finishes quickly on the user's machine;
- run buffered export once and chunked export once;
- compare row count, deterministic ordering, and output SHA-256;
- run a small OLTP probe concurrently and show whether its counter continues advancing;
- report elapsed time and bounded observations without claiming production capacity;
- allow reruns and cleanup through simple commands;
- keep MySQL, Python, generated data, and artifacts inside Docker resources.

The lab is educational evidence, not a benchmark certification system. It does not need one-shot semantics, seven immutable phases, historical-loss accounting, append-only manifests, calibration reconstruction, or a separate read-only verifier.

## macOS boundary

The host may execute Git and Docker CLI only. The lab must not install or invoke host Python, `uv`, `pip`, or MySQL; it must not create host runtime/artifact directories or writable bind mounts. Repository source may be copied into containers with `docker cp`. Generated evidence stays in a named Docker volume or disposable container layer.

## Existing seventh-run failure

The failed seventh runtime is diagnostic history, not reader-facing performance evidence. It stopped during `control-1` because the durable metrics publication did not advance before the heartbeat deadline. Do not retry it, promote it to `VERIFIED`, or use it to update scenario performance claims.

The existing `evidence-v1` volume remains untouched until the user separately authorizes cleanup. The credential-containing failed harness layer is likewise not deleted as part of this documentation/implementation reset; cleanup is an explicit operational choice.

## Repository change boundary

Implementation will:

- simplify or replace the reader-facing files under `mysql-handson/00-lab/senior-scenarios/`;
- update only the report/export scenario and routing text needed to describe the simple lab;
- preserve the other three senior scenarios and their established evidence;
- remove reader-facing references to the abandoned eighth-runtime design;
- keep report/export status truthful until the simple lab actually passes.

Historical commits and ignored diagnostic reports are not rewritten. No Docker cleanup, merge, push, branch deletion, or worktree deletion is part of implementation.

## Verification

Before delivery:

- run all lab tests inside a networkless container;
- execute the simple 10,000-order/30,000-item lab inside scoped Docker resources;
- confirm deterministic buffered/chunked equality and OLTP counter progression;
- run Markdown link and diff checks;
- verify the worktree is clean and only intended paths changed.

If the simple live demonstration fails, diagnose the direct cause and keep the documentation status honest. Do not rebuild the audit platform.

## Success criteria

The work is complete when a reader can:

1. navigate the four scenarios in a coherent order;
2. explain the engineering trade-offs at senior interview depth;
3. run the report/export demonstration with a small set of Docker-only commands;
4. distinguish local demonstration results from production sizing claims;
5. finish without host-language/database installation or macOS artifact pollution.
