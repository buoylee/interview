# 系统监控与性能调优 完整学习路线

> **定位**：你有 Java/Go/Python 后端开发经验，但缺乏系统化的性能调优和问题排查能力。本路线从实践环境搭建出发，经操作系统基础、方法论、可观测性，到三门语言的完整性能工程体系，再到压测、排查、架构优化、SRE 实践，最后以综合实战项目收尾，建立可迁移的排查方法论。

> **原则**：系统性与完整性优先，不跳步、不压缩。每个阶段都是下一阶段的前置依赖。每个阶段包含前置条件、能力目标和动手练习。

> **面试目标**：这套路线上可以服务三类目标：资深后端工程师、SRE / 平台工程师、Staff / Tech Lead。所有学习者先完成同一个性能排查核心闭环，再按目标岗位进入不同 track。

### 面试导向入口

| 文件 | 解决的问题 |
|------|------------|
| [TRACKS.md](./performance-tuning-roadmap/TRACKS.md) | Backend Senior / SRE / Staff 三条学习路径怎么选 |
| [INTERVIEW-MATRIX.md](./performance-tuning-roadmap/INTERVIEW-MATRIX.md) | 高频性能面试场景需要哪些能力和证据 |
| [LAB-CONTRACT.md](./performance-tuning-roadmap/LAB-CONTRACT.md) | 哪些实验当前可运行，哪些属于目标态示例 |
| [SENIOR-RUBRIC.md](./performance-tuning-roadmap/SENIOR-RUBRIC.md) | 什么样的回答算资深或 Staff 水平 |

---

## 如何使用这份路线

这份路线不是“100 篇文章顺序读完”的知识清单，而是一套围绕真实排查闭环设计的训练系统。学习时始终围绕一条主线：

```
现象 → 指标 → 假设 → 工具 → 定位 → 修复 → 验证 → 复盘
```

每个阶段只解决这条链路中的一部分能力：

| 阶段范围 | 主要作用 | 学习重点 |
|---------|---------|---------|
| P | 让练习可运行 | 跑通服务、监控、压测入口 |
| 0-2 | 建立底层判断力 | 看懂 CPU、内存、I/O、网络和 Linux 工具输出 |
| 3-3.5 | 建立观测与负载能力 | 能看到指标、日志、Trace，并能制造稳定负载 |
| 4-6 | 掌握语言运行时 | 至少先选一门主语言深入完成 |
| 7 | 学会科学压测 | 建立基线、找拐点、输出报告 |
| 8-10 | 进入生产排查场景 | 网络、数据库、中间件、分布式链路排查 |
| 11-13 | 从修问题到设计系统 | 架构优化、容器环境、SRE 闭环 |
| 14 | 综合演练 | 独立完成发现、定位、修复、验证、复盘 |

降低学习曲线的关键是：**先跑通最小闭环，再扩展深度和广度。** 不要一开始追求三语言、全工具、全场景都掌握。

---

## 推荐学习节奏

### 第 0 轮：最小闭环（2-3 周）

目标是先获得“我能完整排查一次性能问题”的体验。

必学：

```
P → 1 → 2 的核心工具 → 3 的 Prometheus/Grafana → 3.5 → 选择一门语言的 profiling → 7 → 9a → 14 的一个场景
```

产出：
- 一份 PerfShop 基线压测数据
- 一张 RED Dashboard
- 一份 profiling 证据（火焰图、pprof 或 py-spy）
- 一份慢查询或热点方法的优化前后对比
- 一份 1 页性能排查记录

### 第 1 轮：系统主线（8-12 周）

目标是把排查方法固定下来，而不是只会单个工具。

学习顺序：

```
P → 0 → 1 → 2 → 3 → 3.5 → 主语言 4/5/6 → 7 → 8 → 9a → 9b → 10 → 13 → 14
```

阶段 11 和 12 可以根据工作场景插入：如果正在做架构优化，提前学 11；如果服务跑在容器或 K8s 中，提前学 12。

### 第 2 轮：专项深化（按需）

目标是补齐生产环境中的薄弱点。

可选方向：
- Java 服务为主：深入 4a、4b、11/05、Netty、JVM 容器调优
- Go 服务为主：深入 5a、5b、goroutine 泄漏、pprof、runtime 调优
- Python 服务为主：深入 6a、6b、GIL、asyncio、Web 框架部署
- 平台/SRE 为主：深入 3、7、12、13、14
- 复杂故障排查：深入 8、9、10、13/04、13/05

---

## 每个学习单元的完成标准

每篇文章不要只读完，要至少完成下面 4 件事：

1. 说清楚它解决的性能问题是什么
2. 在本机或 PerfShop 上跑出一个可观察现象
3. 用文中的工具拿到一份证据
4. 写下“结论 + 下一步动作”

如果做不到第 2 和第 3 点，说明这篇还停留在概念层，需要回到阶段 P 或阶段 3 补环境和监控。

详细学习方法见：[学习指南](./performance-tuning-roadmap/LEARNING-GUIDE.md)。

---

## 全景路线图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               准备层（环境）                                         │
│  阶段P 实践环境搭建（P0 最小可运行闭环；P2 再扩展为三语言 PerfShop）                 │
│       (0.5周)                                                                       │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               基础层（地基）                                         │
│  阶段0 操作系统基础 → 阶段1 性能分析方法论 → 阶段2 Linux 性能观测工具链               │
│       (1.5周)              (1周)                  (1.5周)                            │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            可观测性层（眼睛）                                        │
│  阶段3 可观测性体系建设（日志 / 指标 / 链路追踪 / 告警）                              │
│       (2周)                                                                         │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            负载生成（桥梁）                                           │
│  阶段3.5 压测快速上手（wrk + Locust 基础，为 Profiling 练习提供负载）                 │
│          (0.5周)                                                                     │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌──────────────────┬──────────────────┴──────────────────┬─────────────────────────────┐
▼                  ▼                                     ▼                             │
┌────────────┐  ┌────────────┐                    ┌────────────┐                       │
│ 阶段4a/4b  │  │ 阶段5a/5b  │                    │ 阶段6a/6b  │    语言层（引擎）      │
│ Java       │  │ Go         │                    │ Python     │                       │
│ Profiling  │  │ Profiling  │                    │ Profiling  │                       │
│ + 排查实战  │  │ + 排查实战  │                    │ + 排查实战  │                       │
│  (3周)     │  │  (2周)     │                    │  (2周)     │                       │
└─────┬──────┘  └─────┬──────┘                    └─────┬──────┘                       │
      └──────────────────┬──────────────────────────────┘                              │
                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            测试层（度量）                                             │
│  阶段7 压测方法论与进阶（完整方法论 / 统计分析 / CI 集成）                            │
│       (1.5周)                                                                       │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            排查层（实战）                                             │
│  阶段8 网络与I/O排查 → 阶段9a 数据库性能 → 阶段9b 中间件性能 → 阶段10 分布式排查    │
│       (1.5周)            (1.5周)              (1周)              (1.5周)             │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            架构层（设计）                                             │
│  阶段11 架构级性能优化 → 阶段12 容器与云原生性能                                     │
│        (2周)                  (1.5周)                                                │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            实践层（闭环）                                             │
│  阶段13 SRE 与生产实践（SLI/SLO / 容量规划 / 混沌工程 / 事故复盘）                   │
│        (1.5周)                                                                       │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            综合层（毕业）                                             │
│  阶段14 综合实战（贯穿项目的完整性能工程演练 + 排查能力自测）                         │
│        (1.5周)                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**21 个阶段，100 个文件，预计 30-32 周（每天 1-2 小时）**

---

## 核心理念：先于一切工具

