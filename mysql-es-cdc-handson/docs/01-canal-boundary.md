# Canal and Adapter evidence boundary

## Verdict
Canal captures and parses committed MySQL binlog changes and delivers incremental row-change data. It is a CDC/incremental-subscription component, not an end-to-end final-consistency solution.
This pinned official Canal Adapter 1.1.8 run did **not** produce the intended Bulk partial failure: the byte-mapped source value `1000` was observed in Elasticsearch as `-24`. This is an observed coercion boundary, not a successful poison-item experiment and not a guarantee.

Canal capture/restart/retention boundaries are evidenced by [evidence:canal-normal-restart](../evidence/canal-normal-restart/result.json), [evidence:canal-outage-within-binlog-retention](../evidence/canal-outage-within-binlog-retention/result.json), and [evidence:canal-outage-beyond-binlog-retention](../evidence/canal-outage-beyond-binlog-retention/result.json). Adapter behavior outside this pinned lab run and any end-to-end no-loss claim are **not tested / non-goal**.

## Pinned observed results
- `m1-basic.result`: `OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP`; `updated_at_matches_source`: `false`.
- `m1-restart.result`: `OBSERVED_RESTART_RECOVERY`.
- `m1-hard-delete.result`: `OBSERVED_DELETE_PROPAGATION`.
- `m1-bulk-partial.bulk_partial_failure_observed`: `false`; `current_run_error_proven`: `false`.
- Stable claim manifest SHA-256: `5218cc78d3abcb6cba139840ca9dd79f6bd311897822d11da0e20e194a6e4c2a`.

The baseline computed-field gap is explicit: the locked `DATE_FORMAT(...) AS updated_at` expression produced a non-null MySQL value but `null` in the Adapter incremental target, so `updated_at_matches_source` is `false`.

## Byte-mapping and repair observation
- `valid_item_applied`: `true`.
- `invalid_item_applied_before_mapping_fix`: `true`.
- `invalid_source_value_preserved_before_fix`: `false` (source `1000`, target `-24`).
- `later_batch_applied_before_mapping_fix`: `true`.
- `invalid_item_retried_after_mapping_fix`: `false`.
- `etl_required`: `true`; `etl_invoked`: `true`; `etl_repair_succeeded`: `true`.
The runner verified the official launcher annotation before invoking `POST /etl/es8/products.yml?params=1401`; it did not write directly to Elasticsearch or move the Canal cursor.

## Missing end-to-end capabilities
M1 has no final multi-table projection, revision fencing, per-Bulk-item settlement contract, durable DLQ, independent reconciliation/repair loop, binlog-gap classification, or rebuild/cutover workflow. `products_adapter_v1` is disposable comparison state, not the serving index.

## Evidence lifecycle
Runtime evidence under `evidence/m1/` is generated locally and intentionally ignored by Git. Regenerate and verify the evidence and this rendered document with:

```bash
make scenario-m1
make verify-m1
```

The links are meaningful in a generated workspace only; a clean checkout does not ship observed runtime JSON. No M1 result claims exactly-once processing or MySQL-to-Elasticsearch final consistency.

M1 Adapter runtime artifacts are **not tested / non-goal** for the committed M6 matrix; the final capability boundary is the lab [README](../README.md) and its committed `evidence:<scenario-id>` bundles.
