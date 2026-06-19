# 22 · 数据访问(桥接章)

> **为什么这章重要**:几乎每个后端服务都要跟数据库打交道,而 Python 这一层(driver / 连接池 / Core / ORM / 事务 / 迁移)是把「会写 Python」变成「能搭生产服务」的关键一段。这章只解决一件事:**面对数据访问,几个核心选择怎么做?** 把选型心智建起来。
>
> **本章是桥接,不是全部**。每条路的机制、内幕、实操、可跑实验,在仓库的 [`../python-data/`](../python-data/)——那是架构师级的专题目录,还带一个真 Postgres lab(池耗尽 / N+1 / 隔离 / async 吞吐都有实测数字)。本章给你决策树,细节去那里。

## 一、全景:从你的代码到数据库,四层

```
业务代码 → SQLAlchemy(ORM / Core) → DBAPI driver(psycopg / asyncpg) → 连接 → 数据库
```

- **DBAPI**:Python 的数据库接口规范(PEP 249,≈JDBC),driver 实现它。
- **Core**:SQL 表达式语言,你掌控 SQL 形状。
- **ORM**:对象映射 + Session(身份/脏跟踪/关系),省事但 SQL 由它生成。
- **连接**:贵资源,要池化。

记忆:**Core 和 ORM 不是「初级 vs 高级」,是两种抽象高度**,同项目可混用。

## 二、四个核心选择(决策树)

### 1. 要不要 ORM?

```
CRUD 业务密集、关系多        ► ORM(对象映射 + Session 省样板)
读多写少 / 报表 / 批量        ► Core 或 raw SQL(掌控 SQL,别让 ORM 碍事)
一次性脚本                   ► 裸 DBAPI 就够
```

一句话:**ORM 的价值在「行变对象 + 自动追踪变更」**;不需要对象图就别上 ORM。

### 2. Core 还是 ORM?

操作对象、要关系导航 → ORM;操作行/列、要可控 SQL(批量/报表)→ Core。同 engine 混用,切换零成本。

### 3. sync 还是 async?

```
常规并发 + 阻塞栈(WSGI)            ► sync(psycopg3)—— 默认,简单,不传染
海量并发连接 + 全异步栈(ASGI)      ► async(asyncpg)
```

接 [第 13 章](13-concurrency-bridge.md) 的「着色」结论:**async 不是更快,是同线程扛更多并发等待**;`await` 会沿调用链传染,无法局部异步——**架构级决定**,项目一开始就定。

### 4. 事务边界放哪?

**一个业务操作 = 一个事务 = 一次 commit**。Web 里用 **session-per-request**(一请求一 Session 一事务)。事务里**绝不夹外部 IO**(HTTP/RPC),否则连接被长占、拖垮连接池。

## 三、两个一句话心智(出事时先想这俩)

- **N+1**:关系懒加载 + 循环里逐个访问 = 1 + N 条查询(慢在「条数 × 往返」)。**先数 SQL 条数**发现它,用 `selectinload`/`joinedload` 压平。
- **连接池**:`pool_size + max_overflow` 是并发硬上限,借不到等满 `pool_timeout` 报错。池耗尽多半是**连接泄漏**(没用 `with` / 长事务),不是池太小。

## 四、去 `python-data/` 深入

本章只够「选对方向」。机制、内幕、实操在专题目录:

| 主题 | 去处 |
|---|---|
| 心智与选型(全景 + 决策树) | [`../python-data/00`](../python-data/00-mindset-and-selection.md) |
| 驱动与 DBAPI(参数化机制、协议往返) | [`../python-data/01`](../python-data/01-drivers-and-dbapi.md) |
| 连接池(QueuePool 参数、池耗尽排查) | [`../python-data/02`](../python-data/02-connection-pooling.md) |
| ORM:Session / UoW / 加载策略 | [`../python-data/03`](../python-data/03-orm-session-uow.md) |
| 事务边界与并发控制(乐观锁、序列化失败) | [`../python-data/04`](../python-data/04-transactions.md) |
| N+1 与查询性能(selectinload、读 EXPLAIN) | [`../python-data/05`](../python-data/05-n-plus-one-and-query-perf.md) |
| 异步数据访问(greenlet 桥、值不值) | [`../python-data/06`](../python-data/06-async-data-access.md) |
| 迁移与 schema 演进(Alembic、zero-downtime) | [`../python-data/07`](../python-data/07-migrations.md) |
| 架构权衡与测试(repository、真 DB 测试) | [`../python-data/08`](../python-data/08-architecture-and-testing.md) |
| 可跑 Postgres lab(四个现象实测) | [`../python-data/lab/`](../python-data/lab/) |
| 数据访问面试卡 | [`../python-data/99`](../python-data/99-interview-cards.md) |

## Java/Go 对照框

| 关注点 | Java | Go | Python |
|---|---|---|---|
| 底层接口 | JDBC | `database/sql` | DBAPI(PEP 249) |
| 控 SQL 中层 | MyBatis | `sqlx` | SQLAlchemy Core |
| 对象 ORM | Hibernate/JPA | GORM/ent | SQLAlchemy ORM |
| 连接池 | HikariCP | `database/sql` 内建 | SQLAlchemy QueuePool |
| 异步 | 虚拟线程/R2DBC(不传染) | goroutine(不传染) | asyncio+asyncpg(**传染**) |

记忆:**MyBatis≈Core、Hibernate≈ORM、HikariCP≈QueuePool**。最大差异:Go/新 Java 用 runtime 屏蔽异步(同步写法拿并发),Python 的 async 是显式 `await` 且传染——所以「要不要 async 数据层」在 Python 是个真取舍。

## 章末面试卡

**Q1. SQLAlchemy 的 Core 和 ORM 怎么选?**
Core 控 SQL、适合批量/报表;ORM 对象映射 + Session、适合 CRUD/领域写;同 engine 混用。详见 [python-data/00](../python-data/00-mindset-and-selection.md)。

**Q2. 什么时候不该用 ORM?**
读多写少的聚合/报表、一次性脚本——ORM 是开销 + N+1 黑箱。详见 [python-data/00](../python-data/00-mindset-and-selection.md)、[05](../python-data/05-n-plus-one-and-query-perf.md)。

**Q3. N+1 是什么、怎么发现?**
懒加载 + 循环访问关系 = 1+N 条查询,慢在往返次数。先数 SQL 条数,用 selectinload 压平。详见 [python-data/05](../python-data/05-n-plus-one-and-query-perf.md)。

**Q4. 连接池耗尽什么现象?**
借不到连接等满 pool_timeout 报 `QueuePool limit ... timed out`,常因连接泄漏。详见 [python-data/02](../python-data/02-connection-pooling.md)。

**Q5. sync 和 async 数据访问怎么选?是小决定吗?**
不是。常规并发用 sync(psycopg3),海量并发 + 全异步栈才用 async(asyncpg);async 会着色传染、是架构级决定。详见 [python-data/06](../python-data/06-async-data-access.md)。

**Q6. 事务边界该放哪?**
包住一个业务操作(session-per-request),事务里不夹外部 IO。详见 [python-data/04](../python-data/04-transactions.md)。
