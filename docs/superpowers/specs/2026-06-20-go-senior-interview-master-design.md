# Go 资深/架构师面试 master 教程 — 设计 spec

> 日期：2026-06-20
> 目录：`golang/`（顶层 master 索引 + 多条 track 子目录）
> 性质：**umbrella spec**——只定主线地图 + 约定 + 建设顺序；每条 track 建前各写自己的设计 spec（像 `2026-05-30-go-concurrency-design.md` 那样）。

## 背景与目标

用户是 5 年+ Java/Go 后端工程师，Go 只用过约 1.5 年且已搁置数年、手生。最近一轮面试里发现**错误处理最佳实践答不好**，由此把目标升级为：把 `golang/` 建成一份**全面、深入、系统**的「Go 资深/架构师面试」教程，供自学复习。诉求关键词：**知识的系统性** + **阅读文档的流畅性**。

仓库现状：
- `golang/concurrency/` 已是一条**成熟主线**（00–09 共 10 章 + 5 张深题卡），风格统一——每章固定 7 段、简体中文、Java/Python 双向桥、补「黑盒内幕」。**这就是本教程要对齐的黄金标准。**
- 顶层 `golang/{base,collections,GC,memory,reflect}.md` 都是 2–22 行 **stub**，形同占位。
- **没有错误处理、类型系统、泛型、数据结构底层、工程化、测试、设计、stdlib、服务设计这些线**——是要补的空白。
- GC / pprof / trace / race 等已在 `performance-tuning-roadmap/05a·05b` 有成熟笔记；observability 已有 `observability/`。这些**只链接、不重写**。

目标（用户四步确认）：
1. **范围**：目标是「全面教程」，不是单写一篇错误处理速答。
2. **外缘**：**全收**——语言内核(A) + 运行时性能(B) + 工程化架构(C) 都进。
3. **厚度**：**按主题右配**——丰的主题做完整 track，薄的做浓缩，格式统一。
4. **格式**：照搬 `concurrency` 模板（7 段 / 子目录 + `99-interview-cards/` / 顶层 master 索引 / 简体 / Java·Python 双向桥）。

## 核心设计决策

- **形式**：顶层 `golang/README.md` 做 master 索引串全图（仿 `concurrency/README.md` 的「章节地图 + 进度地图 + 复用链接」，但升一层管 track）；每条主线一个子目录。
- **复用不重复**：并发 / GC / pprof·trace·race / observability 一律链接已有笔记，master 索引里专设「运行时与性能（见已有笔记）」一节挂进去，本教程不重写。
- **右配厚度**：富主题（类型系统/错误处理/数据结构）4–6 章；中等（泛型）3 章；工程化各 3–4 章。格式统一 7 段。
- **双向桥接**：每个 Go 机制锚两头——从 Java（用户母语）切入，反链 Python（含已建的 `python-concurrency`）。错误处理尤其对照 **Go error 值 vs Java 异常**。
- **calibration**：用户 Go 起点不低但生疏、且偏架构师视角。深度压在**「黑盒内幕」+「为什么这么设计」+「API 边界/工程取舍」**，基础语法快速过。承接 [[feedback_senior_depth_internals]]（资深要补黑盒里发生什么）、[[feedback_internals_in_narrative]]（底层进正文教学，问答题只复习）、[[feedback_learning_delivery]]（逐章交付不灌长文）、[[feedback_just_write_docs]]（自学向，自主写好文档，不让他进 VM 跑了汇报）、[[feedback_ecosystem_balanced_docs]]（对照别绑死 Java，配 Python 等价物）。
- **Go 版本基线**：Go 1.22+。版本敏感点显式标注（`errors.Join` 1.20+、泛型 1.18+、`WithCancelCause` 1.20+、`min/max/clear` 1.21+ 等）。
- **stub 处理**：现有 `base/collections/GC/memory/reflect.md` 在对应 track 落地后**被吸收清理**——collections→`data-structures/`、GC/memory→链接 perf-roadmap、reflect→`type-system/` 一节、base→master 引言。删前逐个查看内容确认无遗漏（“删前先看 target”）。

## 顶层结构

