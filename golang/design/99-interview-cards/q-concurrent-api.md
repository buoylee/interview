# 并发安全的 API 设计

## 一句话回答

设计会被并发使用的类型/库的铁律:**① 默认类型不保证并发安全,必须文档化契约**(「调用方负责同步」还是「本类型安全」,别不说);**② 优先让类型不可变/不共享**(无共享即无竞争,免锁最稳),要共享再加锁、**锁用未导出字段、含锁类型全用指针接收者**(不可拷贝);**③ 库别偷偷开 goroutine**——要开就给调用方控制权(收 `ctx` 可取消 / 提供 `Close`)且 goroutine 自带 recover(否则泄漏 + panic crash 进程);**④ `ctx` 作首参并一路下传**;**⑤ 别在 API 暴露 channel/Mutex**;**⑥ 公共 API 返回 error 不 panic;零值可用**。

## 谁负责同步

| 策略 | 适用 |
|---|---|
| 调用方加锁(类型不安全) | 通用类型、锁粒度调用方定更优(必须文档警示) |
| 内部加锁(类型安全) | 共享单例、调用方难正确加锁 |
| 不可变 / 不共享 | 配置/值对象 / 每 goroutine 一份(最省心) |

## 为什么别导出 Mutex/channel

- 嵌入 `sync.Mutex` 会把 `Lock`/`Unlock` 提升成公共方法(见 [`type-system/04`](../../type-system/04-embedding/README.md))→ 外部能锁你内部状态。用未导出 `mu sync.Mutex`。
- 导出 channel 让「谁关闭/缓冲多大/泄漏」成契约负担;优先方法/回调。

## 证据链接

- 正文:[`03 并发安全的 API 设计`](../03-concurrent-api/README.md);goroutine 泄漏 [`concurrency/04`](../../concurrency/04-goroutine/README.md);ctx [`concurrency/07`](../../concurrency/07-context/README.md);panic crash [`error-handling/05`](../../error-handling/05-concurrent-errors/README.md)

## 易追问的延伸

- **库偷开 goroutine 的危害?** 调用方不知道、停不掉、它 panic crash 整个进程——隐形泄漏源。给 ctx/Close。
- **含锁类型为什么不能拷贝?** 拷贝锁=拷状态,互斥失效;全用指针接收者 + `go vet copylocks`。
- **ctx 取消怎么真生效?** 库内阻塞调用必须接 ctx 往下传,否则取消是空头支票。
- **和 Java?** Java 有线程安全集合明确契约;Go 默认不安全、更多把同步责任交调用方,显式文档化是命门。
