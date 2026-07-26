# Goal and invariants

## Target contract

MySQL is the fact source and Elasticsearch is a rebuildable current-state projection. When the recovery preconditions hold, every product eventually has exactly one Elasticsearch document whose managed fields equal the current MySQL aggregate, whose `source_revision` is the latest committed product revision, and whose searchable flag is false for deleted products.

## Recovery preconditions

- MySQL facts remain available and correct;
- binlog and Kafka retain every required incremental position, or a successful full rebuild replaces the missing interval;
- dependencies eventually recover;
- deterministic data errors are durably isolated and later replayed or repaired;
- an independent verifier can detect missing, extra, stale, modified, and tombstone differences.

## M0 status

M0 satisfies only the source transaction and binlog-to-Kafka capture prerequisites. `product-service` writes only MySQL. It does not yet consume Kafka, write Elasticsearch, reject stale revisions, retain a DLQ, reconcile projections, detect all log gaps, or rebuild an index. A Kafka record proves that one capture message reached Kafka; it does not prove Elasticsearch convergence or end-to-end final consistency.

M0 restart evidence is intentionally narrow: the ACK-derived Canal 1.1.8 cursor is `/home/admin/canal-data/products/meta.dat`; an unchanged hash/decoded position plus unchanged three-partition Kafka end-offset vector proves the observed Canal-only restart resumed exactly for this run. The known static-destination stop NPE is recorded as an upstream limitation, not treated as a success condition or shutdown-safety proof.
