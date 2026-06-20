# Go idiomatic 设计 track —— 设计 spec

> 日期：2026-06-20｜目录：`golang/design/`｜上级：umbrella spec。C 层第三条。

## 背景与目标

「idiomatic Go 设计」是架构师面试的高区分度软考点:**小接口 + 消费方定义 + 接受接口返结构体**、**组合优于继承 + DI**、**函数式选项**、**并发安全的 API 设计(零值可用/谁同步/库别偷开 goroutine)**。把前面 type-system/concurrency/testing 散落的设计原则收束成一条「怎么设计 Go API」的主线。

## 核心设计决策

- 形式:4 章,照搬已认可模板(7 段 + 面试卡)。
- 主线钥匙:**「Go 的设计哲学是组合 + 小接口 + 显式 + 零值可用;为调用方设计,而非为继承层级设计」**。
- 双向桥:Java(继承/Spring DI/Builder/线程安全集合)、Python;重点 Go proverbs(Rob Pike/Dave Cheney)。
- 底层/原则进正文:接口隔离与「越大越弱」、io.Reader/Writer 范式、组合 + wire/手动 DI、functional options 机制、零值可用、谁负责同步、库不偷开 goroutine、ctx 首参、不可拷贝、不在 API 暴露 channel/Mutex。
- 互链:[`type-system/04`](嵌入)、[`testing/01`](接口可测)、[`concurrency`](goroutine/ctx)、[`error-handling/04`](边界)。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-interface-design/` | 接口设计哲学 | 小接口 / 消费方定义 / 接受接口返结构体 / io.Reader·Writer / 接口隔离·「越大越弱」 |
| `01-composition-di/` | 组合与依赖注入 | 组合优于继承(承接 type-system/04)/ 构造注入 / wire vs 手动 DI / 一点拷贝优于一点依赖 |
| `02-functional-options/` | 函数式选项 | 可选配置的惯用法 / `Option func(*cfg)` / vs Builder / 何时用 |
| `03-concurrent-api/` | 并发安全的 API 设计 | 零值可用 / 谁负责同步 / 库别偷开 goroutine / ctx 首参 / 不可拷贝 / 别暴露 channel·Mutex |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡 |

## 交付节奏
1 spec → 2 骨架 → 3 四章 + 面试卡。

## 验收
- 00 能讲「接受接口返结构体」「接口越大越弱」「消费方定义」。
- 03 能讲零值可用、谁同步、库别偷开 goroutine、ctx 首参。

## 非目标
- 不重讲嵌入机制(链 type-system/04)、不重讲 errgroup(链 concurrency)。
- 不做设计模式大全(只讲 Go 惯用的几个)。
