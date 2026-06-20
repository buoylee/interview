# 03 · database/sql:连接池、事务、context

> `database/sql` 是 Go 访问关系库的标准抽象。最大认知点:**`sql.DB` 不是一条连接,而是一个连接池**。再加上事务、context、`rows.Close` 的坑、NULL 处理——都是面试和生产高频。
>
> 桥接锚点:Java JDBC(`Connection`/`Statement`/`ResultSet`)+ HikariCP 连接池;Go 把池**内建进 `sql.DB`**,你不用单独配池库,但要懂它的参数。

---

## 1. 核心问题

- `sql.DB` 是一条连接吗?要不要每次用完关掉、每次新建?
- 连接池怎么配?不配会怎样?
- 查询完为什么必须 `rows.Close()`?不关会怎样?
- 数据库 NULL 怎么扫进 Go 变量?

---

## 2. 直觉理解

### sql.DB 是连接池,不是连接

```go
db, err := sql.Open("postgres", dsn)   // 不真正连接,只是创建池(惰性)
// db 是 *sql.DB —— 一个连接池!全局建一个、长期复用、并发安全
defer db.Close()                        // 程序退出才关(不是每次查询后)
```

最关键认知:**`sql.DB` 是一个并发安全的连接池**,不是一条连接。所以:

- **全局建一个 `db`、长期复用**(像 [`01 net/http`](../01-net-http/README.md) 的 client),别每次请求 `sql.Open`(那会建一堆池,灾难)。
- `sql.Open` **不立即连接**(惰性),第一次查询才真正建连;想立即验证用 `db.Ping()`。
- `db` 并发安全,多 goroutine 直接共用。

### 连接池要配,否则默认有坑

```go
db.SetMaxOpenConns(25)                  // 最大并发连接数(0=无限,可能压垮 DB)
db.SetMaxIdleConns(25)                  // 空闲连接数(太小→频繁建连)
db.SetConnMaxLifetime(5 * time.Minute)  // 连接最长存活(防 DB/LB 掐断的陈旧连接)
db.SetConnMaxIdleTime(time.Minute)
```

默认 `MaxOpenConns=0`(无限,高并发会建爆连接打挂 DB)、`MaxIdleConns=2`(太小,频繁建关连接)。**生产必须显式配**。

### 查询完必须关 rows

```go
rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
if err != nil { return err }
defer rows.Close()                       // 必须!否则连接不还池→池耗尽
for rows.Next() {
    var id int; var name string
    if err := rows.Scan(&id, &name); err != nil { return err }
}
return rows.Err()                        // 别忘了检查迭代中的错误
```

`Query` 借走一条连接,**不 `rows.Close()` 连接就不还池**——很快池耗尽、所有查询挂起。`defer rows.Close()` 是铁律。

---

## 3. 原理深入

### 3.1 Query / Exec / QueryRow + Context 版本

```go
db.QueryContext(ctx, q, args...)    // 多行,返回 *Rows(要 Close)
db.QueryRowContext(ctx, q, args...) // 单行,.Scan() 即可(无需 Close)
db.ExecContext(ctx, q, args...)     // 增删改,返回 Result(RowsAffected/LastInsertId)
```

**永远用带 `Context` 的版本** + 占位符参数(`$1`/`?`)防 SQL 注入(见 5 节)。ctx 让查询能超时/取消(承接 [`concurrency/07`](../../concurrency/07-context/README.md))。

### 3.2 事务

```go
tx, err := db.BeginTx(ctx, nil)
if err != nil { return err }
defer tx.Rollback()                  // 关键:defer Rollback,Commit 成功后 Rollback 变 no-op
if _, err := tx.ExecContext(ctx, "UPDATE ..."); err != nil {
    return err                       // 出错直接返回,defer 的 Rollback 兜底
}
return tx.Commit()                   // 成功提交
```

模式:`defer tx.Rollback()` + 末尾 `tx.Commit()`。Commit 后 Rollback 自动变 no-op,所以这个 defer 安全地兜住所有错误路径(忘了显式 Rollback 的坑)。事务期间所有操作用 `tx.`(同一条连接)。

### 3.3 NULL 处理

数据库 NULL 不能直接扫进 `string`/`int`(会报错)。两种办法:

```go
var name sql.NullString              // sql.NullString{String, Valid}
rows.Scan(&name)
if name.Valid { use(name.String) }
// 或用指针:*string,NULL → nil
var name *string
rows.Scan(&name)
```

可空列用 `sql.NullXxx` 或指针类型。

### 3.4 驱动模型

`database/sql` 只是**接口层**,真正连库靠**驱动**(匿名导入注册):

```go
import _ "github.com/lib/pq"          // Postgres 驱动,init 时注册 "postgres"
db, _ := sql.Open("postgres", dsn)
```

