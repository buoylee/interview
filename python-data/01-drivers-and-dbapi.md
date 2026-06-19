# 01 · 驱动与 DBAPI:Python 跟数据库通话的最底层

> **为什么这章重要**:ORM 再花哨,落到地上都是一个 driver 在跟数据库收发字节。看懂这一层,你才答得上「参数化为什么能防注入」「为什么一堆小查询那么慢」「psycopg 和 asyncpg 到底差在哪」——这些是 ORM 帮你藏起来、但出事时必须掀开的底。
>
> **一句话心智**:**连接是资源**(要显式关)、**SQL 永远参数化**(值和语句分开传)、**一次 `execute` 是一次网络往返**(RTT 才是小查询的隐藏成本)。

## 一、PEP 249:Python 的 JDBC

Python 没有「官方数据库 API 实现」,但有一份**接口规范**——**PEP 249 / DBAPI 2.0**。每个 driver(psycopg、asyncpg、sqlite3、PyMySQL…)都实现它,于是上层(SQLAlchemy、Django ORM)只需面向这一套接口,换库不换代码。

核心就五个动词:

```python
import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost/datalab")  # 连
cur = conn.cursor()                                  # 游标:一次查询的执行/取数句柄
cur.execute("SELECT id, name FROM authors WHERE id = %s", (1,))  # 执行(带参数)
row = cur.fetchone()                                 # 取一行 -> (1, 'Author 1')
conn.commit()                                        # 提交(DBAPI 默认开事务!)
conn.close()                                         # 关连接(释放资源)
```

DBAPI ≈ Java 的 JDBC:`Connection`/`Statement`/`ResultSet` 对应 `connection`/`cursor`/`fetch*`。两个 Java 人最容易踩的差异:

1. **DBAPI 默认在事务里**(`autocommit=False`)。不 `commit()`,你的写入只活在这条连接的事务里,别的连接看不到、连接一关就回滚。Java 里 JDBC 也是默认手动提交,这点反而一致——但很多人被「脚本跑完没报错、数据却没进库」坑过,根因就是忘了 commit。
2. **`paramstyle` 因 driver 而异**:psycopg 用 `%s`,sqlite3 用 `?`,有的用 `:name`。这是 DBAPI 留的方言。**好在你几乎永远不直接写 DBAPI**——SQLAlchemy 帮你抹平。

## 二、参数化:不是为了好看,是为了不被注入

**永远不要把值拼进 SQL 字符串**,把它作为**参数**单独传:

```python
# ✅ 参数化:值走独立通道,driver/数据库当「数据」处理
cur.execute("SELECT * FROM authors WHERE name = %s", (user_input,))

# ❌ 字符串拼接:user_input = "x'; DROP TABLE authors; --" 就完了
cur.execute(f"SELECT * FROM authors WHERE name = '{user_input}'")
```

**机制**(这是面试爱追的「为什么」):参数化不是「转义引号」那么浅。在 Postgres 的扩展查询协议下,SQL **语句模板**和**参数值**是**分两条消息**发给数据库的——数据库先 `Parse`(只解析模板、定下语法树),再 `Bind`(把值塞进占位符)。值是在语法树**已经定型之后**才进来的,所以它无论包含什么引号、分号、`DROP TABLE`,都只会被当成**一个字符串字面量**,绝无可能改变语句结构。拼接则相反——值在解析**之前**就成了 SQL 文本的一部分,于是能改写语句。

> 注入的语言层细节(`eval`/拼接/转义的坑)见 [`../python/18`](../python/18-security.md)。这里给你 driver 层的根因:**参数化 = 语句结构和数据在协议层就分了家**。

## 三、内幕:一次 `execute` 到底发生了什么

Postgres 的**扩展查询协议**,一次参数化 `execute` 是一组消息往返:

```
客户端 ──Parse──►   服务端解析 SQL 模板,（可选）存成 prepared statement
客户端 ──Bind──►    把参数值绑定到这个语句
客户端 ──Execute──► 真正执行,服务端开始算
客户端 ──Sync──►    一个事务边界标记
服务端 ──结果──►    行数据 / 完成标记
```

关键推论:**一次 `execute` ≈ 一个网络往返(RTT)**。本地回环 RTT 是几十微秒,跨可用区是几毫秒。于是:

- **N 次小查询 = N 个 RTT**。哪怕每条 SQL 在数据库里只跑 0.1ms,100 条跨网就是 100 个 RTT——这正是 **N+1 问题**慢的物理根源(第 [05](05-n-plus-one-and-query-perf.md) 章)。修法的本质都是**把 N 个往返压成 1~2 个**(JOIN、`IN`、批量)。
- **prepared statement** 让重复执行同一模板省掉 `Parse`:模板解析一次、缓存执行计划,后续只 `Bind+Execute`。psycopg3 会对重复语句自动 prepare;这对「同一条 SQL 跑很多次」(循环里、热点接口)是实打实的提速。

