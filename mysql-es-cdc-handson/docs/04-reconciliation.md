# Independent reconciliation

MySQL is the fact source; Elasticsearch is a repairable current-state projection.

## What a PASS proves

A PASS proves that, during one stable source watermark, every source product has
exactly one managed Elasticsearch document, every managed field matches, every
inactive product is a latest-revision tombstone, and Elasticsearch external
version metadata equals `source_revision`.

Counts, Kafka lag, or the absence of an exception are not substitutes for this
proof. A fresh zero-difference PASS is required after repair.

## Independence rule

The verifier owns a separate SQL query, target record, projector, canonicalizer,
and tests. It never imports the consumer implementation. This is why a
consumer-only mapping defect remains visible. The M4 scenario deliberately makes
the consumer derive `category_name` from `category_id`; the independent verifier
must report exactly one `MODIFIED/category_name` difference for product 1001.

## Repair rule

Stale documents use strict external versions. A missing document may still have
an Elasticsearch delete-version tombstone, so missing and equal-revision field
corruption use a narrowly scoped `external_gte` overwrite after an independent
stable-source check. Normal CDC never uses `external_gte`. Extra documents are
deleted with optimistic concurrency metadata.

Repairs are bounded, persisted per product, and accepted only for a conclusive
DIFF with a stable watermark and no active `LOG_GAP`. A fresh verifier run must
PASS before the pipeline can return to HEALTHY.

## Limits

Reconciliation does not recreate missing binlog or Kafka history, recover lost
MySQL facts, or make a moving snapshot conclusive. A moving source produces
INCONCLUSIVE and repair is rejected. Confirmed log gaps require M5 rebuild.
