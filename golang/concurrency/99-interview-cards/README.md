# 99 · 面试卡 —— Go 并发高频题速查

> 反向产出：把全课高频考点压成「速答表（背诵用）」+「深题卡（讲清用，每张链回正文做证据）」。
>
> 配套对照：Python 侧同主题见 [`python-concurrency/99-interview-cards/`](../../../python-concurrency/99-interview-cards/README.md)。

## 卡片索引（深题卡）

- [讲一下 GMP / 为什么要 P](q-gmp.md)
- [Go 的抢占式调度怎么实现](q-preemption.md)
- [goroutine 和线程 / 虚拟线程的区别](q-goroutine-vs-thread.md)
- [channel 底层 / 无缓冲 vs 有缓冲 / close 语义](q-channel.md)
- [goroutine 泄漏：原因与排查](q-goroutine-leak.md)
- （对照）[goroutine 和 asyncio 的区别](../../../python-concurrency/99-interview-cards/q-asyncio-vs-goroutine.md) — 复用 Python 课卡片

## 速答表（一行一条，背诵用）

| 问题 | 速答 | 详 |
|---|---|---|
| GMP 是什么 | G=任务、M=OS 线程、P=执行许可证+本地队列；M 占 P 才能跑 G | [01](../01-gmp-scheduler/README.md) |
| 为什么要 P | 给每个执行槽配本地无锁队列，打碎 GM 模型的全局锁 | [01](../01-gmp-scheduler/README.md) |
| GOMAXPROCS 是什么 | 能同时执行 Go 代码的 P 数量，默认=逻辑核数；决定并行度（非 goroutine 上限） | [01](../01-gmp-scheduler/README.md) |
| work stealing | P 本地队列空了，随机偷别的 P 队列的一半 | [01](../01-gmp-scheduler/README.md) |
| M 能超过 GOMAXPROCS 吗 | 能。阻塞在 syscall 的 M 不占 P，runtime 另起 M 接管 P | [03](../03-netpoller-blocking/README.md) |
| 抢占怎么实现 | sysmon 发现 G 跑超 10ms→发 SIGURG→信号处理器→asyncPreempt 保存现场→切回调度器 | [02](../02-preemption/README.md) |
| 协作 vs 抢占 | 让出主动权在代码（await/函数安全点）还是 runtime（信号强制打断） | [02](../02-preemption/README.md) |
| Go 1.14 之前的坑 | 协作式只在函数调用安全点让出，无函数调用的死循环抢不了，会饿死别人/挂起 STW | [02](../02-preemption/README.md) |
| 为什么不用写 await | 让出点由 runtime 抢占式插入，不靠你手写；故无函数染色 | [02](../02-preemption/README.md) |
| time.Sleep 怎么让出 | 不调 OS sleep；gopark+per-P timer 堆注册定时器，M 跑别人，到点 goready 唤醒 | [03](../03-netpoller-blocking/README.md) |
| 网络 I/O 为什么不阻塞线程 | fd 非阻塞+注册 netpoller(epoll)，gopark 挂起 G 释放 M，就绪后唤醒 | [03](../03-netpoller-blocking/README.md) |
| netpoller 是什么 | runtime 内置全局网络轮询器，底层 epoll/kqueue/IOCP；asyncio 事件循环的内核态等价物 | [03](../03-netpoller-blocking/README.md) |
| 文件 I/O 为什么撑 M | 常规文件不能 epoll，走阻塞 syscall+P 交接，每个并发文件操作占一根 M | [03](../03-netpoller-blocking/README.md) |
| goroutine 为什么轻 | 2KB 可增长栈 vs MB 固定；用户态切换纳秒级 vs 内核态微秒级；G 结构体复用 | [00](../00-execution-model/README.md)/[04](../04-goroutine/README.md) |
| 栈怎么增长 | 2KB 起，序言查栈不足→morestack 分配两倍新栈、拷贝、调指针；上限 1GB；GC 可收缩 | [04](../04-goroutine/README.md) |
| goroutine 能开多少 | 几十万量级（1GB/2KB），远超线程几千 | [00](../00-execution-model/README.md) |
| goroutine 泄漏 | 永久挂起（等没对端 channel/漏取消/无超时），占内存 GC 收不了，NumGoroutine 单调涨 | [04](../04-goroutine/README.md) |
| 循环变量捕获 bug | 闭包捕获变量本身非当次值，≤1.21 共享同一个；1.22 改每轮独立；传参最稳 | [04](../04-goroutine/README.md) |
| 无缓冲 vs 有缓冲 channel | 无缓冲=同步握手(同步点)；有缓冲=异步队列(满才阻塞)；≈SynchronousQueue/BlockingQueue | [05](../05-channel-select/README.md) |
| 从关闭的 channel 收发 | 收：取完缓冲后返回零值+ok=false 不阻塞；发：panic；close 已关/nil：panic | [05](../05-channel-select/README.md) |
| nil channel | 收发永久阻塞；select 里置 nil 可动态禁用某分支 | [05](../05-channel-select/README.md) |
| select 怎么选 | 多个就绪伪随机选；有 default 且无就绪走 default(非阻塞)；否则阻塞等任一就绪 | [05](../05-channel-select/README.md) |
| 谁该关 channel | 发送方关、只关一次；接收方不关；多发送方用 Once/协调者/context | [05](../05-channel-select/README.md) |
| Mutex 可重入吗 | 不可重入（递归 Lock 死锁）；不可拷贝（go vet copylocks）；零值可用 | [06](../06-sync-memory-model/README.md) |
| data race vs race condition | 前者=无同步并发访问同址且≥1写(可被-race检测,UB)；后者=更宽的时序逻辑 bug | [06](../06-sync-memory-model/README.md) |
| happens-before 几条 | channel 发送hb接收、Unlock hb 后续Lock、go语句hb启动、Done hb Wait返回；goroutine 结束不hb任何东西 | [06](../06-sync-memory-model/README.md) |
| atomic vs Mutex | 单值原子操作用 atomic(CAS/无锁)；多字段临界区用 Mutex | [06](../06-sync-memory-model/README.md) |
| map 能并发读写吗 | 不能，并发写直接 fatal；用 Mutex+map 或 sync.Map | [06](../06-sync-memory-model/README.md) |
| context 干什么 | 沿链传取消信号+截止时间+请求值；统一控制一棵 goroutine 超时/取消防泄漏 | [07](../07-context/README.md) |
| 取消怎么传播 | 派生成树；cancel 关 done channel(广播)+设Err+递归取消子节点+从父摘除 | [07](../07-context/README.md) |
| 为什么 defer cancel | 释放内部定时器+父的子引用，不调泄漏；go vet lostcancel | [07](../07-context/README.md) |
| 超时会强杀 goroutine 吗 | 不会，协作式——goroutine 必须自己 select <-ctx.Done() | [07](../07-context/README.md) |
| 怎么并发调 N 个下游 | errgroup.WithContext+SetLimit 限并发+g.Go 返回error+g.Wait 收首错并联动取消 | [08](../08-patterns/README.md) |
| errgroup 比 WaitGroup 强在 | 收首个错误+出错自动 cancel 派生 ctx+SetLimit 限并发 | [08](../08-patterns/README.md) |
| 限并发 vs 限速率 | 并发度用信号量(带缓冲channel/SetLimit)；速率用令牌桶 rate.Limiter | [08](../08-patterns/README.md) |
| 重试注意什么 | 只重试可重试错误+指数退避+抖动+操作幂等+等待期间响应 ctx | [08](../08-patterns/README.md) |
| 优雅关闭 | signal.NotifyContext→cancel→srv.Shutdown(timeoutCtx)→WaitGroup 排空 | [08](../08-patterns/README.md) |
| 怎么排查泄漏/死锁/竞态 | pprof goroutine / goroutine?debug=2、trace / go test -race | [09](../09-pitfalls-tuning/README.md) |
| GOMAXPROCS 容器坑 | 默认按宿主机核数非 cgroup 限额→过度调度；automaxprocs 或 Go1.25+ 修 | [09](../09-pitfalls-tuning/README.md) |
