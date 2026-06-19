# python-data 数据访问架构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个架构师级的 `python-data/` 自学目录(9 章 + 面试卡)+ 桥接章 `python/22`,配一个可跑的 Postgres lab,真数字实测回填。

**Architecture:** 照 repo 既有范式(`python/13` 桥接章 → `python-concurrency/`)。先建 lab 跑出真实输出(Phase A),再写引用这些数字的章节(Phase B),最后做桥接章与 README 整合(Phase C)。

**Tech Stack:** Python 3.11、SQLAlchemy 2.0(async 为主)、psycopg3 + asyncpg、Alembic、Postgres 16(docker-compose)、uv。

## Global Constraints

- 锚点:Postgres 16 + SQLAlchemy 2.0(2.0 风格:`DeclarativeBase`/`Mapped`/`mapped_column`)。纯开源。
- 基线 CPython **3.11**;3.12+ 语法单独标注并给 3.11 等价写法。
- 房屋风格(每章固定):**导引(为什么重要 + 一句话心智)→ 正文由浅入深(底层内幕写进正文,不 defer 到问答)→ 生态/Java-Go 对照框(平衡,不绑死 Java,配 Go/Python 等价物)→ 章末面试卡(只当复习自检层)**。
- 代码块都能直接跑。
- 边界:只覆盖「Python 进程 → DB 之间这一层」。DB 引擎/SQL 调优 → 指 `mysql/`、`transaction/`;分布式/分片 → 指 `distr-tx/`、`Sharding-Sphere/`;缓存/多存储 → 指 `redis/`;池的纯性能篇 → 指 `performance-tuning-roadmap/11-architecture/02-connection-pooling.md`;并发模型本身 → 指 `python/13`、`python-concurrency/`。
- 真数字:lab 输出实测回填章节,标注「Postgres 16 / 本地、你的数字会不同」。
- 目录名 `python-data/`;桥接章 `python/22-data-access-bridge.md`。

---

# Phase A — Lab(先跑出真数字)

> 本阶段需要 Postgres 16 在线。Task A1 负责拉起;若 Docker daemon 关闭,先 `open -a Docker` 等待就绪,或退用本地 pg cluster。Phase A 完成后 Postgres 可关。

### Task A1: Lab 脚手架 + 建库灌数据

**Files:**
- Create: `python-data/lab/docker-compose.yml`
- Create: `python-data/lab/pyproject.toml`
- Create: `python-data/lab/db.py`
- Create: `python-data/lab/models.py`
- Create: `python-data/lab/seed.py`

**Interfaces:**
- Produces(后续 demo 全部 import 这些):
  - `db.make_engine(**kw) -> Engine`(sync,`postgresql+psycopg://`)
  - `db.make_async_engine(**kw) -> AsyncEngine`(`postgresql+asyncpg://`)
  - `db.SYNC_URL: str` / `db.ASYNC_URL: str`
  - `models.Base`、`models.Author(id,name,books)`、`models.Book(id,author_id,title,published_year,author)`、`models.Account(id,balance)`
  - 数据集:20 authors × 5 books = 100 books;`accounts(id=1, balance=100)`

- [ ] **Step 1: 写 docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: datalab
    ports:
      - "5432:5432"
```

- [ ] **Step 2: 写 pyproject.toml**

```toml
[project]
name = "python-data-lab"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy[asyncio]>=2.0",
    "psycopg[binary]>=3.1",
    "asyncpg>=0.29",
    "alembic>=1.13",
]
```

- [ ] **Step 3: 写 db.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

_HOST = os.environ.get("PG_HOST", "localhost:5432/datalab")
_USER = os.environ.get("PG_USER", "postgres")
_PWD = os.environ.get("PG_PASSWORD", "postgres")

SYNC_URL = f"postgresql+psycopg://{_USER}:{_PWD}@{_HOST}"
ASYNC_URL = f"postgresql+asyncpg://{_USER}:{_PWD}@{_HOST}"

def make_engine(**kw):
    return create_engine(SYNC_URL, **kw)

def make_async_engine(**kw):
    return create_async_engine(ASYNC_URL, **kw)
```

- [ ] **Step 4: 写 models.py**

```python
from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    books: Mapped[list["Book"]] = relationship(back_populates="author")

class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    title: Mapped[str] = mapped_column(String(200))
    published_year: Mapped[int] = mapped_column(Integer)
    author: Mapped["Author"] = relationship(back_populates="books")

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int] = mapped_column(Integer)
```

- [ ] **Step 5: 写 seed.py**

