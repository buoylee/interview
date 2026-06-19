# 99 · 面试卡:数据访问速记 + 猜行为 drill

> 各章高频题的一句话速记(`问 — 答 ｜标签`),面试前快扫;卡壳的回对应章补。末尾是「猜行为」drill,数字均来自 `lab/` 实测。

## 选型与分层(ch00)

- **Core 和 ORM 怎么选?** Core 操作表/列、你控 SQL,适合批量/报表;ORM 操作对象 + Session 记账,适合 CRUD/领域写;同 engine 混用。｜core-vs-orm
- **什么时候不该用 ORM?** 读多写少的聚合/报表、一次性脚本——ORM 是开销 + 黑箱(N+1)。会用不算资深,知道不用才算。｜no-orm
- **SQLAlchemy 在哪一层?** driver(DBAPI)之上的 Core + ORM 两层,生成 SQL 交给 psycopg/asyncpg 执行;换 driver 只改 URL 前缀。｜layering

## 驱动与 DBAPI(ch01)

- **DBAPI(PEP 249)?** Python 的数据库接口规范(≈JDBC),各 driver 实现,上层框架面向它,换库不换代码。｜dbapi
- **参数化为什么防注入?** 扩展协议下语句模板(Parse)和值(Bind)分两步发,值在语法树定型后才绑定,只当字面量,改不了结构。｜param-binding
- **N+1 为什么慢?** 一次 execute ≈ 一个 RTT;N 条 = N 个往返,延迟被往返数主导,与单条 SQL 多快无关。｜rtt
- **psycopg3 vs asyncpg?** psycopg3 默认(同步、不传染);asyncpg 原生异步、高并发更快但只配 async engine、着色传染。｜drivers
- **脚本没报错数据没进库?** DBAPI 默认在事务里,忘 commit;连接一关就回滚。用 `with conn:`。｜forgot-commit

## 连接池(ch02)

- **为什么要池?** 建连接贵(握手+认证+fork backend),复用摊薄成本,避免顶爆 max_connections。｜pool-why
- **pool_size vs max_overflow?** 硬上限 = 两者之和;overflow 用完即关。｜pool-limit
- **recycle / pre_ping?** recycle 定期回收防老连接被掐断;pre_ping 借出前探测换掉坏连接(生产必开)。｜pool-health
- **池耗尽现象?** 借不到等满 pool_timeout 抛 `QueuePool limit ... timed out`;接口延迟逼近 timeout。常因连接泄漏(没 with/长事务),非池太小。｜pool-exhaust
- **池多大?** 所有实例×worker×(size+overflow) ≤ max_connections − 预留;池每 worker 一份会成倍放大。｜pool-size

## ORM 机制(ch03)

- **Session 是什么?** 一次工作单元:identity map + 脏跟踪 + 关系加载,≈Hibernate persistence context。｜session
- **flush vs commit?** flush 发 SQL 不提交(本事务可见可回滚);commit 先 flush 再提交事务。｜flush-commit
- **identity map?** 同 Session 同主键同对象(`a1 is a2`),防内存里同行分裂。｜identity-map
- **N+1 怎么来?** 关系默认懒加载,循环里逐个访问关系 → 1+N 条。｜n-plus-one-origin
- **DetachedInstanceError?** Session 关后访问未加载的懒加载属性;≈Hibernate LazyInitializationException。eager 加载规避。｜detached

## 事务(ch04)

- **事务边界放哪?** 包住一个业务操作;太大占连接拖垮池(别夹外部 IO),太小丢原子性。｜txn-boundary
- **session-per-request?** 一请求一 Session 一事务;解决连接归还 + Detached。｜session-per-request
- **乐观锁?** version 列 + `WHERE version=读到的` 自增,0 行即冲突抛 StaleDataError(`version_id_col`);读多写少优于悲观锁。｜optimistic-lock
- **序列化失败?** SERIALIZABLE 下读写冲突,提交被中止报 SQLSTATE 40001(psycopg `SerializationFailure`);处理是重试整个事务。｜serialization-failure
- **savepoint?** `begin_nested()` 局部回滚,批量插入个别撞约束跳过其余照提。｜savepoint

## N+1 与性能(ch05)

- **怎么发现 N+1?** echo 看 SQL 流 / `before_cursor_execute` 数条数(可测试断言)/ APM。｜detect-n+1
- **selectinload vs joinedload?** selectinload 父1+子IN=2条,适合一对多;joinedload 一条 JOIN,适合多对一/一对一,拉一对多父行膨胀。｜eager-strategies
- **何时下沉 raw SQL?** 复杂聚合/报表、ORM SQL 失控、大批量写;用 Core/`text()`,同 Session 混用。｜raw-sql
- **怎么读执行计划?** 代码里 `EXPLAIN ANALYZE` 看 Seq Scan / JOIN / 行数耗时定位。｜explain

