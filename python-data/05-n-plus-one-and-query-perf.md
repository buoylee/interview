# 05 · N+1 与查询性能:从应用侧看

> **为什么这章重要**:N+1 是 ORM 项目最常见、也最隐形的性能杀手——代码读起来人畜无害(`for a in authors: use(a.books)`),却在背后发了几十上百条查询。它不会报错,只是慢;等你上线被打爆才发现。这章教你**主动发现**它(数 SQL 条数),掌握修法谱系,并知道**什么时候该抛开 ORM 直接写 SQL**。
>
> **一句话心智**:N+1 = 1 条查父 + N 条查子;**先把「发了几条 SQL」变成可见的数字**,再用 eager / JOIN / raw SQL 把 N 个往返压成 1~2 个。

## 一、N+1 怎么来的(承上一章)

第 [03](03-orm-session-uow.md) 章讲过根因:关系默认懒加载,循环里逐个访问关系属性就触发 N 条查询。回顾这段「人畜无害」的代码:

```python
authors = s.scalars(select(Author)).all()   # 1 条:查所有 author
for a in authors:
    print(len(a.books))                      # 每个 a 第一次访问 .books -> 1 条查询
# 20 个 author => 1 + 20 = 21 条
```

为什么慢的是「条数」而不是「数据量」?回到第 [01](01-drivers-and-dbapi.md) 章:**一次查询 ≈ 一个网络往返(RTT)**。21 条就是 21 个 RTT,延迟被往返次数主导——哪怕每条 SQL 本身快得离谱。

## 二、怎么发现:把 SQL 条数变成数字

N+1 不报错,所以**你得主动量它**。三种手段,从糙到细:

**① `echo=True`**——engine 打开后把每条 SQL 打到日志,人眼就能看到「怎么发了一长串 SELECT books WHERE author_id=...」:

```python
engine = create_engine(URL, echo=True)   # 开发期临时开,看 SQL 流
```

**② 计数监听器**——精确数条数,可在测试里断言(`lab/demos/n_plus_one.py` 用的就是这个):

```python
from sqlalchemy import event
counter = {"n": 0}

@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, params, context, executemany):
    counter["n"] += 1
# 跑一段业务,读 counter["n"] 就知道发了几条
```

**③ APM / 慢查询日志**——生产里靠可观测性(每请求 SQL 数、DB 耗时)发现 N+1,见 [`../fastapi-ops/`](../fastapi-ops/) 与 [`../observability/`](../observability/)。

把 ② 做成测试断言,就能**在 CI 里挡住 N+1 回归**(第 [08](08-architecture-and-testing.md) 章细讲)。

## 三、修法谱系:selectinload vs joinedload vs raw

**实测对比**(`lab/demos/n_plus_one.py`,Postgres 16 / 本地,你的数字会不同):

```
N+1 (lazy): 21 queries, 100 books, 35.5 ms
fixed (selectinload): 2 queries, 100 books, 4.5 ms
```

21 → 2 条,35.5ms → 4.5ms。修法有三档,**按场景选,不是越激进越好**:

| 修法 | SQL 条数 | 怎么取 | 适合 / 代价 |
|---|---|---|---|
| `selectinload` | **2** | 父一条,子一条 `WHERE author_id IN (...)` | **默认首选**。一对多、集合大时尤佳;两条干净查询 |
| `joinedload` | **1** | 一条 `LEFT JOIN` 把父子一起拿 | 多对一 / 一对一好;一对多会让父行**随子行数膨胀**(网络/内存放大,客户端去重) |
| raw SQL / Core 聚合 | 1 | 自己写精确的 JOIN / 聚合 | ORM 生成的 SQL 失控、或复杂报表时;最可控但最啰嗦 |

```python
from sqlalchemy.orm import selectinload, joinedload
s.scalars(select(Author).options(selectinload(Author.books)))   # 2 条,推荐
s.scalars(select(Author).options(joinedload(Author.books)))     # 1 条,但行数膨胀
```

经验:**一对多用 `selectinload`、多对一/一对一用 `joinedload`**。joinedload 拉一对多时,父字段会在每个子行上重复传输(N 本书 → 作者信息重复 N 次),数据量一大反而不划算。

## 四、什么时候该抛开 ORM,直接写 SQL

ORM 不是终点。出现这些信号,**下沉到 Core 或 raw SQL**:

- **复杂聚合 / 报表**:多表 JOIN + GROUP BY + 窗口函数,用 ORM 关系导航既绕又生成不出你要的 SQL。直接 `select(...)` 写 Core,或 `text()` 写 raw。
- **ORM 生成的 SQL 失控**:你 eager 了好几层关系,SQLAlchemy 拼出一条巨型 JOIN,计划很差。这时手写一条精准的更好。
- **批量写**:几万行的 `INSERT`/`UPDATE`,逐对象走 ORM 太慢,用 Core 的 `insert().values([...])` 批量、或 `bulk_insert_mappings`。

