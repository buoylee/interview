# Goal and invariants

## Target contract

MySQL is the fact source and Elasticsearch is a rebuildable current-state projection. When the recovery preconditions hold, every product eventually has exactly one Elasticsearch document whose managed fields equal the current MySQL aggregate, whose `source_revision` is the latest committed product revision, and whose searchable flag is false for deleted products.

该 current-state 结论由 [evidence:duplicate-event](../evidence/duplicate-event/result.json)、[evidence:late-old-revision](../evidence/late-old-revision/result.json)、[evidence:delete-then-old-event-replay](../evidence/delete-then-old-event-replay/result.json)、[evidence:manual-elasticsearch-drift](../evidence/manual-elasticsearch-drift/result.json) 和 [evidence:rebuild-with-concurrent-writes](../evidence/rebuild-with-concurrent-writes/result.json) 在记录前提下支持；强一致、exactly-once、持续生产 SLO 均为 **not tested / non-goal**。

## Recovery preconditions

- MySQL facts remain available and correct;
- binlog and Kafka retain every required incremental position, or a successful full rebuild replaces the missing interval;
- dependencies eventually recover;
- deterministic data errors are durably isolated and later replayed or repaired;
- an independent verifier can detect missing, extra, stale, modified, and tombstone differences.

这些前提中的可回放窗口、缺口进入重建、独立差异发现分别见 [evidence:canal-outage-beyond-binlog-retention](../evidence/canal-outage-beyond-binlog-retention/result.json)、[evidence:consumer-offset-beyond-kafka-retention](../evidence/consumer-offset-beyond-kafka-retention/result.json)、[evidence:consumer-systematic-mapping-bug](../evidence/consumer-systematic-mapping-bug/result.json)。跨所有 MySQL 历史、任意 retention 配置均为 **not tested / non-goal**。

## M0 status

M0 satisfies only the source transaction and binlog-to-Kafka capture prerequisites. `product-service` writes only MySQL. It does not yet consume Kafka, write Elasticsearch, reject stale revisions, retain a DLQ, reconcile projections, detect all log gaps, or rebuild an index. A Kafka record proves that one capture message reached Kafka; it does not prove Elasticsearch convergence or end-to-end final consistency.

M0 restart evidence is intentionally narrow: the ACK-derived Canal 1.1.8 cursor is `/home/admin/canal-data/products/meta.dat`; an unchanged hash/decoded position plus unchanged three-partition Kafka end-offset vector proves the observed Canal-only restart resumed exactly for this run. The known static-destination stop NPE is recorded as an upstream limitation, not treated as a success condition or shutdown-safety proof.

## M3 crash-window boundary

The lab-only failpoints use exit code 86 to observe two pinned crash windows. A crash after an Elasticsearch Bulk success but before the Kafka offset commit is safe under the observed fixture because replay is fenced by `source_revision`; the equal revision settles as `STALE` without changing the document. A crash after the independent MySQL DLQ transaction but before the offset commit keeps one deterministic DLQ identity and increments its attempts on replay.

Task 6 does not claim final recovery for the after-DLQ case. Restoring the Elasticsearch mapping deliberately leaves that row `PENDING`, with terminal boundary `RECOVERY_DEFERRED_TO_TASK7` and `final_consistency_claim=false`. Task 7 must reload current MySQL state and may mark the row `RESOLVED` only after Elasticsearch settles it as `APPLIED` or `STALE`; direct SQL status changes and unconditional `DlqStore.resolve` calls are outside the recovery contract.

该 crash/DLQ 边界的受控证据是 [evidence:consumer-crash-after-elasticsearch-before-offset](../evidence/consumer-crash-after-elasticsearch-before-offset/result.json)、[evidence:elasticsearch-bulk-partial-failure](../evidence/elasticsearch-bulk-partial-failure/result.json) 与 [evidence:dlq-replay-fails-then-succeeds](../evidence/dlq-replay-fails-then-succeeds/result.json)；Task 7 自动闭环为 **not tested / non-goal**。
