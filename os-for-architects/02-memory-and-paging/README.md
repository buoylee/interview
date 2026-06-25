# 02 · 虚存/内存 → 内存预算与缓存层

> 这一章不重教虚存机制，只教一件事：**把"内存原语"翻成"设计期的预算决策"**。机制细节进 `linux-handson/04`，完整容量推导进 `performance-tuning-roadmap`。

---

## 一、盲点

你对内存的反应是**事后的**：`free -m` 剩得不多了？加内存。Swap 用了？内存不够。OOMKill 了？limit 设小了。

架构师在**事前**就把问题挡住：写代码之前先算内存预算（堆 + 堆外 + 栈 × 线程数 + page cache 余量），定 limit 之前先想清楚 page cache 会被算进 cgroup RSS，选服务模型之前先想清楚大 JVM 堆会和 page cache 抢内存。

**同样懂 OOMKill，资深解释它、架构师从设计上规避它。**

---

## 二、原语 → 决策映射表

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| swap / OOMKill | "swap 了 → 内存不够，加内存或调大 limit" | 容器 memory limit = 堆 + 堆外 + 栈 × 线程数 + page cache 余量；**limit 不能等于堆大小**；线上服务关 swap、留余量，避免 OOMKill 而非事后重启 |
| page cache 可回收 | "看 `available`，available 还够就没问题" | 把 page cache 当"免费缓存层"纳入设计；读密集服务（Kafka consumer、日志型数据库）靠 page cache 做第一层加速，**不要主动 drop_caches**；设计时留足 page cache 空间 |
| GC ↔ page fault | "缺页多 / GC 停顿久，调 JVM 参数" | 大堆绑定 NUMA node（`numactl --membind`）；限制堆大小，让 page cache 能和 JVM 共存；服务拆小避免单进程堆过大与 OS cache 抢内存 |
| RSS 只增不降 | "可能有内存泄漏，上 profiler 查" | 设计期定内存预算基线（冷启动 RSS + 业务峰值增量）；监控 RSS 设告警阈值；选有 arena 收缩能力的 allocator（如 tcmalloc/jemalloc）应对 fragmentation |
| mmap / 共享内存 | "mmap 是 IO 加速手段" | 选数据库引擎时看它是否用 mmap（如 LMDB/RocksDB mmap-mode）；mmap 绕过 write buffer 但不绕 page cache，持久化语义要单独分析 |
| OOM score | "OOMKill 杀了关键进程，很惨" | 给关键服务设 `oom_score_adj` 降分（cgroup v1；v2 改用 `memory.oom.group`）；多容器共节点时用 QoS class（Guaranteed/Burstable/BestEffort）决定谁先被杀（容器场景一般不禁 OOMKill，否则进程 hang 更糟） |

---

## 三、定量锚点

**容器内存预算公式（反射式）**：

```
memory limit ≥ 堆（-Xmx / runtime.MemLimit）
             + 堆外（native memory：Netty direct buffer / mmap / JNI）
             + 栈（线程数 × 每线程栈，HotSpot 64 位默认约 1MB，`-Xss` 可调）
             + page cache 余量（读密集服务建议 20–30% limit 预留）
             + 系统开销（OS 自身 ~50–100 MB）
```

**一个具体例子**：Java 服务 `-Xmx 4G`，Netty 堆外 1G，500 线程 × 1M 栈 = 0.5G，page cache 余量 1G，OS ~0.1G → limit **≥ 6.6 GB**，实际拨 7 GB。如果 limit = 4G，第一个 Full GC 触发 native 分配就 OOMKill。

完整的 cgroup memory 核算（`memory.limit_in_bytes` 到 page cache 算法、`memory.memsw.limit_in_bytes`、Kubernetes resource/request 换算）指向：

→ [`../../performance-tuning-roadmap/12-container/01-cgroup-resource.md`](../../performance-tuning-roadmap/12-container/01-cgroup-resource.md)

---

## 四、决策清单 & 反模式

**设计内存分配时问自己**：

- [ ] 这个服务的堆外内存来源有哪些（direct buffer / mmap / native lib）？有没有计入 limit？
- [ ] 线程数峰值是多少？栈内存总量算过吗？
- [ ] page cache 会不会被 cgroup 算进 RSS？如果算进去，还有没有余量？
- [ ] 这台节点上有几个容器？OOM 时谁先被杀的优先级设好了吗？
- [ ] RSS 基线是什么？多久做一次对照，判断是不是在缓慢泄漏？
- [ ] 选的运行时（JVM / Go runtime / CPython）内存模型是什么？arena 会不会导致 RSS 不回收？

