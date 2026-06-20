# Go 测试工程 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/testing/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）
> 性质：C 层第二条。

## 背景与目标

测试是架构师面试的工程素养考点,Go 的测试文化又很有特色:**标准库无断言库(刻意)**、**table-driven + 子测试**是惯用法、**mock 靠小接口 + DI**、**fuzzing/benchmark 内置**。用户从 Java(JUnit/Mockito/AssertJ)来,差异明显。

目标:读完能写惯用的 table-driven 测试、用接口 + DI 做可测设计、写 benchmark/fuzz、把集成测试接进 CI。

## 核心设计决策

- **形式**：3 章,照搬已认可模板(7 段 + `99-interview-cards/`)。
- **主线钥匙 = 「测试即普通 Go 代码:table-driven + 子测试是惯用法;可测性来自小接口 + 依赖注入;benchmark/fuzz/coverage 内置」**。
- **双向桥**：JUnit(@Test/@ParameterizedTest/@BeforeEach)、Mockito、AssertJ ←→ Go testing/testify/gomock;pytest(fixture/parametrize)。重点:**Go 标准库无断言库(刻意),table-driven 取代参数化**。
- **底层内幕进正文**:`t.Run` 子测试、`t.Parallel` 与并行调度(及 1.22 前循环变量坑)、`t.Helper`/`t.Cleanup`/`TestMain`、golden file + `testdata/`、消费方定义接口做 mock、fake vs mock、`b.N` 自适应、fuzzing 语料、coverage profile。
- **Go 版本**:1.22+;fuzzing 1.18、`t.Cleanup` 1.14、二进制覆盖率 1.20、循环变量修复 1.22。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-unit-testing/` | 单元测试基础 | `*_test.go` / **table-driven + `t.Run` 子测试** / `t.Parallel`·`t.Helper`·`t.Cleanup` / TestMain / 断言哲学(无 stdlib assert、testify、go-cmp)/ golden file + testdata |
| `01-mock-interfaces/` | mock 与接口 | **消费方定义小接口 + DI 做可测** / 手写 fake vs gomock vs testify/mock / httptest / sqlmock / fake vs mock |
| `02-benchmark-fuzz-integration/` | 基准·模糊·集成 | `b.N`·benchmem·benchstat / fuzzing(1.18)/ 集成测试(build tag + testcontainers)/ coverage |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡(table-driven·parallel、mock·接口、benchmark·fuzz) |

## 已有素材的处理

- 接口/方法集机制链 [`type-system`](../type-system/);可测设计的「小接口/消费方定义」与 [`design/`](../design/)(待建)互链——本 track 讲「为测试而设计接口」,design track 讲「接口设计哲学」,互相引用不重复。
- race(`go test -race`)机制链 [`concurrency/06`](../concurrency/)与 [`engineering/02`](../engineering/);本 track 只在测试上下文提。
- pprof/benchmark 调优深度链 perf-roadmap。

## 交付节奏

1. 写本 spec。2. 骨架 README + 3 章目录。3. 写 00 确认,推进 01/02 + 面试卡。

## 验收标准

- 00 能写 table-driven + 子测试 + cleanup,并解释为什么 Go 不内置断言库。
- 01 能讲「为可测性用接口 + DI」、手写 fake 与 gomock 的取舍、httptest 用法。
- 02 能写 benchmark 并用 benchmem/benchstat 解读、写一个 fuzz、用 build tag 隔离集成测试。

## 非目标（YAGNI）

- 不做某 mock 框架的 API 大全。
- 不重讲 pprof/race 原理(链已有)。
- 不展开具体 CI 平台。