> 工具只是手段。**你真正需要的是四样东西：**
> 1. **度量意识** — 没有数据就没有调优，所有判断必须基于指标而非猜测
> 2. **分层排查思维** — 硬件 → OS → Runtime/VM → 框架 → 业务代码，逐层缩小范围
> 3. **基线思维** — 不知道「正常」是什么样，就不可能发现「异常」
> 4. **科学方法** — 假设 → 实验 → 数据 → 结论，不靠猜、不靠经验直觉

---

## 贯穿项目：PerfShop

> 整条路线围绕一个**贯穿项目**展开实操，避免「学完理论不知道怎么串起来」。

**PerfShop** 是一个简化的电商 API 服务，包含三个语言版本（Java / Go / Python），具备以下模块：
- 商品查询（涉及数据库、缓存）
- 下单（涉及并发、事务、MQ）
- 用户鉴权（涉及网络、TLS）

每个阶段会在 PerfShop 上做对应的练习：

| 阶段 | 在 PerfShop 上做什么 |
|------|---------------------|
| P | 搭建 P0 最小环境，先跑通一个可观测服务 |
| 3 | 接入 Prometheus + 日志 + Tracing |
| 3.5 | 用 wrk 对商品查询接口加压 |
| 4a | 用 async-profiler 找到 Java 版的瓶颈 |
| 5a | 用 pprof 找到 Go 版的瓶颈 |
| 6a | 用 py-spy 找到 Python 版的瓶颈 |
| 7 | 完整压测三语言版本，输出性能报告 |
| 8 | 模拟网络超时，用 tcpdump 排查 |
| 9a | 用 EXPLAIN 优化慢查询 |
| 9b | 排查 Redis 慢命令 |
| 10 | 模拟下单链路的超时传播 |
| 14 | 端到端性能工程演练 |

---

## 详细内容导航

> 每个阶段展开为独立文件夹。每个文件 = 一个学习单元 = 1.5-2.5 小时（理论 + 实操）。
> 每个阶段包含：**前置条件** / **学完能做什么** / **动手练习**。
> 表格中的“文件数”只统计正式学习单元，不包含各阶段的 `README.md` 学习指南。

### 学习辅助

| 文件 | 用途 |
|------|------|
| [LEARNING-GUIDE.md](./performance-tuning-roadmap/LEARNING-GUIDE.md) | 学习节奏 / 三层路线 / 阶段检查点 / PerfShop 落地优先级 / 学习单元统一模板 |
| [templates/](./performance-tuning-roadmap/templates/) | 排查记录 / 压测报告 / Profiling 报告 / 复盘模板 |
| [labs/perfshop-p0/](./performance-tuning-roadmap/labs/perfshop-p0/) | PerfShop P0 最小实验闭环标准 |

### 准备层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **P** | [实践环境搭建](./performance-tuning-roadmap/P-lab-setup/) | 2 | Docker Compose 监控栈 / P0 最小 PerfShop 闭环 |

### 基础层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **0** | [操作系统基础](./performance-tuning-roadmap/00-os-fundamentals/) | 6 | CPU 调度 / 内存管理 / 磁盘 I/O / TCP 核心 / Socket 与内核网络 / 进程线程协程 |
| **1** | [性能分析方法论](./performance-tuning-roadmap/01-methodology/) | 4 | 科学方法 / USE 方法 / RED 与黄金指标 / 性能定律（Amdahl/Little/USL） |
| **2** | [Linux 性能观测工具链](./performance-tuning-roadmap/02-linux-tools/) | 6 | CPU 工具 / 内存工具 / 磁盘工具 / 网络工具 / strace+perf+ftrace / eBPF 入门 |

### 可观测性层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **3** | [可观测性体系建设](./performance-tuning-roadmap/03-observability/) | 6 | 结构化日志 / 日志基础设施(ELK/Loki) / Metrics 理论 / Prometheus+Grafana / 分布式链路追踪 / 告警与 On-call |

### 负载生成（桥梁）

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **3.5** | [压测快速上手](./performance-tuning-roadmap/03x-load-gen-quickstart/) | 2 | wrk 快速上手 / Locust 快速上手 |

### 语言层（三语言对称结构）

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **4a** | [Java Profiling 与 JVM](./performance-tuning-roadmap/04a-java-profiling/) | 5 | JVM 内存模型 / GC 算法对比 / GC 日志与参数 / async-profiler 与火焰图 / JFR+JMC |
| **4b** | [Java 排查与调优实战](./performance-tuning-roadmap/04b-java-debugging/) | 6 | Arthas / Heap Dump 与内存泄漏(MAT) / **Thread Dump 分析** / 并发性能排查 / 常见反模式 / Netty 性能排查 |
| **5a** | [Go Profiling 与运行时](./performance-tuning-roadmap/05a-go-profiling/) | 5 | pprof 六种 profile / go tool trace / Go GC 与调优 / Race Detector 与并发分析 / testing.B+benchstat+OTel |
| **5b** | [Go 排查与调优实战](./performance-tuning-roadmap/05b-go-debugging/) | 5 | Goroutine 泄漏排查 / net/http 与 gRPC 性能 / Go 常见反模式 / 生产调优(GOMAXPROCS/CGO) / Go 排查案例集 |
| **6a** | [Python Profiling 与运行时](./performance-tuning-roadmap/06a-python-profiling/) | 5 | cProfile/py-spy/Scalene / 内存分析(tracemalloc/objgraph) / CPython GC 与引用计数 / OTel+prometheus_client / pytest-benchmark+line_profiler |
| **6b** | [Python 排查与调优实战](./performance-tuning-roadmap/06b-python-debugging/) | 5 | GIL 深入与并发选型 / asyncio 事件循环排查 / Web 框架调优(FastAPI/Django/Gunicorn) / 常见反模式与 C 扩展 / Python 排查案例集 |

### 测试层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **7** | [压测方法论与进阶](./performance-tuning-roadmap/07-load-testing/) | 5 | 压测方法论 / 工具对比与实操 / 微基准(JMH/testing.B/pytest-benchmark) / 报告解读与统计 / CI 性能回归检测 |

### 排查层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **8** | [网络与 I/O 排查](./performance-tuning-roadmap/08-network-io/) | 5 | tcpdump+Wireshark / 连接问题排查 / 丢包与延迟分析 / TLS 排查 / I/O 性能排查 |
| **9a** | [数据库性能](./performance-tuning-roadmap/09a-database/) | 5 | 慢查询与 EXPLAIN / 索引优化 / 锁与事务 / 连接池监控 / 查询优化与大表策略 |
| **9b** | [中间件性能](./performance-tuning-roadmap/09b-middleware/) | 4 | Redis 性能排查 / Redis 内存分析与调优 / MQ 性能(Kafka/RabbitMQ) / MQ 排查案例集 |
| **10** | [分布式系统排查](./performance-tuning-roadmap/10-distributed/) | 5 | 超时传播与断路器 / 重试风暴与限流 / Trace 定位瓶颈 / 依赖分析与降级 / 一致性排查 |

### 架构层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **11** | [架构级性能优化](./performance-tuning-roadmap/11-architecture/) | 7 | 缓存策略 / 连接池调优 / 异步与响应式 / 数据库架构优化 / JVM 生产调优 / 性能设计模式 / **协议与序列化性能** |
| **12** | [容器与云原生性能](./performance-tuning-roadmap/12-container/) | 4 | cgroup 与资源限制 / K8s 性能调优 / 容器监控体系 / Service Mesh 性能 |

### 实践层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **13** | [SRE 与生产实践](./performance-tuning-roadmap/13-sre/) | 5 | SLI/SLO/SLA / 容量规划 / 混沌工程 / 事故响应 / 事故复盘 |

### 综合层

| 阶段 | 文件夹 | 文件数 | 核心内容 |
|------|--------|--------|---------|
| **14** | [综合实战](./performance-tuning-roadmap/14-capstone/) | 3 | 贯穿项目演练指南 / 全链路性能工程实战 / 排查能力自测题 |

