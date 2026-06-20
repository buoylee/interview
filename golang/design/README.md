# Go idiomatic 设计 —— 给 Java 后端的「组合 + 小接口 + 零值可用」

> C 层第三条,最贴「架构师」味。Go 的设计哲学和 Java 的「继承层级 + Spring 容器 + 重型抽象」很不一样:**小接口、消费方定义、接受接口返结构体、组合优于继承、函数式选项、零值可用、为调用方设计**。本 track 把前面散落的设计原则收束成「怎么设计 Go API」。
>
> 总钥匙:**组合而非继承、小接口而非大抽象、显式而非魔法、零值可用、为调用方设计。** (Go proverbs)
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-design-track-design.md`｜Go 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` 接口设计哲学(核心),`01` 组合与 DI,`02` 函数式选项,`03` 并发安全 API 设计。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(继承/Spring DI/Builder/线程安全集合)。重点是 Go proverbs 背后的取舍。
4. **想答面试**：去 `99-interview-cards/`。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-interface-design/`](00-interface-design/) | 接口设计哲学 | 小接口 / **消费方定义** / 接受接口返结构体 / io.Reader·Writer / 「越大越弱」 ← 从这开始 |
| [`01-composition-di/`](01-composition-di/) | 组合与依赖注入 | 组合优于继承 / 构造注入 / wire vs 手动 DI / 一点拷贝优于一点依赖 |
| [`02-functional-options/`](02-functional-options/) | 函数式选项 | `Option func(*cfg)` 可选配置惯用法 / vs Builder / 何时用 |
| [`03-concurrent-api/`](03-concurrent-api/) | 并发安全的 API 设计 | 零值可用 / 谁负责同步 / 库别偷开 goroutine / ctx 首参 / 不可拷贝 |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 |
|---|---|
| 设计 spec | ✅ |
| 骨架 + 进度地图 | ✅ |
| 00-interface-design | ✅ 小接口/消费方定义/接受接口返结构体/越大越弱 |
| 01-composition-di | ✅ 组合优于继承/构造注入/wire vs 手动/一点拷贝优于一点依赖 |
| 02-functional-options | ✅ Option func(*cfg)/vs config struct/何时用 |
| 03-concurrent-api | ✅ 零值可用/谁同步/库别偷开 goroutine/ctx 首参/不可拷贝 |
| 99-interview-cards | ✅ 速答表(16 条) + 4 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- [`type-system/04`](../type-system/04-embedding/README.md) — 嵌入机制(本 track 讲「怎么用组合做设计」)
- [`type-system/01`](../type-system/01-interface-internals/README.md) — 接口底层
- [`testing/01`](../testing/01-mock-interfaces/README.md) — 小接口 + DI 的可测性(同源)
- [`concurrency/`](../concurrency/) — goroutine/ctx(并发 API 设计)
- [`error-handling/04`](../error-handling/04-error-design/README.md) — 错误的 API 边界设计

← 回 [`golang/` master 索引](../README.md)
