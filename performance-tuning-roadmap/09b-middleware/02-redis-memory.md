# Redis 内存分析与调优

## 为什么需要关注 Redis 内存

Redis 是内存数据库，内存就是它的"硬盘"。内存用完意味着数据被淘汰、写入被拒绝。但 Redis 实际占用的内存往往比存储的数据大得多——**内存碎片、数据结构开销、持久化缓冲区**都在消耗内存。理解 Redis 的内存模型，才能做到精细化管理，让每一字节内存都物尽其用。

---

## 一、INFO MEMORY 解读

`INFO MEMORY` 是 Redis 内存分析的起点，包含了所有关键内存指标。

### 1.1 完整输出解读

```bash
redis-cli INFO memory

# Memory
used_memory:2147483648            # Redis 分配器分配的内存总量（2GB），包含数据 + 内部开销
used_memory_human:2.00G
used_memory_rss:2684354560        # Redis 进程实际占用的物理内存（2.5GB），操作系统视角
used_memory_rss_human:2.50G
used_memory_peak:3221225472       # 历史内存使用峰值（3GB）
used_memory_peak_human:3.00G
used_memory_peak_perc:66.67%      # 当前内存占峰值的比例
used_memory_overhead:536870912    # 内部管理开销（元数据、缓冲区等）
used_memory_startup:1048576       # Redis 启动时占用的基础内存
used_memory_dataset:1610612736    # 纯数据占用 = used_memory - used_memory_overhead
used_memory_dataset_perc:75.00%   # 数据占总内存的比例
total_system_memory:17179869184   # 系统总内存（16GB）
total_system_memory_human:16.00G
used_memory_lua:40960             # Lua 脚本引擎占用的内存
maxmemory:4294967296              # 配置的最大内存限制（4GB）
maxmemory_human:4.00G
maxmemory_policy:allkeys-lru      # 内存淘汰策略
mem_fragmentation_ratio:1.25      # 内存碎片率 = used_memory_rss / used_memory
mem_allocator:jemalloc-5.2.1      # 内存分配器
active_defrag_running:0           # 是否正在进行碎片整理
lazyfree_pending_objects:0        # 等待异步释放的对象数
```

### 1.2 关键指标说明

| 指标 | 含义 | 健康范围 |
|------|------|---------|
| `used_memory` | 分配器分配的总内存 | < maxmemory * 80% |
| `used_memory_rss` | OS 看到的实际物理内存 | 与 used_memory 接近 |
| `used_memory_overhead` | 内部开销（不含数据） | 占比越小越好 |
| `used_memory_dataset_perc` | 数据占比 | > 60% 正常 |
| `mem_fragmentation_ratio` | 碎片率 | 1.0 ~ 1.5 |
| `maxmemory` | 内存上限 | 物理内存的 60%-75% |

### 1.3 数据库级内存分布

```bash
# 查看每个 DB 的 key 数量和过期 key 数量
redis-cli INFO keyspace
# db0:keys=1523456,expires=892341,avg_ttl=3600000
# db1:keys=12345,expires=0,avg_ttl=0

# 查看具体 Key 前缀的内存占用（需要 redis-rdb-tools）
pip install rdbtools python-lzf

# 导出 RDB 并分析
redis-cli BGSAVE
rdb -c memory /var/lib/redis/dump.rdb --bytes 1024 -f /tmp/redis_memory.csv

# 按前缀统计
awk -F',' '{split($1,a,":"); print a[1]":"a[2]}' /tmp/redis_memory.csv | \
  sort | uniq -c | sort -rn | head -20
# 输出：
# 892341  cache:product
# 523456  user:session
# 102345  queue:pending
```

---

## 二、内存碎片

### 2.1 什么是内存碎片

Redis 使用内存分配器（默认 jemalloc）分配内存。当频繁的写入、修改、删除操作导致内存块大小不一致时，就会产生碎片——**分配器分配了内存但无法被有效利用**。