```python
from sqlalchemy.orm import Session
from db import make_engine
from models import Base, Author, Book, Account

def main():
    engine = make_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for a in range(1, 21):
            author = Author(name=f"Author {a}")
            s.add(author)
            s.flush()
            for b in range(1, 6):
                s.add(Book(author_id=author.id, title=f"Book {a}-{b}",
                           published_year=2000 + b))
        s.add(Account(id=1, balance=100))
        s.commit()
    print("seeded: 20 authors, 100 books, 1 account")

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 拉起 Postgres**

Run: `docker compose -f python-data/lab/docker-compose.yml up -d`
若 daemon 关闭:先 `open -a Docker`,轮询 `docker info` 直到就绪再重试;仍不可用则用本地 pg cluster(`initdb`/`pg_ctl` 或 brew postgresql),并相应导出 `PG_HOST/PG_USER/PG_PASSWORD`。
Expected: 容器 `Up`,`5432` 可连。

- [ ] **Step 7: 装依赖并灌数据**

Run:
```bash
cd python-data/lab && uv sync && uv run python seed.py
```
Expected: `seeded: 20 authors, 100 books, 1 account`

- [ ] **Step 8: Commit**

```bash
git add python-data/lab/docker-compose.yml python-data/lab/pyproject.toml python-data/lab/uv.lock python-data/lab/db.py python-data/lab/models.py python-data/lab/seed.py
git commit -m "feat(python-data): lab 脚手架 + Postgres 建库灌数据"
```

---

### Task A2: demo — 连接池耗尽

**Files:**
- Create: `python-data/lab/demos/pool_exhaustion.py`
- Modify: `python-data/lab/CAPTURED.md`(create if absent)

**Interfaces:**
- Consumes: `db.make_engine`
- Produces: `CAPTURED.md` 段「pool_exhaustion」记录真实 TimeoutError 文本 + 等待秒数(供 ch02 引用)

- [ ] **Step 1: 写 demos/pool_exhaustion.py**

```python
import time, threading
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SATimeoutError
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from db import make_engine

engine = make_engine(pool_size=2, max_overflow=0, pool_timeout=1)

def hold(i, secs):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print(f"conn {i}: acquired")
        time.sleep(secs)
    print(f"conn {i}: released")

for i in range(2):                       # 占满 pool_size=2
    threading.Thread(target=hold, args=(i, 3), daemon=True).start()
time.sleep(0.5)

t0 = time.perf_counter()
try:
    with engine.connect() as conn:       # 第 3 个请求:无可用连接
        conn.execute(text("SELECT 1"))
except SATimeoutError as e:
    print(f"conn 2: TimeoutError after {time.perf_counter()-t0:.2f}s -> {e}")
```

- [ ] **Step 2: 跑并观察现象**

Run: `cd python-data/lab && uv run python demos/pool_exhaustion.py`
Expected: 两行 `acquired`,然后约 1.0s 后打印 `TimeoutError after ~1.0s -> QueuePool limit of size 2 overflow 0 reached, connection timed out`。

- [ ] **Step 3: 回填真实输出到 CAPTURED.md**

把上一步真实 stdout 粘进 `CAPTURED.md` 的 `## pool_exhaustion` 段,记下 timeout 文本与秒数。

- [ ] **Step 4: Commit**

```bash
git add python-data/lab/demos/pool_exhaustion.py python-data/lab/CAPTURED.md
git commit -m "feat(python-data): pool 耗尽 demo + 实测输出"
```

---

### Task A3: demo — N+1

**Files:**
- Create: `python-data/lab/demos/n_plus_one.py`
- Modify: `python-data/lab/CAPTURED.md`

**Interfaces:**
- Consumes: `db.make_engine`、`models.Author`
- Produces: `CAPTURED.md` 段「n_plus_one」:before(查询数/时延)与 after(查询数/时延)

- [ ] **Step 1: 写 demos/n_plus_one.py**

```python
import time, sys, pathlib
from sqlalchemy import event, select
from sqlalchemy.orm import Session, selectinload
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from db import make_engine
from models import Author

engine = make_engine()
counter = {"n": 0}

@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, params, context, executemany):
    counter["n"] += 1

def run(label, use_eager):
    counter["n"] = 0
    t0 = time.perf_counter()
    with Session(engine) as s:
        stmt = select(Author)
        if use_eager:
            stmt = stmt.options(selectinload(Author.books))
        authors = s.scalars(stmt).all()
        total = sum(len(a.books) for a in authors)   # 触发 books 加载
    dt = (time.perf_counter() - t0) * 1000
    print(f"{label}: {counter['n']} queries, {total} books, {dt:.1f} ms")

run("N+1 (lazy)", use_eager=False)
run("fixed (selectinload)", use_eager=True)
```

