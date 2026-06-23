# Python 数据访问架构

写给**有后端底子、要把 Python 数据层用到架构师水准**的人:不是「怎么调 SQLAlchemy 的 API」,而是**从 Python 进程到数据库这一层的机制、内幕与取舍**——driver、连接池、Core/ORM、Session/工作单元、事务边界、N+1、async、迁移、repository。每个关键现象都有一个**可跑的 Postgres lab** 实测出数字。

这是 [`../python/`](../python/) 资深教程的延伸:`python/` 聚焦语言本身,数据访问只在 [`python/23`(桥接章)](../python/23-data-access-bridge.md) 讲「怎么选」,实操深度在这里(对照 `python/13` 并发桥接章 → `../python-concurrency/` 的关系)。

> **环境约定**:锚点 **Postgres 16 + SQLAlchemy 2.0**(async 为主),纯开源;示例代码都对真库实测过。`lab/` 里的数字是 Apple Silicon / 本地回环跑出来的,**你的会不同**——看的是数量级与现象。

## 怎么读

- **线性通读**:00 → 08 顺序。00 建立「要不要 ORM / Core vs ORM / sync vs async」三个先决选择的总纲,后面每章是其中一格的展开。
- **按主题跳读**:每章自带「导引 + Java/Go 对照框 + 章末面试卡」,可独立读。
- **面试前突击**:扫 [`99-interview-cards.md`](99-interview-cards.md),卡壳回对应章;`lab/` 的「猜行为 drill」是实测过的高频题。
- **动手**:进 [`lab/`](lab/),`docker compose up -d && uv sync && uv run python seed.py`,跑四个 demo 亲眼看现象。

## 章节目录

| # | 章 | 一句话 |
|---|---|---|
| 00 | [心智与选型](00-mindset-and-selection.md) | 全景四层;要不要 ORM / Core vs ORM / sync vs async 三棵决策树 |
| 01 | [驱动与 DBAPI](01-drivers-and-dbapi.md) | PEP 249、psycopg3 vs asyncpg、参数化机制、一次 execute 的协议往返 |
| 02 | [连接池](02-connection-pooling.md) | 为什么要池、QueuePool 五参数、池耗尽现象与排查 |
| 03 | [ORM:Session / UoW / 加载策略](03-orm-session-uow.md) | identity map、flush vs commit、lazy/eager——N+1 的根源 |
| 04 | [事务边界与并发控制](04-transactions.md) | 边界放哪、隔离级别、乐观锁、序列化失败重试 |
| 05 | [N+1 与查询性能](05-n-plus-one-and-query-perf.md) | 怎么发现、selectinload/joinedload、何时下沉 raw SQL、读 EXPLAIN |
| 06 | [异步数据访问](06-async-data-access.md) | async engine/session、asyncpg、greenlet 桥、值不值 |
| 07 | [迁移与 schema 演进](07-migrations.md) | Alembic、autogenerate 边界、zero-downtime 模式 |
| 08 | [架构权衡与测试](08-architecture-and-testing.md) | repository?、领域/持久化解耦、数据层测试策略 |
| 99 | [面试卡](99-interview-cards.md) | 各章高频题速记 + 猜行为 drill(实测数字) |
| — | [lab/](lab/) | 可跑 Postgres 实验:池耗尽 / N+1 / 隔离 / async 吞吐 |

## 与仓库其他目录的边界

这里只讲「Python 应用侧怎么把数据访问用好」,几块深水区只给指针:

- **数据访问选型一句话版** → [`../python/23`](../python/23-data-access-bridge.md)(桥接章,决策树)
- **DB 引擎 / SQL 调优 / 隔离级别原理** → [`../mysql/`](../mysql/)、[`../transaction/`](../transaction/)
- **分布式事务 / 分片** → [`../distr-tx/`](../distr-tx/)、[`../Sharding-Sphere/`](../Sharding-Sphere/)
- **缓存 / 多存储编排** → [`../redis/`](../redis/)
- **连接池纯性能调参与压测** → [`../performance-tuning-roadmap/11-architecture/02-connection-pooling.md`](../performance-tuning-roadmap/11-architecture/02-connection-pooling.md)
- **并发模型本身(GIL / asyncio / 着色)** → [`../python/13`](../python/13-concurrency-bridge.md)、[`../python-concurrency/`](../python-concurrency/)
- **Web 服务可观测性(查询追踪 / 慢查询)** → [`../fastapi-ops/`](../fastapi-ops/)、[`../observability/`](../observability/)
