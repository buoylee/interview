# 04 · 事务边界与并发控制

> **为什么这章重要**:事务用错地方,是数据层最贵的 bug——要么边界太大把连接占着不放(拖垮池,第 02 章),要么边界太小丢了原子性(钱扣了货没发)。再加上并发:两个请求同时改一行,谁赢?这章讲三件事:**事务边界放哪、隔离级别从应用侧看到什么、并发冲突怎么兜**。
>
> **一句话心智**:**一个业务操作 = 一个事务 = 一次 `commit`**;并发冲突靠「隔离级别挡一部分 + 乐观锁检测 + 失败重试」三层兜底。

## 一、事务边界:放在「一个业务操作」的两端

边界 = 从 `BEGIN` 到 `COMMIT` 之间。原则:**它应该恰好包住一个完整的业务操作**——下单(扣库存 + 建订单 + 记流水)要么全成、要么全败。

SQLAlchemy 里用 `Session.begin()` 把边界画清楚:

```python
# 推荐:用 begin() 上下文,正常退出自动 commit,异常自动 rollback
with Session(engine) as s:
    with s.begin():                       # ← 事务边界从这里到块结束
        order = Order(user_id=1, total=100)
        s.add(order)
        s.execute(update(Stock).where(...).values(qty=Stock.qty - 1))
    # 块正常结束 -> commit;块内抛异常 -> rollback,且整批都不落库
```

两条反面教材:

- **边界太大**:把一次外部调用(发 HTTP、调下游 RPC、等用户输入)夹在事务中间。事务一直开着 = 连接一直被占 = 池里少一条、数据库里挂一个空转的 backend。**事务里绝不做慢的外部 IO**。
- **边界太小 / 没有边界**:本该原子的几步各自 `commit`,中间崩了就留下半截脏数据。

### session-per-request:Web 服务的标准姿势

Web 框架里,**一个 HTTP 请求 = 一个 Session = 一个事务**:请求进来开 Session,处理完 `commit`(出错 `rollback`),响应返回前关掉。FastAPI 里用依赖注入给每个请求一个 Session:

```python
def get_session():
    with Session(engine) as s:
        yield s          # 交给这个请求用;请求结束时 with 退出 -> 关闭/归还连接
```

这同时解决了第 03 章的 `DetachedInstanceError`(Session 活到响应序列化完)和连接归还问题。

## 二、隔离级别:只从「应用侧看到什么」讲

隔离级别理论(脏读/不可重复读/幻读的完整定义)在 [`../transaction/`](../transaction/)。这里只给你**应用侧要做的决定**:在 SQLAlchemy 怎么设、四级各自意味着什么。

```python
# 在 engine 上设默认隔离级别(也可在 connection / Session 级覆盖)
engine = create_engine(URL, isolation_level="REPEATABLE READ")
# 或针对单次:engine.connect().execution_options(isolation_level="SERIALIZABLE")
```

应用侧的直觉(Postgres 语境):

| 级别 | 你能依赖什么 | 代价 |
|---|---|---|
| READ COMMITTED(PG 默认) | 不会读到别人未提交的数据;但同一事务内两次读同一行可能不同 | 最弱,最快,够用 |
| REPEATABLE READ | 同一事务内反复读结果一致(快照固定) | 写冲突时报序列化错 |
| SERIALIZABLE | 仿佛事务一个个排队跑,无并发异常 | 冲突更易报错,要重试 |

实务:**大多数业务用默认 READ COMMITTED 就够**;只有「读了再基于读到的值写、且不能容忍丢更新」的场景,才升到 REPEATABLE READ / SERIALIZABLE,并配重试。

## 三、并发冲突:乐观锁与序列化失败

两个事务同时改同一行,核心风险是**丢更新(lost update)**:都读到 balance=100,都写 90,本该剩 80 的结果剩了 90。两种防法。

### 乐观锁:version 列(应用层,ORM 原生支持)

给表加一个版本列,SQLAlchemy 的 `version_id_col` 会在每次 UPDATE 时带上 `WHERE version = <读到的版本>` 并自增;如果别人先改了(版本对不上),更新影响 0 行,抛 `StaleDataError`:

```python
class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    __mapper_args__ = {"version_id_col": version}
# 两个 Session 都读到 version=3,各自改 balance:
# 先 commit 的把 version 升到 4;后 commit 的 UPDATE ... WHERE version=3 命中 0 行 -> StaleDataError
```

「乐观」= 假设冲突很少,不提前加锁,**提交时才检测**;冲突了就让上层重试。读多写少时比悲观锁(`SELECT ... FOR UPDATE` 提前锁行)更省。

### 序列化失败:让数据库来抓(数据库层)

