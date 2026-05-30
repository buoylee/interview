# channel 底层 / 无缓冲 vs 有缓冲 / close 语义

## 一句话回答

channel 底层是加锁的 `hchan`（环形缓冲 + 收发等待队列 + 一把 lock）。**无缓冲 = 同步握手**（发送阻塞到接收就位，是同步点，≈SynchronousQueue）；**有缓冲 = 异步队列**（满才阻塞，≈BlockingQueue）。`close` 是**一对多广播**，规则记死：发送方关、只关一次，向已关闭发送/重复关/关 nil 都 panic。

## hchan 结构

```
buf        环形缓冲数组（有缓冲才有）
qcount/dataqsiz  当前元素数 / 容量
sendx/recvx 环形下标
sendq/recvq 等待发送/接收的 goroutine（sudog 队列）
lock       互斥锁（收发都先抢）
```

## 发送的三条路径

`ch <- v`（持锁后按优先级）：
1. **recvq 有等待接收者** → 直接把 v 拷给它，goready 唤醒（最快，绕过缓冲）
2. **缓冲有空位** → 拷进 buf，继续
3. **否则** → 包成 sudog 挂 sendq，gopark 阻塞

接收对称。无缓冲 = 必走路径 1 或 3（要么当面交接，要么阻塞）。

## close 全部规则（边界高频）

| 操作 | 结果 |
|---|---|
| 从已关闭 channel 收 | 取完缓冲后返回**零值+ok=false**，不阻塞 |
| 向已关闭 channel 发 | **panic** |
| close 已关闭/nil channel | **panic** |
| nil channel 收发 | 永久阻塞（select 里可用来禁用分支） |

## select

多个就绪 → **伪随机**选一个；有 `default` 且无就绪 → 走 default（非阻塞）；否则阻塞等任一就绪。

## 证据链接

- 正文：[`05 channel 与 select`](../05-channel-select/README.md)

## 易追问的延伸

- **谁该关 channel？** 发送方、只关一次；多发送方用 `sync.Once`/协调者/context。
- **channel 是无锁的吗？** 不是，每次收发抢 hchan.lock；它图的是封装而非极致性能。
- **channel vs 锁怎么选？** 数据所有权转移/编排用 channel，简单共享状态保护用锁/atomic（[06](../06-sync-memory-model/README.md)），别教条。
- **channel 死锁何时报？** 所有 goroutine 都阻塞时 runtime fatal；部分泄漏不报（靠 pprof）。
- **for range ch？** 迭代到 channel 关闭且取空自动退出。