```
mem_fragmentation_ratio = used_memory_rss / used_memory

> 1.5  → 碎片严重，浪费了 50% 以上内存
1.0~1.5 → 正常范围
< 1.0  → 说明 Redis 在使用 Swap，极其危险！
```

### 2.2 碎片产生的常见原因

| 原因 | 说明 |
|------|------|
| 频繁修改不同大小的 value | 旧空间释放后无法被新 value 完全利用 |
| 大量删除操作 | 释放的内存块分散，无法合并 |
| Key 的过期与淘汰 | 频繁的自动清理造成内存空洞 |
| 数据结构编码转换 | ziplist → hashtable 转换导致内存重分配 |

### 2.3 碎片整理

```bash
# Redis 4.0+ 支持在线碎片整理（activedefrag）
redis-cli CONFIG SET activedefrag yes

# 碎片整理参数调优
redis-cli CONFIG SET active-defrag-enabled yes
redis-cli CONFIG SET active-defrag-ignore-bytes 100mb       # 碎片 < 100MB 不触发
redis-cli CONFIG SET active-defrag-threshold-lower 10       # 碎片率 > 10% 才触发
redis-cli CONFIG SET active-defrag-threshold-upper 100      # 碎片率 > 100% 全力整理
redis-cli CONFIG SET active-defrag-cycle-min 1              # 最小 CPU 占比 1%
redis-cli CONFIG SET active-defrag-cycle-max 25             # 最大 CPU 占比 25%
redis-cli CONFIG SET active-defrag-max-scan-fields 1000     # 每次扫描最大字段数

# 查看碎片整理状态
redis-cli INFO memory | grep defrag
# active_defrag_running:1
# active_defrag_hits:12345      # 已整理的分配次数
# active_defrag_misses:678      # 无需整理的分配次数
# active_defrag_key_hits:890    # 已整理的 key 数
# active_defrag_key_misses:34   # 无需整理的 key 数
```

### 2.4 碎片率过低（< 1.0）的处理

```bash
# 碎片率 < 1.0 意味着 Redis 正在使用 Swap，极度危险
# 排查步骤：

# 1. 确认 Swap 使用
redis-cli INFO server | grep process_id
# process_id:12345
cat /proc/12345/smaps | grep -i swap | awk '{sum+=$2} END {print sum/1024 "MB"}'

# 2. 紧急处理
#    - 增加物理内存
#    - 降低 maxmemory
#    - 淘汰非关键数据
#    - 水平扩容（增加节点）

# 3. 关闭 Swap（Redis 服务器不应该使用 Swap）
swapoff -a   # 临时关闭（确保有足够物理内存！）
```

---

## 三、数据结构选择对内存的影响

Redis 内部对不同数据结构有不同的编码方式，选择合适的数据结构能节省大量内存。

### 3.1 编码方式对比

```bash
# 查看 Key 的编码方式
redis-cli OBJECT ENCODING mykey

# String 的编码方式
redis-cli SET num 12345
redis-cli OBJECT ENCODING num
# "int"                        # 整数值用 int 编码，只占 8 字节

redis-cli SET short "hello"
redis-cli OBJECT ENCODING short
# "embstr"                     # <= 44 字节的字符串，紧凑编码

redis-cli SET long "a]very long string that exceeds 44 bytes in length......"
redis-cli OBJECT ENCODING long
# "raw"                        # > 44 字节，普通 SDS 编码
```

### 3.2 Hash vs String：存储对象的内存对比

