# Reliable CDC pipeline (M2–M3)

## Execution chain

Canal 1.1.8 emits a Kafka record whose Kafka key is `null`; ordering is supplied by
Canal's `product_id` `partitionHash`, not by a serialized record key. The consumer
executes one bounded chain:

```text
raw Kafka value -> parse revision signals -> reload current MySQL snapshot
-> deterministic projection -> Elasticsearch Bulk with version_type=external
-> inspect every item -> durable product/record DLQ or ACK
```

The signal is only a reason to refresh. It is not the target document. Rehydrating
the current MySQL snapshot means an old signal may safely refresh revision 9 even
if the signal itself mentioned revision 7. Replay follows the same rule and never
trusts the product payload retained as failure evidence.

Before a `product_id` exists, malformed/structurally invalid Canal data is a
record-level poison record. Its exact raw key/value and topic/partition/offset are
durably stored before ACK. Replay reparses the original raw value after the parser
or wire-compatibility defect is fixed, de-duplicates its product IDs, reloads every
current source snapshot, and resolves only when every item is APPLIED or STALE.

## Version fencing and deletion

`version_type=external` accepts a greater revision. An equal or lower revision is
classified STALE and cannot overwrite the newer document. Duplicate delivery is
therefore harmless only inside this deterministic projection/revision contract.
Deletion is a versioned tombstone (`searchable=false`), not a physical delete: a
late old active write must meet the tombstone's greater revision and remain stale.

Delivery remains at-least-once. APPLIED and STALE settle an item. Retryable
transport/protocol/item failures leave the offset uncommitted. Permanent data
failures ACK only after an idempotent durable DLQ write. The internal replay paths
are localhost lab/admin surfaces, not unauthenticated production API guidance.

`HEALTHY` means the consumer's current observations and both DLQ counts are clean;
it does not prove global MySQL/Elasticsearch equality. M4 adds independent
verification and reconciliation.

Revision fencing and replay are evidenced by [evidence:consumer-crash-after-elasticsearch-before-offset](../evidence/consumer-crash-after-elasticsearch-before-offset/result.json), [evidence:duplicate-event](../evidence/duplicate-event/result.json), [evidence:late-old-revision](../evidence/late-old-revision/result.json), and [evidence:delete-then-old-event-replay](../evidence/delete-then-old-event-replay/result.json). Per-item settlement and durable DLQ are evidenced by [evidence:elasticsearch-bulk-partial-failure](../evidence/elasticsearch-bulk-partial-failure/result.json), [evidence:mapping-conflict](../evidence/mapping-conflict/result.json), and [evidence:dlq-replay-fails-then-succeeds](../evidence/dlq-replay-fails-then-succeeds/result.json). Strong consistency, exactly-once and unauthenticated production admin APIs are **not tested / non-goal**.