**共 100 个详细学习单元 + 21 个阶段学习指南 + 1 个总学习指南 + 学习产物模板 + PerfShop P0 实验标准**

---

## 选择性学习路线

> 以下路线从完整内容中筛选核心文件。**完整路线优先，时间不足时参考此表选择性学习。**

### Java 优先路线（4 周）

| 周 | 天数 | 内容 | 文件 |
|---|------|------|------|
| 1 | Day 1 | ★ 搭建实践环境 | P/01 + P/02 |
| 1 | Day 2-3 | ★ CPU/内存基础 | 00/01 + 00/02 |
| 1 | Day 4 | ★ USE/RED 方法论 | 01/02 + 01/03 |
| 1 | Day 5-6 | ★ Prometheus + Grafana | 03/04 |
| 1 | Day 7 | wrk + Locust 快速上手 | 03x/01 + 03x/02 |
| 2 | Day 8-9 | ★ JVM 内存模型 + GC 算法 | 04a/01 + 04a/02 |
| 2 | Day 10 | ★ GC 日志与参数 | 04a/03 |
| 2 | Day 11 | ★ async-profiler + 火焰图 | 04a/04 |
| 2 | Day 12 | Arthas 实操 | 04b/01 |
| 2 | Day 13-14 | 常见反模式 + Netty 排查 | 04b/05 + 04b/06 |
| 3 | Day 15-16 | ★ 压测方法论 + 工具实操 | 07/01 + 07/02 |
| 3 | Day 17-18 | ★ 网络排查 | 08/01 + 08/02 |
| 3 | Day 19-20 | 数据库性能 | 09a/01 + 09a/02 |
| 3 | Day 21 | ★ Heap Dump 与内存泄漏 | 04b/02 |
| 4 | Day 22-23 | 缓存 + 连接池 | 11/01 + 11/02 |
| 4 | Day 24-25 | ★ JVM 生产调优 | 11/05 |
| 4 | Day 26-27 | SLI/SLO + 告警 | 13/01 + 03/06 |
| 4 | Day 28 | 事故复盘 | 13/05 |

### 三语言均衡路线（+2 周 = 共 6 周）

在 Java 优先路线基础上追加：

| 周 | 天数 | 内容 | 文件 |
|---|------|------|------|
| 5 | Day 29-30 | Go pprof + trace | 05a/01 + 05a/02 |
| 5 | Day 31 | Go GC 调优 | 05a/03 |
| 5 | Day 32-33 | Goroutine 泄漏 + gRPC 性能 | 05b/01 + 05b/02 |
| 5 | Day 34-35 | Go 反模式 + 案例 | 05b/03 + 05b/05 |
| 6 | Day 36-37 | Python profiling + 内存 | 06a/01 + 06a/02 |
| 6 | Day 38 | GIL 与并发选型 | 06b/01 |
| 6 | Day 39-40 | Web 框架调优 | 06b/03 |
| 6 | Day 41-42 | Python 反模式 + 案例 | 06b/04 + 06b/05 |

### 选择性学习时可跳过

```
非优先（时间充足再看）：
  - 00/03 磁盘 I/O（除非排查磁盘问题）
  - 02/06 eBPF（进阶内容，基础工具够用时不急）
  - 08/04 TLS 排查（遇到时再看）
  - 11/03 异步/响应式（需要时再看）
  - 12/* 容器与云原生（团队已有 K8s 基础设施时再看）
  - 13/03 混沌工程（团队级实践，个人可后补）
```

---

## 各阶段详细大纲

---

### 阶段 P：实践环境搭建（0.5 周）

> **不搭环境，后面全是纸上谈兵。** 这个阶段只做一件事：让你有一个可以练习的完整环境。

**前置条件**：Docker 和 Docker Compose 已安装，Java/Go/Python 开发环境就绪。

**学完能做什么**：一条命令拉起最小实验环境，至少跑通一个 HTTP 服务、Prometheus 指标和 Grafana 观测入口。完整 Java / Go / Python 三语言 PerfShop 属于 P2 目标态，不是阶段 P 的完成前置。

| 文件 | 内容 |
|------|------|
| 01-monitoring-stack.md | Docker Compose 编排 / Prometheus + Grafana + Jaeger + Loki 一键部署 / 端口与访问 / 数据持久化 / 常见问题 |
| 02-perfshop-demo.md | PerfShop 作为贯穿项目的目标架构 / P0 单服务闭环 / P1 多组件扩展 / P2 Java + Go + Python 三语言同构目标 |

**动手练习**：
1. `docker compose up -d` 启动 P0 环境，确认 Grafana 或 Prometheus 有数据
2. 用 curl 请求一个 PerfShop 商品查询接口，确认返回正常
3. 在后续 P1/P2 阶段再补 Trace、Redis、Kafka 和三语言同构服务

---

### 阶段 0：操作系统基础（1.5 周）

> **为什么放第一个？** 所有性能问题最终都会落到 OS 层。不理解 CPU 调度，你看不懂 context switch 的火焰图。不理解内存管理，你判断不了 GC 和 page fault 的影响。不理解 TCP 栈，你排查不了你的 Netty 超时问题。这是地基。

**前置条件**：基本的 Linux 命令行使用能力。

**学完能做什么**：看到 `top` 的输出能解释每一列的含义；能画出 TCP 三次握手的时序图并说出每个状态的意义；能解释 page fault 对性能的影响。

| 文件 | 内容 |
|------|------|
| 01-cpu-architecture-scheduling.md | CPU 架构（多核/缓存层级/NUMA）/ 用户态 vs 内核态 / 上下文切换代价 / 中断与软中断 / CFS 调度器 |
| 02-memory-management.md | 虚拟内存 / 页表与 TLB / Page Fault（Major/Minor）/ Swap 机制 / OOM Killer / NUMA 内存策略 |
| 03-disk-io-filesystem.md | 块设备模型 / 文件系统（ext4/xfs）/ Page Cache / I/O 调度器 / 顺序 vs 随机 I/O / fsync 与 fdatasync |
| 04a-network-tcp-core.md | TCP/IP 四层模型 / 三次握手与四次挥手细节 / TIME_WAIT 成因与影响 / 拥塞控制（慢启动/CUBIC/BBR）/ Nagle 与延迟 ACK |
| 04b-network-socket-kernel.md | Socket Buffer（sk_buff）/ 内核收发包完整流程 / 网卡多队列与 RSS / 中断合并 / 零拷贝（sendfile/mmap） |
| 05-process-thread-coroutine.md | 进程 vs 线程 vs 协程对比 / fork 与 COW / 信号机制 / 文件描述符与 fd 上限 / I/O 多路复用（select/poll/epoll/io_uring） |

**动手练习**：
1. 用 `/proc/[pid]/status` 和 `/proc/[pid]/maps` 观察 PerfShop Java 版的进程信息，解释看到的数据
2. 用 `ss -tnp` 观察 PerfShop 的 TCP 连接，找出哪些连接处于 ESTABLISHED、TIME_WAIT 状态
3. 写一个程序故意触发大量 page fault，用 `perf stat` 验证

---

### 阶段 1：性能分析方法论（1 周）

> **在碰任何工具之前，先建立分析框架。** 没有方法论，你只是在随机尝试工具。这一阶段教你「面对性能问题时的起手式」。

**前置条件**：阶段 0 完成，理解 CPU/内存/网络/磁盘的基本概念。

**学完能做什么**：面对一个「接口慢了」的报告，你能列出一份 USE 检查清单，知道先查什么、再查什么；能用 Little 定律计算需要多少并发才能打满目标吞吐量。

