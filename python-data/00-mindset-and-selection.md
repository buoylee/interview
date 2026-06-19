# 00 · 心智与选型:这一层怎么搭、要不要 ORM

> **为什么这章重要**:数据访问的所有细节,都长在三个**先决选择**上——**要不要 ORM?Core 还是 ORM?sync 还是 async?** 选错了,后面再多技巧也是在错的地基上打补丁。这章给你这一层的全景图和三棵决策树,后面每章是其中一格的展开。
>
> **一句话心智**:你写的不是「SQL」也不是「对象」,你在操作**一条到数据库的连接**;ORM / Core 只是这条连接之上不同抽象高度的两副手套。

> 本目录聚焦「**Python 进程 → 数据库**之间这一层」。DB 引擎本身(索引、SQL 调优、隔离级别原理)在 [`../mysql/`](../mysql/)、[`../transaction/`](../transaction/);分布式/分片在 [`../distr-tx/`](../distr-tx/)、[`../Sharding-Sphere/`](../Sharding-Sphere/);缓存/多存储在 [`../redis/`](../redis/)。这里只讲应用侧怎么把这条连接用好。

## 一、全景:四层,从你的代码到数据库

```
你的业务代码
    │  对象 / 领域模型
┌───▼─────────────────────────────────────────────┐
│ SQLAlchemy                                       │
│   ORM 层    Session / 实体 / 关系 / 加载策略       │  ← 抽象高:对象, 自动生成 SQL
│   Core 层   Table / select() / 表达式语言          │  ← 抽象中:你控 SQL 形状
├──────────────────────────────────────────────────┤
│ DBAPI driver  psycopg3(sync) / asyncpg(async)    │  ← PEP 249 统一接口
└───┬──────────────────────────────────────────────┘
    │  连接(TCP / Unix socket)+ 协议往返
┌───▼──────┐
│ Postgres │
└──────────┘
```

四层各管一件事:

- **DBAPI driver**(第 [01](01-drivers-and-dbapi.md) 章):最底层,Python 跟数据库通话的标准接口(PEP 249)。`connect → cursor → execute → fetch`。一切都压在它上面。
- **Core**(第 [03](03-orm-session-uow.md) 章里对比):SQLAlchemy 的 SQL 表达式语言。你用 Python 拼出 `select(...).where(...)`,它生成 SQL——**SQL 的形状由你掌控**,但不替你管对象。
- **ORM**:在 Core 之上再加一层对象映射——表 ↔ 类、行 ↔ 实例、外键 ↔ 关系属性,外加一个 **Session** 帮你记账(谁脏了、何时 flush)。**方便,但 SQL 是它替你生成的**,N+1 这类问题就藏在这一层。
- **连接**:贵资源,要池化(第 [02](02-connection-pooling.md) 章)。

关键认知:**Core 和 ORM 不是「初级 vs 高级」,是「两种抽象高度」**,同一个项目里可以混用——领域写操作用 ORM,报表/批量用 Core,极端热点下沉 raw SQL。

## 二、同一个查询,三种写法

「查 id=1 作者的所有书名」,从底到高:

```python
# 1) 裸 DBAPI(driver 直接来,最贴 SQL,无任何映射)
import psycopg
with psycopg.connect("postgresql://postgres:postgres@localhost/datalab") as conn:
    rows = conn.execute(
        "SELECT title FROM books WHERE author_id = %s", (1,)
    ).fetchall()
    titles = [r[0] for r in rows]

# 2) SQLAlchemy Core(表达式语言;SQL 形状你定,但跨方言可移植)
from sqlalchemy import create_engine, select, MetaData, Table
engine = create_engine("postgresql+psycopg://postgres:postgres@localhost/datalab")
md = MetaData()
books = Table("books", md, autoload_with=engine)
with engine.connect() as conn:
    titles = conn.scalars(
        select(books.c.title).where(books.c.author_id == 1)
    ).all()

# 3) ORM(对象进对象出;关系、身份、脏跟踪都由 Session 管)
from sqlalchemy.orm import Session
with Session(engine) as s:
    author = s.get(Author, 1)        # 一个对象
    titles = [b.title for b in author.books]   # 关系属性,SQL 由 ORM 生成
```

往下走 = 更贴 SQL、更可控、更啰嗦;往上走 = 更像在操作对象、更省事、SQL 离你更远。**「SQL 离你多远」就是这一层所有取舍的总开关**——离得近你掌控也背负细节,离得远你省事但黑箱里会冒 N+1。

## 三、三棵决策树

### 1. 要不要用 ORM?

```
你的负载主要是什么?
├── CRUD 业务密集(增删改查对象、关系多、领域逻辑重)
│       ► ORM。对象映射 + Session 记账省掉大量样板
├── 读多写少 / 报表 / 复杂聚合 / 批量
│       ► Core 或 raw SQL。你要掌控 SQL 形状,ORM 反而碍事
└── 一次性脚本 / 极简
        ► 裸 DBAPI 就够,别为三行查询拖进一个 ORM
```

判断句:**ORM 的价值在「把行变成有行为的对象、并自动追踪变更」**。你的业务如果根本不需要对象图(就是一堆 SELECT 聚合),ORM 给你的全是开销和黑箱。资深的标志不是「会用 ORM」,是**知道什么时候不用**。

### 2. Core 还是 ORM?

