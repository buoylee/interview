# 实测输出存档

> 环境:Postgres 16(docker-compose,OrbStack)、SQLAlchemy 2.0.51、psycopg 3.3.4 /
> asyncpg 0.31.0、Python 3.11、Apple Silicon、本地回环。**你的数字会不同**——
> 看的是数量级与现象,不是绝对值。各章引用这里的真实输出。

## pool_exhaustion

`make_engine(pool_size=2, max_overflow=0, pool_timeout=1)`,两线程占满池,第三个 checkout:

```
conn 0: acquired
conn 1: acquired
conn 2: TimeoutError after 1.00s -> QueuePool limit of size 2 overflow 0 reached, connection timed out, timeout 1.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)
```

要点:等满 `pool_timeout`(1.00s)才报错;错误文本点名 `QueuePool limit of size 2 overflow 0`。

## n_plus_one

20 authors,各 5 books;`sum(len(a.books))` 触发关系加载。`before_cursor_execute` 计数:

```
N+1 (lazy): 21 queries, 100 books, 35.5 ms
fixed (selectinload): 2 queries, 100 books, 4.5 ms
```

要点:lazy = 1(查 authors)+ 20(每位查 books)= **21 条**;`selectinload` 收成 **2 条**;时延 35.5ms → 4.5ms(~8x)。

## isolation

两事务 SERIALIZABLE,都读 balance=100 再都写 90:

```
both read balance=100
tx1 committed -> balance=90
tx2 serialization failure: SerializationFailure / sqlstate=40001
```

要点:tx2 提交被 Postgres 以 **SQLSTATE 40001**(`could_not_serialize_access` / psycopg 类名 `SerializationFailure`)中止——靠它防丢更新,生产里配重试。

## async_vs_sync

20 次 `SELECT pg_sleep(0.05)`;sync 单连接串行,async 走 N 大小的池并发:

```
sync : 20 queries x 0.05s sequential = 1.07s
async: 20 concurrent                   = 0.28s  (speedup 3.7x)
```

要点:async ~3.7x,而非理论的 20x——20 条新 async 连接的建连/握手开销吃掉一部分。诚实的现实数字:**async 赢在「大量并发等待」,赢幅受连接与事件循环开销折损**。
