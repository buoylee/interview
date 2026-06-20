# Go 错误处理 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/error-handling/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）

## 背景与目标

用户面试被「Go 错误处理最佳实践」问住——这正是 Go 与 Java/Python **设计哲学差最大**的一块：Go 把 error 当**普通返回值**，故意不要异常控制流。资深/架构师面试不止考 API（`errors.Is`/`As`），更考**取舍与设计**：什么时候 panic、API 边界暴露什么错误、错误怎么分层不泄漏内部、并发里错误怎么聚合传播。本 track 要把这套从哲学讲到实战。

目标：读完能在面试白板上讲清「Go 为什么不用异常」「`%w` 包装与 `Is/As` 的匹配机制」「defer/recover 的求值与执行时机」「错误设计的边界原则」，并指导日常写出 idiomatic 的错误代码。

## 核心设计决策

- **形式**：6 章 mini-track，照搬 `concurrency/` 模板（每章 7 段 + `99-interview-cards/`）。
- **主线钥匙 = 「error 是值（value），不是控制流（exception）」**：所有章节最后落回这条。Java 异常是「抛出去让上层管」，Go error 是「就地当数据处理或显式上抛」。
- **双向桥**：每章对照 **Java 异常体系**（checked/unchecked、try-catch-finally、异常链 `getCause`、`try-with-resources`）与 **Python**（`try/except`、`raise from`、`contextlib`），点明 Go 的取舍。
- **底层内幕进正文**：`error` 接口本质、`%w` 如何构造 `wrapError`、`Is`/`As` 如何沿 `Unwrap()` 链遍历、`Unwrap() []error`（1.20 多重包装）、defer 的参数求值时机与 LIFO 执行、recover 为什么只在 defer 直接调用才生效。
- **架构师视角**：第 04 章是重心——错误分层、边界暴露、哨兵 vs 行为接口、不重复包装、错误与日志/可观测性的分工。
- **Go 版本标注**：`Is`/`As`/`Unwrap` 1.13；多重 `%w` 与 `errors.Join`、`Unwrap() []error`、`WithCancelCause`/`Cause` 1.20。Go 2 `check/handle`、`try` 提案均已**否决**——讲清「为什么社区选择不加语法糖」。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-philosophy/` | **错误哲学** | error 是值不是异常；为什么 Go 故意不要 try-catch；与 Java 异常/Go panic 的边界划分 ← 立地基 |
| `01-error-values/` | error 接口与三种风格 | `error` 接口本质；sentinel（`io.EOF`）/ typed（自定义 struct）/ opaque（不透明，只暴露行为）三种风格的取舍 |
| `02-wrapping/` | 包装与检查 | `fmt.Errorf %w` 怎么构造错误链；`errors.Is`（值匹配）/ `errors.As`（类型提取）/ `errors.Unwrap` 的遍历机制；多重 `%w`（1.20） |
| `03-panic-recover-defer/` | panic·recover·defer | defer 参数求值 vs 执行时机、LIFO；recover 只在 defer 直接生效；re-panic；panic 跨 goroutine 不可恢复；**何时才该 panic** |
| `04-error-design/` | **错误设计实战** ← 重心 | API 边界暴露什么；错误分层（领域错误 vs 基础设施错误）；不泄漏内部；不重复包装；哨兵 vs 行为接口；错误与日志/可观测性的分工；`errors.Join` 聚合 |
| `05-concurrent-errors/` | 并发中的错误 | `errgroup`（首错取消）；`errors.Join` 聚合多 goroutine 错误；goroutine 里的 panic 会**整进程 crash**；channel 传错误的惯例 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡（error vs 异常 / `%w` 与 Is·As / defer·recover 时机 / 何时 panic / errgroup），链回正文 |

## 已有素材的处理

- 链接 `golang/concurrency/07-context/`（取消传播）与 `08-patterns/`（errgroup 已提及）——第 05 章错误聚合与之互链，不重复讲 errgroup 的并发机制，只讲「错误」这一面。
- 链接 `golang/concurrency/04-goroutine/`（goroutine panic / 泄漏）——第 03/05 章引用。
- 现有顶层 stub 与本 track 无重叠，不动。

## 交付节奏

1. 写本 track spec（本文件）。
2. 搭骨架：`error-handling/README.md`（进度地图 + 章节地图）+ 6 个章节目录。
3. **先写 00 + 04**：00 立「error 是值」哲学地基，04 是用户面试卡住的「错误设计最佳实践」核心。确认深度/风格后逐章补 01/02/03/05 + 面试卡。

## 验收标准

- 00 能讲清「Go 为什么不用异常」且给出 panic vs error 的边界判据。
- 02 能在白板上画出 `%w` 错误链与 `Is`/`As` 的遍历过程。
- 04 能回答「你的 API 该向调用方暴露什么错误、怎么不泄漏内部、怎么不重复包装」——即面试卡住的那道题。
- 面试卡每张链回正文证据。

## 非目标（YAGNI）

- 不重讲 errgroup/context 的并发机制（链接 concurrency track）。
- 不做某框架专属的错误中间件（service-design track 再谈）。
- 不逐行读 `errors`/`fmt` 源码，深到「关键结构 + 遍历逻辑 + 为什么」即可。
