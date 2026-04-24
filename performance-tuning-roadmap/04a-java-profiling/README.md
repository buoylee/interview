# 阶段 4a：Java Profiling 与 JVM 学习指南

> 本阶段目标：理解 JVM 运行时，并能用 GC 日志、async-profiler、JFR 找到 Java 服务的性能证据。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-jvm-memory-model.md](./01-jvm-memory-model.md) | 堆、栈、Metaspace、对象布局、TLAB |
| 2 | [02-gc-algorithms.md](./02-gc-algorithms.md) | G1、ZGC、Shenandoah 的目标和取舍 |
| 3 | [03-gc-log-tuning.md](./03-gc-log-tuning.md) | 读懂 GC 日志，判断是否需要调 GC |
| 4 | [04-async-profiler-flamegraph.md](./04-async-profiler-flamegraph.md) | CPU、alloc、lock、wall 火焰图 |
| 5 | [05-jfr-jmc.md](./05-jfr-jmc.md) | JFR 事件、JMC 分析、持续诊断 |

---

## 本阶段主线

Java 性能排查先分清问题类型：

```text
CPU 高 → async-profiler cpu
GC 频繁或停顿长 → GC 日志 + JFR
内存分配高 → async-profiler alloc
锁竞争 → async-profiler lock / JFR
CPU 不高但接口慢 → wall-clock profile / Trace
```

---

## 最小完成标准

学完后应该能做到：

- 解释 JVM Heap 与非 Heap 内存的区别
- 能读懂一次 G1 GC 日志的关键字段
- 能采集一张 CPU 火焰图
- 能说出火焰图里 top 3 热点的调用路径
- 能用 JFR 录制 60 秒并找到慢方法或 GC 事件

---

## 本阶段产物

建议留下：

- 一份 GC 日志摘要
- 一张 CPU 火焰图
- 一张 alloc 或 wall 火焰图
- 一份 JFR 录制文件或分析截图
- 一段“优化前后指标对比”

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 一遇到慢就调 JVM 参数 | 先判断瓶颈是否真的在 JVM |
| 只看 Heap 不看 RSS | Java 内存还包括 Metaspace、线程栈、Direct Buffer |
| 火焰图看颜色 | 重点看宽度和调用路径，不看颜色 |
| 只采一次 profile | 多采几次确认热点稳定 |

---

## 下一阶段衔接

阶段 4a 解决“拿到 JVM 与代码热点证据”。阶段 4b 会进入具体排查实战：Arthas、Heap Dump、Thread Dump、锁竞争和 Netty。

