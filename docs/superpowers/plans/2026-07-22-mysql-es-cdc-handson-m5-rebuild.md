# MySQL ES CDC Hands-on M5 Rebuild and Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Rebuild a complete Elasticsearch generation from current MySQL facts while writes continue during the scan, replay every overlapping CDC event, close a short and explicit cutover fence, independently verify the shadow generation, and atomically switch aliases without a data gap.

**Architecture:** The verifier coordinates a generation state machine. It captures Kafka end offsets `O_start` before opening one MySQL repeatable-read snapshot, scans every active product and inactive tombstone into a new physical index, and starts a consumer-owned shadow replayer at `O_start`. At cutover, a row-lock write gate drains in-flight business transactions, one MySQL transaction emits a marker into every Kafka partition, both the primary group and shadow replayer pass those marker offsets, the verifier proves exact equality against the shadow index, and one Elasticsearch aliases request moves both read and write aliases. The existing primary listener then resumes against the newly promoted generation.

**Tech Stack:** Java 21, Spring Boot 4.1.0, Spring JDBC, Spring Kafka 4.1.0, Kafka AdminClient and assign/seek consumer APIs, Spring RestClient, Jackson 3, MySQL 8.4.8, Kafka 4.1.2, Canal 1.1.8, Elasticsearch 8.17.0, JUnit 5, AssertJ.

## Global Constraints

- Execute only after the M4 completion gate passes.
- Work only in branch `codex/mysql-es-cdc-handson` and its isolated worktree.
- Capture `O_start` before `START TRANSACTION WITH CONSISTENT SNAPSHOT`; reversing that order creates an unprovable gap.
- Scan through one dedicated MySQL connection and one repeatable-read transaction. Pool-backed independent page queries are not a consistent snapshot.
- Scan every `product_search_revision` row, including inactive rows. Every generation retains latest-revision tombstones; no compaction or physical deletion is part of M5.
- Shadow replay starts at each partition's `O_start`, uses current MySQL rehydration, targets the explicit new physical index, and uses strict external versions.
- Kafka retention must cover the entire interval from `O_start` until cutover. If any required offset falls below a partition beginning offset, fail the run and start a new rebuild; never skip forward.
- A purged MySQL binlog position requires an explicit Canal cursor rebootstrap under the write gate before normal rebuild starts. Back up and hash the old cursor, record the old missing and new valid positions, use reset-time anchors to advance the ACK-derived cursor, then prove preserved normal-mode restart identity and distinct exactly-next-event sentinels in all three partitions. Never silently delete metadata.
- The business write gate is a MySQL row-lock fence. Closing it waits for in-flight mutation transactions and makes later mutations return HTTP 503 until reopened.
- A single Kafka marker is not a cross-partition barrier. Insert one `cdc_barrier` row per partition in one MySQL transaction and observe all three marker offsets.
- Canal records still have null Kafka keys. Barrier routing uses `partitionHash` over `partition_token`, not Kafka record keys.
- Do not derive `O_barrier` from a momentary topic end offset. Record the exact marker offset plus one for each partition.
- Alias cutover moves `products_search` and `products_write` in one `_aliases` request. No delete-then-add sequence is allowed.
- Verification must target the explicit shadow index while writes are gated and both replay paths are at the barrier.
- Before alias switch failure: keep old aliases, resume primary consumer, reopen writes, retain failed generation as evidence. After alias switch success: the new generation is authoritative even if cleanup fails.
- M5 guarantees no projection gap under its stated retention and source-health preconditions; it does not claim zero write pause.

## Locked Interfaces

~~~text
WriteGate.close(UUID runId, String reason) -> WriteGateLease
WriteGate.open(UUID runId) -> void
BarrierPublisher.publish(UUID runId, int partitions) -> Barrier
BarrierObserver.awaitAll(Barrier, Duration) -> Map<TopicPartition, Long markerNextOffsets>
KafkaOffsetSnapshotter.endOffsets(String topic) -> Map<TopicPartition, Long>
ConsistentSourceScanner.open() -> SourceSnapshotCursor
GenerationManager.create(UUID runId) -> IndexGeneration
GenerationManager.atomicCutover(IndexGeneration generation) -> AliasCutoverResult
ShadowReplayClient.start(ShadowReplayRequest) -> void
ShadowReplayClient.awaitOffsets(UUID runId, Map<TopicPartition,Long>, Duration) -> void
PrimaryConsumerControl.pause()/resume() -> PrimaryConsumerStatus
RebuildCoordinator.start(RebuildRequest) -> RebuildRun
~~~

---

### Task 1: Add a transaction-draining write gate and one marker per Kafka partition

**Files:**

