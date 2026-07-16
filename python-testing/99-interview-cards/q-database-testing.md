# 为什么数据层要对真 Postgres 测试，rollback fixture 何时会误导？

## 30 秒回答

数据库 adapter 的风险属于 Postgres：DDL、NUMERIC/UUID/JSONB 映射、唯一约束、事务可见性、乐观更新和 `FOR UPDATE SKIP LOCKED`。这些不能由 SQLite 或 ORM mock 作证。每个测试应通过真实 UoW 显式 commit/rollback，并从 fresh session 观察结果；如果外层 transaction 无条件 rollback，它会让“commit 是否真的跨事务可见”变成无法验证的假命题。

## 机制

真实写入在 transaction commit 前只对当前 snapshot 可见；fresh UoW 是验证发布边界的 oracle。乐观锁把 expected version 放进 UPDATE predicate，并以 rowcount 判断冲突。outbox claim 必须在短事务内锁行、更新时间并提交；两个独立 connection 才能证明 SKIP LOCKED。迁移测试还要验证 upgrade/downgrade、精确类型、constraint、index、nullability 和 timezone，而不是只检查表名存在。

## lab 生产案例

[`SQLAlchemyUnitOfWork`](../lab/src/order_service/adapters/sqlalchemy.py) 明确拥有 session 的 commit、rollback 与 close；migration 建立订单、outbox 和退款状态。integration fixtures 用 `postgres:16-alpine` 执行 Alembic head，并在测试间 TRUNCATE。测试从第二个 UoW 检查 commit visibility，以两个 session 验证锁中第一行会被另一个 claim 跳过。

## 取舍／反例

savepoint/外层 rollback 对不验证真实 commit 的 repository 查询可加速清理，但不能被用于证明跨事务发布、after-commit hook、锁释放或连接归还。SQLite 适合 SQLite 自己的应用，不适合模拟 Postgres JSONB 与锁。所有 integration 都走 E2E 也不合理：migration、constraint 和 rowcount 应在窄 adapter boundary 更快、更直接地失败。

## 追问

- 怎样证明 session 在正常和异常退出时都只关闭一次？
- downgrade 测试失败后如何避免污染后续 schema？
- `rowcount == 0` 如何区分 missing row 与 stale version？
- 为什么两个 coroutine 共用一个 session 不构成数据库并发证据？

## 证据链接

- 章节：[数据库核心问题](../06-database-integration.md#核心问题)、[事务 fixture](../06-database-integration.md#直觉模型)、[外层 rollback 取舍](../06-database-integration.md#设计取舍)
- Production：[`sqlalchemy.py`](../lab/src/order_service/adapters/sqlalchemy.py)、[`0001_orders_and_outbox.py`](../lab/migrations/versions/0001_orders_and_outbox.py)、[`0002_refund_state.py`](../lab/migrations/versions/0002_refund_state.py)
- Tests：[`test_migrations.py`](../lab/tests/integration/test_migrations.py)、[`test_sqlalchemy_uow.py`](../lab/tests/integration/test_sqlalchemy_uow.py)、[`test_sqlalchemy_outbox.py`](../lab/tests/integration/test_sqlalchemy_outbox.py)

[返回速答索引](README.md)