```python
from sqlalchemy import text
# raw SQL —— 复杂聚合直接写,参数仍然绑定(别拼字符串)
rows = s.execute(text("""
    SELECT a.name, count(b.id) AS n
    FROM authors a JOIN books b ON b.author_id = a.id
    GROUP BY a.name HAVING count(b.id) > :min
"""), {"min": 3}).all()
```

这正是第 [00](00-mindset-and-selection.md) 章「要不要 ORM」判断的落地:**ORM 管对象写操作,聚合/报表/批量该用 Core/raw 就用**——同一个 Session 里混着用,毫无冲突。

## 五、从 Python 侧读 EXPLAIN

发现「某条查询慢」时,别靠猜,**把执行计划从代码里拉出来看**——是不是没走索引(`Seq Scan`)、JOIN 方式对不对:

```python
from sqlalchemy import text
plan = s.execute(text(
    "EXPLAIN ANALYZE SELECT * FROM books WHERE author_id = :a"
), {"a": 1}).fetchall()
for line in plan:
    print(line[0])
```

**实测计划**(Postgres 16 / 本地,seed 数据量很小,你的会不同):

```
Seq Scan on books  (cost=0.00..2.25 rows=5 width=...) (actual time=... rows=5 loops=1)
  Filter: (author_id = 1)
Planning Time: ... ms
Execution Time: ... ms
```

小表上 Postgres 选 `Seq Scan`(全表扫)是对的——表才 100 行,扫比走索引还快。**数据量大了同样的查询若仍是 `Seq Scan`,就是缺 `books(author_id)` 索引的信号**。怎么加索引、加什么索引属于 DB 引擎层(见 [`../mysql/`](../mysql/)、[`../performance-tuning-roadmap/`](../performance-tuning-roadmap/));应用侧你要会的是:**怀疑慢查询时,顺手 `EXPLAIN ANALYZE` 把计划读出来定位**。

## Java/Go 对照框

| 关注点 | Java(Hibernate) | Go | Python(SQLAlchemy) |
|---|---|---|---|
| N+1 来源 | 懒加载关系 | GORM 关系 / 手写漏批量 | 懒加载关系 |
| eager 一条 JOIN | `JOIN FETCH` / `@Fetch(JOIN)` | `Preload`(GORM) | `joinedload` |
| eager 批量 IN | `@BatchSize` / `@Fetch(SUBSELECT)` | 手写 `IN` | `selectinload` |
| 发现工具 | Hibernate statistics / SQL 日志 | SQL 日志 / APM | `before_cursor_execute` 计数 / echo |
| 下沉裸 SQL | 原生 query / MyBatis | 直接 `database/sql` | `text()` / Core |

Hibernate 用户最熟:`selectinload ≈ @BatchSize/SUBSELECT`、`joinedload ≈ JOIN FETCH`,连「一对多 JOIN FETCH 会让父行膨胀」这个坑都一模一样。Go 因为偏手写 SQL,N+1 往往是「忘了批量」而非「框架偷偷懒加载」,反而更显眼。

## 章末面试卡

**Q1. N+1 是什么?为什么它慢的是「条数」?**
查父集合后,对每个父对象逐个懒加载子关系,形成 1(查父)+ N(逐个查子)条查询。慢在条数是因为一次查询≈一个网络往返(RTT),N+1 条就是 N+1 个 RTT,延迟被往返次数主导,与单条 SQL 多快无关。

**Q2. 怎么主动发现 N+1?**
它不报错,得量化:开发期 `echo=True` 看 SQL 流;用 `before_cursor_execute` 监听器精确数条数(可在测试里断言挡回归);生产靠 APM / 慢查询日志看每请求 SQL 数。

**Q3. selectinload 和 joinedload 有什么区别?各自适合什么?**
selectinload:父一条 + 子一条 `IN(...)`,共 2 条,适合一对多/大集合。joinedload:一条 LEFT JOIN 拿父子,共 1 条,适合多对一/一对一;拉一对多会让父行随子行数膨胀(重复传输 + 客户端去重)。经验:一对多用 selectinload,多对一/一对一用 joinedload。

**Q4. 什么时候应该放弃 ORM、直接写 SQL?**
复杂聚合/报表(多表 JOIN+GROUP BY+窗口)、ORM 生成的 SQL 失控、大批量写。这些用 Core 或 `text()` raw SQL 更可控,且能和 ORM 在同一 Session 混用。ORM 管对象写,聚合/批量交给 SQL。

**Q5. 怀疑一条查询慢,应用侧怎么定位?**
从代码里 `EXPLAIN ANALYZE` 把执行计划拉出来读:看是不是 `Seq Scan`(全表扫,大表上即缺索引信号)、JOIN 方式、实际行数与耗时。加索引属 DB 层,但「读计划定位」是应用侧该会的。