- Create: `mysql-es-cdc-handson/infra/mysql/init/05-rebuild-control.sql`
- Modify: `mysql-es-cdc-handson/infra/mysql/apply-reconciliation-control.sh`
- Create: `mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/application/WriteGateClosedException.java`
- Create: `mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductWriteGate.java`
- Modify: `mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java`
- Create: `mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/api/ProductControllerAdvice.java`
- Create: `mysql-es-cdc-handson/product-service/src/test/java/com/interview/mysqlescdc/product/application/ProductWriteGateIT.java`
- Modify: `mysql-es-cdc-handson/infra/canal/instance.properties`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/WriteGate.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/JdbcWriteGate.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/Barrier.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/BarrierPublisher.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/JdbcBarrierPublisher.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/rebuild/BarrierRoutingIT.java`

**Interfaces:**

- Product mutations acquire a shared lock on the singleton gate row before reading or changing product facts.
- The coordinator closes or opens the gate with an exclusive lock.
- Tokens `"0"`, `"1"`, and `"2"` route to partitions 0, 1, and 2 under Canal's Java-string hash with database hashing disabled.

- [ ] **Step 1: Write concurrent gate tests first**

The integration test uses two independent JDBC connections and latches to prove:

1. an in-flight mutation holds `SELECT ... FOR SHARE` and the close transaction blocks;
2. after that mutation commits, close completes;
3. a mutation started after close receives `WriteGateClosedException` and changes neither facts, per-product revision, nor global watermark;
4. reopening with the owning run ID restores writes;
5. a different run ID cannot reopen another run's gate.

- [ ] **Step 2: Run the gate test and verify the red state**

~~~bash
./mvnw -pl product-service -Dtest=ProductWriteGateIT test
~~~

Expected: FAIL because the gate table and service do not exist.

- [ ] **Step 3: Create the exact rebuild schema**

Create `05-rebuild-control.sql`:

~~~sql
USE product_catalog;

CREATE TABLE IF NOT EXISTS product_write_gate (
  singleton_id TINYINT UNSIGNED NOT NULL,
  closed BOOLEAN NOT NULL DEFAULT FALSE,
  owner_run_id BINARY(16) NULL,
  reason VARCHAR(255) NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (singleton_id),
  CONSTRAINT chk_product_write_gate_singleton CHECK (singleton_id = 1)
) ENGINE=InnoDB;

INSERT INTO product_write_gate(singleton_id, closed)
VALUES (1, FALSE)
ON DUPLICATE KEY UPDATE singleton_id = singleton_id;

CREATE TABLE IF NOT EXISTS cdc_barrier (
  run_id BINARY(16) NOT NULL,
  partition_token CHAR(1) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (run_id, partition_token),
  CONSTRAINT chk_cdc_barrier_token CHECK (partition_token IN ('0','1','2'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rebuild_run (
  run_id BINARY(16) NOT NULL,
  generation_name VARCHAR(128) NOT NULL,
  status ENUM(
    'CREATED','CANAL_RECOVERY_REQUIRED','CANAL_RECOVERING',
    'SNAPSHOTTING','REPLAYING','GATING','VERIFYING',
    'CUTTING_OVER','CUTOVER_COMMITTED','COMPLETED','FAILED'
  ) NOT NULL,
  source_watermark BIGINT UNSIGNED NULL,
  source_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  verification_run_id BINARY(16) NULL,
  canal_recovery_id BINARY(16) NULL,
  alias_swapped BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at TIMESTAMP(6) NULL,
  failure_phase VARCHAR(64) NULL,
  failure_message VARCHAR(512) NULL,
  PRIMARY KEY (run_id),
  UNIQUE KEY uk_rebuild_generation (generation_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rebuild_partition_offset (
  run_id BINARY(16) NOT NULL,
  phase ENUM('START','SHADOW','BARRIER') NOT NULL,
  topic_name VARCHAR(128) NOT NULL,
  partition_id INT NOT NULL,
  next_offset BIGINT NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (run_id, phase, topic_name, partition_id),
  CONSTRAINT fk_rebuild_offset_run FOREIGN KEY (run_id) REFERENCES rebuild_run(run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS canal_position_recovery (
  recovery_id BINARY(16) NOT NULL,
  rebuild_run_id BINARY(16) NOT NULL,
  status ENUM(
    'STARTED','CURSOR_BACKED_UP','RESET_BOOTED',
    'RESET_ANCHORS_ACKED','NORMAL_RESTART_VERIFIED',
    'NORMAL_SENTINELS_OBSERVED','COMPLETED','FAILED'
  ) NOT NULL,
  cursor_path VARCHAR(255) NOT NULL,
  cursor_backup_path VARCHAR(255) NOT NULL,
  old_cursor_sha256 CHAR(64) NOT NULL,
  old_journal_name VARCHAR(255) NOT NULL,
  old_position BIGINT NOT NULL,
  reset_lower_bound_journal VARCHAR(255) NULL,
  reset_lower_bound_position BIGINT NULL,
  reset_cursor_sha256 CHAR(64) NULL,
  reset_journal_name VARCHAR(255) NULL,
  reset_position BIGINT NULL,
  reset_anchor_run_id BINARY(16) NULL,
  reset_anchor_offsets_json JSON NULL,
  reset_anchor_events_json JSON NULL,
  reset_restart_offsets_before_json JSON NULL,
  normal_restart_cursor_sha256 CHAR(64) NULL,
  normal_restart_journal_name VARCHAR(255) NULL,
  normal_restart_position BIGINT NULL,
  normal_restart_offsets_after_json JSON NULL,
  normal_sentinel_run_id BINARY(16) NULL,
  normal_sentinel_offsets_json JSON NULL,
  normal_sentinel_events_json JSON NULL,
  started_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at TIMESTAMP(6) NULL,
  failure_message VARCHAR(512) NULL,
  PRIMARY KEY (recovery_id),
  UNIQUE KEY uk_canal_recovery_run (rebuild_run_id),
  CONSTRAINT fk_canal_recovery_run
    FOREIGN KEY (rebuild_run_id) REFERENCES rebuild_run(run_id)
) ENGINE=InnoDB;
~~~

Add this migration to the fresh-volume init list and the existing-volume apply script after 03-pipeline-control.sql and 04-reconciliation-control.sql.

- [ ] **Step 4: Implement the shared-lock mutation check**

~~~java
@Component
public final class ProductWriteGate {
    private final JdbcClient jdbcClient;

    public ProductWriteGate(JdbcClient jdbcClient) {
        this.jdbcClient = jdbcClient;
    }

    public void assertOpenForMutation() {
        GateRow row = jdbcClient.sql("""
                SELECT closed, BIN_TO_UUID(owner_run_id) AS owner_run_id, reason
                FROM product_write_gate
                WHERE singleton_id = 1
                FOR SHARE
                """)
                .query(GateRow.class)
                .single();
        if (row.closed()) {
            throw new WriteGateClosedException(row.ownerRunId(), row.reason());
        }
    }
}
~~~

Call `assertOpenForMutation()` as the first statement inside every mutation transaction, before fact reads. Map `WriteGateClosedException` to HTTP 503 with body:

~~~json
{"code":"PRODUCT_WRITES_PAUSED","retryable":true}
~~~

- [ ] **Step 5: Implement exclusive close/open ownership**

`JdbcWriteGate.close` starts a transaction, locks the singleton `FOR UPDATE`, rejects an active different owner, updates `closed=TRUE`, owner and reason, then commits. Because close needs an exclusive row lock, it waits for all in-flight shared mutation locks.

`open` locks the row, requires the same owner run ID, sets `closed=FALSE`, and clears owner/reason. It is idempotent if already open and owner is null.

- [ ] **Step 6: Publish three barrier rows atomically**

~~~java
@Transactional
public Barrier publish(UUID runId, int partitions) {
    if (partitions != 3) {
        throw new IllegalArgumentException("v1 barrier contract requires exactly 3 partitions");
    }
    for (int partition = 0; partition < partitions; partition++) {
        String token = Integer.toString(partition);
        int routed = Math.floorMod(token.hashCode(), partitions);
        if (routed != partition) {
            throw new IllegalStateException("barrier token routing mismatch");
        }
        jdbcClient.sql("""
                INSERT INTO cdc_barrier(run_id, partition_token)
                VALUES (UUID_TO_BIN(:runId), :token)
                """)
                .param("runId", runId.toString())
                .param("token", token)
                .update();
    }
    return new Barrier(runId, Set.of("0", "1", "2"));
}
~~~

- [ ] **Step 7: Extend the Canal capture and routing contract**

Set:

~~~properties
canal.instance.filter.regex=product_catalog\.(product_search_revision|cdc_barrier)
canal.mq.partitionsNum=3
canal.mq.database.hash=false
canal.mq.partitionHash=product_catalog.product_search_revision:product_id,product_catalog.cdc_barrier:partition_token
~~~

`BarrierRoutingIT` publishes one barrier, consumes raw Kafka records with `isolation.level=read_committed`, parses `cdc_barrier`, and asserts the same run ID appears once in partitions 0, 1, and 2 with a null Kafka record key.

- [ ] **Step 8: Run and commit the gate/barrier contract**

~~~bash
./mvnw -pl product-service,consistency-verifier \
  -Dtest=ProductWriteGateIT,BarrierRoutingIT test
git add .
git commit -m "feat(cdc-lab): fence rebuild cutovers in MySQL and Kafka"
~~~

---

### Task 2: Create immutable physical generations and atomic alias cutover

**Files:**

- Create: `mysql-es-cdc-handson/infra/elasticsearch/products-v3-template.json`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/IndexGeneration.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/AliasState.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/AliasCutoverResult.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/GenerationManager.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RestGenerationManager.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/rebuild/RestGenerationManagerIT.java`

