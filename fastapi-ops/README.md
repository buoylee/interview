# FastAPI 系统监控与调优学习路径

> 目标：具备监控系统、分析瓶颈、调优服务的完整能力
> 载体：FastAPI + 真实生产场景
> 前提：有丰富编程经验，缺乏系统层直接操作经验

---

## 学习地图

```
阶段一：地基           阶段二：看见            阶段三：分析           阶段四：调优
─────────────────    ────────────────────    ──────────────────    ──────────────────
01 FastAPI 生产化  →  03 应用级指标(Prometheus)  06 性能剖析(profiling)  08 应用层调优
02 系统指标读取    →  04 分布式追踪(OTel/Jaeger)  07 压测(Locust)        09 系统层调优
                  →  05 结构化日志(Loki)
```

---

## 各阶段详细说明

### 阶段一：地基

#### [01-foundation](./01-foundation/) — FastAPI 生产化部署
**核心问题**：一个"能跑"的 FastAPI 和一个"能上生产"的 FastAPI 差在哪？

- Uvicorn / Gunicorn + UvicornWorker 配置
- 优雅关机（graceful shutdown）与信号处理
- 健康检查端点设计（liveness / readiness）
- 中间件：请求 ID、耗时记录、限流
- 依赖注入与连接池（数据库、Redis）
- Docker 容器化 + 多阶段构建
- 环境变量与配置管理（pydantic-settings）

**产出**：一个生产可用的 FastAPI 模板项目

---

#### [02-system-metrics](./02-system-metrics/) — 读懂系统指标
**核心问题**：服务慢/挂，第一时间看什么？

- `/proc` 文件系统：进程、CPU、内存、网络的数据源头
- CPU：`top` / `htop` / `mpstat` — 区分 us/sy/wa/si/st
- 内存：`free` / `vmstat` — RSS、VSZ、PageFault、Swap
- I/O：`iostat` / `iotop` — await、util、r/w throughput
- 网络：`ss` / `netstat` / `iftop` — 连接状态、TIME_WAIT、队列
- 文件描述符：`lsof` / `ulimit` — fd 泄漏排查
- 进程：`strace` / `perf` 初步认识
- 用 Python `psutil` 在 FastAPI 中暴露系统指标

**产出**：会用命令行工具做第一轮排查，知道数字背后的含义

---

### 阶段二：看见（Observability 三支柱）

#### [03-app-metrics](./03-app-metrics/) — Prometheus + Grafana
**核心问题**：如何让服务"说出"自己的状态？

- Prometheus 数据模型：Counter / Gauge / Histogram / Summary
- `prometheus-fastapi-instrumentator` 自动埋点
- 手动埋点：业务指标（下单数、错误率、队列深度）
- PromQL 核心语法：rate / irate / histogram_quantile
- Grafana Dashboard：RED 方法（Rate / Error / Duration）
- AlertManager 告警规则设计

**产出**：能看到 P99 延迟、错误率、QPS 实时变化

---

#### [04-tracing](./04-tracing/) — OpenTelemetry + Jaeger
**核心问题**：一个慢请求，时间花在哪一步？

- Trace / Span / Context Propagation 概念
- OpenTelemetry Python SDK 接入 FastAPI
- 自动埋点：HTTP、SQLAlchemy、Redis、httpx
- 手动 Span：关键业务逻辑
- Jaeger UI：Trace 分析、依赖拓扑
- W3C TraceContext 标准，跨服务传播

**产出**：能追踪跨服务请求链路，定位慢在哪个 Span

---

#### [05-logging](./05-logging/) — 结构化日志
**核心问题**：日志怎么写才能在出事时快速检索？

- 结构化日志 vs 纯文本日志
- `structlog` 配置与使用
- 日志级别策略（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 关联 TraceID：日志 + Trace 联动
- Loki + Promtail 采集
- LogQL 基础查询
- 日志采样（高频接口避免日志爆炸）

**产出**：日志可检索、可关联 Trace，不再靠 `grep` 裸搜

---

### 阶段三：分析

#### [06-profiling](./06-profiling/) — 性能剖析
**核心问题**：CPU 占满或接口慢，代码里到底是哪行？

- `cProfile` + `snakeviz`：函数级 CPU 分析
- `py-spy`：**生产环境**可用的采样 profiler（零侵入）
- `memray`：内存分配追踪，定位内存泄漏
- `asyncio` 专项：`aiomonitor` / 慢协程检测
- 火焰图（Flame Graph）阅读方法
- 线程/协程 dump：卡死时看调用栈

**产出**：能在生产拿到 CPU 火焰图，定位热点函数

---

#### [07-load-testing](./07-load-testing/) — 压测
**核心问题**：服务能承受多少并发？瓶颈在哪里先触发？

- Locust 基础：Task / User / 并发模型
- 压测场景设计：阶梯加压、峰值、长时稳定
- 压测时同步观测：Grafana + Prometheus
- 瓶颈识别：CPU bound / IO bound / 锁竞争 / 连接池耗尽
- 压测报告解读：RPS、P95/P99、错误率

**产出**：能设计压测场景，边压边看指标，找到系统极限

---

### 阶段四：调优

#### [08-tuning](./08-tuning/) — 应用层调优
**核心问题**：找到瓶颈后怎么改？

- Worker 数量：CPU bound vs IO bound 的不同策略
- 异步最佳实践：不在协程里做阻塞调用
- 数据库连接池调优：pool_size / max_overflow / pool_timeout
- 缓存策略：Redis 缓存、HTTP 缓存头、本地 LRU
- 序列化优化：`orjson` 替换标准 json
- 响应流式传输（Streaming Response）
- 后台任务 vs 消息队列的选型

**产出**：有一套系统化的应用层调优清单

---

#### [09-system-tuning](./09-system-tuning/) — 系统层调优
**核心问题**：代码改不了更多了，OS 层还能做什么？

- 文件描述符限制：`ulimit -n` / `/etc/security/limits.conf`
- TCP 参数：`somaxconn` / `tcp_backlog` / `TIME_WAIT` 复用
- 内存：`vm.swappiness` / 大页内存 / OOM Killer 策略
- CPU：进程亲和性（CPU affinity）/ NUMA
- 容器环境：cgroup 限制对 Java/Python 的影响
- `sysctl` 常用参数速查

**产出**：能做基础的 OS 层参数调整，知道边界在哪

---

## 实践项目

每个阶段都围绕同一个 FastAPI 项目演进，模拟真实业务场景：

```
一个包含以下接口的服务：
  POST /orders          - 创建订单（写数据库）
  GET  /orders/{id}     - 查询订单（读数据库 + Redis 缓存）
  GET  /reports/daily   - 生成日报（CPU密集型）
  POST /notify          - 发送通知（外部 HTTP 调用）
```

从"裸 FastAPI"一步步加入：监控埋点 → 日志 → 追踪 → 压测 → 调优

---

## 工具栈一览

| 层次 | 工具 |
|------|------|
| 应用框架 | FastAPI + Uvicorn + Gunicorn |
| 指标 | Prometheus + Grafana |
| 追踪 | OpenTelemetry + Jaeger |
| 日志 | structlog + Loki + Grafana |
| 剖析 | py-spy + memray |
| 压测 | Locust |
| 容器 | Docker Compose（本地全栈） |
| 系统工具 | htop / iostat / ss / strace / perf |

---

## 开始

```bash
cd 01-foundation
# 每个目录都有独立的 README.md 和可运行代码
```
