# 阶段 6a：Python Profiling 与运行时学习指南

> 本阶段目标：掌握 Python 服务的 CPU、内存、GC 和观测手段，能在不大幅侵入业务代码的情况下找到热点。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-python-profiling-tools.md](./01-python-profiling-tools.md) | cProfile、py-spy、Scalene、火焰图 |
| 2 | [02-python-memory-analysis.md](./02-python-memory-analysis.md) | tracemalloc、memory_profiler、objgraph、pympler |
| 3 | [03-cpython-gc.md](./03-cpython-gc.md) | 引用计数、循环引用、分代 GC、weakref |
| 4 | [04-python-observability.md](./04-python-observability.md) | prometheus_client、OTel、structlog |
| 5 | [05-python-benchmark.md](./05-python-benchmark.md) | pytest-benchmark、line_profiler、timeit |

---

## 本阶段主线

Python 排查先区分问题类型：

```text
CPU 热点 → py-spy / cProfile / Scalene
RSS / working set / OOM 趋势 → Prometheus process/container 指标
Python 分配增长 → tracemalloc / objgraph
RSS 增长但 tracemalloc 稳定 → Memray / native allocator 调查
循环引用 → gc debug
Web 延迟 → 指标 + Trace + 框架 profiler
优化验证 → pytest-benchmark
```

生产环境先用常驻指标发现异常，再临时启用 profiler 定位根因：

- FastAPI 进程指标与多 worker 限制：[`fastapi-ops/03-app-metrics`](../../fastapi-ops/03-app-metrics/README.md)
- 容器 working set、RSS、OOM 与告警：[`12-container/03-container-monitoring`](../12-container/03-container-monitoring.md)
- 受控生产 profiling：[`fastapi-ops/06-profiling`](../../fastapi-ops/06-profiling/README.md)

---

## 最小完成标准

学完后应该能做到：

- 用 py-spy 观察运行中进程热点
- 用 cProfile 生成一次函数耗时报告
- 用 tracemalloc 对比两次内存快照
- 解释 RSS、Python allocation 与 container memory 为什么可能不同步
- 解释引用计数和循环引用的区别
- 用 pytest-benchmark 验证一次优化

---

## 本阶段产物

建议留下：

- 一份 py-spy top 或火焰图
- 一份 cProfile 输出摘要
- 一份 tracemalloc snapshot 对比
- 一份 benchmark 优化前后结果

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 用 time.time 手写 benchmark | 使用 timeit 或 pytest-benchmark |
| 只看 sys.getsizeof | 用 pympler 等工具看深层对象大小 |
| 多线程能加速 CPU 密集任务 | 先理解 GIL 限制 |
| 只优化 Python 代码 | 可能瓶颈在数据库、网络或序列化 |

---

## 下一阶段衔接

阶段 6a 解决“如何观察 Python 运行时”。阶段 6b 会进入 GIL、asyncio、Web 框架部署和常见反模式。
