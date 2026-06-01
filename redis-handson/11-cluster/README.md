# Cluster（分片集群）

## 1. 核心问题

单机/主从都是「一份全量数据」,内存和写吞吐受单机上限。Cluster 把数据**分片**到多个 master,横向扩展。本章讲清:16384 槽怎么分、key 怎么定位(CRC16)、客户端怎么路由(MOVED/ASK)、multi-key 的限制(hash tag)、扩缩容(reshard)、以及故障转移(gossip + 投票)。

## 2. 直觉理解

- **16384 个槽(slot)**:Cluster 把整个 key 空间切成 16384 份,每个 master 负责一段连续的槽。`key 属于哪个槽 = CRC16(key) % 16384`。
- **客户端路由**:你连任意节点发命令,如果这个 key 的槽不归它管,它回一个 **MOVED**(带正确节点地址)让你重连;cluster 模式客户端(`redis-cli -c`)自动跟随重定向(sc01)。
- **multi-key 限制**:一条命令涉及多个 key 时,这些 key **必须在同一个槽**,否则报 CROSSSLOT;用 **hash tag `{}`** 强制同槽(sc02)。
- **高可用**:每个 master 配从;master 挂了,gossip 检测 + 其他 master 投票,把它的从升为新 master。

## 3. 原理深入

### 3.1 槽与 CRC16
- `CLUSTER KEYSLOT key` 看 key 落哪个槽。sc01 实测:`foo`→12182、`bar`→5061。
- 算法:`HASH_SLOT = CRC16(key) mod 16384`;若 key 含 `{...}`,只对 `{}` 内的子串算(hash tag)。
- 集群健康需 **16384 槽全部被分配**(`cluster_slots_assigned:16384`、`cluster_state:ok`);有槽没人管 → `cluster_state:fail`、拒绝服务那些槽。

### 3.2 MOVED vs ASK 重定向
- **MOVED**:key 的槽**永久**归别的节点 → 客户端应更新本地「槽→节点」路由表并重连。sc01 实测:非 `-c` 模式 `SET foo` 在错节点上返回 `MOVED 12182 <ip>:6379`;`-c` 模式自动重定向后 OK。
- **ASK**:槽正在**迁移中**(reshard),这个 key 暂时在目标节点 → 客户端**这一次**去目标节点(先发 `ASKING`),但**不更新**路由表(迁移没完)。
- 区别:MOVED=永久换家(更路由表),ASK=临时借住(只这次)。

### 3.3 multi-key 与 hash tag
- 跨槽的 multi-key 命令(`MSET`/`MGET`/`SINTERSTORE`…)直接报 **CROSSSLOT**。sc02 实测:`MSET a b c`(不同槽)→ `CROSSSLOT`。
- **hash tag**:key 里加 `{x}`,只用 `{}` 内的部分算槽 → 想放一起的 key 用相同 tag 即同槽。sc02 实测:`{u}:a` 和 `{u}:b` 都落槽 11826,`MSET` 成功。
- 用途:把「需要一起操作」的 key(同一用户的多个 key)用 `{userid}` 绑到同槽。

### 3.4 扩缩容(reshard)
- 加节点:`cluster meet` 让新节点入群 → `reshard` 把部分槽(及其 key)迁到新节点。迁移期间该槽的 key 用 **ASK** 重定向。
- 减节点:先把它的槽 reshard 走(清空),再 `cluster forget` 移除。
- 槽迁移是「一个槽一个槽、一个 key 一个 key」迁的,在线进行。

### 3.5 gossip 与故障转移
- 节点间用 **gossip 协议**(meet/ping/pong)互相交换状态;每个 master 和所有其他 master 互连。
- **故障检测**:某 master `cluster-node-timeout` 内 ping 不通另一个 → 标记 **pfail(主观下线)**;通过 gossip 传播,**过半持槽 master 都认为某节点 pfail → 标记 fail(客观下线)**。
- **故障转移**:下线 master 的从发起选举,**持槽 master 过半投票**(每个配置纪元每 master 一票)→ 票数过半的从 `REPLICAOF NO ONE` 升主、接管槽。
- **实测注记**:本极简 compose lab 里,killed master 后能观察到 `Marking node ... as failing (quorum reached)`、`cluster state: fail`(检测到了),但副本的**自动选举升主在 60s 内未稳定完成**——dockerized 极简集群对 `cluster-announce-ip`/时序较敏感(无独立持久卷、IP 动态)。**自动故障转移的可工作实证见哨兵章 [07 sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md) / [10 章](../10-replication-sentinel/README.md)**(机制类似:检测下线 → 选主 → 接管)。

## 4. 日常开发应用

- 数据量/写吞吐超单机 → cluster 分片;客户端用支持 cluster 的库(自动管理 MOVED 路由表)。
- 需要 multi-key 原子(事务/Lua/MSET)的 key,用 **hash tag** 绑同槽(如 `order:{uid}`、`cart:{uid}`)。
- 别滥用 hash tag 把太多 key 绑一个 tag → 数据倾斜(某槽/节点过载,呼应热 key)。

## 5. 调优实战

- **CROSSSLOT 报错** → 涉及的 key 不同槽;加 hash tag 或拆成单 key 操作。
- **客户端频繁 MOVED** → 路由表过期(刚 reshard 过);好的客户端会自动刷新 `CLUSTER SLOTS`。
- **数据/请求倾斜** → hash tag 用得太粗,或某些大 key/热 key 集中(12 章);调整 tag 粒度。
- **cluster_state:fail** → 有槽没 master 管(节点全挂且无从接管);恢复节点或重分配槽。

## 6. 面试高频考点

- **为什么 16384 槽?** 折中:槽位图(每节点维护)大小可控(16384 bit=2KB),又够细分。
- **key 怎么定位?** `CRC16(key) % 16384` → 槽 → 负责该槽的 master(sc01)。
- **MOVED vs ASK?** MOVED 永久(更路由表),ASK 迁移中临时(发 ASKING、不更表)。
- **multi-key 怎么办?** 必须同槽;hash tag `{}` 绑同槽(sc02 CROSSSLOT)。
- **cluster 故障转移?** gossip 检测 pfail → 过半 master 标记 fail → 从被过半 master 投票选为新主。
- **cluster 支持事务/多 key 吗?** 仅限同槽的 key。

## 7. 一句话总结

Cluster 把 key 空间分成 **16384 槽**(`CRC16%16384`)分给多 master 横向扩展;客户端靠 **MOVED**(永久)/**ASK**(迁移中)重定向路由;multi-key 必须**同槽**,用 **hash tag `{}`** 绑定;高可用靠 gossip 检测 + 过半 master 投票把从升主。

## Scenarios

- [01 - 槽 / CRC16 / MOVED 重定向](scenarios/01-slot-moved-redirect.md)
- [02 - hash tag:multi-key 跨槽 CROSSSLOT 与同槽](scenarios/02-hash-tag-crossslot.md)
- 故障转移机制见 §3.5；自动切换实证见 [07 章 sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)
