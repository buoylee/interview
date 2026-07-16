# 06 数据库整合测试：让 Postgres 自己作证

## 核心问题

内存 adapter 能证明业务流程，却不能证明 PostgreSQL 的约束、类型、事务和锁。数据库整合测试的目标不是重复 unit test，而是让真正拥有语义的组件提供证据：唯一约束由 Postgres 拒绝重复键，乐观并发由受版本保护的 `UPDATE` 行数判定，outbox 抢占由 `FOR UPDATE SKIP LOCKED` 协调。

## 直觉模型

把每个测试看成一次真实交易：测试创建自己的 `AsyncSession`，只有显式 `commit()` 才发布结果；退出时 rollback 并关闭。fixture 拥有容器和 engine，测试拥有事务。每个测试之后执行真实 `TRUNCATE ... CASCADE`，而不是依赖外层 rollback 隐藏 commit。

## 机制深入

迁移使用同步 psycopg，因为 Alembic 的 migration context 是同步的；应用使用 `postgresql+psycopg` 的 async engine。表与领域对象显式映射：金额保持 `numeric(18,2)`/`Decimal`，时间使用 `timestamptz` 和带时区 `datetime`，payload 使用 JSONB，标识使用 UUID。

乐观更新执行 `WHERE id = :id AND version = :expected`。`rowcount != 1` 不是普通“未找到”，而是并发写已经改变了观察到的版本。outbox claim 在同一事务内锁定候选行，`SKIP LOCKED` 让另一个消费者继续处理其他行；30 秒 lease 在边界处使用 `<=`，与 memory adapter 保持同一契约。

## 设计取舍

SQLite 适合它自己的行为测试，但它没有 PostgreSQL 的 JSONB、锁语义、驱动行为和完全相同的 DDL，因此不能作为这里的替身。隐藏的外层事务能加速清理，却会让“新 UoW 是否看见已提交数据”成为假阳性；需要它时，应把 savepoint 限制在不验证真实 commit 的测试层。

## 贯穿 lab

session-scoped Testcontainers 启动 `postgres:16-alpine`，先执行 `alembic upgrade head`，再创建 async engine/session factory。迁移测试执行 downgrade→upgrade 并反射 schema。repository 测试覆盖映射、唯一约束、rollback、commit visibility 和 stale save。outbox 测试用两个同时存在的真实事务证明锁中行被跳过。

```bash
cd python-testing/lab
uv run pytest tests/integration -m "integration and docker" -q
uv run pytest -q
```

第二条命令由项目级 `-m not docker` 保证不会意外启动容器；显式运行 Docker 测试必须覆盖默认 marker 表达式。

## 故障工单

容器失败时先区分层次：Docker socket 是否可访问、镜像是否存在或可拉取、容器日志是否显示 readiness、迁移 URL 是否保留 psycopg driver。记录原始异常后只验证一个假设。不要把连接失败改写成 SQLite 测试，也不要用 retry 掩盖迁移错误。

清理失败通常意味着前一个测试留下了 aborted transaction 或 schema 被 downgrade 后未恢复。先检查 transaction ownership，再确认 migration test 在结束前 upgrade 回 head。并发测试挂起时，检查锁事务是否仍持有连接，以及 claim 查询是否真的包含 `skip_locked=True`。

## Java / Go 对照

Java 的 Testcontainers 与事务测试注解容易产生同样的外层 rollback 盲点；Go 的 `database/sql` 则更明显地要求调用方持有 `Tx`。Python 的 AsyncSession 也不是“自动事务安全层”：commit、rollback、close 的所有权仍需在 UoW 中写清楚。

## 验收与面试卡

- migration 可 downgrade→upgrade，表、约束、索引和类型可反射。
- 新 UoW 只能看到已提交写入；正常未提交退出和异常退出都不可见。
- 真实唯一约束和乐观冲突都产生稳定失败。
- outbox 完整覆盖 due、lease、limit、transition、missing ID 与 `SKIP LOCKED`。
- 默认 suite 不访问 Docker。

一句话：整合测试应验证“数据库拥有的语义”，而不是用更慢的方式重跑领域 unit test。事务隔离、锁和迁移的深入背景见 [`python-data/`](../python-data/)。
