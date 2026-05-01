# 性能面试能力矩阵

> 目标：把路线中的章节映射到真实面试场景，帮助学习者从“我学了哪些章节”转换成“我能处理哪些性能问题”。

## 1. 使用方法

每个场景按同一结构训练：

- 先识别现象。
- 再给出第一轮排查路径。
- 然后说明证据和工具。
- 最后讲清机制、修复、验证和相关章节。

面试中不要只报工具名。好的回答要说明为什么这个工具能验证或推翻某个假设。

## 2. 场景矩阵

| 场景 | 先看什么 | 核心证据 | 需要解释的机制 | 相关章节 |
|------|----------|----------|----------------|----------|
| 接口慢 / P99 抖动 | RED、发布和流量时间线 | P95/P99、Trace、GC pause、连接池 pending | 平均值掩盖长尾、排队放大、下游等待 | 1、3、7、10、14 |
| CPU 高 | load、CPU user/system、热点线程 | `top -H`、`mpstat`、`pidstat`、profile | 用户态计算、系统调用、软中断、调度等待 | 0、2、4/5/6 |
| 内存泄漏 / OOM | RSS、heap、off-heap、容器限制 | heap dump、NMT、pprof heap、tracemalloc、dmesg | heap 与 RSS 区别、GC 可达性、cgroup OOM | 0、4a/4b、5a/5b、6a/6b、12 |
| GC / runtime pause | 延迟尖刺和 pause 时间相关性 | GC log、JFR、runtime metrics | STW、对象晋升、分配速率、collector trade-off | 4a、5a、6a |
| 慢 SQL | DB 耗时和慢查询占比 | slow log、EXPLAIN、rows examined、buffer pool | 索引选择、回表、锁等待、执行计划 | 9a |
| 锁等待 / 死锁 | 线程堆积和事务等待 | InnoDB status、performance_schema、thread dump | 隔离级别、行锁、间隙锁、等待图 | 9a、4b |
| Redis 慢命令 / 大 Key | Redis latency、命中率、内存 | SLOWLOG、`--bigkeys`、INFO MEMORY | 单线程事件循环、数据结构复杂度、内存碎片 | 9b、11 |
| Kafka consumer lag | lag 增长和消费吞吐 | consumer group lag、rebalance、partition skew | 分区、批量、offset、rebalance 风暴 | 9b、10 |
| 连接池耗尽 | pending、timeout、active=max | HikariCP metrics、DB connections、thread dump | 池大小、下游容量、请求排队、泄漏 | 9a、11 |
| 下游超时 / 重试风暴 | Trace 和下游错误率 | retry count、QPS 放大、timeout config | 超时预算、指数退避、抖动、幂等 | 10、13 |
| 网络丢包 / TLS | 重传、握手耗时、连接错误 | tcpdump、Wireshark、ss、mtr | TCP 重传、拥塞控制、TLS 握手和会话复用 | 8、0 |
| K8s throttling / OOMKilled | container CPU/memory 和事件 | cgroup 指标、kubectl describe、cadvisor | CFS quota、request/limit、QoS、OOM killer | 12 |
| 容量规划 / SLO | 当前基线和目标流量 | 压测曲线、error budget、QPS/P99 拐点 | Little 定律、排队论、SLO 与成本权衡 | 1、7、13 |

## 3. 场景训练模板

```text
场景：
现象：
影响面：
第一假设：
需要证据：
使用工具：
排除项：
根因机制：
缓解动作：
长期修复：
验证指标：
相关章节：
```

## 4. 示例：连接池耗尽

### 现象

接口 P99 从 100ms 上升到 3s，错误率开始出现少量 5xx，数据库 CPU 不高。

### 排查路径

1. 先看入口 RED，确认 P99 和错误率变化。
2. 看应用线程和连接池指标：active、idle、pending、timeout。
3. 看数据库连接数是否接近上限。
4. 用 thread dump 确认是否大量线程卡在获取连接。
5. 检查是否存在连接泄漏或下游 SQL 变慢导致连接持有时间变长。

### 证据

- `hikaricp.connections.active` 持续等于 max。
- `hikaricp.connections.pending` 大于 0。
- `hikaricp.connections.timeout` 增长。
- thread dump 中大量线程等待 `getConnection`。

### 机制

连接池耗尽不一定表示池太小。更常见的是查询变慢、事务过长或连接泄漏导致连接持有时间增长。连接持有时间增长会让请求排队，排队会放大 P99。

### 修复和验证

- 短期：降低超时时间，限流或降级非核心请求。
- 中期：修复慢 SQL、连接泄漏或事务边界。
- 长期：给连接池 pending、timeout、active/max 建告警。
- 验证：P99、错误率、pending、timeout 回到基线。

## 5. 面试使用建议

- 每个场景准备一个 3 分钟回答和一个 8 分钟深挖版本。
- 3 分钟版本强调路径和证据。
- 8 分钟版本补机制、权衡、验证、复盘。