- [ ] **Step 2: 跑并观察现象**

Run: `cd python-data/lab && uv run python demos/n_plus_one.py`
Expected: `N+1 (lazy): 21 queries, 100 books, ...`(1 查 authors + 20 查 books);`fixed (selectinload): 2 queries, 100 books, ...`。after 时延明显更低。

- [ ] **Step 3: 回填 CAPTURED.md** — `## n_plus_one` 段记两行真实输出(21 vs 2 + 真实 ms)。

- [ ] **Step 4: Commit**

```bash
git add python-data/lab/demos/n_plus_one.py python-data/lab/CAPTURED.md
git commit -m "feat(python-data): N+1 demo + 实测查询数/时延"
```

---

### Task A4: demo — 事务隔离(序列化失败)

**Files:**
- Create: `python-data/lab/demos/isolation.py`
- Modify: `python-data/lab/CAPTURED.md`

**Interfaces:**
- Consumes: `db.make_engine`(`isolation_level="SERIALIZABLE"`)
- Produces: `CAPTURED.md` 段「isolation」:真实序列化失败错误类名/SQLSTATE

- [ ] **Step 1: 写 demos/isolation.py**

```python
import sys, pathlib
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from db import make_engine

engine = make_engine(isolation_level="SERIALIZABLE")
c1, c2 = engine.connect(), engine.connect()
t1, t2 = c1.begin(), c2.begin()

b1 = c1.execute(text("SELECT balance FROM accounts WHERE id=1")).scalar()
b2 = c2.execute(text("SELECT balance FROM accounts WHERE id=1")).scalar()
print(f"both read balance={b1}")

c1.execute(text("UPDATE accounts SET balance=:b WHERE id=1"), {"b": b1 - 10})
t1.commit()
print("tx1 committed -> balance=90")

try:
    c2.execute(text("UPDATE accounts SET balance=:b WHERE id=1"), {"b": b2 - 10})
    t2.commit()
    print("tx2 committed (unexpected)")
except DBAPIError as e:
    t2.rollback()
    print(f"tx2 serialization failure: {type(e.orig).__name__} / "
          f"sqlstate={getattr(e.orig, 'sqlstate', getattr(e.orig, 'pgcode', '?'))}")
finally:
    c1.close(); c2.close()
```

- [ ] **Step 2: 跑并观察现象**

Run: 先 `uv run python seed.py` 复位 balance,再 `uv run python demos/isolation.py`
Expected: `both read balance=100` → `tx1 committed` → `tx2 serialization failure: ...`(SQLSTATE 40001 could_not_serialize_access)。

- [ ] **Step 3: 回填 CAPTURED.md** — `## isolation` 段记真实错误类名 + SQLSTATE。

- [ ] **Step 4: Commit**

```bash
git add python-data/lab/demos/isolation.py python-data/lab/CAPTURED.md
git commit -m "feat(python-data): 事务隔离序列化失败 demo + 实测错误"
```

---

### Task A5: demo — async vs sync 吞吐

**Files:**
- Create: `python-data/lab/demos/async_vs_sync.py`
- Modify: `python-data/lab/CAPTURED.md`

**Interfaces:**
- Consumes: `db.make_engine`、`db.make_async_engine`
- Produces: `CAPTURED.md` 段「async_vs_sync」:sync 总时延、async 总时延、speedup

- [ ] **Step 1: 写 demos/async_vs_sync.py**

```python
import asyncio, time, sys, pathlib
from sqlalchemy import text
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from db import make_engine, make_async_engine

N, SLEEP = 20, 0.05   # 模拟每次查询 50ms 往返延迟

def sync_run():
    engine = make_engine()
    t0 = time.perf_counter()
    with engine.connect() as conn:
        for _ in range(N):
            conn.execute(text("SELECT pg_sleep(:s)"), {"s": SLEEP})
    engine.dispose()
    return time.perf_counter() - t0

async def async_run():
    engine = make_async_engine(pool_size=N)
    async def one():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT pg_sleep(:s)"), {"s": SLEEP})
    t0 = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(N)])
    await engine.dispose()
    return time.perf_counter() - t0

s = sync_run()
a = asyncio.run(async_run())
print(f"sync : {N} queries x {SLEEP}s sequential = {s:.2f}s")
print(f"async: {N} concurrent                   = {a:.2f}s  (speedup {s/a:.1f}x)")
```

