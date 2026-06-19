# 02 · 连接池:并发的隐形闸门

> **为什么这章重要**:建一条数据库连接很贵(TCP 握手 + 认证 + 服务端 fork 一个 backend),贵到不能每个请求建一条。池把连接**复用**起来——但池的几个参数,就是你整个服务**并发上限的闸门**。调错了,要么连接泄漏拖垮数据库,要么池太小把请求堵死。这章讲清每个参数,并实测「池耗尽」长什么样。
>
> **一句话心智**:池 = 一小撮连接反复借还;`pool_size + max_overflow` 是借出上限,借不到就等 `pool_timeout`,等满就报错。

## 一、为什么要池

建一条 Postgres 连接的成本:TCP 三次握手 → TLS(如启用)→ 认证 → 服务端 `fork` 一个 backend 进程。几毫秒起步,且每条连接在服务端常驻内存。如果每个 HTTP 请求都新建+关闭一条,你在反复付这笔重税,还容易把数据库的 `max_connections` 顶爆。

**池的办法**:开服时建好一小撮连接,放在池里;请求来了**借**一条用,用完**还**回去(不是真关)。`engine.connect()` / `Session` 拿到的就是借来的连接,`with` 退出时归还。

SQLAlchemy 的 `create_engine` **默认就带池**(`QueuePool`),你什么都不配也在用池——只是用的默认参数。

## 二、QueuePool 的五个参数

```python
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg://postgres:postgres@localhost/datalab",
    pool_size=10,        # 常驻连接数:池子里固定养这么多
    max_overflow=20,     # 高峰临时溢出:最多再多开这么多(用完即关)
    pool_timeout=30,     # 借不到连接时,最多等几秒,等满抛 TimeoutError
    pool_recycle=1800,   # 连接活过这么多秒就回收重建(防被 DB/中间件掐断)
    pool_pre_ping=True,  # 借出前先 ping 一下,坏连接当场换掉
)
```

逐个吃透:

- **`pool_size`**:稳态并发能同时用的连接数。**并发的主闸门**。
- **`max_overflow`**:突发流量时,池可以临时再借出这么多(超出 `pool_size` 的部分用完即关,不常驻)。所以**真正的硬上限 = `pool_size + max_overflow`**。设 `max_overflow=0` 就是「严格只有 `pool_size` 条」。
- **`pool_timeout`**:连接全借出去了、又来一个请求,它愿意排队等几秒;等满抛 `QueuePool limit ... timed out`。
- **`pool_recycle`**:连接太老会被数据库或中间件(防火墙/pgbouncer)悄悄掐断,下次用就报 `server closed the connection`。设个比那些超时短的值,让池主动回收重建。
- **`pool_pre_ping`**:借出前发一个轻量探测,连接已死就丢掉换新的。**生产几乎必开**——它换掉「半夜数据库重启后第一波请求全 500」这类问题。

## 三、池耗尽:现象、报错、排查

把池调到极小,故意撞上限,看它真实的样子(`lab/demos/pool_exhaustion.py`):

```python
engine = make_engine(pool_size=2, max_overflow=0, pool_timeout=1)
# 两个线程各借一条连接、各 hold 3 秒 → 池(2 条)被占满
# 第三个 engine.connect() 无连接可借,等满 pool_timeout=1s 后:
```

**实测输出**(Postgres 16 / 本地,你的数字会不同):

```
conn 0: acquired
conn 1: acquired
conn 2: TimeoutError after 1.00s -> QueuePool limit of size 2 overflow 0 reached, connection timed out, timeout 1.00
```

读这条报错的三个信号:

1. **`QueuePool limit of size 2 overflow 0 reached`**:硬上限(`pool_size + max_overflow`)被打满了。
2. **`timed out ... timeout 1.00`**:它老老实实等了 `pool_timeout`(1.00s)才放弃——**生产里如果接口 P99 突然涨到接近你的 `pool_timeout`,十有八九是池在排队**。
3. 真实生产中这条报错往往不是「池太小」,而是**连接泄漏**:某处借了连接忘了还(没用 `with`、Session 没关、长事务占着不放),池被慢慢漏空。

**排查清单**:

- 报错文本先确认硬上限值,对照你配的 `pool_size + max_overflow`。
- `engine.pool.status()` 能打印池的实时占用(借出/空闲数)。
- 翻代码找「拿了连接/Session 不在 `with` 里、或事务跨了一次外部调用(HTTP/RPC)还占着连接」——这是泄漏头号源。
- 区分两种病:**池太小**(加 `pool_size`)vs **连接泄漏 / 长事务**(改代码,别让连接被长期占用)。盲目加大池只会把问题推给数据库的 `max_connections`。

## 四、池多大合适?别拍脑袋

一条朴素但好用的上界:

```
所有应用实例的 (pool_size + max_overflow) 总和  ≤  Postgres 的 max_connections − 预留
```

要点:

- **池是每个进程一份**。gunicorn/uvicorn 开 8 个 worker,每个 worker 一个 engine、一份池——`pool_size=10` 实际是 `8 × 10 = 80` 条连接打到数据库。多实例 + 多 worker 很容易把 `max_connections`(默认才 100)顶爆。这点直接接 [`../python/10`](../python/10-modules-packages-imports.md)/[`19`](../python/19-production-skeleton.md):**连接池属于每 worker 初始化一份的资源**。
- 池不是越大越好。连接在数据库侧也耗内存和调度;超过数据库能并行处理的数量,多出来的连接只是在排队,反而增加上下文切换。
- 经验起点:`pool_size` ≈ 该 worker 的并发请求数;拿不准从小开始,用监控(池占用、DB 活动连接数)往上调。

## 五、应用池 + pgbouncer:两层池不冲突

大规模下常见**两层**:应用进程各自的 SQLAlchemy 池 + 一个外部 **pgbouncer** 池(挡在所有应用和 Postgres 之间)。它们解决不同问题:

- **应用池**:省掉「每请求建连」,管的是「这个进程怎么复用它的连接」。
- **pgbouncer**:把成百上千个应用连接,复用到数据库少量真实连接上(尤其 transaction-pooling 模式),管的是「整个集群别把 Postgres 的 `max_connections` 压垮」。

两者叠加是正解,不是重复。配 pgbouncer(transaction 模式)时注意:**prepared statement 缓存、`SET`/会话级状态会失效**,SQLAlchemy 这边可能要关掉语句缓存或调整——这属于运维细节。

> 池的**纯性能调参与压测**(多大池吞吐最高、和 DB 端怎么配合)在 [`../performance-tuning-roadmap/11-architecture/02-connection-pooling.md`](../performance-tuning-roadmap/11-architecture/02-connection-pooling.md)。本章管「机制 + 怎么不出事」,那边管「怎么调到最快」。

## Java/Go 对照框

| 关注点 | Java(HikariCP) | Go(`database/sql`) | Python(SQLAlchemy QueuePool) |
|---|---|---|---|
| 稳态大小 | `maximumPoolSize` | `SetMaxOpenConns` | `pool_size`(+`max_overflow`) |
| 空闲连接 | `minimumIdle` | `SetMaxIdleConns` | (池本身常驻 `pool_size`) |
| 借不到等多久 | `connectionTimeout` | 阻塞(靠 ctx 超时) | `pool_timeout` |
| 连接最长寿命 | `maxLifetime` | `SetConnMaxLifetime` | `pool_recycle` |
| 存活探测 | `keepaliveTime` / 测试查询 | `SetConnMaxIdleTime` | `pool_pre_ping` |

来自 Java 的你几乎是一一对应:**`maximumPoolSize`≈`pool_size+max_overflow`、`connectionTimeout`≈`pool_timeout`、`maxLifetime`≈`pool_recycle`**。最大差异:Go 的池内建在 `database/sql`,Python 的池在 SQLAlchemy 这一层(DBAPI 本身不带池)。

## 章末面试卡

**Q1. 为什么需要连接池?**
建数据库连接贵(TCP 握手 + 认证 + 服务端 fork backend,几毫秒且常驻内存),不能每请求一建。池开服时备好一撮连接,请求借用、用完归还(非真关),摊薄建连成本,也避免把数据库 `max_connections` 顶爆。

**Q2. `pool_size` 和 `max_overflow` 是什么关系?硬上限是多少?**
`pool_size` 是常驻连接数,`max_overflow` 是高峰临时溢出数(用完即关)。同时能借出的**硬上限 = pool_size + max_overflow**。设 `max_overflow=0` 即严格只有 `pool_size` 条。

**Q3. `pool_recycle` 和 `pool_pre_ping` 各解决什么?**
`pool_recycle` 让连接活过 N 秒就主动回收重建,防数据库/中间件把老连接悄悄掐断后下次用即报错;`pool_pre_ping` 在借出前轻量探测,坏连接当场换掉。生产几乎必开 `pre_ping`,避免「DB 重启后第一波请求全失败」。

**Q4. 池耗尽是什么现象?怎么排查?**
请求借不到连接,等满 `pool_timeout` 后抛 `QueuePool limit ... timed out`;表现为接口延迟逼近 `pool_timeout`。排查:看报错里的硬上限、用 `engine.pool.status()` 看占用,重点找连接泄漏(没用 `with`、Session 没关、长事务跨外部调用占着连接)。先分清是池太小还是泄漏,别盲目加大池。

**Q5. 应用连接池和 pgbouncer 重复吗?池该开多大?**
不重复:应用池管「本进程复用连接」,pgbouncer 管「把全集群大量连接收敛到 Postgres 少量真实连接」。大小上界:所有实例 × worker 数 × (pool_size+max_overflow) ≤ DB max_connections − 预留;注意池是每 worker 一份,多 worker 会成倍放大。