**反模式（常见设计错误）**：

| 反模式 | 为什么错 | 正确做法 |
|---|---|---|
| `limit = -Xmx`（limit 等于堆大小） | 堆外 + 栈 + OS 开销没计入，必 OOMKill | limit = 堆 + 堆外 + 栈估算 + page cache 余量 |
| 只看 `free` / `available`，忽略 page cache 被算进 cgroup RSS | cgroup 计 page cache：容器内 `free` 显示足，但 cgroup 已到 limit，触发 OOMKill | 用 `memory.stat`（`cache` 字段）确认 cgroup 真实水位 |
| 关 swap 又不留余量 | 关 swap 正确；但 limit 紧贴实际用量，没有抖动缓冲，一次 Full GC 峰值就 OOMKill | 关 swap + limit 留 20% 余量（抖动缓冲） |
| 多个大堆服务共节点，page cache 被挤死 | 每个服务 `-Xmx` 都申请大堆，OS page cache 空间被压缩，读密集 IO 缺页飙升 | 容量规划时算 `Σ堆 + page cache 底线`，再定节点规格或拆服务 |
| mmap 文件当"省内存"用，不算入预算 | mmap 也吃 RSS（通过 page cache），大文件 mmap 会把 page cache 填满，影响其他服务 | mmap 文件大小纳入内存预算；不适合内存紧张的多租户节点 |

---

## 五、指针

**下指（机制·动手实验）**：

- [`../../linux-handson/04-memory-model/`](../../linux-handson/04-memory-model/) — 虚存机制、RSS vs VSZ vs SHR、page cache 回收机制、`/proc/meminfo` 字段逐行读懂，含 stress-ng 实验

- [`../../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md`](../../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md) — 资深级内存管理机制深度：NUMA、THP、内存压力算法、swap 策略

**横指（深决策）**：

- [`../../performance-tuning-roadmap/11-architecture/01-caching-strategy.md`](../../performance-tuning-roadmap/11-architecture/01-caching-strategy.md) — page cache 作为缓存层的完整架构决策：何时靠 OS cache，何时上应用层缓存，层次设计

- [`../../performance-tuning-roadmap/12-container/01-cgroup-resource.md`](../../performance-tuning-roadmap/12-container/01-cgroup-resource.md) — cgroup memory 核算完整版：`memory.stat`、OOM 触发顺序、Kubernetes QoS class、limit/request 换算

- [`../../system-design/06-存儲選型.md`](../../system-design/06-存儲選型.md) — 存储引擎选型时的内存约束：LSM vs B-Tree 内存占用模型，读放大 vs 写放大对 page cache 的依赖差异

---

## 六、面试转化

**Q1：容器 memory limit 怎么设？**

- **能答**："根据服务实际用多少内存来设，留一点余量。"
- **能设计**：拆分内存构成——`堆（-Xmx）+ 堆外（direct buffer / JNI / mmap）+ 栈（线程数 × 每栈）+ page cache 余量 + OS 开销`，每项逐一估算，limit = 求和 + 20% 缓冲。同时配合 `oom_score_adj` 和 Kubernetes QoS class 决定 OOM 时谁先被杀，保护核心服务。

---

**Q2：page cache 算不算你的内存？**

- **能答**："page cache 是可回收的，不算真实使用，available 够就行。"
- **能设计**：分两层说清楚。**OS 层**：page cache 可被回收，`available` 含可回收 cache，裸机上"够用"判断用 `available` 是对的。**cgroup 层**：默认配置下 page cache 算进 `memory.usage_in_bytes`，容器内看到的 `free` 不代表 cgroup 还有余量；可通过 `memory.stat` 的 `cache` 字段确认真实业务内存水位。架构决策：**读密集服务在 cgroup limit 里主动预留 page cache 空间**（不要把 limit 全给堆），才能让 OS cache 发挥加速作用。

---

**Q3：服务 RSS 持续增长，你设计期怎么防？**

- **能答**："上 profiler 查泄漏。"
- **能设计**：设计期定三件事——① 内存预算基线（冷启动 + 峰值业务增量），② RSS 监控告警（基线 × 1.3 告警，基线 × 1.5 自动重启），③ 选 allocator（tcmalloc/jemalloc arena 收缩 vs glibc malloc fragmentation），让"RSS 只增不降"在 SLA 内可控，而不是等 OOMKill 再应急。
