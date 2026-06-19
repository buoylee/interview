# 设计:`python-data/` — Python 数据访问架构

> 日期:2026-06-19 ｜ 状态:已核准设计,待写实作计画
> 目标读者:7 年 Java/Go 后端 + 1 年全栈,补 Python 到**架构师级**的数据访问判断力。

## 1. 背景与动机

`python/` 教程把人带到「资深 Python 语言专家」,但 README 自陈聚焦**语言本身**,数据访问层不在其 charter。盘点全仓后确认:Python 端「从进程到数据库这一层」**没有一条架构视角的主线**,只碎在各处——

- `performance-tuning-roadmap/11-architecture/02-connection-pooling.md`:只从**性能**角度讲连接池。
- `fastapi-ops/`:SQLAlchemy 只当 **ops/追踪**的范例。
- `python/18-security.md`:SQL 注入只当**安全**点。
- `mysql/`、`DB/`、`transaction/`、`distr-tx/`:**DB 引擎 / SQL 层**,语言无关,不是「Python 服务怎么跟 DB 打交道」。

这一层(driver、连接池、Core/ORM、Session/UoW、事务边界、N+1、async、迁移、repository)正是把 Python 从 senior 抬到架构师的关键缺口。

## 2. 范围与边界

- **锚点**:Postgres 16 + SQLAlchemy 2.0(async 为主),纯开源。
- **IN**:从 Python 进程到 DB 之间那一层的机制**与架构判断**——DBAPI/driver、连接池、Core vs ORM、Session/Unit-of-Work、事务边界与并发控制、N+1 与查询性能(应用侧)、async 数据访问、Alembic 迁移、repository / 数据层测试。全程编入「**该不该用 ORM、何时下沉 raw SQL**」的判断。
- **OUT(只给指针,不重写)**:
  - DB 引擎 / SQL 调优、隔离级别理论 → `mysql/`、`transaction/`
  - 分布式 / 分片 / 分布式事务 → `distr-tx/`、`Sharding-Sphere/`
  - 缓存与多存储编排 → `redis/`
  - 连接池的纯性能篇 → `performance-tuning-roadmap/11-architecture/02-connection-pooling.md`(本目录讲机制与排查,不重写性能数字篇)
  - 并发模型本身(GIL、着色、asyncio 实操)→ `python/13`、`python-concurrency/`

## 3. 定位与摆放

照 repo 既有范式(`python/13` 并发桥接章 → `python-concurrency/`):

- **桥接章** `python/22-data-access-bridge.md`:只讲「怎么选 driver / Core vs ORM / sync vs async + 事务一句话心智」,接住面试的「为什么 / 怎么选」,深度指向下方。
- **独立深水目录** `python-data/`:架构师级深度 + 可跑 lab。
- **README 整合**:`python/README.md`「与仓库其他目录的关系」加第 4 条指针(数据访问深度 → `../python-data/`);章节 TOC 表加 ch22。

## 4. 章节大纲(`python-data/`)