## 异步(ch06)

- **何时用 async 数据层?** 海量并发 IO + 全异步栈才值;不是更快,是同线程扛更多并发等待;着色传染、架构级决定。｜async-when
- **greenlet 桥?** 让同步式 ORM 跑在可切换栈,需 IO 时交还事件循环 await,完成切回。｜greenlet
- **MissingGreenlet vs Detached?** 前者:对象还绑 open session 但协程里同步触发懒加载;后者:session 已关对象 detached。都靠 eager 规避。｜missing-greenlet
- **async 池?** AsyncAdaptedQueuePool,参数同;常配更大但非无限,超池大小照排队。｜async-pool

## 迁移(ch07)

- **迁移是什么/为什么不自动建表?** schema 的版本化(upgrade/downgrade 链,提交 git);自动建表不可控/不可审计/改名丢数据/无法零停机。｜migrations
- **autogenerate 边界?** 可靠:加删表/列、索引;测不准:改名(误判删+加丢数据)、类型转换、数据迁移——要手写 + 必 review。｜autogenerate
- **不停机改表?** 加索引 `CREATE INDEX CONCURRENTLY`(`postgresql_concurrently=True`+`autocommit_block`);改列扩-迁-缩三步跨多次部署。｜zero-downtime
- **迁移和部署谁先?** 向后兼容先迁移后发码;破坏性走扩-迁-缩,删旧列推到全实例更新后。｜deploy-order

## 架构与测试(ch08)

- **要 repository 吗?** 默认直接 Session;查询复用/隔离领域/会换实现才包,否则 YAGNI。｜repository
- **领域 vs ORM 实体分吗?** 默认合一;领域复杂到实体撑不住才拆(+映射成本)。｜domain-split
- **数据层怎么测?** 真 DB:事务回滚 fixture(快)+ testcontainers(真提交/并发/迁移);别 mock ORM。｜db-testing
- **挡 N+1 回归?** 监听器数 SQL 条数 + `assert count <= 阈值`,CI 早于 APM 发现。｜n+1-assert

---

## 猜行为 drill（数字均为 lab 实测,Postgres 16 / 本地）

**D1.** `make_engine(pool_size=2, max_overflow=0, pool_timeout=1)`,两线程各占一条连接 hold 3s,第三个 `connect()` 会怎样?
<details><summary>答</summary>等满 **1.00s** 后抛 `QueuePool limit of size 2 overflow 0 reached, connection timed out`。等待时长 = pool_timeout。</details>

**D2.** 20 个 author 各 5 本书,`for a in authors: len(a.books)`(默认懒加载)发几条 SQL?加 `selectinload(Author.books)` 呢?
<details><summary>答</summary>懒加载 **21** 条(1 查 authors + 20 查 books);selectinload **2** 条(1+1 IN)。实测时延 35.5ms → 4.5ms。</details>

**D3.** 两事务 SERIALIZABLE,都读 balance=100,都 UPDATE 成 90,先后 commit。第二个 commit 结果?
<details><summary>答</summary>第一个成功(balance=90);第二个被 Postgres 以 **SQLSTATE 40001**(`SerializationFailure`)中止——防住丢更新。正确处理:重试整个事务。</details>

**D4.** `s.add(obj)` 后立刻 `print(obj.id)`,再 `s.flush()` 后再 print。两次分别是什么?
<details><summary>答</summary>flush 前 **None**(还没发 INSERT,自增主键未知);flush 后 **拿到主键**(如 21,但事务还没提交)。</details>

**D5.** `version_id_col` 下,两 Session 都读到 version=1,各自改后先后 commit。第二个 commit?
<details><summary>答</summary>第一个把 version 升到 2;第二个 `UPDATE ... WHERE version=1` 命中 **0 行** → 抛 **StaleDataError**(乐观锁检测到冲突)。</details>

**D6.** async session 里 `a = (await s.scalars(...)).first()`,然后在 `async with` 块**内**直接 `a.books`(没 await、没 eager)。报什么?若改成块**外**访问呢?
<details><summary>答</summary>块内:**MissingGreenlet**(对象绑在 session 上但同步触发懒加载 IO,无桥)。块外:**DetachedInstanceError**(session 已关、对象 detached)。两者都用 `selectinload` 规避。</details>

**D7.** 20 次 `SELECT pg_sleep(0.05)`,sync 单连接串行 vs async 并发(池=20),各约多久?
<details><summary>答</summary>sync ≈ **1.07s**(20×0.05 串行);async ≈ **0.28s**(并发,~3.7x)。注意没到理论 20x——建连 + 事件循环开销折损。</details>