| 维度 | Core | ORM |
|---|---|---|
| 你操作的 | 行 / 列 / 表达式 | 对象 / 关系 |
| SQL 形状 | **你定** | 它生成 |
| 适合 | 批量、报表、可控查询、迁移脚本 | 领域写操作、CRUD、关系导航 |
| N+1 风险 | 几乎没有(你自己写 JOIN) | **有**(懒加载) |
| 上手 | 啰嗦但透明 | 省事但有「魔法」|

混用是常态:一个项目里 90% 走 ORM,导报表那几个接口切 Core。**它俩共享同一个 engine 和连接池**,切换零成本。

### 3. sync 还是 async?

```
你的服务并发形态?
├── 常规并发(几十~几百并发)、用阻塞栈(WSGI / 同步框架)
│       ► sync(psycopg3)。简单、不会函数着色传染
└── 海量并发连接(成千上万)、且全链路异步(ASGI / FastAPI + async)
        ► async(asyncpg)。详见第 06 章;代价是 async 着色传染整条调用链
```

这条直接接 [`../python/13`](../python/13-concurrency-bridge.md) 的「着色」结论:**async 不是「更快」,是「同样的线程扛住更多并发等待」**;一旦选了,`await` 会沿调用链蔓延,无法局部异步。所以是**架构级决定**,不是随手切。详见第 [06](06-async-data-access.md) 章(那里有 sync vs async 的实测吞吐对比)。

## 四、本目录地图

| 章 | 一句话 |
|---|---|
| [01 驱动与 DBAPI](01-drivers-and-dbapi.md) | PEP 249、psycopg3 vs asyncpg、参数化、一次 execute 的协议往返 |
| [02 连接池](02-connection-pooling.md) | 为什么要池、QueuePool 参数、池耗尽现象与排查 |
| [03 ORM:Session / UoW / 加载策略](03-orm-session-uow.md) | identity map、flush vs commit、lazy/eager——N+1 的根源 |
| [04 事务边界与并发控制](04-transactions.md) | 边界放哪、隔离级别、乐观锁、序列化失败重试 |
| [05 N+1 与查询性能](05-n-plus-one-and-query-perf.md) | 怎么发现、selectinload/joinedload、何时下沉 raw SQL、读 EXPLAIN |
| [06 异步数据访问](06-async-data-access.md) | async engine/session、asyncpg、greenlet 桥、值不值 |
| [07 迁移与 schema 演进](07-migrations.md) | Alembic、autogenerate 边界、zero-downtime 模式 |
| [08 架构权衡与测试](08-architecture-and-testing.md) | repository?、领域/持久化解耦、数据层测试 |
| [99 面试卡](99-interview-cards.md) | 各章高频题 + 猜行为 drill |
| [lab/](lab/) | 可跑的 Postgres 实验:池耗尽 / N+1 / 隔离 / async 吞吐 |

## Java/Go 对照框

| 关注点 | Java | Go | Python |
|---|---|---|---|
| 底层接口 | JDBC | `database/sql` | DBAPI(PEP 249) |
| 控 SQL 的中层 | MyBatis(SQL 映射) | `sqlx`(给 `database/sql` 加便利) | **SQLAlchemy Core** |
| 对象映射 ORM | Hibernate / JPA | GORM / ent | **SQLAlchemy ORM** |
| 异步 | 同步 + 虚拟线程 / R2DBC | 同步驱动 + goroutine | **asyncio + asyncpg(显式着色)** |

对照记忆:**MyBatis ≈ Core**(手控 SQL),**Hibernate ≈ ORM**(对象 + 持久化上下文)。Go 没有重 ORM 传统,主流是 `database/sql`/`sqlx` 手写 SQL——这其实和「Python 里能用 Core 就别上 ORM」的务实派同源。你从 Java 带来的「Hibernate 一切皆对象」直觉,在 Python 社区会被「能少点魔法就少点」的风气拉回来一些。

## 章末面试卡

**Q1. SQLAlchemy 的 Core 和 ORM 有什么区别?怎么选?**
Core 是 SQL 表达式语言,你操作表/列/表达式,自己掌控 SQL 形状,适合批量/报表/可控查询;ORM 在 Core 之上加对象映射 + Session(身份、脏跟踪、关系、加载策略),适合 CRUD 和领域写操作。同一 engine 上可混用——大部分走 ORM,报表那几条切 Core。

**Q2. 什么时候根本不该用 ORM?**
负载主要是读多写少的聚合/报表、或一次性脚本时:ORM 的对象映射和 Session 记账纯属开销,还把 SQL 藏进黑箱(N+1 风险)。这种用 Core 或 raw SQL 更透明可控。「会用 ORM」不算资深,「知道何时不用」才算。

**Q3. SQLAlchemy 在整个分层里处在哪一层?它和 driver 是什么关系?**
SQLAlchemy 是 driver(DBAPI)之上的两层:Core(SQL 表达式)和 ORM(对象映射)。它不直接跟数据库通话,而是把生成的 SQL 交给底层 DBAPI driver(psycopg3 / asyncpg)执行。换 driver 只改 URL 前缀,上层代码不动。

**Q4. sync 和 async 的数据访问怎么选?这是个小决定吗?**
不是。常规并发 + 阻塞栈用 sync(psycopg3);海量并发连接 + 全异步栈(ASGI)才用 async(asyncpg)。async 不是「更快」,是用同样线程扛更多并发等待;而且 `await` 会沿调用链传染(着色),无法局部异步——所以是架构级决定。详见第 06 章。