```bash
# 方案 A：每个字段一个 String Key
SET user:1001:name "张三"
SET user:1001:age "28"
SET user:1001:city "北京"
# 每个 Key 都有 dictEntry（约 56 字节） + SDS 开销
# 3 个字段总开销 ≈ 3 * (56 + 64 + value_size) ≈ 400+ 字节

# 方案 B：一个 Hash Key（推荐）
HSET user:1001 name "张三" age "28" city "北京"
# 当字段数 <= hash-max-ziplist-entries(默认 512) 且
# 每个 value <= hash-max-ziplist-value(默认 64 字节) 时
# 使用 ziplist 编码，内存非常紧凑
# 总开销 ≈ 56 + ziplist_size ≈ 120 字节

redis-cli OBJECT ENCODING user:1001
# "ziplist" (Redis < 7.0) 或 "listpack" (Redis 7.0+)
```

### 3.3 编码转换阈值

| 数据结构 | 紧凑编码 | 转换条件 | 标准编码 |
|---------|---------|---------|---------|
| Hash | ziplist/listpack | 字段数 > `hash-max-ziplist-entries`(512) 或 value > `hash-max-ziplist-value`(64B) | hashtable |
| List | ziplist/listpack | 元素数 > `list-max-ziplist-size`(-2=8KB) | quicklist |
| Set | intset | 元素数 > `set-max-intset-entries`(512) 或含非整数 | hashtable |
| ZSet | ziplist/listpack | 元素数 > `zset-max-ziplist-entries`(128) 或 value > `zset-max-ziplist-value`(64B) | skiplist+hashtable |

### 3.4 内存优化：用 Hash 分桶存储

```python
# 存储 1000 万用户的在线状态
# 方案 A：String（内存大）
# SET online:user:1 "1"
# SET online:user:2 "1"
# ...
# 1000 万个 Key，每个 Key 开销约 70 字节 → 约 700MB

# 方案 B：Hash 分桶（内存小）
# HSET online:bucket:0 "1" "1"    ← user_id=1, bucket=1%1000=0
# HSET online:bucket:0 "1001" "1"
# ...
# 分 10000 个桶，每个桶 1000 个字段
# 每个桶使用 ziplist 编码
# 总内存约 200MB，节省 70%

import redis
r = redis.Redis()
BUCKET_SIZE = 1000

def set_online(user_id):
    bucket = user_id // BUCKET_SIZE
    r.hset(f"online:bucket:{bucket}", str(user_id), "1")

def is_online(user_id):
    bucket = user_id // BUCKET_SIZE
    return r.hexists(f"online:bucket:{bucket}", str(user_id))
```

---

## 四、淘汰策略

当 Redis 使用内存达到 `maxmemory` 时，需要通过淘汰策略决定删除哪些数据。

### 4.1 八种淘汰策略

| 策略 | 作用范围 | 淘汰规则 | 适用场景 |
|------|---------|---------|---------|
| `noeviction` | - | 不淘汰，写入返回 OOM 错误 | 数据不能丢的场景 |
| `volatile-lru` | 设有 TTL 的 Key | 近似 LRU | 缓存 + 持久化混用 |
| `volatile-ttl` | 设有 TTL 的 Key | TTL 最小的优先淘汰 | 临时数据优先清理 |
| `volatile-random` | 设有 TTL 的 Key | 随机淘汰 | 均匀过期的数据 |
| `volatile-lfu` | 设有 TTL 的 Key | 近似 LFU（访问频率最低） | 区分冷热数据 |
| `allkeys-lru` | 所有 Key | 近似 LRU | **通用缓存推荐** |
| `allkeys-random` | 所有 Key | 随机淘汰 | 访问模式均匀 |
| `allkeys-lfu` | 所有 Key | 近似 LFU | 热点数据明显 |

### 4.2 配置与监控

```bash
# 设置淘汰策略
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 设置最大内存
redis-cli CONFIG SET maxmemory 4gb

# LRU/LFU 采样精度（值越大越精确但越慢）
redis-cli CONFIG SET maxmemory-samples 10   # 默认 5，推荐 10

# 监控淘汰情况
redis-cli INFO stats | grep evicted_keys
# evicted_keys:12345    # 累计被淘汰的 key 数量

# 如果 evicted_keys 持续快速增长，说明内存不够用
# 每分钟采集 evicted_keys 并告警
```

