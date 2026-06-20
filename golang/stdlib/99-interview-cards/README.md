# 99 · 面试卡 —— Go 标准库精要高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**io.Reader/Writer 是小接口组合典范;http.Client 和 sql.DB 都是要复用的池;凡阻塞皆接 ctx。**

## 卡片索引(深题卡)

- [io 接口家族:Reader/Writer/Copy](q-io-interfaces.md)
- [net/http:client 连接池·超时·drain body](q-net-http.md)
- [encoding/json:tag·流式·float64 坑](q-json.md)
- [database/sql:连接池·事务·rows.Close](q-database-sql.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| io.Reader/Writer 为什么这么设计 | 单方法接口→无数类型满足→统一处理文件/网络/内存/HTTP;组合典范 | [00](../00-io/README.md) |
| Read 契约坑 | 可能同时返 n>0 和 err;先处理 n 再判 err;io.EOF 是正常结束哨兵 | [00](../00-io/README.md) |
| io.Copy 优化 | 缓冲搬运;dst 实现 ReaderFrom 或 src 实现 WriterTo 则零拷贝/sendfile | [00](../00-io/README.md) |
| 怎么流式不 OOM | io.Copy/bufio.Scanner/json.Decoder,别 io.ReadAll;LimitReader 设上限 | [00](../00-io/README.md) |
| 写 HTTP 要框架吗 | 标准库够(1.22 ServeMux 支持 GET /x/{id});中间件=func(Handler)Handler 洋葱 | [01](../01-net-http/README.md) |
| 为什么不能用 http.Get | 默认 Timeout=0 永不超时,下游卡住就泄漏 | [01](../01-net-http/README.md) |
| http.Client 要复用吗 | 要;内部 Transport 是 keep-alive 连接池,每次 new 丢池+TIME_WAIT 暴涨 | [01](../01-net-http/README.md) |
| 为什么必须读完关 body | 不读完 body 连接不能放回池复用→泄漏;defer Close + io.Copy(Discard,body) | [01](../01-net-http/README.md) |
| 连接池调什么 | MaxIdleConnsPerHost(默认才 2,高并发要调大)/MaxIdleConns/IdleConnTimeout | [01](../01-net-http/README.md) |
| server 超时 | Read/Write/IdleTimeout 防慢攻击;Shutdown(ctx) 优雅关闭 | [01](../01-net-http/README.md) |
| json 什么字段被序列化 | 只有导出字段(大写);tag 改名/omitempty 省零值/`-` 忽略;未导出永远忽略 | [02](../02-encoding-json/README.md) |
| 数字解进 interface{} 为什么 float64 | JSON 不分整浮,解进 any 一律 float64;要精度用 UseNumber/解进具体类型 | [02](../02-encoding-json/README.md) |
| Marshal vs Encoder | Marshal 一次性进内存;Encoder/Decoder 流式对接 io,HTTP body 用它 | [02](../02-encoding-json/README.md) |
| 自定义序列化 | 实现 MarshalJSON/UnmarshalJSON(枚举↔字符串/时间格式) | [02](../02-encoding-json/README.md) |
| 区分缺失 vs 零值 | 用指针字段(*int,nil=缺失);普通 int 区分不了 | [02](../02-encoding-json/README.md) |
| sql.DB 是连接吗 | 不是,是并发安全连接池;全局一个长期复用;Open 惰性,Ping 验证 | [03](../03-database-sql/README.md) |
| 连接池怎么配 | SetMaxOpenConns(默认无限会打挂DB)/MaxIdleConns(默认2)/ConnMaxLifetime | [03](../03-database-sql/README.md) |
| 为什么必须 rows.Close | Query 借连接不 Close 不还池→耗尽→查询全 hang;defer rows.Close + rows.Err | [03](../03-database-sql/README.md) |
| 事务安全写法 | BeginTx + defer tx.Rollback(Commit 后变 no-op)+ 末尾 tx.Commit | [03](../03-database-sql/README.md) |
| NULL 处理 | sql.NullString/NullInt64 或指针类型 | [03](../03-database-sql/README.md) |
| 防 SQL 注入 | 占位符参数($1/?),绝不 fmt.Sprintf 拼 SQL | [03](../03-database-sql/README.md) |

← 回 [`stdlib` 索引](../README.md)
