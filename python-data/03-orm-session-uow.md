# 03 · ORM 机制:Session、工作单元、加载策略

> **为什么这章重要**:ORM 的「魔法」全在 **Session** 这一个对象里——它是一次**工作单元(Unit of Work)**,帮你记账(谁是同一个对象、谁脏了、何时发 SQL)。看懂 Session,你就答得上「`flush` 和 `commit` 差在哪」「为什么改了对象没 `commit` 也发了 SQL」「N+1 到底从哪冒出来」。这章是后面事务(04)和 N+1(05)两章的地基。
>
> **一句话心智**:Session 攒着你的改动不急着发,到 `flush` 才把它们翻译成 SQL、到 `commit` 才落库;你导航关系属性(`author.books`)时,它在背后**偷偷发查询**——这就是 N+1 的源头。

## 一、Session 是一次「工作单元」

来自 Hibernate 的你会很眼熟:Session ≈ Hibernate 的 persistence context。它在一段事务里**追踪一批对象**,核心干三件事:

1. **Identity map(身份映射)**:同一个 Session 里,同一主键**永远是同一个 Python 对象**。
2. **Unit of Work(工作单元)**:你 `add`/改属性/`delete`,它先记在账上(脏跟踪),到 `flush` 时**一次性按依赖顺序**翻译成 INSERT/UPDATE/DELETE。
3. **关系加载**:你访问 `author.books`,它按配置的加载策略去取数据。

```python
from sqlalchemy.orm import Session

with Session(engine) as s:
    a1 = s.get(Author, 1)
    a2 = s.get(Author, 1)
    print(a1 is a2)          # True —— identity map:同一对象,不是两份拷贝

    a1.name = "改个名"        # 只是改了 Python 对象,还没发 SQL
    s.commit()               # 此刻才 UPDATE,并提交事务
```

`a1 is a2` 为 `True` 是 identity map 的直接体现——避免同一行在内存里分裂成两个不一致的对象。

## 二、`flush` vs `commit`:最爱考的一对

- **`flush`**:把 Session 攒的改动**翻译成 SQL 发给数据库**(INSERT/UPDATE/DELETE),但**事务还没提交**——数据库看得到(在本事务内),别的连接看不到,还能回滚。
- **`commit`**:先 `flush`(如果还有没发的),**再提交事务**(真正落库,别人可见)。

```python
with Session(engine) as s:
    a = Author(name="新作者")
    s.add(a)
    print(a.id)         # None —— 还没发 SQL,主键(自增)未知
    s.flush()           # 发 INSERT;数据库返回自增主键
    print(a.id)         # 21 —— 现在有了,但事务还没提交
    # ... 可以拿这个 id 去插子记录(seed.py 里就这么用)
    s.commit()          # 提交;别的连接现在才看得见
```

什么时候要手动 `flush`?**需要拿数据库生成的值(自增主键、默认值、触发器结果)继续往下做**时——比如先插父行拿到 id,再插引用它的子行(`seed.py` 正是如此)。日常你很少手动 `flush`:`commit` 会自动先 flush,查询前 SQLAlchemy 也会 **autoflush**(把挂起的改动先发掉,保证你查到的是最新状态)。

> 还有 `expire`/`refresh`:`commit` 后默认 `expire_on_commit=True`,对象属性被标记「过期」,下次访问会重新查库拿最新值。这避免你拿着 commit 前的旧快照。代价是 commit 后访问属性会触发额外查询——长事务/批量场景可关掉它。

## 三、加载策略:N+1 就生在这里

关系属性(`author.books`)**默认是懒加载(lazy='select')**:对象先不带 books,**你第一次访问 `.books` 时才发一条查询**去取。问题来了——循环里对每个 author 访问 `.books`:

```python
from sqlalchemy import select
with Session(engine) as s:
    authors = s.scalars(select(Author)).all()   # 1 条:SELECT * FROM authors
    for a in authors:
        print(len(a.books))                      # 每个 a 触发 1 条 SELECT books WHERE author_id=?
    # 20 个 author => 1 + 20 = 21 条查询  ← 这就是 N+1
```

**eager 加载**把它压平。两种主力:

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload:父查一条,子用一条 IN(...) 批量拿 —— 总 2 条
s.scalars(select(Author).options(selectinload(Author.books)))