标准库定义 `driver.Driver` 接口,各驱动(pq/pgx、mysql、sqlite)实现它——又是「小接口 + 多实现」(见 [`design/00`](../../design/00-interface-design/README.md))。换库只换驱动 + DSN。

### 3.5 prepared statement

`db.PrepareContext` 返回可复用的 `*Stmt`(预编译,防注入 + 复用执行计划)。但注意:`Stmt` 绑在连接上,池里跨连接会重新 prepare;高频简单查询直接用 `QueryContext`(它内部也会 prepare)往往更省心。

---

## 4. 日常开发应用

- **全局一个 `*sql.DB`**、长期复用、并发共享;别每次 `sql.Open`。
- **启动时配连接池**(MaxOpenConns/MaxIdleConns/ConnMaxLifetime)+ `Ping()` 验证。
- **永远用 `XxxContext` + 占位符参数**(防注入 + 可取消)。
- **`defer rows.Close()` + 检查 `rows.Err()`**。
- **事务用 `defer tx.Rollback()` + `tx.Commit()`** 模式。
- **可空列用 `sql.NullXxx` 或指针**。
- 复杂场景用 `sqlx`(扫描到 struct)或 `pgx`(原生 PG);ORM(gorm)按需,但理解底层池仍重要。

---

## 5. 生产&调优实战

- **`sql.Open` 每请求一次 = 灾难**:建一堆池、连接爆炸打挂 DB。全局单例。
- **不配 MaxOpenConns 会打挂 DB**:默认无限,高并发瞬间几千连接;按 DB 承载力设上限(常 25-100),让超出的请求排队而非压垮 DB。
- **不 `rows.Close()` = 连接泄漏 = 池耗尽**:表现为查询全部 hang;`defer rows.Close()` + `go vet`/`sqlclosecheck` 工具检查。
- **`SetConnMaxLifetime` 防陈旧连接**:DB/负载均衡/防火墙会掐断长连接,池里留着会拿到坏连接报错;设个 lifetime(如 5min)让池定期换新。
- **SQL 注入**:永远用占位符参数(`$1`/`?`),**绝不** `fmt.Sprintf` 拼 SQL(见 [`error-handling/04`](../../error-handling/04-error-design/README.md) 安全)。
- **ctx 超时**:慢查询用 ctx 超时能取消(驱动支持时真的会中断),防一个慢查询占满连接池。
- **监控池**:`db.Stats()` 看 InUse/Idle/WaitCount,WaitCount 高说明池太小或有连接泄漏。

---

## 6. 面试高频考点

- **`sql.DB` 是连接吗?** 不是,是**并发安全的连接池**;全局建一个长期复用,`sql.Open` 惰性不立即连(`Ping` 验证)。别每次请求 Open。
- **连接池怎么配?默认坑?** SetMaxOpenConns(默认 0 无限,会打挂 DB)、SetMaxIdleConns(默认 2,太小)、SetConnMaxLifetime(防陈旧连接)。生产必须显式配。
- **为什么必须 rows.Close()?** Query 借走连接,不 Close 不还池 → 池耗尽、查询全 hang。`defer rows.Close()` + 查 `rows.Err()`。
- **事务怎么写得安全?** `BeginTx` + `defer tx.Rollback()`(Commit 后变 no-op,兜住所有错误路径)+ 末尾 `tx.Commit()`。
- **NULL 怎么处理?** `sql.NullString`/`NullInt64` 或指针类型。
- **怎么防 SQL 注入?** 占位符参数(`$1`/`?`),绝不字符串拼接。
- **driver 怎么接?** `database/sql` 是接口层,匿名导入驱动(`_ "github.com/lib/pq"`)注册;小接口多实现,换库换驱动 + DSN。
- **和 JDBC 对比?** JDBC 的 Connection 要配 HikariCP;Go 的池内建进 sql.DB,但参数要自己调。

---

## 7. 一句话总结

> **`database/sql` 最关键认知:`sql.DB` 不是一条连接,是一个并发安全的连接池**——全局建一个、长期复用(别每次 `sql.Open`),`Open` 惰性不立即连(`Ping` 验证)。**连接池必须显式配**(MaxOpenConns 默认无限会打挂 DB、MaxIdleConns 默认才 2、SetConnMaxLifetime 防陈旧连接)。查询**必须 `defer rows.Close()`**(否则连接不还池→耗尽→全 hang)+ 检查 `rows.Err()`。永远用 `XxxContext` + 占位符参数(可取消 + 防注入,绝不拼 SQL)。事务用 `defer tx.Rollback()` + `tx.Commit()` 兜错误路径;NULL 用 `sql.NullXxx`/指针;驱动靠匿名导入注册(小接口多实现)。≈ JDBC + HikariCP,但池内建进 sql.DB。

← 上一章 [`02 encoding/json`](../02-encoding-json/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):io 家族、net/http、json、database/sql 速查。｜ 回 [`stdlib` 索引](../README.md)