| # | 章 | 核心 | lab |
|---|---|---|---|
| 00 | 心智与选型(全景) | 这一层全景;DBAPI→Core→ORM 的层次;sync/async、要不要 ORM 的总判断。对照 JDBC/Hibernate/MyBatis、`database/sql`/sqlx/GORM | — |
| 01 | 驱动与 DBAPI | PEP 249、psycopg3 vs asyncpg、参数化(注入回指 `python/18`)、**一次 execute 的协议往返内幕** | — |
| 02 | 连接池 | QueuePool 参数(pool_size/max_overflow/timeout/recycle/pre_ping)、池耗尽现象与排查、pgbouncer 与应用池关系、async 池。对照 HikariCP | ✅ 池耗尽复现 |
| 03 | ORM 机制:Session / UoW / 加载策略 | identity map、flush vs commit、lazy vs eager loading、session 生命周期——**N+1 的根源章**。对照 Hibernate persistence context | — |
| 04 | 事务边界与并发控制 | session-per-request、commit 放哪、隔离级别从应用侧看、乐观锁(version_id)、序列化失败重试 | ✅ 隔离级别行为 |
| 05 | N+1 与查询性能(应用侧) | 怎么发现(echo / SQL 计数)、selectinload/joinedload、何时下沉 raw SQL、**从 Python 读 EXPLAIN** | ✅ N+1 修复前后查询数/时延 |
| 06 | 异步数据访问 | async engine/session、asyncpg、greenlet 桥、async 下的池、值不值(回指 `python/13` 着色) | ✅ async vs sync 吞吐 |
| 07 | 迁移与 schema 演进 | Alembic、autogenerate 边界、zero-downtime 模式(加列/改列/CONCURRENTLY 建索引)、迁移与部署顺序。对照 Flyway/Liquibase | — |
| 08 | 架构权衡与测试(判断层收口) | repository vs active-record vs 直接用 session、领域模型 / 持久化模型解耦、数据层测试(事务回滚 fixture vs testcontainers) | — |
| 99 | 面试卡 | 高频题 + 猜行为 drill 汇总 | — |

## 5. Lab(`python-data/lab/`)

```
docker-compose.yml      # postgres:16
pyproject.toml          # uv: sqlalchemy[asyncio], asyncpg, psycopg, alembic
seed.py                 # 建表 + 灌可复现数据
demos/
  pool_exhaustion.py    # 池耗尽 → TimeoutError 现形
  n_plus_one.py         # before/after,打印查询数 + timing
  isolation.py          # 两 session 撞出 serialization failure
  async_vs_sync.py      # N 并发查询吞吐对比
README.md               # 怎么跑 + 回填的真数字
```

**真数字流程**:实作时把 Postgres 拉起来(优先启动 Docker daemon 跑 `docker-compose`;若 daemon 不可用,退而用本地 pg cluster)跑每个 demo,把真实 EXPLAIN / timing / query-count / 错误输出回填进对应章节,标注「Postgres 16 / 本地、你的数字会不同」。lab 可跑、输出可复现。读者自学时读得到数字,想跑也能跑——**不需要读者跑完回报**。

环境已确认:Python 3.11.8、SQLAlchemy 2.0.34、uv 0.7.13、psql client 在位;Docker daemon 当前关闭(实作时启动)。

## 6. 房屋风格(沿用 `python/` 既定惯例)

每章固定结构:**导引(为什么重要 + 一句话心智)→ 正文由浅入深(底层内幕写进正文,不 defer 到问答)→ 生态 / Java-Go 对照框(平衡,不绑死 Java,配 Go/Python 等价物)→ 章末面试卡(只当复习自检层,不承载新知识)**。

- 代码块都能直接跑;CPython 3.11 基线实测,3.12+ 语法单独标注并给 3.11 等价写法。
- 面试向:接得住「猜行为 / 解释陷阱 / 为什么 / 怎么选」追问。

## 7. 命名与编号决定

- 目录名:`python-data/`(对齐 `python-concurrency/`)。
- 桥接章:`python/22-data-access-bridge.md`(现有章节到 21 + 99)。

## 8. 交付方式

章节逐章增量交付(非一次性长文倾倒);lab 与对应章节配套产出。每章产出后即可独立阅读。

## 9. 成功标准

读者读完后能够:

1. 对一个 Python 服务的数据访问,**做出并辩护**:用不用 ORM、Core vs ORM、sync vs async、池参数怎么定。
2. 解释 N+1 怎么产生、怎么发现、几种修法的取舍,并能从 Python 侧读 EXPLAIN。
3. 设计事务边界(session-per-request、commit 位置、乐观锁、重试),说清隔离级别从应用侧的可见行为。
4. 规划 zero-downtime 迁移。
5. 答得上对应面试追问(章末面试卡 + 99 汇总)。
