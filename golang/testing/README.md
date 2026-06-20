# Go 测试工程 —— 给 Java 后端的「测试即普通代码 + 小接口可测」

> C 层第二条。Go 的测试文化很有特色:**标准库故意不带断言库**、**table-driven + 子测试**是惯用法、**可测性来自小接口 + 依赖注入**(而非重型 mock 框架)、**benchmark/fuzzing/coverage 全内置**。这些是架构师面试的工程素养考点。
>
> 总钥匙:**测试就是普通 Go 代码(`testing` 包 + `if got!=want`);table-driven + `t.Run` 是惯用法;可测性靠小接口 + DI;benchmark/fuzz/coverage 内置。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-testing-track-design.md`｜Go 版本基线 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` 单元测试基础(table-driven/子测试/cleanup),`01` mock 与接口(可测设计),`02` benchmark·fuzzing·集成测试。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(JUnit/Mockito/AssertJ)、**Python**(pytest fixture/parametrize)。重点:Go 无 stdlib 断言、table-driven 取代参数化。
4. **想答面试**：去 `99-interview-cards/` 找卡。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-unit-testing/`](00-unit-testing/) | 单元测试基础 | **table-driven + `t.Run` 子测试** / `t.Parallel`·`t.Helper`·`t.Cleanup` / 断言哲学 / golden file ← 从这开始 |
| [`01-mock-interfaces/`](01-mock-interfaces/) | mock 与接口 | **消费方小接口 + DI 做可测** / 手写 fake vs gomock / httptest / sqlmock / fake vs mock |
| [`02-benchmark-fuzz-integration/`](02-benchmark-fuzz-integration/) | 基准·模糊·集成 | `b.N`·benchmem·benchstat / fuzzing / 集成测试(build tag·testcontainers)/ coverage |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-testing-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-unit-testing | ✅ | table-driven + t.Run / Parallel·Helper·Cleanup / 断言哲学 / golden file |
| 01-mock-interfaces | ✅ | 消费方小接口 + DI / fake·gomock / httptest / sqlmock |
| 02-benchmark-fuzz-integration | ✅ | b.N·benchstat / fuzzing / testcontainers 集成 / coverage |
| 99-interview-cards | ✅ | 速答表(20 条) + 3 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- [`type-system/02`](../type-system/02-method-sets/README.md) — 接口/方法集(mock 靠接口)
- [`design/`](../design/) — 接口设计哲学(本 track 讲「为测试而设计接口」,互链)
- race 机制 → [`concurrency/06`](../concurrency/06-sync-memory-model/README.md) / [`engineering/02`](../engineering/02-toolchain/README.md)
- `java/` — JUnit/Mockito 对标锚点

← 回 [`golang/` master 索引](../README.md)