### 4.3 LRU vs LFU 选择

```
LRU（Least Recently Used）：淘汰最久未访问的数据
  优点：实现简单，适合时间局部性强的场景
  缺点：可能淘汰"低频但刚被访问过一次"的冷数据，保留"曾经热门但已过时"的数据

LFU（Least Frequently Used）：淘汰访问频率最低的数据
  优点：能更好地识别真正的热数据
  缺点：新写入的 Key 频率低，容易被过早淘汰

推荐：
  - 通用缓存 → allkeys-lru
  - 有明显热点 → allkeys-lfu
  - 缓存+持久化混用 → volatile-lru（只淘汰设了 TTL 的 Key）
```

---

## 五、持久化对性能的影响

### 5.1 RDB 快照

```bash
# RDB 持久化原理：fork 子进程 → 子进程写 RDB 文件
# 性能影响集中在 fork 阶段

# 查看 fork 耗时
redis-cli INFO persistence
# rdb_last_bgsave_status:ok
# rdb_last_bgsave_time_sec:3            # 上次 BGSAVE 耗时 3 秒
# latest_fork_usec:156000               # 上次 fork 耗时 156ms

# fork 耗时与内存大小关系（经验值）
# 1GB 内存 → fork 约 20ms
# 10GB 内存 → fork 约 200ms
# 25GB 内存 → fork 约 500ms
# fork 期间 Redis 会短暂阻塞所有请求！

# RDB 配置（redis.conf）
save 900 1          # 900 秒内有 1 个 key 变化则触发
save 300 10         # 300 秒内有 10 个 key 变化则触发
save 60 10000       # 60 秒内有 10000 个 key 变化则触发

# 生产建议：大实例（>10GB）降低 RDB 频率或关闭
save ""             # 关闭 RDB 自动触发
```

### 5.2 AOF 持久化

```bash
# AOF 持久化原理：记录每个写命令 → 定期重写压缩

# AOF 刷盘策略
appendfsync always      # 每次写命令都 fsync → 最安全，性能最差（QPS 降低 90%+）
appendfsync everysec    # 每秒 fsync → 推荐，最多丢 1 秒数据
appendfsync no          # 不主动 fsync → 性能最好，由 OS 决定何时刷盘

# AOF 重写（rewrite）
# 当 AOF 文件过大时，Redis 会触发重写：fork 子进程，生成精简的 AOF
auto-aof-rewrite-percentage 100    # AOF 文件比上次重写后增长 100% 触发
auto-aof-rewrite-min-size 64mb     # AOF 文件至少达到 64MB 才触发

# AOF 重写期间的性能影响
# 1. fork 阻塞（同 RDB）
# 2. 重写期间的写命令需要同时写入 AOF 缓冲区和重写缓冲区
# 3. 大量磁盘 I/O

# 查看 AOF 状态
redis-cli INFO persistence | grep aof
# aof_enabled:1
# aof_rewrite_in_progress:0
# aof_last_rewrite_time_sec:5
# aof_current_size:1073741824        # 当前 AOF 文件 1GB
# aof_base_size:536870912            # 上次重写后的大小 512MB
```

### 5.3 混合持久化（Redis 4.0+）

```bash
# 混合持久化 = RDB 格式的全量数据 + AOF 格式的增量数据
# 兼顾 RDB 的快速加载和 AOF 的数据安全

# 开启混合持久化
aof-use-rdb-preamble yes    # redis.conf

# AOF 重写时：
# 前半部分是 RDB 格式（二进制，加载快）
# 后半部分是 AOF 格式（文本，增量命令）

# 生产推荐配置：
# 混合持久化 + appendfsync everysec
```

### 5.4 持久化性能优化

