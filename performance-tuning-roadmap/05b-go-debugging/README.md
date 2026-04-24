# 阶段 5b：Go 排查与调优实战学习指南

> 本阶段目标：识别并修复 Go 服务中的高频生产问题，特别是 goroutine 泄漏、连接复用、逃逸、slice/map 内存和 gRPC 性能。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-goroutine-leak.md](./01-goroutine-leak.md) | goroutine 泄漏模式、pprof、goleak |
| 2 | [02-network-grpc-perf.md](./02-network-grpc-perf.md) | HTTP Transport、连接池、httptrace、gRPC |
| 3 | [03-go-antipatterns.md](./03-go-antipatterns.md) | slice、map、defer、string/bytes、interface 开销 |
| 4 | [04-go-production-tuning.md](./04-go-production-tuning.md) | GOMAXPROCS、逃逸分析、CGO、编译参数 |
| 5 | [05-go-case-studies.md](./05-go-case-studies.md) | 多场景完整排查案例 |

---

## 本阶段主线

Go 实战排查要关注“轻量并发带来的隐蔽问题”：

```text
goroutine 数持续涨 → 泄漏
连接数持续涨 → Body 未关闭或连接池配置错误
内存不降 → slice/map 持有底层数组或 runtime 未归还
延迟抖动 → GC、锁、网络、下游阻塞
```

---

## 最小完成标准

学完后应该能做到：

- 识别至少 3 种 goroutine 泄漏模式
- 用 pprof 找到泄漏调用栈
- 正确配置 HTTP Client Transport
- 用逃逸分析解释一次堆分配
- 写一个 goleak 或 benchmark 验证修复

---

## 本阶段产物

建议留下：

- 一份 goroutine 泄漏排查记录
- 一份 HTTP/gRPC 连接池配置说明
- 一份逃逸分析输出摘录
- 一个 Go 反模式修复前后 benchmark

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 每次请求创建 http.Client | 复用 Client 和 Transport |
| 只 Close Body 不读取 | 需要理解连接复用条件 |
| 过度使用 channel | 简单共享状态可优先考虑 mutex |
| 逃逸一定坏 | 关键路径需要 benchmark 验证 |

---

## 下一阶段衔接

完成 5b 后，你已经具备 Go 主语言排查能力。后续可以进入阶段 7 做系统压测，或进入 8-10 排查网络、数据库和分布式问题。