> 想从 Python 侧亲眼看一次查询的执行计划?第 [05](05-n-plus-one-and-query-perf.md) 章有 `EXPLAIN (ANALYZE)` 从代码里跑出来的例子。

## 四、psycopg3 vs asyncpg:两个 Postgres driver

SQLAlchemy 连 Postgres 最常用这两个,**通过 URL 前缀选**:

```python
SYNC_URL  = "postgresql+psycopg://postgres:postgres@localhost/datalab"   # psycopg3,同步阻塞
ASYNC_URL = "postgresql+asyncpg://postgres:postgres@localhost/datalab"   # asyncpg,原生异步
```

| | psycopg3 | asyncpg |
|---|---|---|
| 模型 | 同步阻塞(也支持 async) | **原生 async**(为 asyncio 而生) |
| 用在 | 常规 / 阻塞栈 / 脚本 | 高并发异步栈(FastAPI 等) |
| 性能特点 | 稳、通用 | 协议层手写优化,高并发下更快 |
| 配 SQLAlchemy | `postgresql+psycopg://` | `postgresql+asyncpg://`(只能配 async engine) |

记忆:**psycopg3 = 默认选择**(简单、不传染 async);**asyncpg = 你已经全异步了才上**(第 [06](06-async-data-access.md) 章详述 async 数据访问与它的代价)。别为了「听说 asyncpg 快」就在同步项目里硬塞——你会被迫把整条链路改异步。

## 五、连接是资源:永远用 `with` 关掉

连接占着 TCP + 服务端一个 backend 进程,**漏了不关 = 连接泄漏 = 最终池耗尽**(第 [02](02-connection-pooling.md) 章)。所以一律 `with`:

```python
# 裸 DBAPI:with 自动 commit(正常退出)/ rollback(异常)+ 关闭
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("UPDATE accounts SET balance = balance - 10 WHERE id = %s", (1,))
    # 退出内层:cursor 关;退出外层:事务提交 + 连接关
```

实践里你几乎不裸用 DBAPI——SQLAlchemy 的 `engine.connect()` / `Session` 同样是 `with` 上下文,且背后接的是**连接池**(用完归还而非真关)。但「连接是必须显式释放的资源」这条心智,从最底层一直贯穿到 ORM。

## Java/Go 对照框

| 关注点 | Java(JDBC) | Go(`database/sql`) | Python(DBAPI) |
|---|---|---|---|
| 接口规范 | JDBC | `database/sql` 接口 | PEP 249 |
| 连接 / 执行 | `Connection`/`Statement`/`ResultSet` | `DB`/`Stmt`/`Rows` | `connection`/`cursor`/`fetch*` |
| 参数化 | `PreparedStatement` `?` | `db.Query("... ?", args)` | `execute(sql, params)`(`%s`/`?`/`:name`) |
| 默认事务 | 手动 commit | 显式 `Begin/Commit` | **手动 commit**(易忘) |
| 异步 | 同步 / R2DBC | 同步 + goroutine | 同步(psycopg)/ async(asyncpg) |

最大相通处:**参数化 = `PreparedStatement`**,机制一模一样(语句结构和数据分家)。最大差异:Go 的 `database/sql` 内建连接池;Python 的 DBAPI **不带池**,池是 SQLAlchemy 给的(下一章)。

## 章末面试卡

**Q1. DBAPI(PEP 249)是什么?**
Python 的数据库访问**接口规范**(类比 JDBC),定义 `connect/cursor/execute/fetch*/commit` 等。各 driver(psycopg、asyncpg、sqlite3)各自实现,上层框架面向这套接口,所以换 driver 不改上层代码。

**Q2. 参数化查询为什么能防 SQL 注入(讲机制,别只说「能防」)?**
因为在扩展查询协议下,SQL 语句模板(`Parse`)和参数值(`Bind`)是分两步、分通道发给数据库的;值是在语法树定型之后才绑定的,无论它含什么引号/分号,只会被当成字符串字面量,改变不了语句结构。字符串拼接则让值在解析前就混进 SQL 文本,所以能注入。

**Q3. 为什么一堆小查询(N+1)那么慢?**
因为**一次 `execute` ≈ 一个网络往返(RTT)**。哪怕单条 SQL 在库里只跑零点几毫秒,N 条跨网就是 N 个 RTT,延迟被往返次数主导。修法的本质是把 N 个往返压成 1~2 个(JOIN / IN / 批量)。

**Q4. psycopg3 和 asyncpg 怎么选?**
psycopg3 是默认:同步阻塞、通用、不会让代码被迫异步。asyncpg 是原生异步驱动,高并发下更快,但只配 async engine、会把 `await` 着色传染整条链路——只在你已经是全异步栈(如 FastAPI async)时才上。

**Q5. 为什么脚本跑完没报错,数据却没进库?**
DBAPI 默认在事务里(非 autocommit),忘了 `commit()` 的话写入只活在那条连接的事务中,连接一关就回滚。用 `with conn:` 让正常退出自动提交,可避免。