| 优化项 | 配置 | 说明 |
|-------|------|------|
| 关闭 RDB 自动触发 | `save ""` | 大实例避免频繁 fork |
| AOF 刷盘策略 | `appendfsync everysec` | 性能与安全折衷 |
| 混合持久化 | `aof-use-rdb-preamble yes` | 加快重启速度 |
| 限制重写频率 | `auto-aof-rewrite-percentage 200` | 降低重写频率 |
| 禁止 fork 期间 fsync | `no-appendfsync-on-rewrite yes` | 减少 fork 期间的 I/O |
| 控制实例大小 | maxmemory < 10GB | 减少 fork 耗时 |

---

## 六、内存优化实践

### 6.1 压缩列表（ziplist/listpack）阈值调优

```bash
# 增大 ziplist 阈值，让更多 Hash/ZSet 使用紧凑编码
# 注意：阈值越大，ziplist 越长，O(N) 遍历越慢（但通常可接受）

# Hash
hash-max-ziplist-entries 512     # 默认 512，可适当增大到 1024
hash-max-ziplist-value 64        # 默认 64 字节

# ZSet
zset-max-ziplist-entries 128     # 默认 128
zset-max-ziplist-value 64        # 默认 64 字节

# List（quicklist 中每个节点的 ziplist 大小限制）
list-max-ziplist-size -2         # -2 表示每个 ziplist 节点最大 8KB

# Set（intset 阈值）
set-max-intset-entries 512       # 默认 512

# 验证编码变化
redis-cli HSET test f1 v1 f2 v2
redis-cli OBJECT ENCODING test
# "ziplist"

# 添加 513 个字段后
redis-cli OBJECT ENCODING test
# "hashtable"    ← 编码转换，内存使用陡增
```

### 6.2 共享对象池

```bash
# Redis 内部维护了 0~9999 的整数共享对象池
# 当多个 Key 的 value 是 0~9999 的整数时，共享同一个对象，节省内存

# 验证共享
redis-cli SET a 100
redis-cli SET b 100
redis-cli DEBUG OBJECT a
# Value at:0x7f1234567890 refcount:2147483647 encoding:int ...
# refcount 非常大，说明是共享对象

# 注意：开启 maxmemory 淘汰策略后（LRU/LFU），
# 需要记录每个 Key 的访问信息，共享对象池会被禁用
# 这是正常行为，不需要特别处理
```

### 6.3 embstr 编码优化

```bash
# String 值 <= 44 字节时使用 embstr 编码
# embstr 将 RedisObject 和 SDS 分配在一块连续内存中
# 优势：一次内存分配、缓存友好

# 实际优化：控制 value 长度
# 不好：JSON 格式存储（冗余字段名）
SET user:1001 '{"name":"张三","age":28,"city":"北京","level":"vip"}'
# 长度 > 44 字节，使用 raw 编码

# 好：用分隔符存储（节省空间）
SET user:1001 "张三|28|北京|vip"
# 长度 < 44 字节，使用 embstr 编码
# 但牺牲了可读性，需要应用层解析

# 更好的方案：用 Hash（ziplist 编码更省内存）
HSET user:1001 name "张三" age 28 city "北京" level "vip"
```

### 6.4 Key 名称优化

```bash
# Key 名称本身也占内存，数据量大时不可忽视

# 不好：冗余前缀
SET user:session:detail:info:1001 "..."
# Key 长度 33 字节

# 好：简短但可识别
SET us:1001 "..."
# Key 长度 7 字节

# 1000 万 Key 时差距：
# 33 字节 * 10M = 330MB
#  7 字节 * 10M = 70MB
# 节省 260MB

# 权衡：可读性 vs 内存
# 推荐：适度缩写，保持团队约定的前缀规范
# 如 u: (user), s: (session), c: (cache), q: (queue)
```

---

## 七、内存分析工具

### 7.1 redis-rdb-tools