```
golang/
├── README.md                ← 新建：master 索引（全图 + 进度地图 + 复用链接）
├── error-handling/          ← A2（先做）
├── type-system/             ← A1
├── data-structures/         ← A4
├── generics/                ← A3
├── engineering/             ← C1
├── testing/                 ← C2
├── design/                  ← C3（idiomatic Go 与设计）
├── stdlib/                  ← C4
├── service-design/          ← C5
└── concurrency/             ← ✅ 已存在，master 链接进去
```

## 主线地图（右配章数，格式统一 7 段 + `99-interview-cards/`）

### A. 语言与运行时内核

| Track | 目录 | 章数 | 章节 |
|---|---|---|---|
| **A2 错误处理** ← 先做 | `error-handling/` | 6 | 00 错误哲学（error 是值 / 为什么不用异常 / 与 Java 异常·Go panic 的边界）· 01 三种风格（sentinel / typed / opaque 不透明）· 02 包装与检查（`fmt.Errorf %w` / `errors.Is` / `errors.As` / `errors.Unwrap` / 错误链）· 03 panic·recover·defer（defer 求值与执行时机 / recover 只在 defer / re-panic / 何时才该 panic）· 04 错误设计实战（API 边界暴露什么 / 错误分层 / 不泄漏内部 / 不重复包装 / 与日志·可观测性）· 05 并发中的错误（errgroup / `errors.Join` 多错误聚合 / goroutine panic 传播与 crash） |
| **A1 类型系统与接口** | `type-system/` | 6 | 00 值类型与内存布局（零值 / 可比较性 / 值 vs 引用语义）· 01 接口底层（iface vs eface / itab / 动态派发 / 接口是两个字）· 02 方法集与接收者（值 vs 指针接收者 / 什么能赋给接口）· 03 类型断言与类型 switch（comma-ok / 性能 / 底层）· 04 嵌入与组合（struct/interface 嵌入 / 方法提升 / 组合优于继承）· 05 nil 的多张面孔（nil interface vs typed nil 陷阱） |
| **A4 数据结构底层** | `data-structures/` | 5 | 00 slice（三元组 / 扩容策略 / 共享底层数组与 append 别名坑）· 01 map（hmap/bucket / 渐进扩容 / 为什么无序 / 不可寻址 / 并发不安全）· 02 string·[]byte·rune（不可变 / UTF-8 / 转换拷贝 / unsafe 零拷贝）· 03 逃逸分析与栈/堆（逃逸规则 / `-gcflags=-m`）· 04 struct 内存对齐与布局（padding / 字段重排省内存 / 空 struct） |
| **A3 泛型** | `generics/` | 3 | 00 基础（type parameters / constraints / `comparable` / 约束接口）· 01 底层实现（GCShape stenciling + 字典：非 C++ 模板、非 Java 擦除，介于之间）· 02 工程取舍（泛型 vs 接口 vs 代码生成 / 何时别用 / `slices`·`maps`·`cmp` 标准库） |

### B. 运行时与性能（只链接，不重写）

master 索引设一节「运行时与性能（见已有笔记）」，挂入：
- 并发 → `golang/concurrency/` ✅
- GC 与内存管理 → `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md`
- pprof / trace / 逃逸 / race → `performance-tuning-roadmap/05a-go-profiling/0{1,2,4}-*.md`、`05b-go-debugging/*`

### C. 工程化与架构