**Interfaces:**

- Generation name is `products_v3_{yyyyMMddHHmmss}_{first8-run-id}` and is stored before index creation.
- Mapping `_meta` includes `schema_version=3`, `deletion_mode=tombstone`, and the rebuild run ID.

- [ ] **Step 1: Write create, refuse-reuse, and atomic-cutover tests**

Tests must prove:

- create applies exact field mappings and `_meta`;
- a pre-existing generation name is rejected rather than reused;
- cutover moves both aliases in one request;
- `products_write` has `is_write_index=true` only on the new generation;
- an injected aliases-request failure leaves both aliases on the old generation;
- repeating cutover after success reports `alreadyApplied=true`.

- [ ] **Step 2: Create the exact mapping template**

`products-v3-template.json`:

~~~json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  },
  "mappings": {
    "dynamic": "strict",
    "_meta": {
      "schema_version": 3,
      "deletion_mode": "tombstone"
    },
    "properties": {
      "product_id": {"type": "long"},
      "sku": {"type": "keyword"},
      "name": {"type": "text"},
      "description": {"type": "text"},
      "category_id": {"type": "long"},
      "category_name": {"type": "keyword"},
      "price_cents": {"type": "long"},
      "available_quantity": {"type": "integer"},
      "searchable": {"type": "boolean"},
      "source_revision": {"type": "long"},
      "source_updated_at": {"type": "date"}
    }
  }
}
~~~