# joinedload:一条 SQL 用 JOIN 把父子一起拿 —— 1 条,但父行会随子行数膨胀(去重在客户端做)
s.scalars(select(Author).options(joinedload(Author.books)))
```

**实测**(`lab/demos/n_plus_one.py`,Postgres 16 / 本地,你的数字会不同):

```
N+1 (lazy): 21 queries, 100 books, 35.5 ms
fixed (selectinload): 2 queries, 100 books, 4.5 ms
```

21 → 2 条,时延 35.5ms → 4.5ms。**N+1 的修法、joinedload vs selectinload 的取舍、怎么主动发现它**,是第 [05](05-n-plus-one-and-query-perf.md) 章的主题;这里你只要记住根因:**懒加载 + 在循环里导航关系**。

## 四、detached 对象:Session 关了就别再碰关系

对象的「生命」绑在 Session 上。Session 一关(`with` 退出),里面的对象变成 **detached**;此时再访问一个**没加载过的懒加载属性**,会炸:

```python
with Session(engine) as s:
    a = s.get(Author, 1)
a.books     # ❌ DetachedInstanceError:Session 已关,没法再去库里懒加载 books
```

这是 Web 开发的高频坑:在请求处理函数里查出对象、Session 随请求结束关闭,然后在模板/序列化层访问懒加载关系 → 炸。三种解法:

1. **在 Session 还开着时就 eager 加载**好要用的关系(`selectinload`)——最常用。
2. 把 Session 的生命周期对齐整个请求(session-per-request,第 [04](04-transactions.md) 章)。
3. 在 Session 内就把对象转成纯数据(dict / Pydantic 模型)再出去。

> Hibernate 用户:这就是 `LazyInitializationException` 的同一个故事——「session/EntityManager 关了之后碰懒加载关系」。换了名字,病根一样。

## Java/Go 对照框

| 概念 | Hibernate / JPA | Python(SQLAlchemy ORM) |
|---|---|---|
| 会话 / 上下文 | `Session` / `EntityManager`(persistence context) | `Session` |
| 身份映射 | first-level cache(同一行同一对象) | identity map |
| 攒改动批量发 | `flush()` | `flush()` |
| 提交事务 | `Transaction.commit()` | `Session.commit()`(含 flush) |
| 懒加载关了 session 后炸 | `LazyInitializationException` | `DetachedInstanceError` |
| 改了对象自动发 UPDATE | dirty checking | dirty tracking |

几乎是同构的两套实现——**你的 Hibernate 直觉绝大多数能直接迁移**。Go 这边 GORM 也有类似的预加载(`Preload`)和 N+1,但 Go 主流仍偏手写 SQL(`sqlx`),没有这么重的 persistence context 概念,也就少了这套陷阱(代价是样板多)。

## 章末面试卡

**Q1. Session 是什么?它在 ORM 里扮演什么角色?**
Session 是一次**工作单元(Unit of Work)**,在一段事务里追踪一批对象:维护 identity map(同主键同对象)、做脏跟踪(攒改动到 flush 时批量发 SQL)、管关系加载。类比 Hibernate 的 persistence context。

**Q2. `flush` 和 `commit` 有什么区别?**
`flush` 把攒的改动翻译成 SQL 发给数据库,但事务未提交(本事务可见、可回滚、别人看不到);`commit` 会先 flush 再提交事务(真正落库、别人可见)。需要拿自增主键继续插子行时手动 flush;commit 会自动先 flush。

**Q3. identity map 是什么?有什么用?**
同一个 Session 里,同一主键始终返回同一个 Python 对象(`a1 is a2` 为 True)。它避免同一行在内存里分裂成多个不一致的副本,也让脏跟踪能聚焦到唯一对象上。

**Q4. N+1 是怎么从 ORM 里冒出来的?**
关系属性默认懒加载(lazy='select'):查父对象时不带子集合,第一次访问 `.books` 才发查询。在循环里对 N 个父对象逐个访问关系,就变成 1(查父)+ N(逐个查子)条查询。用 `selectinload`/`joinedload` 提前 eager 加载可压平。

**Q5. `DetachedInstanceError` 怎么触发、怎么避免?**
Session 关闭后,对象变 detached,再访问未加载的懒加载属性时抛出(因为没有活的 Session 去库里取)。避免:在 Session 开着时就 eager 加载要用的关系、或让 Session 覆盖整个请求、或在 Session 内把对象转成纯数据再出去。等价于 Hibernate 的 `LazyInitializationException`。