```bash
# 安装
pip install rdbtools python-lzf

# 导出内存分析报告
rdb -c memory /var/lib/redis/dump.rdb -f /tmp/memory.csv

# CSV 格式：database, type, key, size_in_bytes, encoding, num_elements, len_largest_element
# 0,hash,user:1001,120,ziplist,4,8
# 0,string,cache:product:9527,5242880,raw,1,5242880

# 按类型统计
awk -F',' 'NR>1 {sum[$2]+=$4; count[$2]++} END {for(t in sum) printf "%s: %d keys, %.2fMB\n", t, count[t], sum[t]/1024/1024}' /tmp/memory.csv
# hash: 523456 keys, 128.50MB
# string: 892341 keys, 1024.00MB
# set: 12345 keys, 256.00MB

# 找出 Top 100 大 Key
sort -t',' -k4 -rn /tmp/memory.csv | head -100
```

### 7.2 Redis Memory Analyzer（RMA）

```bash
# 安装
pip install rma

# 分析
rma -f /var/lib/redis/dump.rdb

# 输出摘要：
# Summary
# -------
# Total keys: 1523456
# Total memory: 2147483648 bytes (2.00 GB)
# Total key name memory: 45703680 bytes (43.58 MB)
#
# Top key patterns:
# Pattern          Count      Memory      Avg Size
# cache:product:*  892341     1073741824  1203 bytes
# user:session:*   523456     536870912   1025 bytes
# queue:pending:*  102345     536870912   5243 bytes   ← 大 value，需关注
```

### 7.3 在线内存分析（不依赖 RDB）

```bash
# MEMORY DOCTOR（Redis 4.0+）
redis-cli MEMORY DOCTOR
# 输出诊断建议：
# Sam, I have a few concerns:
# * Peak memory: In the past this instance used more than 150% the memory
#   it is currently using. Consider setting maxmemory.
# * High fragmentation: The instance has memory fragmentation greater than
#   1.4. Consider using MEMORY PURGE or restarting.

# MEMORY PURGE（释放 jemalloc 的空闲页）
redis-cli MEMORY PURGE
# OK

# MEMORY STATS（详细内存统计）
redis-cli MEMORY STATS
# 1) "peak.allocated"
# 2) (integer) 3221225472
# 3) "total.allocated"
# 4) (integer) 2147483648
# ...
# 23) "keys.count"
# 24) (integer) 1523456
# 25) "keys.bytes-per-key"
# 26) (integer) 1409         # 平均每个 key 1409 字节
```

---

## 八、内存调优 Checklist

| 检查项 | 命令/方法 | 健康标准 | 优化手段 |
|-------|----------|---------|---------|
| 内存使用率 | `INFO memory` → `used_memory` / `maxmemory` | < 80% | 扩容或数据瘦身 |
| 碎片率 | `mem_fragmentation_ratio` | 1.0 ~ 1.5 | 开启 activedefrag |
| Swap 使用 | 碎片率 < 1.0 或 `/proc/<pid>/smaps` | 0 | 增加物理内存 |
| 淘汰率 | `INFO stats` → `evicted_keys` 增速 | 低增长 | 扩容或优化数据 |
| 数据编码 | `OBJECT ENCODING key` | ziplist/intset 占比高 | 调整阈值参数 |
| Key 大小 | `--bigkeys` / `MEMORY USAGE` | 无 > 1MB 的 Key | 拆分大 Key |
| 持久化影响 | `latest_fork_usec` | < 100ms | 控制实例大小 < 10GB |
| 数据结构选择 | 代码审查 | Hash 替代多个 String | 重构存储模型 |
| Key 名称长度 | 抽样统计 | 合理缩写 | 制定命名规范 |
| 过期清理 | `expired_keys` 增速 | 稳定 | 分散过期时间 |

### 内存优化优先级

```
1. 选择合适的淘汰策略（不花钱的优化）
2. 优化数据结构（Hash 替代 String，利用 ziplist）
3. 处理大 Key（拆分或压缩）
4. 控制碎片率（开启 activedefrag）
5. 调整持久化策略（减少 fork 开销）
6. 水平扩容（增加节点，分散数据）
```