- [ ] **Step 2: 跑并观察现象**

Run: `cd python-data/lab && uv run python demos/async_vs_sync.py`
Expected: sync ≈ 1.0s(20×0.05 串行);async ≈ 0.05–0.2s;speedup 数倍。

- [ ] **Step 3: 回填 CAPTURED.md** — `## async_vs_sync` 段记真实两行 + speedup。

- [ ] **Step 4: Commit**

```bash
git add python-data/lab/demos/async_vs_sync.py python-data/lab/CAPTURED.md
git commit -m "feat(python-data): async vs sync 吞吐 demo + 实测 speedup"
```

---

### Task A6: lab README

**Files:**
- Create: `python-data/lab/README.md`

- [ ] **Step 1: 写 lab/README.md**,含:
  - 一句话:这个 lab 用真实 Postgres 复现数据访问的四个核心现象。
  - 前置:Docker(或本地 pg);`docker compose up -d` → `uv sync` → `uv run python seed.py`。
  - 四个 demo 各一行说明 + 运行命令。
  - 「实测数字」表:从 `CAPTURED.md` 汇总(pool 等待秒数、N+1 21→2、隔离 SQLSTATE 40001、async speedup),标注「Postgres 16 / 本地、你的数字会不同」。
  - 收尾指针:各现象的讲解在 `../0X-*.md`。

- [ ] **Step 2: 校对运行命令可跑**(对照 Task A1–A5 的实际命令)。

- [ ] **Step 3: Commit**

```bash
git add python-data/lab/README.md
git commit -m "docs(python-data): lab README + 实测数字汇总"
```

---

# Phase B — 章节(引用 Phase A 的真数字)

> 每章统一交付步骤:**(1) 按 brief 写 `.md`;(2) 抽出可跑代码块在 3.11 实跑确认能跑;(3) 房屋风格自检(导引/正文内幕/对照框/面试卡四件齐 + 3.11 基线标注);(4) commit。** 下列每个 Task 的 brief 给出:一句话心智、正文 beats、必含代码/示例、对照框要点、要引用的 CAPTURED 数字、面试卡题目。

### Task B1: ch00 心智与选型(全景)

**Files:** Create `python-data/00-mindset-and-selection.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「先决定**要不要 ORM、Core 还是 ORM、sync 还是 async**,再谈细节——这三个选择决定后面所有形态。」
  - beats:① 这一层全景图(应用 → SQLAlchemy(ORM/Core)→ DBAPI driver → DB);② DBAPI 是什么(PEP 249,统一接口,见 ch01);③ Core vs ORM:Core = SQL 表达式、可控、适合批量/报表;ORM = 对象映射、适合领域写操作;④ sync vs async 的决策(回指 `python/13` 着色,详见 ch06);⑤ **要不要 ORM** 的判断:CRUD 业务密集→ORM;重 SQL/分析→Core/raw;一次性脚本→直接 driver;⑥ 本目录地图(各章一句话)。
  - 必含:一张分层 ASCII 图;一个同一查询的 Core 写法 vs ORM 写法对照小例。
  - 对照框:JDBC/Hibernate/MyBatis ｜ Go `database/sql`/sqlx/GORM ｜ Python DBAPI/SQLAlchemy Core/ORM。点出「MyBatis≈Core 手控 SQL,Hibernate≈ORM」。
  - 面试卡:Q「Core 和 ORM 怎么选?」Q「什么时候根本不该上 ORM?」Q「SQLAlchemy 在分层里处在哪一层?」
- [ ] **Step 2: 跑代码块**(Core/ORM 小例可对 lab 库跑或用 `create_engine("sqlite://")` 跑通) — 确认能跑。
- [ ] **Step 3: 房屋风格自检**。
- [ ] **Step 4: Commit** `git add python-data/00-mindset-and-selection.md && git commit -m "docs(python-data): ch00 心智与选型"`

---

### Task B2: ch01 驱动与 DBAPI

**Files:** Create `python-data/01-drivers-and-dbapi.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「连接是**资源**,SQL 永远**参数化**,一次 `execute` 是一次**网络往返**。」
  - beats:① PEP 249 DBAPI:`connect/cursor/execute/fetch*`,paramstyle;② psycopg3 vs asyncpg(同步阻塞驱动 vs 原生异步驱动,SQLAlchemy 各自的 URL);③ 参数化为什么必须(回指 `python/18` 注入);④ **内幕**:一次 `execute` 协议往返(parse/bind/execute/sync,服务端 prepared statement、为什么 N 次小查询慢在 RTT);⑤ 连接生命周期与显式关闭(`with`)。
  - 必含:裸 DBAPI(`psycopg.connect`)最小例 + 参数化正例/拼字符串反例;SQLAlchemy 两种 URL 字符串。
  - 对照框:JDBC `PreparedStatement` ｜ Go `db.Query(?, args)` ｜ Python paramstyle。
  - 面试卡:Q「DBAPI 是什么?」Q「为什么参数化能防注入(机制)?」Q「psycopg 和 asyncpg 区别?」Q「为什么一堆小查询慢?」(引出 RTT,接 ch05)。
