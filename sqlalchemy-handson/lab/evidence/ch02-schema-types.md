# 第 02 章 — Schema 與型別系統

## Hypothesis

- MetaData 命名慣例會產生可預測的 PostgreSQL constraint 名稱。
- PostgreSQL Dialect reflection 會保留 JSONB 型別與 partial index predicate。

## Setup

- 資料庫版本為 PostgreSQL 18.4。
- M1 Lab 以 SQLAlchemy MetaData.create_all() 建立 schema。

## Observation

- table_count=8
- tables=idempotency_records,inventories,inventory_reservations,order_lines,orders,outbox_events,products,tenants
- product_unique_constraints=uq_products_tenant_id_id,uq_products_tenant_id_sku
- outbox_indexes=ix_outbox_events_claimable
- product_attributes_type=JSONB
- outbox_claimable_predicate=((status)::text = 'pending'::text)

## Explanation

- 具名 constraint 是 migration 與 IntegrityError translation 的穩定識別依據。
- TypeDecorator.cache_ok=True 讓 Money 型別可安全參與 statement cache。

## Decision

- 所有與業務相關的 constraint 都要命名。金額則以 Decimal-backed numeric 儲存。

## Caveat

- create_all() 只用於 Lab bootstrap。production schema evolution 由 M3 的 Alembic 負責。
