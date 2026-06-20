# Go 标准库精要 —— 给 Java 后端的「电池内置 + 小接口组合」

> C 层第四条。Go 标准库「电池内置」,且设计本身就是 idiomatic Go 的范本:**io 接口家族**是组合哲学的最佳示范、**net/http** 自带生产级 server/client、**encoding/json** 和 **database/sql** 覆盖日常。面试常考这四个包的**设计与坑**。
>
> 总钥匙:**io.Reader/Writer 是小接口组合的典范;http.Client 和 sql.DB 都是「要复用的池」;凡阻塞/IO 皆接 ctx。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-stdlib-track-design.md`｜Go 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` io 接口家族(理解组合),`01` net/http,`02` encoding/json,`03` database/sql。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(java.io 装饰器流 / HttpClient / Jackson / JDBC+HikariCP)。
4. **想答面试**：去 `99-interview-cards/`。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-io/`](00-io/) | io 接口家族 | Reader/Writer/Closer / 组合 / bufio / `io.Copy` / 流式 / `io.EOF` ← 从这开始 |
| [`01-net-http/`](01-net-http/) | net/http | server(Handler/ServeMux/中间件)/ client(**连接池·超时·复用·drain body**)/ ctx |
| [`02-encoding-json/`](02-encoding-json/) | encoding/json | tag·omitempty / 流式 Encoder·Decoder / 自定义 Marshaler / RawMessage / 数字坑 |
| [`03-database-sql/`](03-database-sql/) | database/sql | **sql.DB 是连接池** / 事务 / context 方法 / Scan / NULL / 驱动模型 |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 |
|---|---|
| 设计 spec | ✅ |
| 骨架 + 进度地图 | ✅ |
| 00-io | ✅ Reader/Writer 组合典范 / io.Copy / 流式 / io.EOF |
| 01-net-http | ✅ Handler·ServeMux 1.22·中间件 / client 连接池·超时·drain body |
| 02-encoding-json | ✅ tag·omitempty / 流式 / 自定义 Marshaler / float64 坑 |
| 03-database-sql | ✅ sql.DB 是池 / 连接池参数 / 事务 / rows.Close / NULL |
| 99-interview-cards | ✅ 速答表(22 条) + 4 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- [`design/00`](../design/00-interface-design/README.md) — 接口设计(io 是范例)
- [`concurrency/07`](../concurrency/07-context/README.md) — ctx(http/sql 都接 ctx)
- [`error-handling/01`](../error-handling/01-error-values/README.md) — io.EOF 哨兵
- [`data-structures/02`](../data-structures/02-string-bytes-rune/README.md) — string/[]byte(io 处理字节)
- `java/` — java.io / JDBC / Jackson 对标锚点

← 回 [`golang/` master 索引](../README.md)