| Track | 目录 | 章数 | 章节 |
|---|---|---|---|
| **C1 工程化与工具链** | `engineering/` | 3 | 00 modules 与依赖（版本语义 / MVS 最小版本选择 / `replace`·vendor / `go.sum` 校验 / workspace）· 01 项目结构与构建（project layout / `internal/` / build tags / `embed` / 交叉编译）· 02 工具链（`go vet`·staticcheck·golangci-lint / `go generate` / race detector / pprof 集成） |
| **C2 测试工程** | `testing/` | 3 | 00 单元测试（table-driven / `t.Run` 子测试 / `t.Helper`·`t.Cleanup` / golden file）· 01 mock 与接口（消费方接口 / 依赖注入 / `httptest` / sqlmock / gomock）· 02 benchmark·fuzzing·集成测试（`b.N` / 内存基准 / `go fuzz` / testcontainers / 覆盖率） |
| **C3 idiomatic Go 与设计** | `design/` | 4 | 00 接口设计哲学（小接口 / 消费方定义 / 接受接口返回结构体 / `io.Reader`·`Writer` 范式）· 01 组合优于继承 + 依赖注入 · 02 函数式选项（functional options）· 03 并发安全的 API 设计（零值可用 / 谁负责同步 / 库不偷开 goroutine 不给退出路径 / ctx 作首参） |
| **C4 标准库精要** | `stdlib/` | 4 | 00 io 接口家族（Reader/Writer/Closer / 组合 / bufio / `io.Copy` / 流式）· 01 net/http（server mux·中间件 / client 连接池·超时 / context 集成）· 02 encoding/json（struct tag / 流式 encoder / 自定义 Marshaler / protobuf 概览）· 03 database/sql（连接池 / prepared / 事务 / context / 扫描） |
| **C5 服务/API 设计** | `service-design/` | 4 | 00 服务骨架（配置 / 启动·优雅关闭 / 信号处理 / 健康检查）· 01 gRPC vs REST（protobuf / 拦截器 / 错误码映射 / 流式）· 02 中间件与横切关注点（日志 / 认证 / 限流 / 重试 / 熔断）· 03 可观测性接入（OTel / metrics·trace·log → 链接 `observability/`） |

合计约 **38 章 + 9 套面试卡**，全部增量交付。

## 约定（照搬 concurrency 黄金标准）

- 每章固定 **7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
- 简体中文；**Java/Python 双向桥**；底层内幕**写进正文教学**，`99-interview-cards/` 只做最后的复习自检（承接 [[feedback_internals_in_narrative]]）。
- 代码片段标 Go 版本、可直接 `go run`。不搭独立 lab（自学向，[[feedback_just_write_docs]]）。
- 每条 track 一个 `99-interview-cards/`：速答表（背诵）+ 深题卡（每张链回章节做证据）。
- 复用不重复：并发 / GC / profiling / observability 一律链接已有笔记。

## 建设顺序（增量交付）

1. **error-handling（急性痛点先做）**
2. type-system
3. data-structures
4. generics
5. engineering
6. testing
7. design
8. stdlib
9. service-design

B 层随时挂进 master 索引。每条 track 建前先写该 track 的设计 spec，再搭骨架（README 进度地图）+ 逐章交付，每章一交付，确认深度/风格后推进。

## 交付节奏（本 umbrella 之后的下一步）

1. 写本 umbrella spec（本文件）。
2. 用户 review spec。
3. 建 `golang/README.md` master 索引骨架（全图 + 进度地图 + B 层复用链接）。
4. 进入 **error-handling track**：写该 track 的设计 spec → 搭骨架 → 先写 00 + 04 两章（00 立错误哲学地基、04 是「错误设计实战」即用户面试卡住的最佳实践核心），确认深度/风格后逐章推进。

## 验收标准

- 顶层 `golang/README.md` 一眼能看清全教程地图与每条 track 进度，阅读动线流畅（“系统性 + 阅读流畅性”）。
- 每条 track 自洽：读完一章能讲清该章「核心问题」与面试考点，无需先做实验。
- 每个 Go 机制都有 Java/Python 对标；资深点（接口底层、错误设计、泛型实现、内存布局等）讲到「能在面试白板上画/讲清内幕」。
- 面试卡每张都能链回正文证据。

## 非目标（YAGNI）

- **不重写已有线**：并发 / GC / pprof·trace·race / observability 只链接。
- **不逐行抠 runtime 源码**：深到「机制 + 关键结构/函数名 + 为什么」即可（资深面试够用）。
- **不做分布式系统/中间件原理**：那是 `system-design/`、`distr-tx/`、`redis-handson/` 等另几条线，本教程只在 service-design 层面点到并链接。
- **不搭 docker/lab 环境**：理论 + 可跑片段为主。
- **不是 Go 入门语法书**：基础语法快速过，重心在内幕与架构取舍。
