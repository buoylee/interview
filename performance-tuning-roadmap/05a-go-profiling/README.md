# 阶段 5a：Go Profiling 与运行时学习指南

> 本阶段目标：掌握 Go runtime 的观测方式，能用 pprof、trace、benchmark 和 runtime 指标解释 Go 服务的性能瓶颈。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-go-pprof.md](./01-go-pprof.md) | CPU、Heap、Goroutine、Block、Mutex profile |
| 2 | [02-go-trace.md](./02-go-trace.md) | goroutine 调度、网络阻塞、GC 时间线 |
| 3 | [03-go-gc-runtime.md](./03-go-gc-runtime.md) | GOGC、GOMEMLIMIT、runtime/metrics |
| 4 | [04-go-race-concurrency.md](./04-go-race-concurrency.md) | Race Detector、channel、mutex、sync.Pool |
| 5 | [05-go-benchmark-observability.md](./05-go-benchmark-observability.md) | testing.B、benchstat、Prometheus、OTel |

---

## 本阶段主线

Go 排查优先从 pprof 开始：

```text
CPU 高 → CPU profile
内存涨 → Heap profile
goroutine 涨 → Goroutine profile
锁竞争 → Mutex profile
channel/IO 阻塞 → Block profile + go tool trace
```

---

## 最小完成标准

学完后应该能做到：

- 给 Go 服务暴露 `/debug/pprof`
- 在压测期间采集 CPU profile
- 用 heap profile 判断主要分配来源
- 用 goroutine profile 找到阻塞最多的调用栈
- 用 `go test -bench` 和 benchstat 对比优化效果

---

## 本阶段产物

建议留下：

- 一份 CPU profile 分析
- 一份 Heap profile 分析
- 一份 goroutine profile 摘要
- 一份 go trace 截图或关键事件说明
- 一份 benchmark 优化前后对比

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 只看 alloc_space | 同时看 inuse_space，区分分配量和存活量 |
| goroutine 多就一定泄漏 | 看数量是否持续增长，以及阻塞栈是否重复 |
| GOGC 越大越好 | 需要在内存占用和 GC 频率之间权衡 |
| benchmark 只跑一次 | 多次运行，用 benchstat 看统计差异 |

---

## 下一阶段衔接

阶段 5a 解决“如何观察 Go runtime”。阶段 5b 会进入 goroutine 泄漏、网络客户端、反模式和生产调优。

