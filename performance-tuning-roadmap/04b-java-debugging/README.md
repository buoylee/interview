# 阶段 4b：Java 排查与调优实战学习指南

> 本阶段目标：把 4a 的 profiling 证据转化为实际定位和修复能力，覆盖线上 Java 服务高频问题。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-arthas.md](./01-arthas.md) | 在线观察方法耗时、调用栈、参数和返回值 |
| 2 | [03-thread-dump-analysis.md](./03-thread-dump-analysis.md) | 线程状态、死锁、BLOCKED、线程池饥饿 |
| 3 | [02-heap-analysis.md](./02-heap-analysis.md) | Heap Dump、MAT、Dominator Tree、泄漏分析 |
| 4 | [04-concurrency-performance.md](./04-concurrency-performance.md) | 锁竞争、线程池、False Sharing、ThreadLocal |
| 5 | [05-common-antipatterns.md](./05-common-antipatterns.md) | Java 常见性能反模式 |
| 6 | [06-netty-performance.md](./06-netty-performance.md) | EventLoop、Pipeline、ByteBuf、网络排查 |

---

## 本阶段主线

典型排查入口：

```text
接口慢 → Arthas trace/watch
线程卡住 → jstack / Thread Dump
内存上涨 → Heap Dump / MAT
吞吐上不去 → lock profile / 线程池指标
网络超时 → Netty Pipeline + tcpdump + Trace
```

---

## 最小完成标准

学完后应该能做到：

- 用 Arthas 找到一个慢方法
- 读懂 Thread Dump 中 RUNNABLE、BLOCKED、WAITING 的含义
- 用 MAT 找到一次内存泄漏的引用链
- 判断线程池是否队列堆积或线程不足
- 解释 Netty EventLoop 为什么不能阻塞

---

## 本阶段产物

建议留下：

- 一段 Arthas `trace` 输出
- 一份 Thread Dump 分析记录
- 一张 MAT Dominator Tree 截图或摘要
- 一份锁竞争或线程池分析结论
- 一个 Java 反模式修复前后对比

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 在线上随意 redefine | 先理解风险，优先观察不修改 |
| Heap Dump 越大越好 | 采集合适时机，避免影响服务 |
| 看到 BLOCKED 就认为死锁 | 区分短暂锁竞争和真正死锁 |
| Netty 超时只看应用日志 | 同时看 Pipeline、EventLoop、TCP 包和超时配置 |

---

## 下一阶段衔接

完成 4b 后，你已经具备 Java 主语言排查能力。后续可以进入阶段 7 学完整压测方法，或进入 8-10 学网络、数据库和分布式排查。

