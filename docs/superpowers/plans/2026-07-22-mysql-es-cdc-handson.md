# MySQL ES CDC Hands-on Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible practical project that proves what Canal contributes to MySQL-to-Elasticsearch synchronization, which failure classes it does not close, and which end-to-end capabilities are required for defensible current-state eventual consistency.

**Architecture:** MySQL is the only fact source. Product transactions emit per-product monotonic revision rows in the same database transaction. Canal captures those committed rows and routes them to Kafka by product_id partitionHash with a null Kafka record key. A custom at-least-once consumer rehydrates current MySQL state, projects deterministic active documents or tombstones, and writes Elasticsearch with strict external versions. Durable product and record DLQs fence offset acknowledgment. An implementation-independent verifier detects and repairs bounded drift. A generation rebuild uses a consistent MySQL snapshot, overlapping Kafka replay, a short write gate, partition barriers, independent verification, and one atomic alias request. Confirmed log gaps enter REBUILD_REQUIRED; a purged MySQL binlog position additionally requires an evidenced Canal cursor rebootstrap before rebuild.

**Tech Stack:** Java 21, Maven Wrapper 3.9.11, Spring Boot 4.1.0, MySQL 8.4.8, Canal 1.1.8, Kafka 4.1.2, Elasticsearch 8.17.0, Toxiproxy 2.12.0, Docker Compose v2, Bash 3.2-compatible scripts, curl, jq, JUnit 5, AssertJ.

## Design Authority

The approved system contract is [2026-07-22-mysql-es-cdc-handson-design.md](../specs/2026-07-22-mysql-es-cdc-handson-design.md).

If implementation evidence contradicts the design, stop at the current milestone, record the compatibility result, amend the design and affected plans, and only then continue. Do not silently change pinned versions or weaken a completion gate.

## Global Constraints