| 文件 | 内容 |
|------|------|
| 01-scientific-method.md | 性能问题的科学方法 / 假设 → 实验 → 数据 → 结论 / 控制变量法 / 避免认知偏差（确认偏误/幸存者偏差/过早优化）|
| 02-use-method.md | USE 方法（Utilization/Saturation/Errors）/ 按资源逐项检查 / 每种资源的具体指标 / USE 检查清单模板 |
| 03-red-golden-signals.md | RED 方法（Rate/Errors/Duration）/ Google 四大黄金指标 / USE vs RED 适用场景 / 服务 vs 资源视角 |
| 04-performance-laws.md | Amdahl 定律（并行加速上限）/ Little 定律（并发=吞吐×延迟）/ USL（通用可扩展性定律）/ 排队论基础 / 容量模型构建 |

**动手练习**：
1. 对 PerfShop 的商品查询接口做一份 USE 检查清单（列出：CPU/内存/磁盘/网络各查什么指标、用什么命令）
2. 用 Little 定律计算：如果目标 QPS 是 1000，P99 延迟 50ms，需要多少并发连接？

---

### 阶段 2：Linux 性能观测工具链（1.5 周）

> **先会「看」，再学「改」。** 每个工具的重点是：看什么指标、正常值是多少、异常时意味着什么。

**前置条件**：阶段 0 + 阶段 1 完成。理解 OS 基础概念和 USE/RED 方法论。

**学完能做什么**：拿到一台「有性能问题」的 Linux 服务器，你能在 5 分钟内用标准工具链（uptime → vmstat → mpstat → pidstat → iostat → ss）定位到瓶颈在 CPU / 内存 / 磁盘 / 网络中的哪个。

