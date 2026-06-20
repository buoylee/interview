# Go 标准库精要 track —— 设计 spec

> 日期：2026-06-20｜目录：`golang/stdlib/`｜上级：umbrella spec。C 层第四条。

## 背景与目标

标准库是 Go「电池内置」的体现,也是面试常考的实战考点:**io 接口家族(组合哲学的最佳范例)**、**net/http(server 中间件 + client 连接池/超时)**、**encoding/json(tag/流式/自定义 Marshaler)**、**database/sql(连接池/事务/context)**。用户从 Java(java.io/HttpClient/Jackson/JDBC+HikariCP)来,直接对照。

## 核心设计决策

- 形式:4 章,照搬模板(7 段 + 面试卡)。
- 主线钥匙:**「标准库用小接口组合(io.Reader/Writer 为典范);http.Client 和 sql.DB 都是要复用的池;凡阻塞皆接 ctx」**。
- 双向桥:java.io 装饰器流、HttpClient、Jackson/Gson 注解、JDBC + HikariCP。
- 底层/实战进正文:io 单方法接口 + 组合 + io.Copy 的 ReaderFrom/WriterTo 优化;http server Handler/ServeMux(1.22 方法+路径)/中间件、client Transport 连接池 + 超时 + 必须 drain body;json tag/omitempty/流式 Encoder/自定义 Marshaler/RawMessage/数字解析坑;sql.DB 是池(SetMaxOpenConns 等)/事务/context 方法/Scan/NULL/必须 rows.Close。
- 互链:[`design/00`](接口设计——io 是范例)、[`concurrency/07`](ctx)、[`error-handling`](io.EOF 哨兵)、[`data-structures/02`](string/[]byte)。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-io/` | io 接口家族 | Reader/Writer/Closer / 组合 / bufio / io.Copy / 流式 / io.EOF |
| `01-net-http/` | net/http | server(Handler/ServeMux 1.22/中间件)/ client(Transport 连接池·超时·复用·drain body)/ ctx |
| `02-encoding-json/` | encoding/json | tag/omitempty / Marshal·Unmarshal / 流式 Encoder·Decoder / 自定义 Marshaler / RawMessage / 数字坑 |
| `03-database-sql/` | database/sql | sql.DB 是连接池(SetMaxOpenConns…)/ 事务 / context 方法 / Scan / NULL / 驱动模型 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡 |

## 交付节奏
1 spec → 2 骨架 → 3 四章 + 面试卡。

## 验收
- 00 能讲 io.Reader/Writer 为什么是组合典范、io.Copy 怎么用。
- 01 能讲 http.Client 要复用、默认无超时的坑、连接复用要 drain body、ServeMux 1.22 路由、中间件。
- 02 能讲 tag/omitempty/流式/自定义 Marshaler/数字解析成 float64 的坑。
- 03 能讲 sql.DB 是池不是连接、连接池参数、事务、必须 rows.Close、NULL 处理。

## 非目标
- 不做标准库 API 大全;聚焦四个高频包的设计与坑。
- 不展开 gRPC(归 service-design)、不展开 ORM。