- Work only in branch codex/mysql-es-cdc-handson and its isolated worktree.
- Create the practical project under mysql-es-cdc-handson/ at repository root.
- Run build, Compose, scenario, and Git commands from mysql-es-cdc-handson/. File maps in the detailed plans are repository-worktree-relative.
- Complete milestones in order. A later plan may not compensate for an unproven earlier completion gate.
- MySQL remains the fact source; Elasticsearch remains a disposable current-state projection.
- No application dual write and no exactly-once claim.
- Every index generation stores the latest-revision searchable=false tombstone for every inactive product. Physical tombstone compaction is a future extension, not a v1 mode.
- Canal 1.1.8 Kafka ProducerRecord uses a null record key. product_id is the partitionHash routing input, not the record key. The implementation must prove this against the live pinned stack. Official evidence: [CanalKafkaProducer.java](https://github.com/alibaba/canal/blob/canal-1.1.8/connector/kafka-connector/src/main/java/com/alibaba/otter/canal/connector/kafka/producer/CanalKafkaProducer.java#L200-L260) and [partitionHash documentation](https://github.com/alibaba/canal/wiki/Canal-Kafka-RocketMQ-QuickStart#canalmqpartitionhash-%E8%A1%A8%E8%BE%BE%E5%BC%8F%E8%AF%B4%E6%98%8E).
- A Kafka offset advances only after every represented product is APPLIED, STALE because of version_conflict_engine_exception, or durably stored in the correct DLQ.
- Invalid raw records that cannot yield product_id use the record DLQ keyed by topic:partition:offset; they must not be forced into the product DLQ schema.
- Every Elasticsearch Bulk item is classified. Top-level HTTP success is insufficient, and a non-version-conflict 409 is not STALE.
- Reconciliation owns an independent query, expected model, projector, canonicalizer, tests, and target reader.
- A confirmed MySQL or Kafka log gap cannot be repaired by bounded document repair or offset skipping.
- A MySQL binlog gap is not closed by rebuilding Elasticsearch alone. With the write gate closed, reset mode must first publish and ACK one reset-time recovery anchor in each partition so ACK-derived `meta.dat` can advance. A reset=false restart must preserve that exact cursor and offset vector, then a distinct normal-mode sentinel in each partition must prove exactly-next-event before rebuild can restore HEALTHY.
- Canal 1.1.8 uses release-native `file-instance.xml`: `FailbackLogPositionManager` falls back from memory to `MetaLogPositionManager`, which reads the acknowledged MQ client cursor persisted by `FileMixedMetaManager` as destination-scoped `meta.dat`. The unwired `FileMixedLogPositionManager`/`parse.dat` path is not enabled because its MQ ACK/restart boundary has not been proven.
- Canal 1.1.8 static-destination stop can throw at `CanalMQRunnable.future.cancel(true)` because `start(destinations)` did not set that future. One observed restart preserved the ACK cursor and offsets, but no general shutdown-safety claim follows; every restart gate must prove persisted cursor identity, unchanged Kafka end offsets, exact resume, and one next event.
- All scenario waits are condition based and bounded. Fixed sleep is never a success criterion.
- Stage and commit only files belonging to the current task. Preserve unrelated repository changes.

## Locked Runtime Topology

| Component | Name or endpoint | Contract |
|---|---|---|
| product-service | localhost:8081 | MySQL-only business mutation API |
| search-sync-consumer | localhost:8082 | Kafka consumer, DLQ and rebuild controls |
| consistency-verifier | localhost:8083 | reconciliation, pipeline state and rebuild coordinator |
| Canal Adapter baseline | localhost:8084 | M1-only black-box experiment |
| MySQL | localhost:3308 | container port 3306, database product_catalog |
| Kafka | localhost:29092 | internal broker kafka:9092 |
| Elasticsearch | localhost:9200 | security disabled only for the local lab |
| Toxiproxy API | localhost:8474 | named dependency faults |
| Canal | localhost:11111/11112 | server and metrics |

## Locked Data and Messaging Names

| Kind | Name | Rule |
|---|---|---|
| Kafka topic | product-search-revisions | exactly 3 partitions |
| Primary group | product-search-sync-v1 | manual immediate ACK |
| Canal destination | products | Kafka-mode primary path |
| Adapter destination | products_adapter | TCP-mode M1 path |
| M1 index | products_adapter_v1 | never receives custom-consumer writes |
| M2 initial index | products_v2 | initial strict-version generation |
| Rebuild index | products_v3_YYYYMMDDhhmmss_hash | explicit physical shadow target |
| Write alias | products_write | unfiltered, one write index |
| Search alias | products_search | exact term filter searchable=true |
| Cursor volume | canal-data | /home/admin/canal-data/products/meta.dat (acknowledged MQ client cursor used for parser resume) |

## Locked Migration Order

| Order | Path | Owner |
|---:|---|---|
| 00 | infra/mysql/init/00-users.sql | M0 users and grants |
| 01 | infra/mysql/init/01-schema.sql | M0 facts and revision schema |
| 02 | infra/mysql/init/02-seed.sql | M0 deterministic seed |
| 03 | infra/mysql/init/03-pipeline-control.sql | M2 product and record DLQs |
| 04 | infra/mysql/init/04-reconciliation-control.sql | M4 watermark, verification, repair and conditions |
| 05 | infra/mysql/init/05-rebuild-control.sql | M5 gate, barriers, generations, offsets and cursor recovery |

Fresh MySQL volumes apply these files lexically. Existing volumes use the milestone apply scripts in the same order.

## Locked Java Package Boundaries

~~~text
com.interview.mysqlescdc.product.api
com.interview.mysqlescdc.product.application

com.interview.mysqlescdc.consumer.canal
com.interview.mysqlescdc.consumer.source
com.interview.mysqlescdc.consumer.projection
com.interview.mysqlescdc.consumer.sink
com.interview.mysqlescdc.consumer.dlq
com.interview.mysqlescdc.consumer.pipeline
com.interview.mysqlescdc.consumer.rebuild
com.interview.mysqlescdc.consumer.health
com.interview.mysqlescdc.consumer.metrics
com.interview.mysqlescdc.consumer.failpoint

com.interview.mysqlescdc.verifier.source
com.interview.mysqlescdc.verifier.projection
com.interview.mysqlescdc.verifier.target
com.interview.mysqlescdc.verifier.reconciliation
com.interview.mysqlescdc.verifier.repair
com.interview.mysqlescdc.verifier.state
com.interview.mysqlescdc.verifier.rebuild
com.interview.mysqlescdc.verifier.lab
~~~

consistency-verifier may not import com.interview.mysqlescdc.consumer. Shared truth exists only in documented external contracts, not shared projector code.

## Milestone Execution Order

- [ ] **M0 — Foundation and capture contract:** Execute [M0 Foundation](2026-07-22-mysql-es-cdc-handson-m0-foundation.md). Produce the Maven project, transaction-safe revision source, pinned dependency stack, persistent Canal cursor volume, live null-key/partition prerequisites, and M0 evidence.
- [ ] **M1 — Official Adapter boundary:** Execute [M1 Adapter](2026-07-22-mysql-es-cdc-handson-m1-adapter.md). Build only from the official Adapter 1.1.8 archive with locked SHA-256 and record black-box ACK, retry, restart, delete, mapping and partial-Bulk observations.
- [ ] **M2-M3 — Reliable custom consumer:** Execute [M2-M3 Reliable Consumer](2026-07-22-mysql-es-cdc-handson-m2-m3-reliable-consumer.md). M2 and M3 stay combined because parser, rehydration, strict external versions, two DLQ levels, offset settlement, failpoints and replay form one reviewable correctness boundary.
- [ ] **M4 — Independent reconciliation:** Execute [M4 Reconciliation](2026-07-22-mysql-es-cdc-handson-m4-reconciliation.md). Prove exact equality under a stable global source watermark, detect an intentionally consumer-only defect, and repair only bounded drift.
- [ ] **M5 — Full rebuild and cutover:** Execute [M5 Rebuild](2026-07-22-mysql-es-cdc-handson-m5-rebuild.md). Prove one-snapshot scan, overlap replay, tombstone completeness, barrier vector, filtered atomic alias switch, crash recovery, Kafka-gap rebuild and MySQL-gap cursor rebootstrap.
- [ ] **M6 — Fault matrix and evidence:** Execute [M6 Fault Evidence](2026-07-22-mysql-es-cdc-handson-m6-fault-evidence.md). Run all 18 distinct cases twice from reset and publish only bundles that satisfy the machine-checkable PASS contract.

## Cross-Milestone Interface Contract

### Source revision

- product_search_revision has one row per product.
- Every successful mutation updates facts and revision in one MySQL transaction.
- revision strictly increases for create, price, inventory, category fan-out and delete.
- Delete sets active=false and retains the latest revision.

### Projection

- The consumer treats a Canal row as a signal, then reloads the full current aggregate with one MySQL statement.
- Active documents include every managed field, searchable=true and source_revision.
- Inactive documents include only the tombstone contract, searchable=false and source_revision.
- Strict version_type=external fences normal CDC. Controlled M4 same-revision repair alone may use external_gte after a stable independent source check.

### Settlement

- APPLIED and version_conflict_engine_exception STALE are settled.
- Retryable transport, 408, 429 and 5xx failures hold the offset.
- Deterministic item failures enter sync_dlq_record before ACK.
- Unparseable raw records enter sync_record_dlq before ACK.
- Any pending row in either DLQ means DEGRADED.

### Verification

- PASS requires a stable source watermark, full unfiltered target scan, exact managed-field equality, source_revision equality, Elasticsearch _version equality, latest tombstones and zero extras.
- MISSING, EXTRA, MODIFIED, STALE, FUTURE_REVISION, TOMBSTONE_MISMATCH and VERSION_METADATA_MISMATCH remain distinct evidence classes.

### Rebuild

- O_start is captured before opening the consistent MySQL snapshot.
- Shadow replay begins from the per-partition O_start vector and rejects expired offsets.
- Cutover closes the write gate, emits and observes one marker per partition, waits for primary and shadow positions, pauses primary, independently verifies, then moves both aliases in one request.
- products_search must retain the exact searchable=true filter after cutover.
- Every generation retains tombstones; no compacted generation exists.
- For a purged Canal source position, cursor recovery is linked to the rebuild run and separately records reset-time anchor offsets/events, the ACK-derived cursor hash/position, normal-restart cursor/offset identity, and per-partition normal-mode sentinel offsets/events.

## Coverage Matrix

| Design area | Implemented by | Primary gate |
|---|---|---|
| terminology and Canal boundary | M0, M1, M6 | observed Adapter and Kafka evidence |
| source transaction and revision invariant | M0 | rollback and fan-out integration tests |
| Canal-to-Kafka routing contract | M0, M2 | live null key and same-product partition test |
| deterministic current-state projection | M2 | parser, source and projector tests |
| strict versioning and per-item Bulk settlement | M2-M3 | real ES and crash-window scenarios |
| product and raw-record DLQ | M2-M3 | durable-before-ACK and replay tests |
| independent exact reconciliation | M4 | consumer-only defect plus direct drift matrix |
| bounded repair and truthful pipeline state | M4 | second stable-source check and fresh PASS |
| snapshot plus overlap rebuild | M5 | concurrent-write generation test |
| barrier and atomic alias cutover | M5 | both crash sides and alias-filter assertion |
| Kafka and MySQL log-gap recovery | M5-M6 | REBUILD_REQUIRED, cursor evidence and rebuild |
| all declared failure classes | M6 | exact 18-row catalog and two clean runs |
| user-facing final answer | M6 README | every claim links to scenario evidence |

## Execution and Commit Contract

Each detailed task follows red-green-refactor:

1. Add the smallest failing contract or test.
2. Run it and capture the expected failure.
3. Implement only the named behavior.
4. Run focused tests, then the milestone gate.
5. Run git diff --check and inspect git status.
6. Commit only the task's files with the message specified in the detailed plan.

Do not start a later milestone with a dirty worktree, a skipped compatibility gate, unresolved DLQ, or weakened scenario assertion.

## Final Completion Gate

The project is complete only when:

- all six detailed plans have every checkbox completed;
- M0-M6 gates pass twice from reset where required;
- the exact 18 M6 scenarios publish valid PASS evidence;
- unresolved product and record DLQ counts are zero;
- the independent verifier reports a conclusive exact zero-diff PASS;
- every inactive product has a latest-revision tombstone in the serving generation;
- no confirmed gap was repaired by skipping offsets or deleting evidence;
- a MySQL binlog gap includes linked reset-time anchor ACK evidence, preserved normal-mode Canal cursor/offset identity, and exactly-next-event sentinel evidence for all three partitions;
- README answers both original questions with capability boundaries, required additions, preconditions and scenario links;
- the isolated worktree is clean.

## Execution Handoff

Planning does not authorize implementation yet. After this plan is reviewed, select one execution mode:

1. Subagent-Driven: use superpowers:subagent-driven-development, one fresh worker per task with review checkpoints.
2. Inline Execution: use superpowers:executing-plans and execute sequential batches in the current thread.