At create time, add `rebuild_run_id` and `created_at` to `_meta` in the request body; do not mutate the checked-in template.

- [ ] **Step 3: Implement exact alias-state inspection**

Read:

~~~http
GET /_alias/products_search,products_write
~~~

Reject cutover unless both aliases currently name exactly one same old index and `products_write` marks it as write index. This avoids silently normalizing an already-corrupt alias topology.

- [ ] **Step 4: Implement one-request cutover**

~~~json
{
  "actions": [
    {"remove": {"index": "products_v2", "alias": "products_search"}},
    {"remove": {"index": "products_v2", "alias": "products_write"}},
    {"add": {"index": "products_v3_20260722120000_ab12cd34", "alias": "products_search", "filter": {"term": {"searchable": true}}}},
    {"add": {"index": "products_v3_20260722120000_ab12cd34", "alias": "products_write", "is_write_index": true}}
  ]
}
~~~

Send the actions to `POST /_aliases`. After HTTP success, re-read aliases, assert `products_search` retains exactly the `term searchable=true` filter, and persist `alias_swapped=true` before any cleanup. RestGenerationManagerIT must fail if the filter is absent or broadened.

- [ ] **Step 5: Verify against real Elasticsearch and commit**

~~~bash
./mvnw -pl consistency-verifier -Dtest=RestGenerationManagerIT test
git add infra/elasticsearch consistency-verifier
git commit -m "feat(cdc-lab): manage atomic index generations"
~~~

---

### Task 3: Capture exact offsets and replay a shadow generation

**Files:**

- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/KafkaOffsetSnapshotter.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/AdminKafkaOffsetSnapshotter.java`
- Create: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/rebuild/ShadowReplayRequest.java`
- Create: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/rebuild/ShadowReplayStatus.java`
- Create: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/rebuild/ShadowReplayService.java`
- Create: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/rebuild/RebuildControlController.java`
- Modify: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/ElasticsearchGateway.java`
- Modify: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGateway.java`
- Modify: `mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/pipeline/SearchRevisionListener.java`
- Create: `mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/rebuild/ShadowReplayServiceIT.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/ShadowReplayClient.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/HttpShadowReplayClient.java`

**Interfaces:**

- `ElasticsearchGateway.write(target, documents)` accepts only `products_write` or a validated `products_v3_*` physical index.
- Main listener ID is `product-search-main`.
- Shadow replay is one active run per consumer process and does not commit the primary consumer group's offsets.

- [ ] **Step 1: Write offset-retention and replay tests**

Tests must prove:

- all three end offsets are captured as `O_start`;
- start offset below Kafka beginning offset fails with `RequiredOffsetExpiredException`;
- shadow assigns all partitions and seeks to the exact supplied offsets;
- unrelated `cdc_barrier` records advance shadow offsets but do not write search documents;
- old revision signals reload current MySQL state and cannot overwrite a newer shadow document;
- stop closes the dedicated consumer and leaves primary group offsets unchanged.

- [ ] **Step 2: Implement exact offset snapshot and validation**

`AdminKafkaOffsetSnapshotter.endOffsets` lists topic partitions and uses latest offsets. `assertRetained` uses earliest offsets and requires:

~~~java
if (requiredOffset < beginningOffset) {
    throw new RequiredOffsetExpiredException(topicPartition, requiredOffset, beginningOffset);
}
~~~

Persist one `rebuild_partition_offset(phase='START')` row per partition before opening the MySQL snapshot.

- [ ] **Step 3: Extend the sink with an explicit validated target**

The gateway signature becomes:

~~~java
BulkWriteResult write(String target, List<SearchDocument> documents);
~~~

Validate target with:

~~~java
private static final Pattern TARGET =
        Pattern.compile("products_write|products_v3_[0-9]{14}_[0-9a-f]{8}");
~~~

The main processor always supplies `products_write`; only `ShadowReplayService` supplies a physical generation.

- [ ] **Step 4: Implement assign/seek shadow replay**

Create a dedicated Kafka consumer with:

~~~properties
enable.auto.commit=false
auto.offset.reset=none
isolation.level=read_committed
group.id=rebuild-shadow-{runId}
key.deserializer=org.apache.kafka.common.serialization.StringDeserializer
value.deserializer=org.apache.kafka.common.serialization.StringDeserializer
~~~

The worker:

~~~text
1. Validate every required offset is retained.
2. assign(all topic partitions), then seek(each O_start).
3. poll in a single worker thread.
4. Parse product revision rows; ignore but advance past cdc_barrier rows.
5. Reload current MySQL snapshots and project with the normal consumer projector.
6. Bulk-write the explicit generation and inspect every item.
7. Advance the in-memory and rebuild_partition_offset SHADOW position only after settlement.
8. On retryable failure, retain position and retry with bounded backoff.
9. On permanent data failure, fail the rebuild; do not publish to the primary DLQ and skip.
~~~

For M5, any shadow poison record fails the generation because cutover requires an exact shadow.

- [ ] **Step 5: Add primary pause/resume and control endpoints**

Set listener ID:

~~~java
@KafkaListener(
        id = "product-search-main",
        topics = "product-search-revisions",
        groupId = "product-search-sync-v1")
~~~

Endpoints:

~~~text
POST   /internal/rebuild/shadow/start
GET    /internal/rebuild/shadow/{runId}
DELETE /internal/rebuild/shadow/{runId}
POST   /internal/rebuild/primary/pause
POST   /internal/rebuild/primary/resume
~~~

Pause and resume through `KafkaListenerEndpointRegistry`. Status reports assigned partitions, next offsets, target index, running flag, and failure class.

- [ ] **Step 6: Run live replay tests and commit**

~~~bash
./mvnw -pl search-sync-consumer,consistency-verifier \
  -Dtest=ShadowReplayServiceIT test
git add search-sync-consumer consistency-verifier
git commit -m "feat(cdc-lab): replay CDC into shadow generations"
~~~

---

### Task 4: Scan one consistent MySQL snapshot into the new generation

**Files:**

- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/SourceSnapshotCursor.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/ConsistentSourceScanner.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/JdbcConsistentSourceScanner.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/SnapshotGenerationWriter.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/rebuild/JdbcConsistentSourceScannerIT.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/rebuild/SnapshotGenerationWriterIT.java`