| 文件 | 核心工具与内容 |
|------|---------------|
| 01-cpu-tools.md | uptime(load average) / top/htop / mpstat(per-CPU) / pidstat(per-process) / vmstat / /proc/stat |
| 02-memory-tools.md | free / vmstat(si/so) / slabtop / pmap / /proc/meminfo / numastat / smem |
| 03-disk-tools.md | iostat(await/util) / iotop / blktrace / lsof / fio(性能基准) |
| 04-network-tools.md | ss / netstat / tcpdump / iftop / nload / ip / ethtool / /proc/net/snmp |
| 05-tracing-profiling.md | strace(系统调用追踪) / ltrace / perf stat / perf record / perf top / ftrace / /proc/[pid]/* |
| 06-ebpf-bcc-bpftrace.md | eBPF 架构 / bcc 工具集(execsnoop/biosnoop/tcplife) / bpftrace 单行脚本 / 典型排查场景 |

**动手练习**：
1. 对正在运行的 PerfShop，用 Brendan Gregg 的 [USE Method Linux Checklist](http://www.brendangregg.com/USEmethod/use-rosetta.html) 逐项过一遍
2. 用 `strace -c -p <pid>` 对 PerfShop Java 版抓 10 秒系统调用统计，分析主要开销在哪类调用
3. 用 `perf record` 对 PerfShop Go 版抓一次 CPU profile，生成火焰图

---

### 阶段 3：可观测性体系建设（2 周）

> **现代后端的标配基础设施。** 没有这三个支柱（日志、指标、链路追踪），你在生产环境就是盲人。

**前置条件**：阶段 P 的监控栈已搭建运行。阶段 2 完成。

**学完能做什么**：能独立搭建一套完整的可观测性体系；能写 PromQL 查询 P99 延迟；能在 Jaeger 中追踪一个跨服务请求；能设计不会让人告警疲劳的告警规则。

| 文件 | 内容 |
|------|------|
| 01-structured-logging.md | 结构化日志 vs 文本日志 / 日志级别规范 / MDC 与 TraceID 注入 / 日志格式设计（JSON）/ 性能影响 / **框架调试日志配置速查**（Netty LoggingHandler / HikariCP debug / Spring 各级日志 / Go GODEBUG / Python logging per-module） |
| 02-log-infrastructure.md | ELK Stack 架构 / Loki+Grafana / Filebeat/Fluentd 日志采集 / 日志查询技巧 / 日志存储与保留策略 |
| 03-metrics-theory.md | 指标四种类型(Counter/Gauge/Histogram/Summary) / RED 指标实现 / USE 指标实现 / Micrometer / 命名规范 |
| 04-prometheus-grafana.md | Prometheus 数据模型 / PromQL 实操（rate/histogram_quantile/聚合）/ 服务发现 / Grafana Dashboard 设计 / 常用 Panel |
| 05-distributed-tracing.md | Trace/Span/Context 模型 / OpenTelemetry 架构 / 采样策略（Head/Tail/Rate）/ Jaeger vs SkyWalking / 上下文传播机制 |
| 06-alerting-oncall.md | 告警设计原则（症状 vs 原因）/ 告警分级(P0-P3) / Alertmanager 路由 / 告警疲劳对策 / On-call 轮转 / Runbook 编写 |

**动手练习**：
1. 给 PerfShop Java 版接入 Micrometer + Prometheus，在 Grafana 中创建一个 RED Dashboard（QPS / 错误率 / P50/P99 延迟）
2. 给 PerfShop 加入 OpenTelemetry SDK，在 Jaeger 中看到完整的「商品查询 → DB 查询 → Redis 缓存」链路
3. 写一条 PromQL：当 5 分钟内 P99 延迟超过 500ms 时触发告警

---

### 阶段 3.5：压测快速上手（0.5 周）

> **这不是完整的压测课程（那是阶段 7）。** 这只是给你一个「能对服务施加负载」的能力，让后续 Profiling 阶段的练习有意义。

**前置条件**：PerfShop 已运行，阶段 3 的 Prometheus 已接入。

**学完能做什么**：能用 wrk 对一个 HTTP 接口施加并发负载；能用 Locust 写一个简单的压测脚本；能在 Grafana 上实时观察压测期间的指标变化。

| 文件 | 内容 |
|------|------|
| 01-wrk-quickstart.md | wrk 安装 / 基本用法 / 并发数与线程设置 / 持续时间 / 读懂输出（Latency/Req-Sec/Transfer）/ 常用命令模板 |
| 02-locust-quickstart.md | Locust 安装 / 写一个最简脚本 / Web UI 使用 / 阶梯加压 / 配合 Grafana 观察 / 常用命令模板 |

**动手练习**：
1. 用 `wrk -t4 -c100 -d30s` 对 PerfShop 商品查询接口压 30 秒，记录 QPS 和延迟
2. 用 Locust 写一个脚本压同样的接口，对比 wrk 的结果
3. 压测期间打开 Grafana Dashboard，观察 CPU / 内存 / QPS / 延迟的变化

---

### 阶段 4a：Java Profiling 与 JVM（1.5 周）

> **Java 性能工程的第一步：理解 JVM 运行时，掌握 profiling 工具。**

**前置条件**：阶段 3.5 完成，你能对 PerfShop Java 版施加负载。

**学完能做什么**：能解释 G1 和 ZGC 的区别并做出选型；能读懂 GC 日志并判断是否需要调优；能用 async-profiler 生成火焰图并找到代码热点。

| 文件 | 内容 |
|------|------|
| 01-jvm-memory-model.md | 堆结构（Eden/Survivor/Old）/ 方法区与 Metaspace / 栈帧 / 对象内存布局 / 内存分配策略（TLAB）/ 逃逸分析 |
| 02-gc-algorithms.md | GC Roots / 可达性分析 / 标记-清除/复制/标记-整理 / 分代假设 / G1 详解 / ZGC 详解 / Shenandoah / 选型决策树 |
| 03-gc-log-tuning.md | GC 日志格式（JDK8 vs JDK11+）/ 关键指标解读 / 常见 GC 参数 / GCEasy 使用 / GC 调优思路与案例 |
| 04-async-profiler-flamegraph.md | 安装与使用 / CPU/Alloc/Lock/Wall 四种模式 / 火焰图解读方法 / On-CPU vs Off-CPU / 实操：找到真实瓶颈 |
| 05-jfr-jmc.md | JFR 事件体系 / 启动方式与配置 / JMC 分析界面详解 / 持续监控方案 / 自定义 JFR 事件 |

**动手练习**：
1. 给 PerfShop Java 版开启 GC 日志，用 wrk 压测 1 分钟，将 GC 日志上传 GCEasy 分析
2. 用 async-profiler 的 CPU 模式对 PerfShop Java 版做 30 秒 profiling，生成火焰图，找出 top 3 热点方法
3. 用 JFR 录制 PerfShop 的 60 秒运行数据，用 JMC 打开并找到最耗时的方法

---

### 阶段 4b：Java 排查与调优实战（1.5 周）

> **从工具到实战：用 profiling 结果定位问题、解决问题。**

**前置条件**：阶段 4a 完成，会使用 async-profiler / JFR / 看 GC 日志。

**学完能做什么**：能用 Arthas 在线诊断问题；能用 MAT 分析 Heap Dump 找到内存泄漏；能读懂 Thread Dump 并找到死锁和阻塞线程；能排查线程池饥饿和锁竞争；能排查 Netty 的超时和内存泄漏。

| 文件 | 内容 |
|------|------|
| 01-arthas.md | dashboard / thread / watch / trace / stack / jad / mc+redefine / ognl / 使用边界与风险 |
| 02-heap-analysis.md | Heap Dump 获取方式 / MAT 使用(Dominator Tree/Leak Suspects/OQL) / VisualVM / 直接内存泄漏 / Metaspace 溢出 |
| 03-thread-dump-analysis.md | jstack 使用 / Thread Dump 格式解读 / BLOCKED/WAITING/TIMED_WAITING 含义 / 找到持有锁的线程 / fastthread.io 在线分析 / 死锁检测 |
| 04-concurrency-performance.md | 锁竞争可视化(JFR/async-profiler lock 模式) / 线程池调优 / False Sharing / volatile 开销 / ThreadLocal 泄漏 |
| 05-common-antipatterns.md | 字符串拼接 / 正则回溯 / 序列化开销 / 连接泄漏 / N+1 查询 / 日志性能陷阱 / 大对象分配 / 反射开销 |
| 06-netty-performance.md | Pipeline 排查方法 / ChannelFuture 监听 / ByteBuf 内存泄漏检测 / EventLoop 阻塞排查 / 水位线(WriteBufferWaterMark) / LoggingHandler 使用 |

**动手练习**：
1. 用 Arthas 的 `trace` 命令追踪 PerfShop 下单接口的调用链，找到最慢的方法
2. 故意在 PerfShop 中制造一个内存泄漏（比如往 static List 不停加对象），用 `jmap` 导出 Heap Dump，用 MAT 找到泄漏源
3. 用 `jstack` 导出 PerfShop 在并发压测下的 Thread Dump，找到 BLOCKED 的线程，分析它在等哪把锁、锁被谁持有
4. 用 async-profiler 的 lock 模式分析 PerfShop 并发下单时的锁竞争

---

### 阶段 5a：Go Profiling 与运行时（1 周）

> **Go 的性能模型与 Java 截然不同：没有 VM、GC 更简单、goroutine 比线程轻量几个数量级。理解差异是关键。**

**前置条件**：阶段 3.5 完成，能对 PerfShop Go 版施加负载。

**学完能做什么**：能用 pprof 生成六种 profile 并解读；能用 go tool trace 分析 goroutine 调度；能调整 GOGC 和 GOMEMLIMIT 控制 GC 行为。

| 文件 | 内容 |
|------|------|
| 01-go-pprof.md | pprof 六种 profile(CPU/Heap/Block/Mutex/Goroutine/Threadcreate) / net/http/pprof / go tool pprof / 火焰图 |
| 02-go-trace.md | go tool trace / 运行时事件可视化 / Goroutine 调度分析 / GC 事件 / 网络阻塞可视化 |
| 03-go-gc-runtime.md | Go GC 原理（三色标记/写屏障）/ GOGC / GOMEMLIMIT / GC pacer / runtime/metrics / runtime.ReadMemStats |
| 04-go-race-concurrency.md | Race Detector 原理与使用 / 数据竞争排查 / Channel vs Mutex 性能对比 / sync.Pool 原理 / sync.Map 适用场景 |
| 05-go-benchmark-observability.md | testing.B / benchstat 统计对比 / 基准测试陷阱 / client_golang(Prometheus) / OTel Go SDK / Delve 调试器 |

**动手练习**：
1. 给 PerfShop Go 版暴露 `/debug/pprof/`，压测期间抓 CPU profile，生成火焰图
2. 用 `go tool trace` 分析 PerfShop Go 版的 goroutine 调度，找出是否有 goroutine 长时间阻塞
3. 分别设置 `GOGC=50` 和 `GOGC=200` 运行 PerfShop Go 版，压测对比 GC 频率和延迟

---

### 阶段 5b：Go 排查与调优实战（1 周）

> **Go 的坑和 Java 不同：goroutine 泄漏比线程泄漏更隐蔽，内存问题更多来自 slice/map 而非 GC。**

**前置条件**：阶段 5a 完成。

**学完能做什么**：能排查 goroutine 泄漏；能分析 gRPC 性能问题；能识别 Go 代码中的常见反模式并修复。

| 文件 | 内容 |
|------|------|
| 01-goroutine-leak.md | 泄漏模式（阻塞 channel/无 cancel context/忘记关闭 ticker）/ pprof goroutine profile / 检测工具(goleak) / 预防模式 |
| 02-network-grpc-perf.md | net/http 连接池 / Transport 调优 / httptrace / gRPC 性能（stream vs unary/连接复用/keepalive）/ 自定义 Dialer |
| 03-go-antipatterns.md | 过度 channel / slice append 内存泄漏 / defer 性能 / string↔[]byte 拷贝 / interface{} 装箱开销 / map 内存不释放 |
| 04-go-production-tuning.md | GOMAXPROCS 设置 / 编译优化(-gcflags/-ldflags) / CGO 开销与规避 / 内存对齐 / 逃逸分析(go build -gcflags='-m') |
| 05-go-case-studies.md | 3-5 个真实案例：goroutine 泄漏导致 OOM / gRPC 连接池耗尽 / GC 频繁导致延迟抖动 / map 大量删除后内存不降 |

**动手练习**：
1. 在 PerfShop Go 版中故意制造 goroutine 泄漏（启动 goroutine 但不关闭），用 pprof goroutine profile 找到泄漏点
2. 用 `go build -gcflags='-m'` 分析 PerfShop 的逃逸情况，找出不必要的堆分配
3. 在 PerfShop 中创建一个大 map 然后删除所有 key，观察内存是否下降，分析原因

---

### 阶段 6a：Python Profiling 与运行时（1 周）

> **Python 的性能特性最特殊：解释执行、GIL、引用计数 GC。不理解这些，profiling 结果看不懂。**

**前置条件**：阶段 3.5 完成，能对 PerfShop Python 版施加负载。

**学完能做什么**：能用 py-spy 对生产 Python 服务 profiling 而不影响运行；能用 tracemalloc 追踪内存分配；能解释 CPython 的引用计数和分代 GC 机制。

| 文件 | 内容 |
|------|------|
| 01-python-profiling-tools.md | cProfile / py-spy(采样 profiler/免修改/生产可用) / Scalene(CPU+内存+GPU) / 火焰图生成 / 各工具适用场景 |
| 02-python-memory-analysis.md | tracemalloc / memory_profiler / objgraph / pympler / sys.getsizeof 陷阱 / 内存快照对比 |
| 03-cpython-gc.md | 引用计数机制 / 循环引用与分代 GC / gc 模块 / weakref / __del__ 陷阱 / PyPy 与 CPython GC 差异 |
| 04-python-observability.md | prometheus_client / OTel Python SDK / structlog(结构化日志) / 自动 instrumentation / 中间件埋点 |
| 05-python-benchmark.md | pytest-benchmark / line_profiler / timeit 正确用法 / 基准测试陷阱（import cache/GC 干扰）|

**动手练习**：
1. 用 `py-spy top --pid <pid>` 实时观察 PerfShop Python 版在压测期间的 CPU 热点
2. 用 tracemalloc 拍两次内存快照（压测前后），对比找出内存增长最多的代码位置
3. 故意制造循环引用，用 `gc.set_debug(gc.DEBUG_LEAK)` 验证 GC 是否能回收

---

### 阶段 6b：Python 排查与调优实战（1 周）

> **Python 的性能瓶颈往往不在算法，而在语言特性本身。知道什么时候该用 C 扩展、什么时候该换并发模型，才是关键。**

**前置条件**：阶段 6a 完成。

**学完能做什么**：能判断一个任务应该用 threading / multiprocessing / asyncio 哪种模型；能排查 asyncio 事件循环阻塞；能优化 FastAPI/Django 的部署配置。

| 文件 | 内容 |
|------|------|
| 01-gil-concurrency-model.md | GIL 原理（为什么存在/何时释放）/ threading vs multiprocessing vs asyncio 选型决策 / CPU 密集 vs I/O 密集 / concurrent.futures |
| 02-asyncio-debugging.md | 事件循环阻塞检测 / 慢回调定位 / asyncio debug 模式 / 常见错误（忘记 await/阻塞调用进事件循环）/ uvloop |
| 03-web-framework-tuning.md | FastAPI 性能调优 / Django 性能调优 / Gunicorn worker 模型(sync/gthread/uvicorn) / ASGI vs WSGI / 连接池配置 |
| 04-python-antipatterns.md | 全局变量与 import 开销 / 深拷贝滥用 / 列表推导 vs 生成器 / 字符串拼接 / 不必要的 dict/list 创建 / C 扩展与 Cython |
| 05-python-case-studies.md | 3-5 个真实案例：GIL 导致多线程 CPU 密集任务无加速 / 循环引用内存泄漏 / asyncio 事件循环阻塞 / Django ORM N+1 |

**动手练习**：
1. 在 PerfShop Python 版中加一个 CPU 密集计算，分别用 threading 和 multiprocessing 实现，压测对比证明 GIL 的影响
2. 在 FastAPI 的异步接口中故意加入 `time.sleep(1)`（同步阻塞），用 asyncio debug 模式检测到它
3. 分别用 Gunicorn 的 sync / gthread / uvicorn worker 部署 PerfShop，压测对比三种模式的 QPS 和延迟

---

### 阶段 7：压测方法论与进阶（1.5 周）

> **阶段 3.5 教你「怎么施加负载」，这一阶段教你「怎么科学地设计和分析一次完整的压测」。**

**前置条件**：语言层（4a-6b）至少完成一门语言。阶段 3.5 已使用 wrk/Locust。

**学完能做什么**：能设计一次完整的压测（目标 → 环境 → 场景 → 执行 → 分析 → 报告）；能解释协调遗漏问题；能在 CI 中集成性能回归检测。

| 文件 | 内容 |
|------|------|
| 01-methodology.md | 压测目标定义 / 基线测试 / 阶梯加压 / 浸泡测试 / 尖峰测试 / 混合场景 / 压测环境要求 / 容量模型验证 |
| 02-tools-comparison.md | Locust / wrk / k6 / JMeter / Vegeta / hey / 选型决策树 / 各工具实操示例与脚本 |
| 03-microbenchmark.md | JMH 原理与模式 / Go testing.B 与 benchstat / pytest-benchmark / 基准测试陷阱（JIT 预热/死码消除/GC 干扰）/ 统计显著性 |
| 04-report-analysis.md | P50/P95/P99 含义与解读 / 吞吐量 vs 延迟权衡 / 协调遗漏(Coordinated Omission) / HDR Histogram / 瓶颈识别方法 |
| 05-ci-performance-gate.md | CI 中的性能回归检测 / 性能基线管理 / 性能预算(Performance Budget) / GitHub Actions/Jenkins 集成 / 告警阈值设定 |

**动手练习**：
1. 对 PerfShop 做一次完整的阶梯加压测试（50 → 100 → 200 → 500 并发），画出 QPS-延迟曲线，找到拐点
2. 对 PerfShop 做一次 2 小时浸泡测试，观察内存是否有缓慢增长（检测内存泄漏）
3. 用 JMH 对 PerfShop 中的一个关键方法做微基准测试，对比优化前后的结果

---

### 阶段 8：网络与 I/O 排查（1.5 周）

> **你的 Netty 超时问题本质上是网络排查问题。这一阶段让你有能力从抓包到分析完整走通。**

**前置条件**：阶段 0 的 TCP 基础（04a/04b）已理解。阶段 2 的网络工具（04）已使用过。

**学完能做什么**：能用 tcpdump 抓包并用 Wireshark 分析 TCP 时序；能排查连接超时、TIME_WAIT 堆积、丢包；能排查 TLS 握手问题。

| 文件 | 内容 |
|------|------|
| 01-tcpdump-wireshark.md | tcpdump 过滤语法 / Wireshark 分析流程 / TCP 时序图解读 / 常见模式识别（重传/窗口缩小/RST）|
| 02-connection-issues.md | 连接超时排查 / 连接拒绝(ECONNREFUSED) / 半连接队列溢出 / TIME_WAIT 堆积 / 端口耗尽 / keepalive |
| 03-packet-loss-latency.md | 丢包分析方法 / TCP 重传统计 / MTU 与分片问题 / 网络延迟定位(traceroute/mtr) / 内核参数调优 |
| 04-tls-debugging.md | TLS 握手过程 / 证书链问题排查 / cipher 协商失败 / TLS 性能影响 / 会话复用(Session Ticket/0-RTT) |
| 05-io-performance.md | I/O 等待分析(iowait) / 磁盘性能排查(iostat 深度) / NFS 性能问题 / 文件系统选择与调优 / Direct I/O |

**动手练习**：
1. 用 tcpdump 抓 PerfShop 与 MySQL 之间的通信，在 Wireshark 中找到慢查询对应的 TCP 时序
2. 用 `tc`（traffic control）给 PerfShop 的网络接口注入 100ms 延迟和 5% 丢包，观察应用层的表现
3. 用 tcpdump 抓一次完整的 TLS 握手过程，标注每个阶段的耗时

---

### 阶段 9a：数据库性能（1.5 周）

> **大部分后端性能问题的根因最终指向数据库。**

**前置条件**：阶段 0 完成（理解磁盘 I/O 和网络）。PerfShop 的 MySQL 已运行。

**学完能做什么**：能通过慢查询日志定位问题 SQL；能读懂 EXPLAIN 输出并优化索引；能排查锁等待和死锁；能监控连接池健康状态。

| 文件 | 内容 |
|------|------|
| 01-slow-query-analysis.md | 慢查询日志配置(MySQL/PostgreSQL) / pt-query-digest / EXPLAIN 深入解读 / 执行计划陷阱 |
| 02-index-optimization.md | B+ Tree 原理 / 索引选择性 / 覆盖索引 / 联合索引与最左前缀 / 索引失效场景 / 索引建议工具 |
| 03-lock-transaction.md | 锁等待分析 / 死锁排查与日志解读 / 事务隔离级别对性能的影响 / MVCC / 长事务危害 / 锁监控 |
| 04-connection-pool-monitor.md | 连接池原理 / HikariCP 参数调优 / pgbouncer / 连接泄漏排查 / 慢连接检测 / 监控指标 |
| 05-query-optimization.md | 查询重写技巧 / 批量操作(batch insert/update) / 分页优化(keyset pagination) / 大表策略 / 读写分离排查 |

**动手练习**：
1. 给 PerfShop 的 MySQL 开启慢查询日志（阈值 100ms），压测后用 pt-query-digest 分析 top 10 慢查询
2. 对最慢的查询执行 EXPLAIN，设计索引优化，对比优化前后的执行时间
3. 模拟两个并发下单请求造成死锁，在 MySQL 的 `SHOW ENGINE INNODB STATUS` 中找到死锁信息

---

### 阶段 9b：中间件性能（1 周）

> **Redis 慢命令和 Kafka consumer lag 是生产环境最高频的性能问题之一，但很多人只会用不会排查。**

**前置条件**：阶段 3 的 Metrics 和 Prometheus 已掌握。PerfShop 的 Redis 和 Kafka 已运行。

**学完能做什么**：能定位 Redis 慢命令和大 Key；能分析 Redis 内存构成并优化；能排查 Kafka consumer lag 并调优吞吐。

| 文件 | 内容 |
|------|------|
| 01-redis-performance.md | SLOWLOG / 慢命令排查 / 大 Key 检测(redis-cli --bigkeys/memory usage) / Pipeline 优化 / 热 Key 识别 / 连接池调优 |
| 02-redis-memory.md | INFO MEMORY 解读 / 内存碎片(mem_fragmentation_ratio) / 数据结构选择对内存的影响 / 淘汰策略 / 持久化对性能的影响(RDB/AOF) |
| 03-mq-performance.md | Kafka 性能模型 / Producer 调优(batch.size/linger.ms/acks) / Consumer 调优(fetch.min.bytes/max.poll.records) / 分区策略 / RabbitMQ 对比 |
| 04-mq-debugging.md | Consumer lag 排查 / 消息积压处理 / 分区倾斜(skew) / Rebalance 风暴 / 消息丢失排查 / 监控指标(Kafka Exporter) |

**动手练习**：
1. 在 PerfShop 中使用 `KEYS *` 命令（故意的），用 `SLOWLOG GET` 找到它，改为 `SCAN`
2. 用 `redis-cli --bigkeys` 扫描 PerfShop 的 Redis，找出大 Key，分析数据结构是否合理
3. 给 PerfShop 的 Kafka consumer 设置 `max.poll.records=1`（故意制造 lag），用 Kafka Exporter + Grafana 看到 lag 增长，然后调优恢复

---

### 阶段 10：分布式系统排查（1.5 周）

> **单机问题不难，难的是分布式场景。超时传播、重试风暴、雪崩，这些是生产环境最凶险的问题。**

**前置条件**：阶段 3 的分布式链路追踪已掌握。阶段 8 的网络排查已掌握。

**学完能做什么**：能分析超时传播链并设置正确的超时策略；能识别重试风暴并用退避+限流解决；能用 Trace 定位跨服务瓶颈；能设计降级策略。

| 文件 | 内容 |
|------|------|
| 01-timeout-circuit-breaker.md | 超时传播链分析 / 超时设置策略（总超时/单次超时/级联超时）/ 断路器原理(Hystrix/Resilience4j/Sentinel) |
| 02-retry-ratelimit.md | 重试风暴成因 / 指数退避 + 抖动 / 幂等性保证 / 限流算法(令牌桶/漏桶/滑动窗口) / 客户端 vs 服务端限流 |
| 03-trace-bottleneck.md | 用分布式 Trace 定位慢服务 / 跨服务延迟分析 / 日志关联(TraceID 串联) / 上下文传播断裂排查 |
| 04-dependency-degradation.md | 依赖图分析与可视化 / 关键路径识别 / 弱依赖 vs 强依赖 / 降级策略(fallback/缓存兜底/默认值) |
| 05-consistency-debugging.md | 数据一致性排查方法 / 最终一致性调试技巧 / 消息丢失排查(MQ) / 消息乱序 / 幂等消费 |

**动手练习**：
1. 在 PerfShop 的下单链路中，给某个依赖服务注入 2 秒延迟，观察超时如何传播到上游调用方
2. 给依赖服务设置 50% 失败率，观察不带退避的重试如何造成重试风暴（看 Prometheus 中 QPS 翻倍）
3. 用 Jaeger 找到 PerfShop 下单链路中最慢的 Span，分析根因

---

### 阶段 11：架构级性能优化（2 周）

> **单点调优有天花板，架构级优化才能量级提升。**

**前置条件**：语言层 + 排查层完成。

**学完能做什么**：能设计合理的缓存策略并处理缓存一致性；能正确配置连接池大小；能做出异步/同步/响应式的技术选型；能给出生产级的 JVM 参数配置。

| 文件 | 内容 |
|------|------|
| 01-caching-strategy.md | Cache-Aside/Write-Through/Write-Behind/Write-Around / 穿透/雪崩/击穿对策 / 多级缓存 / 淘汰策略 / 缓存一致性 |
| 02-connection-pooling.md | 连接池原理与通用调优 / HikariCP / OkHttp / Jedis/Lettuce / 连接池大小公式 / 连接泄漏排查模式 |
| 03-async-reactive.md | 异步编程模型对比(Callback/Future/Reactive) / CompletableFuture / WebFlux / 背压(Backpressure) / 线程模型选择 |
| 04-database-architecture.md | 分库分表策略 / 读写分离 / CQRS 模式 / 冷热数据分离 / 大表归档 / NewSQL 概览 |
| 05-jvm-production-tuning.md | 生产 JVM 参数模板 / 堆大小选择方法 / GC 选择决策树 / 容器环境 JVM(-XX:+UseContainerSupport) / 实际调优案例 |
| 06-performance-patterns.md | 对象池模式 / 批处理(Batching) / 预计算 / 懒加载 / 无锁设计(CAS/Disruptor) / 零拷贝 / 压缩策略 |
| 07-protocol-serialization.md | HTTP/1.1 vs HTTP/2 vs HTTP/3（多路复用/头部压缩/队头阻塞）/ gRPC 协议层优化(stream 模式/keepalive/max message size) / JSON vs Protobuf vs Avro vs MessagePack 性能对比 / 压缩算法选型(gzip/zstd/snappy/lz4) / 连接复用与长连接管理 |

**动手练习**：
1. 给 PerfShop 的商品查询加上 Redis 缓存（Cache-Aside），压测对比缓存前后的 QPS 和 P99
2. 用 HikariCP 连接池公式计算 PerfShop 应该配多大的连接池，调整后压测验证
3. 给 PerfShop Java 版写一份生产 JVM 参数配置，说明每个参数的选择理由
4. 对 PerfShop 的一个接口分别用 JSON 和 Protobuf 序列化，压测对比吞吐量和延迟差异

---

### 阶段 12：容器与云原生性能（1.5 周）

> **现代后端跑在容器里，不理解 cgroup 和 K8s 资源模型，你的调优可能完全失效。**

**前置条件**：语言层完成（特别是 JVM 调优）。Docker 基本使用。

**学完能做什么**：能正确设置容器的 CPU 和内存限制；能配置容器中的 JVM 参数使其感知容器资源；能设计 K8s 的 Request/Limit 策略。

| 文件 | 内容 |
|------|------|
| 01-cgroup-resource.md | cgroups v1/v2 / CPU 限制(CFS quota/period) / 内存限制与 OOM / 容器内观测差异（/proc 的坑）/ JVM 容器感知 |
| 02-k8s-performance.md | Resource Request/Limit 设置策略 / QoS 类别 / HPA/VPA / 调度策略 / 节点亲和性 / Pod 资源画像 |
| 03-container-monitoring.md | cAdvisor / kube-state-metrics / node-exporter / Kubernetes 监控架构 / Prometheus Operator |
| 04-service-mesh-perf.md | Sidecar 代理开销量化 / Istio/Envoy 性能调优 / mTLS 性能影响 / 链路追踪集成 / 何时不用 Service Mesh |

**动手练习**：
1. 给 PerfShop Java 版的 Docker 容器设置 `--memory=512m --cpus=1`，不调整 JVM 参数，观察是否 OOM；然后加上 `-XX:+UseContainerSupport` 验证
2. 对比容器内 `/proc/meminfo` 和宿主机的差异，理解为什么在容器内用 `free` 看到的不准
3. 给 PerfShop 的容器设置不同的 CPU 限制（0.5/1/2 核），压测对比吞吐量是否线性增长

---

### 阶段 13：SRE 与生产实践（1.5 周）

> **调优不是一次性的，是持续的工程实践。这一阶段建立从监控到响应到复盘的完整闭环。**

**前置条件**：可观测性层 + 排查层完成。

**学完能做什么**：能为服务定义 SLI 和 SLO；能做基于压测的容量规划；能设计一次混沌工程实验；能主持一次事故复盘。

| 文件 | 内容 |
|------|------|
| 01-sli-slo-sla.md | 定义与区别 / SLI 选择（可用性/延迟/正确性）/ SLO 设定方法 / Error Budget 与发布节奏 / 实际案例 |
| 02-capacity-planning.md | 容量模型构建 / 压测驱动的容量规划 / 成本优化 / 自动扩缩容策略 / 季节性与突发流量 |
| 03-chaos-engineering.md | 混沌工程原理与 Steady State Hypothesis / ChaosBlade / Chaos Mesh / LitmusChaos / 实验设计与安全边界 |
| 04-incident-management.md | 事故分级(P0-P3) / 响应流程 / 指挥官模式(Incident Commander) / 沟通模板 / 降级预案(Playbook) |
| 05-postmortem.md | 事故复盘模板 / 根因分析(5 Whys/鱼骨图/故障树) / 改进项跟踪 / 无责文化 / 知识沉淀与分享 |

**动手练习**：
1. 为 PerfShop 的商品查询接口定义 SLI（可用性 + P99 延迟）和 SLO（99.9% 可用 + P99 < 200ms），用 Prometheus 查询当前是否达标
2. 基于阶段 7 的压测结果，计算 PerfShop 需要多少实例才能支撑 10000 QPS
3. 写一份 PerfShop 的降级预案：当 Redis 不可用时如何 fallback

---

### 阶段 14：综合实战（1.5 周）

> **把前 13 个阶段学到的一切串起来。这是你的毕业考试。**

**前置条件**：所有阶段完成（或至少完成到阶段 13）。如果是在第 0 轮做最小闭环，可以只选择其中一个场景提前演练，用来验证自己是否已经理解“发现 → 定位 → 修复 → 验证”的基本流程。

**学完能做什么**：面对一个有性能问题的服务，你能从监控发现异常 → 确定排查方向 → 用工具定位根因 → 修复 → 验证 → 复盘，走完完整闭环。

| 文件 | 内容 |
|------|------|
| 01-capstone-guide.md | 贯穿项目完整演练指南 / 如何在 PerfShop 上模拟各类问题 / 演练清单 |
| 02-full-cycle-exercise.md | 端到端性能工程实战：给 PerfShop 注入 5 个不同类型的问题（GC / 慢查询 / goroutine 泄漏 / Redis 大 Key / 超时传播），逐一发现、排查、修复、验证 |
| 03-self-assessment.md | 排查能力自测题（20 道场景题）/ 每题给出现象，你写出排查步骤和可能根因 / 参考答案与评分标准 |

**动手练习**：
1. 让别人（或用脚本）在 PerfShop 中随机注入 3 个性能问题，你只看 Grafana Dashboard 开始排查，记录排查过程
2. 完成 03 中的 20 道自测题，对照答案评估自己的薄弱环节
3. 写一份 PerfShop 的完整性能报告：包含基线数据、瓶颈分析、优化措施、优化后数据

---

## 推荐学习资源

### 必读书籍（按优先级）

| 书名 | 作者 | 覆盖阶段 | 说明 |
|------|------|---------|------|
| **《性能之巅》(Systems Performance)** 第 2 版 | Brendan Gregg | 0, 1, 2 | 系统性能的圣经，覆盖 OS 到应用层 |
| **《Java Performance》** 第 2 版 | Scott Oaks | 4a, 4b, 11 | Java 性能调优最佳参考 |
| **《BPF Performance Tools》** | Brendan Gregg | 2 | Linux 观测进阶，eBPF 专项 |
| **《数据密集型应用系统设计》(DDIA)** | Martin Kleppmann | 9a, 10, 11 | 分布式系统基础，理解性能权衡 |
| **《Google SRE》** | Google | 13 | SRE 实践参考 |
| **《100 Go Mistakes》** | Teiva Harsanyi | 5a, 5b | Go 常见错误与性能陷阱 |
| **《High Performance Python》** 第 2 版 | Gorelick & Ozsvald | 6a, 6b | Python 性能工程专项 |

### 在线资源

| 资源 | 用途 |
|------|------|
| [Brendan Gregg 的博客](http://www.brendangregg.com/) | 性能工程领域最权威的个人博客，Linux 性能图谱 |
| [async-profiler Wiki](https://github.com/async-profiler/async-profiler/wiki) | Java profiling 官方文档 |
| [Arthas 官方文档](https://arthas.aliyun.com/) | 中文友好的 Java 诊断工具 |
| [GCEasy](https://gceasy.io/) | 在线 GC 日志分析 |
| [Go pprof 文档](https://pkg.go.dev/runtime/pprof) | Go profiling 官方参考 |
| [py-spy 文档](https://github.com/benfred/py-spy) | Python 采样 profiler |
| [OpenTelemetry 文档](https://opentelemetry.io/docs/) | 可观测性标准 |

---

## 学习建议

### 每个阶段的学习方法

```
1. 读概念文件，建立心智模型（不急着动手）
2. 在 PerfShop 上实操练习（每个阶段都有具体的动手练习）
3. 对比操作前后的数据（监控截图、火焰图、压测报告）
4. 写一段总结：这个阶段我学到了什么、解决了什么问题、还有什么不确定的
5. 尝试向别人解释你做了什么、为什么有效（费曼学习法）
```

### 关键转折点

| 完成阶段 | 你获得的能力 |
|---------|-------------|
| **阶段 1** | 有了方法论，面对性能问题知道「从哪里开始」 |
| **阶段 3** | 能搭建完整的监控体系，从「盲人」变成「有眼睛」 |
| **阶段 4b** | 能独立排查大部分 Java 性能问题 |
| **阶段 5b + 6b** | 在三门语言上都有独立的性能工程能力 |
| **阶段 10** | 能排查分布式系统的复杂问题（超时传播、雪崩、一致性） |
| **阶段 13** | 建立了从监控到响应到复盘的完整闭环 |
| **阶段 14** | 能独立完成端到端的性能工程，这是你的「毕业」 |

### 你的 Netty 超时问题 — 学完后的正确排查路径

```
1. [阶段4b-06] writeAndFlush 加 ChannelFutureListener → 确认发送是否成功
2. [阶段4b-06] Pipeline 加 LoggingHandler → 看消息在哪个 handler 停住
3. [阶段3-01]  开启 Netty 的 LoggingHandler 调试日志 → 看 pipeline 内部事件
4. [阶段2-04]  tcpdump 双端抓包 → 确认 TCP 层行为
5. [阶段8-01]  Wireshark 分析 → 看 TCP 重传、RST、FIN 时序
6. [阶段4a-03] JFR/GC 日志 → 排除 STW 暂停恰好在 flush 时刻
7. [阶段4b-03] jstack Thread Dump → 检查是否有线程 BLOCKED 在 IO 操作上
8. [阶段4b-04] 检查 EventLoop → 是否有阻塞操作占用了 IO 线程
9. [阶段10-01] 检查中间链路 → LB/Proxy 是否有超时配置
10. [阶段8-02] 检查连接状态 → channel 是否 inactive 但仍在连接池中
```
