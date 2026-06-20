# database/sql:连接池·事务·rows.Close

## 一句话回答

最关键认知:**`sql.DB` 不是一条连接,是一个并发安全的连接池**——全局建一个、长期复用(别每次 `sql.Open`),`Open` 惰性不立即连(`Ping` 验证)。**连接池必须显式配**(`SetMaxOpenConns` 默认无限会打挂 DB、`SetMaxIdleConns` 默认才 2、`SetConnMaxLifetime` 防陈旧连接)。查询**必须 `defer rows.Close()`**(否则借走的连接不还池→耗尽→查询全 hang)+ 检查 `rows.Err()`。永远用 `XxxContext` + 占位符参数(可取消 + 防注入)。

## 事务安全写法

```go
tx, _ := db.BeginTx(ctx, nil)
defer tx.Rollback()              // Commit 成功后变 no-op,兜住所有错误路径
tx.ExecContext(ctx, "...")
return tx.Commit()
```

## 其它

- **NULL**:`sql.NullString`/`NullInt64` 或指针类型。
- **防注入**:占位符 `$1`/`?`,绝不 `fmt.Sprintf` 拼 SQL。
- **驱动**:`database/sql` 是接口层,匿名导入注册(`_ "github.com/lib/pq"`);小接口多实现。

## 证据链接

- 正文:[`03 database/sql`](../03-database-sql/README.md);ctx [`concurrency/07`](../../../concurrency/07-context/README.md);连接池类比 [`01 net/http`](../01-net-http/README.md)

## 易追问的延伸

- **每请求 sql.Open?** 灾难——建一堆池、连接爆炸打挂 DB。全局单例。
- **不配 MaxOpenConns?** 默认无限,高并发瞬间几千连接打挂 DB;设上限让请求排队。
- **ConnMaxLifetime 为什么要?** DB/LB/防火墙会掐断长连接,池里留着会拿坏连接;定期换新。
- **监控?** `db.Stats()` 看 InUse/Idle/WaitCount,WaitCount 高=池太小或泄漏。
- **和 JDBC?** JDBC Connection + HikariCP;Go 池内建进 sql.DB,参数自己调。