- [ ] **Step 2: 跑代码块**(裸 psycopg 例对 lab 库跑)。
- [ ] **Step 3: 自检**。
- [ ] **Step 4: Commit** `docs(python-data): ch01 驱动与 DBAPI`

---

### Task B3: ch02 连接池

**Files:** Create `python-data/02-connection-pooling.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「池把『建连接』(贵)摊到多次复用;池参数 = 并发上限的闸门。」
  - beats:① 为什么要池(建 TCP+认证贵);② SQLAlchemy `QueuePool` 参数逐个讲:`pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`/`pool_pre_ping`;③ **池耗尽**:现象、报错文本、怎么排查(引用 CAPTURED `pool_exhaustion`:`pool_size=2,max_overflow=0,pool_timeout=1` → ~1.0s 后 `QueuePool limit ... timed out`);④ 池大小怎么定(连 worker 数、DB max_connections 关系);⑤ pgbouncer 与应用池的分层(应用池 + 外部连接池何时用);⑥ async 池差异(预告 ch06)。
  - 必含:`make_engine(pool_size=..., ...)` 配置例;CAPTURED 真实 timeout 输出块。
  - 对照框:HikariCP(`maximumPoolSize`/`connectionTimeout`)｜ Go `SetMaxOpenConns/SetMaxIdleConns/SetConnMaxLifetime` ｜ SQLAlchemy QueuePool。**指针**:纯性能调参 → `performance-tuning-roadmap/11-architecture/02-connection-pooling.md`。
  - 面试卡:Q「pool_size 怎么定?」Q「pool_recycle/pre_ping 解决什么?」Q「池耗尽什么现象、怎么查?」Q「应用池和 pgbouncer 重复吗?」
- [ ] **Step 2: 跑代码块**(池配置 + 触发 timeout 的最小例对 lab 库跑,或直接引用 demo)。
- [ ] **Step 3: 自检**(确认引用了 CAPTURED 真数字)。
- [ ] **Step 4: Commit** `docs(python-data): ch02 连接池`

---

### Task B4: ch03 ORM 机制:Session / UoW / 加载策略

**Files:** Create `python-data/03-orm-session-uow.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「Session 是一次**工作单元**:它记账(identity map + 脏跟踪),`flush` 发 SQL、`commit` 落库;懒加载是 N+1 的源头。」
  - beats:① identity map(同一主键同一对象);② unit of work(攒变更,flush 时按依赖排序发 SQL);③ `flush` vs `commit` vs `expire`/`refresh`;④ Session 生命周期与 `expire_on_commit`;⑤ **加载策略**:lazy(`select`,默认)→ 访问关系即发查询 → N+1;eager:`selectinload`(额外一条 IN)/`joinedload`(JOIN);各自适用;⑥ detached 对象 + `DetachedInstanceError` 陷阱。
  - 必含:一个 Session 增改例(`add`→`flush`观察 id→`commit`);lazy 触发额外 SQL 的 `echo=True` 片段(指向 ch05 lab 实测)。
  - 对照框:Hibernate persistence context/`flush`/`merge`/`LazyInitializationException` ｜ Python Session/`flush`/`merge`/`DetachedInstanceError`。直说「这套几乎是 Hibernate 的同构物」。
  - 面试卡:Q「flush 和 commit 区别?」Q「identity map 是什么?」Q「lazy vs eager,N+1 怎么来?」Q「DetachedInstanceError 怎么触发、怎么避免?」
- [ ] **Step 2: 跑代码块**(对 lab 库跑 Session 增改 + echo 片段)。
- [ ] **Step 3: 自检**。
- [ ] **Step 4: Commit** `docs(python-data): ch03 ORM Session/UoW/加载策略`

---

### Task B5: ch04 事务边界与并发控制