在 SERIALIZABLE 下,Postgres 会检测读写依赖冲突,把注定产生异常的那个事务**在提交时中止**,报 **SQLSTATE 40001**。`lab/demos/isolation.py` 实测:

```
both read balance=100
tx1 committed -> balance=90
tx2 serialization failure: SerializationFailure / sqlstate=40001
```

两事务都读了 100、都想写 90,Postgres 让 tx1 过、把 tx2 以 40001 打回——丢更新被数据库挡下了。psycopg 这边抛出来是 `SerializationFailure`(包在 SQLAlchemy 的 `DBAPIError` 里,`e.orig` 是原始驱动异常)。

### 重试:序列化失败/乐观锁失败的标准收尾

无论乐观锁的 `StaleDataError` 还是数据库的 40001,**正确响应都是「重试整个事务」**(不是吞掉、也不是直接 500):

```python
from sqlalchemy.exc import DBAPIError, OperationalError

def run_with_retry(do_txn, attempts=3):
    for i in range(attempts):
        try:
            with Session(engine) as s, s.begin():
                return do_txn(s)              # 整个业务操作放里面
        except DBAPIError as e:
            # 仅对可重试的并发错误重试(40001 序列化失败 / 死锁 40P01)
            code = getattr(e.orig, "sqlstate", None)
            if code in {"40001", "40P01"} and i < attempts - 1:
                continue                       # 重读重算重写
            raise
```

关键:重试必须**重跑整个事务**(重新读、基于新值重算、再写),不能只重发那条 UPDATE——因为你读到的前提已经变了。

## 四、savepoint:事务里的局部回滚

`begin_nested()` 开一个 **savepoint**,可以只回滚一小段而不炸掉整个事务——比如「尝试插入,撞唯一约束就跳过,其余照常提交」:

```python
with Session(engine) as s, s.begin():
    for row in rows:
        try:
            with s.begin_nested():       # savepoint
                s.add(row)
                s.flush()                # 撞唯一约束在这里抛
        except IntegrityError:
            pass                          # 只回滚这一条(到 savepoint),继续
    # 外层事务整体提交
```

## Java/Go 对照框

| 关注点 | Java(Spring) | Go | Python(SQLAlchemy) |
|---|---|---|---|
| 事务边界 | `@Transactional`(声明式) | 手动 `tx.Begin/Commit/Rollback` | `with Session.begin():`(显式) |
| 传播 / 嵌套 | propagation + savepoint | 手动 | `begin_nested()`(savepoint) |
| 隔离级别 | `@Transactional(isolation=...)` | `sql.TxOptions{Isolation}` | `isolation_level=`(engine/连接级) |
| 乐观锁 | JPA `@Version` | 手写 version 列 + WHERE | `version_id_col` |
| 重试 | 手写 / Spring Retry | 手写循环 | 手写循环(认 SQLSTATE) |

最大差异:**Python 没有 Spring 那种声明式 `@Transactional`**——边界是你用 `with` 显式画的(更透明,也更要自己上心)。乐观锁这边 `version_id_col` ≈ JPA `@Version`,机制一致。重试两边都得自己写。

## 章末面试卡

**Q1. 事务边界应该放在哪?太大/太小各有什么害处?**
恰好包住一个完整业务操作的两端(`with Session.begin():`)。太大(把外部 HTTP/RPC 夹在事务里)= 连接被长期占用、拖垮连接池;太小/没边界 = 本该原子的几步各自提交,中途失败留下半截脏数据。事务里绝不做慢的外部 IO。

**Q2. 什么是 session-per-request?它解决什么?**
Web 里一个 HTTP 请求配一个 Session/一个事务:请求进来开、处理完 commit(出错 rollback)、响应前关。它同时解决连接及时归还、和「响应序列化时碰懒加载关系报 DetachedInstanceError」两个问题。

**Q3. 乐观锁怎么实现?它和悲观锁的区别?**
加 version 列,UPDATE 时带 `WHERE version=<读到的>` 并自增,影响 0 行就说明被人抢先改了,抛 StaleDataError(SQLAlchemy 用 `version_id_col` 原生支持)。乐观锁假设冲突少、提交时才检测,适合读多写少;悲观锁(`SELECT ... FOR UPDATE`)提前锁行,适合冲突频繁。

**Q4. SERIALIZABLE 下的序列化失败是什么?该怎么处理?**
两事务读写互相依赖、并发执行会产生异常时,Postgres 在提交时中止其中一个,报 SQLSTATE 40001(psycopg 抛 `SerializationFailure`)。正确处理是**重试整个事务**(重读、重算、重写),而不是吞掉或直接报错。

**Q5. savepoint(`begin_nested`)解决什么?**
在一个大事务里画出可局部回滚的小段:某一步失败只回滚到 savepoint、不炸整个事务,其余照常提交。典型用于「批量插入中个别撞约束就跳过、其余继续」。
