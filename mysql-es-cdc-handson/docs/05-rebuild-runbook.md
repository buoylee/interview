# Full rebuild and gap-free cutover

## Preconditions

MySQL current facts are healthy, Kafka retains all offsets from the new `O_start`, Elasticsearch can create a generation, and the product-service write gate is reachable. Run only against the named local Compose project and save evidence outside containers before changing retention or Canal mode.

## Build invariant

`O_start` is captured before the consistent MySQL snapshot. Transactions visible in the snapshot are scanned; events at or after `O_start` are replayed. Overlap is safe because every document uses `source_revision` as an external version. Snapshot completion alone is not convergence evidence: all three durable shadow offsets must pass the barrier.

## Cutover invariant

The write gate drains in-flight transactions. One MySQL transaction emits a marker to every Kafka partition. The primary consumer and shadow replayer both pass the exact marker offsets before writes pause and independent verification begins. Eligibility also requires stable `PASS`, zero differences, both DLQs empty, the exact gate owner, a healthy shadow, retained offsets, and the expected old alias topology.

## Atomic boundary

Both aliases move in one Elasticsearch `_aliases` request. Before success, the old generation is authoritative. After success, the new generation is authoritative. Process failure does not reverse that fact. `BEFORE_ALIAS_SWITCH` cleans up toward the old generation; `CUTOVER_COMMITTED` and an observed new topology recover only forward.

## Kafka retention gap recovery

A committed offset below the partition beginning offset is a confirmed gap, not ordinary lag. Restore retention first, then capture a newly retained `O_start` and rebuild. `LOG_GAP` is cleared only by the successful rebuild ID whose physical generation has a stable zero-difference `PASS` and committed cutover.

## MySQL binlog cursor recovery

Stop Canal but preserve `/home/admin/canal-data/products/meta.dat` and the named `canal-data` volume. A gate-owned `CANAL_RECOVERING` run records the absent old journal, ordered `SHOW BINARY LOGS` manifest, gate-stable lower bound, reset-time anchors, ACK-derived reset cursor, reset=false identity/vector equality, and distinct exactly-next normal sentinels. Auto-reset is enabled for exactly one Canal boot and is false for normal operation. A known Canal 1.1.8 static-destination stop NPE is recorded; it never substitutes for cursor or offset proof.

This lab deliberately keeps `canal.instance.gtidon=false`: both reset and normal boots use the same journal/position cursor model. On MySQL 8.4, capture the current coordinate with `SHOW BINARY LOG STATUS` (`SHOW MASTER STATUS` is the legacy spelling); use `SHOW BINARY LOGS` to prove the old journal was purged.

## Failure handling

Every wait is bounded. Failure evidence includes phase, gate owner, exact aliases, start/barrier/shadow vectors, health, lag, both DLQs, verification, and service logs. Before cutover, cleanup attempts stop the shadow, resume primary, and reopen only the owned gate. Contradictory topology leaves the gate closed with `REBUILD_REQUIRED`. Never delete cursor evidence to make a restart succeed.

## Guarantee boundary

This procedure rebuilds current Elasticsearch state after an incremental log gap and admits a short write pause. A MySQL binlog gap also requires an evidenced Canal cursor rebootstrap before rebuild; rebuilding Elasticsearch alone does not make future CDC healthy. It cannot recover MySQL facts that no longer exist, historical versions that were never retained, or a source database that is itself corrupt.

## Commands

```bash
make scenario-m5
make verify-m5
```

`M5_EVIDENCE_DIR` selects the evidence directory. Formal acceptance runs from two separate reset environments and evidence directories. The scenario runner removes only its task-created rows, failpoints, toxics, and `products_v3_*` generations when safe; it never removes `meta.dat` or the Canal data volume.

The gap-to-rebuild, concurrent-write, and crash/cutover boundaries are evidenced by [evidence:canal-outage-beyond-binlog-retention](../evidence/canal-outage-beyond-binlog-retention/result.json), [evidence:consumer-offset-beyond-kafka-retention](../evidence/consumer-offset-beyond-kafka-retention/result.json), [evidence:rebuild-with-concurrent-writes](../evidence/rebuild-with-concurrent-writes/result.json), and [evidence:rebuild-crash-and-restart](../evidence/rebuild-crash-and-restart/result.json). Zero pause, MySQL historical recovery, all retention configurations, and a production availability SLO are **not tested / non-goal**.
