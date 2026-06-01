# Redis 为什么单线程还快？io-threads 是什么？

## 一句话回答

「单线程」指**命令执行**单线程:数据全在内存 + 无锁无线程切换 + epoll 多路复用一个线程盯所有连接 → 快。代价是**串行,任何 O(N) 慢命令堵全场**。6.0 的 `io-threads` 只并行**网络 I/O**,命令执行仍单线程。

## 关键点

- **单线程怎么扛高并发连接?** epoll IO 多路复用(Reactor):一个线程把所有连接 fd 注册到 epoll,内核就绪通知 → 分派器 → 处理器。不是一连接一线程。
- **io-threads 让命令并行了吗?**（高频陷阱）**没有**。只把读 socket / 写 socket 多线程化,`execute` 仍单线程。默认关(`io-threads 1`),高网络吞吐才开,且不能 `CONFIG SET`(要改配置重启)。
- **Redis 完全单线程吗?** 不。持久化(fork 子进程)、异步删除(lazyfree 线程)、io-threads 都是额外线程,只有「命令执行」单线程。

## 哪些命令会卡住单线程（O(N)）

`KEYS *`(扫全库,实测 10万 key 4.7ms)、大 `LRANGE 0 -1`、大 `SORT`、大集合 `SINTER/SUNION/SMEMBERS`、大 key `HGETALL`、`DEL` 大 key(用 `UNLINK`)、重 Lua、fork(bgsave/AOF rewrite)。

## 实测证据

- 单线程串行:`DEBUG SLEEP 1` 期间并发 `PING` 等了 0.9s。[sc01](../01-execution-model/scenarios/01-single-thread-blocking.md)
- `KEYS *`(4.7ms,进 slowlog,阻塞)vs `SCAN`(100 次小迭代,不进 slowlog,不阻塞)。[sc02](../01-execution-model/scenarios/02-keys-vs-scan.md)

## 易追问的延伸

- **SCAN 的 COUNT 精确吗?** 不,是建议值(实测 COUNT 1000 单次返回 1004);SCAN 还可能返回重复、rehash 期间弱一致。
- **为什么不用多线程执行命令?** 多线程要加锁,内存操作本来就快,锁开销 + 切换反而拖慢;单线程简单且无并发 bug。
- **CPU 单核打满怎么办?** 命令执行就是单核;靠分片(cluster)横向扩,或开 io-threads 缓解网络瓶颈。

## 证据链接

- 章节原理:[01-execution-model](../01-execution-model/README.md)
- 慢命令排查:[12-production-ops sc03](../12-production-ops/scenarios/03-slowlog-and-latency.md)