**Files:** Create `python-data/04-transactions.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「事务边界 = **一个业务操作一个 commit**;并发冲突靠隔离级别 + 乐观锁 + 重试兜。」
  - beats:① 事务边界放哪:session-per-request、`Session.begin()` 上下文、commit 位置;② SQLAlchemy 隔离级别设置(`isolation_level` on engine/connection)与 Postgres 四级简述(只从**应用侧可见行为**讲,理论指 `transaction/`);③ 乐观锁:`version_id_col`(并发更新检测,`StaleDataError`);④ **序列化失败**:SERIALIZABLE 下 read-write 冲突 → SQLSTATE 40001(引用 CAPTURED `isolation` 真实错误类名/SQLSTATE);⑤ 重试模式(捕获序列化失败→退避重试);⑥ 嵌套与 savepoint(`begin_nested`)。
  - 必含:session-per-request 伪代码;`version_id_col` 配置例;序列化失败重试循环骨架;CAPTURED 真实错误输出块。
  - 对照框:Spring `@Transactional`(传播/隔离)｜ Go 手动 `tx.Begin/Commit/Rollback` ｜ Python Session/`begin`/`begin_nested`。点出 Python 无声明式事务,靠显式边界或装饰器自封装。
  - 面试卡:Q「事务边界放哪?」Q「乐观锁怎么实现(version_id)?」Q「序列化失败什么时候出、怎么处理?」Q「savepoint 干嘛?」
- [ ] **Step 2: 跑代码块**(version_id 例 + 重试骨架对 lab 库跑)。
- [ ] **Step 3: 自检**(确认引用 CAPTURED)。
- [ ] **Step 4: Commit** `docs(python-data): ch04 事务边界与并发控制`

---

### Task B6: ch05 N+1 与查询性能(应用侧)

**Files:** Create `python-data/05-n-plus-one-and-query-perf.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「N+1 = 1 查父 + N 查子;先**数 SQL 条数**发现它,再用 eager/JOIN/下沉 raw SQL 修。」
  - beats:① N+1 怎么产生(承 ch03 lazy);② **怎么发现**:`echo`、`before_cursor_execute` 计数(给 demo 里的计数器代码)、SQL 日志;③ 修法谱系:`selectinload`(IN,N+1→2)/`joinedload`(JOIN,1 条但行数膨胀)/手写聚合查询;④ 引用 CAPTURED `n_plus_one`:21 queries → 2 queries + 真实时延;⑤ **何时下沉 raw SQL / Core**:复杂聚合、报表、ORM 生成 SQL 失控时;⑥ **从 Python 读 EXPLAIN**:`conn.execute(text("EXPLAIN (ANALYZE) ..."))` 读计划,看 Seq Scan/索引。
  - 必含:计数器片段;before/after 的 CAPTURED 真实输出;一个 `EXPLAIN ANALYZE` 从 Python 跑并打印计划的例(可回填真实计划片段)。
  - 对照框:Hibernate N+1 + `JOIN FETCH`/`@BatchSize` ｜ Go 手写 JOIN/手动批量 ｜ Python selectinload/joinedload。
  - 面试卡:Q「N+1 怎么发现?」Q「selectinload 和 joinedload 区别/各自代价?」Q「什么时候放弃 ORM 写 raw SQL?」Q「怎么从应用侧读执行计划?」
- [ ] **Step 2: 跑代码块**(EXPLAIN 例对 lab 库跑,回填真实计划)。
- [ ] **Step 3: 自检**(确认引用 CAPTURED)。
- [ ] **Step 4: Commit** `docs(python-data): ch05 N+1 与查询性能`

---

### Task B7: ch06 异步数据访问

