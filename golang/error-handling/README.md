# Go 错误处理 —— 给 Java/Python 后端的「error 是值，不是控制流」

> Go 把错误当**普通返回值**，故意不要 try-catch 异常控制流。这是 Go 与 Java/Python **哲学差最大**的一块，也是资深面试最爱考取舍的一块。本 track 从「为什么是值」讲到「架构师怎么设计错误」。
>
> 总钥匙：**error 是值（value），不是异常（exception）**。Java 是「抛出去让上层 catch」，Go 是「就地当数据处理，或显式 `return err` 上抛」。每章最后都落回这条。
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-error-handling-track-design.md`｜Go 版本基线 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` 立哲学地基（为什么不用异常），`01–02` 是核心机制（三种错误风格 + `%w`/`Is`/`As` 包装检查），`03` 讲 panic·recover·defer 的真实语义，`04` 是**架构师重心**（错误设计实战），`05` 收并发里的错误。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
3. **双向桥**：每章对照 **Java 异常**（checked/unchecked、try-catch-finally、`getCause` 异常链、try-with-resources）与 **Python**（`try/except`、`raise from`）。
4. **想答面试**：去 `99-interview-cards/` 找卡，链回正文做证据。

## 容易忘时先看这里

- [何时该 panic、何时该 return err](03-panic-recover-defer/README.md) — 边界判据，面试高频。
- [API 边界该暴露什么错误](04-error-design/README.md) — 架构师题，也是最常答不好的那道。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-philosophy/`](00-philosophy/) | **错误哲学** | error 是值不是异常；为什么 Go 故意不要 try-catch；error vs panic 的边界 ← 从这开始 |
| [`01-error-values/`](01-error-values/) | error 接口与三种风格 | `error` 接口本质；sentinel / typed / opaque 三种风格的取舍 |
| [`02-wrapping/`](02-wrapping/) | 包装与检查 | `%w` 怎么造错误链；`errors.Is`/`As`/`Unwrap` 遍历机制；多重 `%w`(1.20) |
| [`03-panic-recover-defer/`](03-panic-recover-defer/) | panic·recover·defer | defer 求值 vs 执行时机、LIFO；recover 只在 defer 生效；何时才该 panic |
| [`04-error-design/`](04-error-design/) | **错误设计实战** ← 重心 | 边界暴露什么 / 错误分层 / 不泄漏内部 / 不重复包装 / 哨兵 vs 行为接口 / 与日志分工 |
| [`05-concurrent-errors/`](05-concurrent-errors/) | 并发中的错误 | errgroup 首错取消 / `errors.Join` 聚合 / goroutine panic 整进程 crash |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-error-handling-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-philosophy | ✅ | error 是值不是控制流 / 为什么否决 try / error vs panic 判据 |
| 01-error-values | ✅ | sentinel / typed / opaque 三种风格 + typed nil 坑 |
| 02-wrapping | ✅ | `%w` 链 / `Is`·`As` 算法 / 多重包装(Join) |
| 03-panic-recover-defer | ✅ | defer 求值·LIFO·改返回值 / recover 为何没接住 / 何时 panic |
| 04-error-design | ✅ | 边界翻译 / `%w` vs `%v` / handle once / 哨兵·类型·行为接口 |
| 05-concurrent-errors | ✅ | errgroup 首错取消 / `errors.Join` / goroutine panic crash |
| 99-interview-cards | ✅ | 速答表(29 条) + 5 张深题卡 |

**本 track 全部完成。** 整条线读完即可系统复习「Go 错误处理最佳实践」。

## 关联已有笔记（复用不重复）

- [`golang/concurrency/07-context/`](../concurrency/07-context/README.md) — 取消传播（第 05 章错误聚合互链）
- [`golang/concurrency/08-patterns/`](../concurrency/08-patterns/README.md) — errgroup 的并发机制（第 05 章只讲「错误」这一面，不重复）
- [`golang/concurrency/04-goroutine/`](../concurrency/04-goroutine/README.md) — goroutine panic / 泄漏（第 03/05 章引用）
- `java/` — Java 异常体系，做对标锚点

← 回 [`golang/` master 索引](../README.md)
