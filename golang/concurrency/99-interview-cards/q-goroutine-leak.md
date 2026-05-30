# goroutine 泄漏：原因与排查

## 一句话回答

goroutine 泄漏 = 一个 goroutine 被**永久挂起、再也不会结束**（多为等一个没有对端的 channel、漏了取消信号、或无超时的无限等待）。它不耗 CPU 但**一直占内存**（栈+引用对象），**GC 回收不了**，表现为 `NumGoroutine` 和内存随时间**单调上涨**直到 OOM。排查用 pprof 的 goroutine profile 按栈聚合定位。

## 三大来源

1. **发/收一个没有对端的 channel**（最常见）——对端永远不来，goroutine 永久 `_Gwaiting`。
2. **漏了取消信号**——起了 goroutine 等某条件，但触发路径提前 return/出错，没通知它退出。
3. **无超时的无限等待**——网络/锁/channel 没设超时，对端永久不响应。

## 为什么 GC 救不了

被泄漏的 goroutine 仍「活着」（被调度器记录、可能引用对象），所以它和它引用的内存都不回收，还被 `NumGoroutine()` 计入。

## 排查三板斧

```go
import _ "net/http/pprof"
runtime.NumGoroutine()        // 趋势单调涨 = 泄漏哨兵
```
```bash
# 按栈聚合——泄漏点会聚集成百上千个相同栈（如 chan receive）
go tool pprof http://localhost:6060/debug/pprof/goroutine
curl 'http://localhost:6060/debug/pprof/goroutine?debug=2'   # 每个 G 完整栈
```

## 怎么防

- 每个 goroutine 给**明确退出路径**：`select <-ctx.Done()`（[07](../07-context/README.md)）/ 监听 channel 关闭。
- `WithTimeout`/`WithCancel` 一定 `defer cancel()`。
- 网络调用带超时（ctx / SetDeadline）。
- `WaitGroup` 用 `defer wg.Done()`（panic 也释放）。
- 测试上 `go.uber.org/goleak` 断言无遗留 goroutine。

## 证据链接

- 正文：[`04 goroutine 实战`](../04-goroutine/README.md) / [`07 context`](../07-context/README.md) / [`09 陷阱与调优`](../09-pitfalls-tuning/README.md)
- 实操：`performance-tuning-roadmap/05b-go-debugging/01-goroutine-leak.md`

## 易追问的延伸

- **泄漏和死锁区别？** 死锁是**全部** goroutine 阻塞（runtime fatal）；泄漏是**部分**永久阻塞（不报错，靠监控/pprof）。
- **channel 泄漏？** 就是 goroutine 泄漏的一种——卡在 chan send/receive。
- **怎么在 CI 拦住？** goleak + 压测下观察 NumGoroutine 曲线是否回落。