**Files:** Create `python-data/06-async-data-access.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「async 数据层只在『海量并发 IO + 全异步栈』才值;它靠 asyncpg + greenlet 桥把 ORM 异步化,池语义照旧但要够大。」
  - beats:① async engine/session(`create_async_engine`、`AsyncSession`、`await session.execute`);② asyncpg 为什么快(原生异步协议);③ **greenlet 桥**:SQLAlchemy 怎么让同步式 ORM API 在 async 下工作(`greenlet_spawn`),为什么 lazy load 在 async 下要小心(`MissingGreenlet`);④ async 下的池(`AsyncAdaptedQueuePool`,pool_size 与并发);⑤ **值不值**:引用 CAPTURED `async_vs_sync`(20 并发 sync ≈1.0s vs async ≈0.x s + speedup),并回指 `python/13` 着色成本——不是所有项目都该异步;⑥ 同步代码里偶发调异步的桥(`asyncio.to_thread` 反向、`run_in_executor`)。
  - 必含:async session 最小例(`async with AsyncSession`);CAPTURED 真实吞吐对比块;`MissingGreenlet` 触发/规避说明。
  - 对照框:Java 同步 JDBC + 虚拟线程 / R2DBC ｜ Go 同步驱动 + goroutine ｜ Python asyncio + asyncpg(显式着色)。指针:并发模型本身 → `python/13`、`python-concurrency/04-asyncio-core`。
  - 面试卡:Q「什么时候该上 async 数据层?」Q「greenlet 桥解决什么?MissingGreenlet 怎么来?」Q「async 池和 sync 池区别?」Q「async 比 sync 快在哪、什么时候不快?」
- [ ] **Step 2: 跑代码块**(async session 例对 lab 库跑)。
- [ ] **Step 3: 自检**(确认引用 CAPTURED + 回指 ch13)。
- [ ] **Step 4: Commit** `docs(python-data): ch06 异步数据访问`

---

### Task B8: ch07 迁移与 schema 演进

**Files:** Create `python-data/07-migrations.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「迁移是**版本化的 schema 变更**;线上改表要 zero-downtime——先兼容再清理,分多次部署。」
  - beats:① Alembic 模型(`versions/` 链、`upgrade`/`downgrade`、`alembic revision --autogenerate`);② autogenerate 的**边界**(能测出加表/列,测不准改名/类型微调/数据迁移,需手写);③ 迁移与部署顺序(先迁移后发代码 vs 先发代码后迁移,取决于变更兼容性);④ **zero-downtime 模式**:加列(给默认/可空)、改列(扩-迁-缩三步)、加索引(`CREATE INDEX CONCURRENTLY`,Alembic 里 `op.create_index(postgresql_concurrently=True)` + 关事务);⑤ 回滚现实(downgrade 常不可逆,靠前向兼容)。
  - 必含:一个 `alembic revision --autogenerate` 产物示意 + 一个手写数据迁移 `op.execute(...)`;CONCURRENTLY 建索引片段。
  - 对照框:Flyway/Liquibase(SQL/changelog)｜ Go `golang-migrate`/goose ｜ Python Alembic。
  - 面试卡:Q「autogenerate 能/不能测出什么?」Q「怎么不停机加索引/改列?」Q「迁移和部署谁先?」
- [ ] **Step 2: 跑代码块**(可选:在 lab 里 `alembic init` 跑一次 autogenerate 验证流程能走通;命令在 README 注明)。
- [ ] **Step 3: 自检**。
- [ ] **Step 4: Commit** `docs(python-data): ch07 迁移与 schema 演进`

---

### Task B9: ch08 架构权衡与测试(判断层收口)

**Files:** Create `python-data/08-architecture-and-testing.md`

- [ ] **Step 1: 写章**
  - 一句话心智:「数据访问要不要抽象,取决于**会不会换实现/要不要隔离领域**;测试优先用真 DB + 事务回滚,别 mock ORM。」
  - beats:① repository vs active-record vs 直接用 Session 的取舍(YAGNI:小项目直接 Session,复杂领域才上 repository);② **领域模型 / 持久化模型解耦**(ORM 实体 ≠ 领域对象,何时拆、代价);③ 数据层测试策略:**事务回滚 fixture**(每用例包在一个 rollback 的事务里,快)vs **testcontainers**(真起 Postgres,贴生产);为什么别 mock session/query;④ 测 N+1 的断言(用 ch05 计数器在测试里断言查询条数);⑤ 收口:把全书的「要不要 ORM/何时 raw/要不要抽象」判断汇成一张决策表。
  - 必含:repository 接口骨架 + 直接用 Session 的对照;pytest 事务回滚 fixture 骨架;查询计数断言例。
  - 对照框:Spring Data Repository ｜ Go repository 手写接口 ｜ Python(无官方 repository,手写或直接 Session)。指针:测试基础 → `python/12`。
  - 面试卡:Q「要不要上 repository?」Q「怎么测数据层、为什么别 mock ORM?」Q「领域模型和 ORM 实体该不该分?」Q「怎么在测试里挡住 N+1?」
- [ ] **Step 2: 跑代码块**(回滚 fixture + 计数断言可对 lab 库跑通)。
- [ ] **Step 3: 自检**。
- [ ] **Step 4: Commit** `docs(python-data): ch08 架构权衡与测试`

---

### Task B10: ch99 面试卡

**Files:** Create `python-data/99-interview-cards.md`

