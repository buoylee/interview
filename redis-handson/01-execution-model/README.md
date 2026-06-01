# 执行模型（单线程 / epoll / io-threads）

## 1. 核心问题

Redis 为什么「单线程」还这么快？单线程怎么扛住成千上万的并发连接？6.0 的 io-threads 又改了什么？以及——**什么命令会把整个 Redis 卡住**？

## 2. 直觉理解

三件事让单线程够快：**数据全在内存**（运算都是内存级）、**命令串行执行**（无锁、无线程切换开销）、**epoll 多路复用**（一个线程用一个 epoll 就能盯住所有连接，谁有数据就处理谁）。

代价就一条:**串行 = 任何一条慢命令会堵住后面所有请求**（sc01 实测：一条 `DEBUG SLEEP 1` 让并发的 `PING` 等了 0.9 秒）。所以「不要用 O(N) 大命令」不是建议，是铁律。

## 3. 原理深入

### 3.1 「单线程」到底指什么
- **命令执行是单线程**——这是对外提供键值服务的主流程（网络读写 + 命令执行）。
- **后台另有线程**:持久化（bgsave/AOF rewrite 由 fork 的子进程）、异步删除（`UNLINK`/惰性释放的 lazyfree 线程）、集群数据同步等。
- **6.0 的 io-threads** 只把**网络 I/O（读 socket、写 socket）**多线程化,**命令执行仍是单线程**。所以 io-threads 不是「命令并行执行」——这是面试最常答错的点。默认 `io-threads 1`（关），高网络吞吐时才开。

### 3.2 epoll / IO 多路复用
Redis 用 epoll 实现 IO 多路复用:把所有连接的 fd 注册到 epoll,内核在「某个 fd 可读/可写」时才通知,事件被放进队列 → **文件事件分派器** → 对应的**事件处理器**（accept / read / write）。一个线程 + 一个 epoll 就能管海量连接,不必一个连接一个线程。这是 Reactor 模式。

### 3.3 一条命令的生命周期
```
客户端连接 → accept
  → 读 socket(read)     ← io-threads 可并行这一步
  → 协议解析(parse RESP)
  → 命令执行(execute)   ← 永远单线程!这里慢就全场慢
  → 写 socket(write)    ← io-threads 可并行这一步
```

### 3.4 什么命令会卡住单线程
- **O(N) 大命令**:`KEYS *`（扫全库，sc02 实测 10 万 key ~4.7ms）、大 `LRANGE 0 -1`、大 `SORT`、大集合 `SINTER/SUNION`、`SMEMBERS` 全量。
- **大 key 操作**:`HGETALL`/`DEL` 一个超大 key（见 12 章，`DEL` 大 key 用 `UNLINK` 异步）。
- **慢 Lua / 大 pipeline 里的重命令**。
- **fork**:bgsave / AOF rewrite 时 fork 子进程，大实例 fork 本身会让主线程短暂卡顿（见 05/12 章）。

## 4. 日常开发应用

- **永远别在线上用 `KEYS`**,用 `SCAN`（游标渐进，sc02 实测 100 次小批迭代走完，不进 slowlog）。
- 别对大 key 做全量操作;删大 key 用 `UNLINK`。
- Lua 脚本别写重循环/大遍历（它也占着单线程）。
- 高并发短连接场景:客户端用连接池;网络吞吐瓶颈时再考虑开 `io-threads`。

## 5. 调优实战

- **某操作让整个实例变慢** → `SLOWLOG GET`（12 章）找那条 O(N) 命令,换 `SCAN`/分页/拆 key。
- **CPU 单核打满、其他核闲** → 正常（命令执行单线程）;若网络是瓶颈（大量小包）可开 `io-threads`（需配置 + 重启,不能 `CONFIG SET`）。
- **周期性卡顿** → 多半是 fork（bgsave 时间点）,见 05/12 章 LATENCY 归因。

## 6. 面试高频考点

- **单线程为什么快?** 内存运算 + 无锁无切换 + epoll 多路复用。
- **单线程怎么处理高并发连接?** epoll IO 多路复用,一个线程盯所有 fd（Reactor）。
- **io-threads 是不是让命令并行执行了?**（陷阱）**不是**,只并行网络读写,命令执行仍单线程。
- **哪些命令危险?** O(N):`KEYS`、大 range、大集合运算、大 key 全量;为什么用 `SCAN` 替 `KEYS`。
- **Redis 完全单线程吗?** 不,持久化/异步删除/io-threads 是额外线程,只有「命令执行」单线程。

## 7. 一句话总结

Redis 「单线程」指**命令执行**单线程（内存运算 + 无锁 + epoll 多路复用 → 快）;io-threads 只并行网络 I/O，命令仍串行。串行的代价是**任何 O(N) 慢命令堵全场**——所以用 `SCAN` 不用 `KEYS`、别碰大 key、Lua 别写重循环。

## Scenarios

- [01 - 单线程串行:慢命令阻塞并发请求](scenarios/01-single-thread-blocking.md)
- [02 - KEYS vs SCAN:阻塞全库扫 vs 渐进迭代](scenarios/02-keys-vs-scan.md)