**Interfaces:**

- Opening a cursor executes `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` and `START TRANSACTION WITH CONSISTENT SNAPSHOT` on the same dedicated connection used for every page.
- Closing rolls back the read-only transaction and returns the connection.

- [ ] **Step 1: Write a concurrent-scan snapshot test**

The test opens a page-size-two snapshot over four products, reads page one, commits a rename/deactivate/new-product set from another connection, then reads remaining pages. The snapshot must contain the original four rows and their original revisions only. A new scanner opened afterward sees the mutations.

- [ ] **Step 2: Run the test and verify the red state**

~~~bash
./mvnw -pl consistency-verifier -Dtest=JdbcConsistentSourceScannerIT test
~~~

Expected: FAIL because the dedicated snapshot cursor does not exist.

- [ ] **Step 3: Implement the dedicated connection lifecycle**

On one `DataSource.getConnection()`:

~~~java
connection.setReadOnly(true);
connection.setAutoCommit(false);
connection.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
try (Statement statement = connection.createStatement()) {
    statement.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT");
}
~~~

Use the independent verifier projection from M4, but execute all keyset queries through prepared statements on this connection. `SourceSnapshotCursor.close()` rolls back and closes even after a Bulk failure.

- [ ] **Step 4: Write snapshot pages with strict external versions**

`SnapshotGenerationWriter` accepts only a newly created physical generation. It writes every `ExpectedDocument` with `version=sourceRevision` and `version_type=external`, inspects every Bulk item, and aborts on any non-success. It never deletes inactive rows.

Persist `rebuild_run.source_count` after every successful page so crash evidence shows exact progress. A failed generation is not resumed from a later page because its MySQL transaction snapshot cannot survive process death; a retry creates a new run and generation.

- [ ] **Step 5: Verify active and tombstone scan output**

The real-ES integration test asserts:

- the document count equals all revision rows, not only active products;
- inactive documents contain only identity, `searchable=false`, revision, and timestamp;
- `_version == source_revision` for active and inactive documents;
- concurrent post-snapshot changes are later corrected by shadow replay.

Run:

~~~bash
./mvnw -pl consistency-verifier \
  -Dtest=JdbcConsistentSourceScannerIT,SnapshotGenerationWriterIT test
~~~

- [ ] **Step 6: Commit consistent snapshot construction**

~~~bash
git add consistency-verifier
git commit -m "feat(cdc-lab): build consistent source generations"
~~~

---

### Task 5: Orchestrate barrier verification and atomic promotion

**Files:**

- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildRequest.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildStatus.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildRunStore.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/JdbcRebuildRunStore.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/BarrierObserver.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/KafkaBarrierObserver.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/PrimaryConsumerControl.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/HttpPrimaryConsumerControl.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildCoordinator.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildController.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildFailpoint.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RebuildFailpointRegistry.java`
- Create: `mysql-es-cdc-handson/consistency-verifier/src/test/java/com/interview/mysqlescdc/verifier/rebuild/RebuildCoordinatorTest.java`

**Interfaces:**

- `POST /internal/rebuild/runs` starts one rebuild at a time.
- `GET /internal/rebuild/runs/{runId}` returns persisted phase, generation, offsets, verification run, gate owner, and alias state.

- [ ] **Step 1: Write order, failure, and idempotent-recovery tests**

Use fakes that record every call. Assert this strict happy-path order:

~~~text
persist CREATED
capture and persist O_start
create generation
open consistent MySQL snapshot
start shadow at O_start
scan snapshot into generation
close snapshot
assert O_start still retained
close write gate
publish three-partition barrier
observe markerNextOffsets for all partitions
wait primary committed offsets >= markerNextOffsets
wait shadow offsets >= markerNextOffsets
pause primary
run independent verify against physical generation
arm/check BEFORE_ALIAS_SWITCH failpoint
atomic alias cutover
persist CUTOVER_COMMITTED and alias_swapped=true
stop shadow
resume primary
clear LOG_GAP condition
open write gate
persist COMPLETED
~~~

Also test failure at every call. Before cutover, aliases must remain old and writes reopen. After cutover, retries must never swap back to old.

Add a second state-machine test for reason MYSQL_BINLOG_GAP:

~~~text
persist CANAL_RECOVERY_REQUIRED
close write gate and drain in-flight mutations
persist CANAL_RECOVERING
wait for an externally submitted, verified canal_position_recovery record
capture and persist O_start while the gate is still closed
create generation
open consistent MySQL snapshot
start shadow at O_start
open write gate
scan snapshot into generation
continue through the normal barrier, verification, and cutover path
~~~

The coordinator must not accept the recovery record unless it contains the old cursor hash and missing file/position; gate-stable reset lower bound; ACK-derived reset cursor hash and retained file/position; three reset-time anchor records/next offsets; preserved cursor identity plus unchanged Kafka offsets across reset=false restart; and three distinct normal-mode sentinel records/next offsets observed exactly once at their expected next offsets. The reset-anchor and normal-sentinel run IDs must differ. LOG_GAP remains active until the rebuilt generation passes and cutover completes.

- [ ] **Step 2: Observe exact barrier offsets in every partition**

The observer assigns all topic partitions at offsets captured immediately before barrier publication, polls until it sees all rows matching the run ID, and records `ConsumerRecord.offset() + 1` for each partition. Reject duplicate tokens in one partition or a token whose hash does not match the observed partition.

This marker vector is `O_barrier`; it is not a scalar and is not the topic's later end-offset vector.

- [ ] **Step 3: Implement the coordinator state machine**

`RebuildCoordinator.start` follows the tested order and updates status before each externally visible phase. It activates `REBUILD_IN_PROGRESS` at creation. Only one nonterminal rebuild is permitted by a MySQL advisory lock named `mysql-es-cdc-rebuild` held by the coordinator connection.

Verification request must use:

~~~json
{
  "target": "products_v3_20260722120000_ab12cd34",
  "pageSize": 200
}
~~~

Require `PASS`, zero differences, stable source watermark, unresolved DLQ zero, and no shadow failure before cutover.

- [ ] **Step 4: Add the deterministic alias failpoint**

~~~java
public enum RebuildFailpoint {
    NONE,
    BEFORE_ALIAS_SWITCH,
    AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN
}
~~~

The registry is available only when lab failpoints are enabled. `BEFORE_ALIAS_SWITCH` throws before the `_aliases` request. `AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN` throws after `CUTOVER_COMMITTED` is persisted so restart recovery can prove the new generation remains authoritative.

- [ ] **Step 5: Implement startup recovery by persisted cutover truth**

On startup, inspect each nonterminal run:

- if `alias_swapped=false` and aliases still old: stop shadow, resume primary, reopen owned gate, mark FAILED;
- if `alias_swapped=true` or both aliases point to the generation: persist `CUTOVER_COMMITTED`, stop shadow, resume primary, reopen gate, verify new generation, then mark COMPLETED;
- if persisted state and actual aliases disagree: keep gate closed, activate `REBUILD_REQUIRED`, expose failure, and require operator resolution.

Never infer rollback from process exit alone.

- [ ] **Step 6: Expose API and run coordinator tests**

Endpoints:

~~~text
POST /internal/rebuild/runs
GET  /internal/rebuild/runs/{runId}
POST /internal/rebuild/runs/{runId}/canal-recovery/start
POST /internal/rebuild/runs/{runId}/canal-recovery/complete
POST /internal/rebuild/runs/{runId}/resume
PUT  /internal/rebuild/failpoint/{failpoint}
DELETE /internal/rebuild/failpoint
~~~

Run:

~~~bash
./mvnw -pl consistency-verifier -Dtest=RebuildCoordinatorTest test
~~~

- [ ] **Step 7: Commit the cutover coordinator**

~~~bash
git add consistency-verifier
git commit -m "feat(cdc-lab): coordinate verified rebuild cutovers"
~~~

---

### Task 6: Prove concurrent rebuild, crash recovery, and gap recovery end to end

**Files:**

- Create: `mysql-es-cdc-handson/scenarios/definitions/m5-concurrent-rebuild.json`
- Create: `mysql-es-cdc-handson/scenarios/definitions/m5-rebuild-before-cutover-crash.json`
- Create: `mysql-es-cdc-handson/scenarios/definitions/m5-rebuild-after-cutover-crash.json`
- Create: `mysql-es-cdc-handson/scenarios/definitions/m5-kafka-gap-rebuild.json`
- Create: `mysql-es-cdc-handson/scenarios/definitions/m5-mysql-binlog-gap-rebuild.json`
- Create: `mysql-es-cdc-handson/scenarios/scripts/run-m5-rebuild.sh`
- Create: `mysql-es-cdc-handson/scenarios/scripts/reset-canal-position.sh`
- Create: `mysql-es-cdc-handson/tests/contracts/canal-position-recovery.sh`
- Create: `mysql-es-cdc-handson/tests/end-to-end/m5-rebuild.sh`
- Create: `mysql-es-cdc-handson/docs/05-rebuild-runbook.md`
- Modify: `mysql-es-cdc-handson/Makefile`
- Modify: `mysql-es-cdc-handson/README.md`

**Interfaces:**

- Runtime evidence for each rebuild contains source watermark, `O_start`, `O_barrier`, shadow offsets, verification run, alias request/response, gate duration, and recovery actions. A MySQL-binlog-gap run additionally contains the old cursor artifact/hash and missing position, reset lower bound, reset-time anchor records/vector, ACK-derived reset cursor hash/position, reset=false restart cursor/offset identity, and distinct normal-mode sentinel records/vector.

- [ ] **Step 1: Define the concurrent-scan scenario**

`m5-concurrent-rebuild.json`:

~~~json
{
  "scenario_id": "m5-concurrent-rebuild",
  "seed": "catalog-500",
  "scan_page_size": 10,
  "mutations_during_scan": [
    {"operation":"rename","productId":1001,"name":"Concurrent Name"},
    {"operation":"inventory","productId":1002,"availableQuantity":77},
    {"operation":"deactivate","productId":1003},
    {"operation":"create","productId":2001,"sku":"SKU-2001"}
  ],
  "expected_gate_behavior":"HTTP_503_DURING_CUTOVER_ONLY",
  "expected_terminal_state":"HEALTHY"
}
~~~

The runner waits for persisted `SNAPSHOTTING`, executes mutations while source pages are still advancing, waits for `GATING`, proves a new mutation returns 503, then expects completion and retries that mutation after reopen.

- [ ] **Step 2: Define failures on both sides of the atomic boundary**

Before-cutover scenario arms `BEFORE_ALIAS_SWITCH` and asserts old aliases, open gate after recovery, primary resumed, failed shadow retained, and state DEGRADED or REBUILD_REQUIRED according to the initiating condition.

After-cutover scenario arms `AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN`, restarts verifier, and asserts new aliases stay new, startup recovery opens the gate, primary resumes against `products_write`, and a fresh independent verification passes.

- [ ] **Step 3: Define confirmed Kafka-gap recovery**

The gap scenario:

1. captures a primary group committed offset;
2. shortens topic retention and writes enough events to move the beginning offset past it;
3. runs the M4 gap detector and requires `REBUILD_REQUIRED`;
4. restores normal retention;
5. starts M5 from a currently retained `O_start`;
6. completes cutover and full independent verification;
7. clears `LOG_GAP` only with the successful rebuild run ID;
8. requires final HEALTHY.

- [ ] **Step 4: Rebootstrap a purged Canal source cursor under evidence**

`reset-canal-position.sh RUN_ID EVIDENCE_DIR` is allowed only while the named rebuild run owns the closed write gate and has status CANAL_RECOVERING. It implements this exact protocol:

1. Read the missing journal/position from the active LOG_GAP condition and prove that journal is absent from `SHOW BINARY LOGS`.
2. Copy `/home/admin/canal-data/products/meta.dat` from the stopped Canal container to `EVIDENCE_DIR/canal-meta-before.dat`; record its SHA-256 and decoded journal/position. In the official 1.1.8 release wiring, `file-instance.xml` uses `FailbackLogPositionManager(MemoryLogPositionManager, MetaLogPositionManager)`, and `MetaLogPositionManager` reads the acknowledged MQ client cursor persisted by `FileMixedMetaManager` as `meta.dat`: <https://github.com/alibaba/canal/blob/canal-1.1.8/deployer/src/main/resources/spring/file-instance.xml> and <https://github.com/alibaba/canal/blob/canal-1.1.8/meta/src/main/java/com/alibaba/otter/canal/meta/FileMixedMetaManager.java>. `FileMixedLogPositionManager` exists but is not wired; this plan must not enable its `parse.dat` path without separate proof of the MQ ACK/restart boundary.
3. Capture the gate-stable `SHOW MASTER STATUS` file, position, and GTID set as the reset lower bound.
4. Start only Canal once with `CANAL_AUTO_RESET_LATEST_POS_MODE=true docker compose -f infra/compose.yaml up -d --force-recreate canal`. This opt-in uses Canal's documented `canal.auto.reset.latest.pos.mode`; normal Compose startup remains false.
5. While reset mode is still active and the business write gate remains closed, call the gate-owned recovery endpoint to insert one `cdc_barrier` row for each partition under a dedicated **reset-anchor run ID**. This internal control path is the only allowed writer under the gate. Observe the three raw null-key Kafka records in partitions 0/1/2, wait until Canal has ACKed them, and record each record plus `offset + 1` as `reset_anchor_offsets_json`.
6. Only after the reset-time anchors are ACKed, poll `meta.dat` until it names a journal still present in `SHOW BINARY LOGS`, its decoded position covers the anchors and is at or beyond the reset lower bound, and Canal no longer reports the purged source position. Record `reset_cursor_sha256`, decoded journal/position, and the Kafka end-offset vector. Waiting for ACK-derived `meta.dat` to advance before producing/ACKing anchors is a protocol error and must time out as FAIL.
7. Restart Canal with `CANAL_AUTO_RESET_LATEST_POS_MODE=false`. Immediately before restart record the reset cursor identity/hash/decoded position and Kafka end offsets; before producing any new row after restart, require the same cursor identity/hash/position, unchanged end offsets, and startup from that exact acknowledged cursor. A reset that works only with auto-reset left enabled is a failure. The known 1.1.8 static-destination stop NPE must be recorded but cannot replace any check or be generalized as harmless.
8. After the reset=false restart, call the recovery endpoint again with a distinct **normal-sentinel run ID** and insert one deterministically mapped `cdc_barrier` row per partition. Starting from the pre-restart per-partition end-offset vector, observe each sentinel exactly once at that partition's expected next offset and store all three records plus their next offsets. Reset-time anchors cannot satisfy this normal-mode sentinel gate.
9. Submit the complete evidence to `/canal-recovery/complete`; only then may the coordinator capture O_start, open its consistent snapshot, start shadow replay, and reopen writes.

The script never deletes cursor evidence or the whole Canal data volume. Failure leaves the gate closed, LOG_GAP active, and the run resumable after operator inspection.

`canal-position-recovery.sh` statically checks that normal mode defaults false, `canal-data` is a named volume, the cursor path is destination-scoped, and the scenario cannot call the completion endpoint without all evidence fields.

- [ ] **Step 5: Write the exact rebuild runbook**

`docs/05-rebuild-runbook.md` must contain:

~~~markdown
# Full rebuild and gap-free cutover

## Preconditions

MySQL current facts are healthy, Kafka retains all offsets from the new O_start, Elasticsearch can create a generation, and the product-service write gate is reachable.

## Build invariant

O_start is captured before the consistent MySQL snapshot. Transactions visible in the snapshot are scanned; events at or after O_start are replayed. Overlap is safe because every document uses source_revision as an external version.

## Cutover invariant

The write gate drains in-flight transactions. One MySQL transaction emits a marker to every Kafka partition. The primary consumer and shadow replayer both pass the exact marker offsets before writes pause and independent verification begins.

## Atomic boundary

Both aliases move in one Elasticsearch _aliases request. Before success, the old generation is authoritative. After success, the new generation is authoritative. Process failure does not reverse that fact.

## Guarantee boundary

This procedure rebuilds current Elasticsearch state after an incremental log gap and admits a short write pause. A MySQL binlog gap also requires an evidenced Canal cursor rebootstrap before rebuild; rebuilding Elasticsearch alone does not make future CDC healthy. It cannot recover MySQL facts that no longer exist, historical versions that were never retained, or a source database that is itself corrupt.
~~~

- [ ] **Step 6: Add M5 commands**

~~~make
.PHONY: rebuild verify-m5 scenario-m5

rebuild:
	curl -fsS -X POST http://localhost:8083/internal/rebuild/runs \
	  -H 'Content-Type: application/json' \
	  -d '{"reason":"manual","pageSize":200}'

scenario-m5:
	bash scenarios/scripts/run-m5-rebuild.sh

verify-m5:
	./mvnw -q -pl product-service,search-sync-consumer,consistency-verifier test
	bash tests/end-to-end/m5-rebuild.sh
~~~

- [ ] **Step 7: Run the complete M5 gate twice from reset**

~~~bash
make reset
make up
bash infra/mysql/apply-reconciliation-control.sh
make bootstrap-index
make verify-m5
make reset
make up
bash infra/mysql/apply-reconciliation-control.sh
make bootstrap-index
make verify-m5
git diff --check
~~~

Expected both times:

- writes continue through snapshot scan and receive 503 only during the explicit cutover gate;
- all three partitions have start, shadow, and barrier offsets recorded;
- active and inactive source rows exist exactly in the promoted generation;
- pre-cutover failure leaves old aliases; post-cutover failure keeps new aliases;
- confirmed Kafka gap returns to HEALTHY only after successful rebuild and fresh PASS;
- confirmed MySQL binlog gap returns to HEALTHY only after reset-time anchors are ACKed, `meta.dat` covers them, reset=false restart preserves cursor/offset identity, distinct normal-mode sentinels prove exactly-next-event in all partitions, and the linked rebuild produces a fresh PASS;
- alias state, write gate, primary consumer, and shadow worker are never left ambiguous.

- [ ] **Step 8: Commit M5**

~~~bash
git add .
git commit -m "feat(cdc-lab): complete verified full rebuilds"
~~~

## M5 Completion Gate

Do not start M6 until:

- `O_start` is captured before a single-connection consistent snapshot;
- shadow replay rejects expired required offsets;
- every generation includes latest-revision tombstones;
- the write gate demonstrably drains in-flight transactions;
- barriers are observed in all three Kafka partitions and yield exact vector offsets;
- old and shadow paths both pass the barrier before verification;
- both aliases move atomically only after an independent zero-diff PASS;
- failures before and after the alias boundary recover according to persisted truth;
- a purged MySQL position cannot clear LOG_GAP until reset-time anchors advance the ACK-derived cursor, reset=false restart preserves exact cursor/offset identity, distinct normal-mode sentinels prove exactly-next-event in all three partitions, and the linked rebuild passes;
- a confirmed Kafka gap is recoverable only through a successful rebuild;
- two reset M5 runs finish with HEALTHY, zero DLQ, zero diff, and open writes.