- [ ] **Step 1: 写章** — 汇总 ch00–08 各章面试卡为速记表(每条「问｜一句话答｜标签」),并加「猜行为」drill(给 N+1 计数、序列化失败、池耗尽、flush/commit 时机 4–6 道,附答案)。格式对齐 `python/99-interview-cards.md`。
- [ ] **Step 2: 复核**每条答案与对应章一致(尤其引用的真数字)。
- [ ] **Step 3: Commit** `docs(python-data): ch99 面试卡`

---

# Phase C — 桥接章与整合

### Task C1: 桥接章 `python/22`

**Files:** Create `python/22-data-access-bridge.md`

- [ ] **Step 1: 写章**(对齐 `python/13` 桥接章风格)
  - 导引:为什么重要 + 「本章是桥接,深度在 `../python-data/`」。
  - 正文:① 这一层全景一句话;② **选型决策树**:要不要 ORM → Core vs ORM → sync vs async →(纯文本决策树);③ 事务边界一句话心智;④ N+1 一句话(数 SQL);⑤ 池一句话(并发闸门)。
  - 「去 `python-data/`」表:主题 → 章节链接(00–08 + 99 + lab)。
  - Java/Go 对照框(浓缩版)。
  - 章末面试卡(5–6 题,均「详见 python-data ch0X」)。
- [ ] **Step 2: 跑代码块**(若有小例)。
- [ ] **Step 3: 自检**(桥接章只讲「怎么选」,不展开实操)。
- [ ] **Step 4: Commit** `git add python/22-data-access-bridge.md && git commit -m "docs(python): ch22 数据访问桥接章 → python-data/"`

---

### Task C2: 目录索引 + README 整合

**Files:**
- Create: `python-data/README.md`
- Modify: `python/README.md`(TOC 表加 ch22 行;「与仓库其他目录的关系」加第 4 条指针)

**Interfaces:**
- Consumes: 全部已建章节文件名(00–08、99、22、lab/)

- [ ] **Step 1: 写 `python-data/README.md`** — 目录定位(架构师级数据访问深度)、读法、章节 TOC 表(00–08 + 99,每章一句话)、lab 入口、与 `python/22`/`mysql`/`transaction`/`redis`/`performance-tuning-roadmap` 的边界指针。对齐 `python-concurrency/README` 风格。
- [ ] **Step 2: 改 `python/README.md`**
  - 章节 TOC 表在 21 行后加:`| 22 | [数据访问(桥接章)](22-data-access-bridge.md) | 选型决策树、事务/N+1/池一句话;深度 → python-data/ |`
  - 「与仓库其他目录的关系」加:`- **数据访问深度** → ../python-data/:driver/连接池/ORM/Session/事务边界/N+1/async/迁移/repository,含可跑 Postgres lab。第 22 章只讲「怎么选」,实操在那里。`
- [ ] **Step 3: 校验链接**(章节文件名与链接一一对应;`grep -l` 抽查路径存在)。
- [ ] **Step 4: Commit** `git add python-data/README.md python/README.md && git commit -m "docs(python): python-data 目录索引 + README 整合 ch22 指针"`

---

## Self-Review

**1. Spec coverage**(逐条对 spec):
- §3 桥接章 → C1 ✓;独立目录 → B1–B10 ✓;README 整合 → C2 ✓
- §4 章节大纲 00–08 + 99 → B1–B10 ✓(顺序与编号一致)
- §5 lab(compose/pyproject/seed/4 demo/README + 真数字回填)→ A1–A6 ✓
- §6 房屋风格(四件套 + 3.11 基线)→ 每个 Phase B/C 任务 Step 1+3 强制 ✓
- §2 边界指针(mysql/transaction/distr-tx/redis/perf-tuning/python-concurrency)→ 分散进 ch00/02/04/06/08/22 的对照框与指针 ✓
- §9 成功标准 1–5 → ch00/05/04/07/99 覆盖 ✓

**2. Placeholder scan:** lab 任务为完整可跑代码;章节任务为完整 content brief(prose 是交付物本身,brief 指定其必含内容,非占位)。无 TODO/TBD。

**3. Type consistency:** demo 全部 `from db import make_engine/make_async_engine` + `from models import Author/Book/Account`,与 A1 Produces 接口一致;CAPTURED.md 段名(pool_exhaustion/n_plus_one/isolation/async_vs_sync)在 A2–A5 写入、B3/B5/B4/B7 引用,一致。

> 已知顺序约束:Phase A 必须在 Phase B 之前(章节引用 CAPTURED 真数字);A1 必须最先(demo 依赖 db/models/seed)。Phase A 需 Postgres 在线。
