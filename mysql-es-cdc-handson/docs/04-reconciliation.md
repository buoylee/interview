# Independent reconciliation

MySQL is the fact source; Elasticsearch is a repairable current-state projection.

This document uses the [general financial reconciliation theory](../../financial-consistency/07-reconciliation/README.md) for difference, repair, review and audit concepts. It only specifies the MySQL-to-Elasticsearch read-model boundary; it does not duplicate the financial domain design.

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

Independent drift and systematic-projector detection/repair are evidenced by [evidence:manual-elasticsearch-drift](../evidence/manual-elasticsearch-drift/result.json), [evidence:category-rename-multi-product](../evidence/category-rename-multi-product/result.json), and [evidence:consumer-systematic-mapping-bug](../evidence/consumer-systematic-mapping-bug/result.json). Reconciliation cannot recover MySQL history or certify a moving source; those limits, as well as production reconciliation SLOs, are **not tested / non-goal**. Log-gap routing is evidenced by [evidence:canal-outage-beyond-binlog-retention](../evidence/canal-outage-beyond-binlog-retention/result.json) and [evidence:consumer-offset-beyond-kafka-retention](../evidence/consumer-offset-beyond-kafka-retention/result.json).
