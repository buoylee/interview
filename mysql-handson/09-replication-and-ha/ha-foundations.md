# MySQL HA 基础：先定义承诺，再讨论产品

高可用的成功边界不是「装了三个数据库」，而是：**在声明的故障模型内，系统只允许一个合法写入方向；客户端收到成功的业务结果不会因切换消失；无法判定的请求必须保留为 UNKNOWN 并可按稳定业务键对账；恢复后还要证明数据收敛。**

这条 invariant 先于产品选择。一个方案若无法回答成功边界、fencing、故障域、RPO／RTO 和恢复入口，就还不是可验证的 HA 方案。

本文不重复复制线程、半同步或 Group Replication 的实现细节。`receiver ACK`、`applier 执行`、`Secondary 可读`是三个不同边界，canonical 说明见 [Chapter 09 的半同步 ACK 边界与 MGR](README.md#35-半同步-lossless-模式)；读己之写策略见 [Chapter 09 §3.9](README.md#39-写后立即读问题读自己的写read-your-writes)。

## 1. 先问：客户端看到成功时，系统承诺了什么

先写业务承诺，再谈节点数：

- **安全性**：同一时刻只有一个被授权的写入方向；失去授权的一侧必须停止写，而不是赌网络会恢复。
- **成功结果**：客户端收到 SUCCESS 后，该 `request_id` 必须能在权威数据中找到。切换不能让已经确认的业务结果消失。
- **未知结果**：断线或超时发生在提交与响应之间时，应用不能从异常类型猜测是否提交；必须用原 `request_id` 查询与重试。
- **收敛**：服务恢复不等于成员已追平。恢复完成要分别验证入口可写、唯一 Primary、已确认 ID 集合和成员数据收敛。

四个容易混淆的边界必须分开：

1. **receive**：副本 receiver 收到复制内容。
2. **ACK**：副本跨过方案定义的确认点，例如持久化 relay log；这不代表已经执行。
3. **apply**：applier 已把事务提交到本地存储引擎。
4. **read visibility**：目标读路径在其一致性规则下已经能看见结果。

因此 durability（成功结果在成员故障后仍存在）与 availability（此刻仍能接受请求）也不是同义词。系统可以为了 durability 等待远端确认，却因失去 quorum 停止写；也可以保持入口存活，却无法提供安全写。

## 2. 三态请求结果：成功、失败、未知

| 客户端观察 | 数据库事实 | 应用动作 |
|---|---|---|
| 收到成功响应 | 事务已跨过方案定义的成功边界 | 记录成功；之后必须能按 `request_id` 找到 |
| 明确得知 SQL 未发送／事务未提交 | 没有业务结果 | 可以用同一 `request_id` 重试 |
| SQL 已发送但响应丢失 | 可能提交，也可能未提交 | 先按 `request_id` 查明；禁止生成新业务键盲重试 |

UNKNOWN 不是数据库的第三种事务状态，而是**应用对数据库事实暂时不知道**。数据库仍只有已提交或未提交；应用层负责稳定 `request_id`、唯一约束、查询与对账，不能要求 Router 替它判断业务幂等。

## 3. 五个平面：应用、路由、控制、数据、存储

| 平面 | 负责什么 | 不负责什么 | 主要验证 |
|---|---|---|---|
| 应用面 | request ID、幂等、三态结果、bounded retry、连接重建、对账 | 不选主，不从超时猜提交结果 | SUCCESS 可查询；UNKNOWN 全部归类 |
| 路由面 | 根据拓扑把**新连接**送到合法端点，提供冗余入口 | 不选主、不复制数据、不迁移既有 TCP／session | 两入口独立；旧连接断开后能重连 |
| 控制面 | 成员资格、健康判断、quorum、选主、拓扑变更、fencing 决策 | 不替应用定义业务成功，不保证每个 Secondary 已 apply | 唯一 Primary；少数派不可写 |
| 数据面 | 执行事务、传播 write-set／日志、排序认证、apply、flow control | 不等于备份历史，也不定义跨地域 DR 决策 | 提交链、队列、冲突、成员追平 |
| 存储面 | redo／binlog／数据页持久化、备份、PITR 与恢复介质 | 副本数量本身不能恢复已复制的误删 | 可恢复备份、重放边界、恢复核对 |

责任链必须完整：控制面授权唯一写入者，数据面执行和复制，存储面保存当前与历史恢复材料，路由面让新连接找到授权端点，应用面处理断线与 UNKNOWN。任何一层都不能用另一层的绿灯代替自己的证明。

## 4. 故障模型：程序、主机、网络、慢节点、存储、入口、故障域

| 故障 | 还能否安全写 | 还能否安全读 | 谁决定 | 谁必须被 fencing | 未知结果来源 | 恢复入口 |
|---|---|---|---|---|---|---|
| MySQL 进程崩溃 | 取决于剩余成员是否有 quorum | 健康成员可按已声明的一致性语义读 | 控制面／成员协议 | 故障进程 | commit 与响应之间断线 | 选主后重连、旧成员 rejoin |
| 整台主机失效 | 同上 | 健康主机上的成员可读 | 控制面／成员协议 | 故障主机 | 客户端连接消失 | 替换主机或恢复成员 |
| 原 Primary 与多数派分区 | 多数派一侧可以 | 多数派可读；少数派旧 Primary 不可信 | quorum | 少数派旧 Primary | 旧连接失效 | 网络恢复后验证并 rejoin |
| 失去 quorum | 不可以 | 只有明确接受陈旧性的读策略才可讨论，不能当强一致读 | 成员协议 | 所有剩余少数派 | 在失去多数派前后的请求 | 恢复多数派，禁止双边强开 |
| 节点很慢 | 通常可以但吞吐受 flow control 约束 | 可读，但慢成员可能落后 | 数据面＋控制面 | 失联后才 fencing | 超时但事务可能完成 | 找出 queue／资源根因 |
| Router 失效 | Cluster 可写但该入口不可达 | 另一 Router／直连健康成员仍可读 | 路由面／应用 | 故障 Router | 连接中断 | 另一个 Router＋应用重连 |
| 存储损坏／误删 | HA 不能恢复历史正确版本 | 可能可读但业务事实已经错误 | 存储／恢复系统 | 损坏副本或在线写入口 | 恢复过程中的业务请求 | 隔离恢复＋Backup／PITR |
| 整个故障域失效 | 本地域不可写；是否可切换取决于另建的 DR | 本地域不可读 | DR 控制面与业务决策 | 原故障域写入口 | 跨域切换窗口内请求 | 本 Lab 不实现；进入 DR Runbook |

「健康成员可读」仍受所声明的 consistency、apply 进度与业务新鲜度约束；它不是允许在 lost-quorum 少数派上继续强一致读。网络分区必须从两边分别回答，不能只写「节点仍 alive」。

故障域也必须具体到共享风险：同一宿主机上的三个容器不是三台主机；同一机架的三台主机不是三个可用区；同一存储阵列上的三个实例也可能只有一个存储故障域。

## 5. Quorum、选主与 fencing

quorum 的作用是让相互隔离的两边不能同时声称拥有写权限。对 `N` 个投票成员，多数派至少为 `floor(N/2)+1`；三成员可在一个成员故障后保留 `2/3` 多数派。

**两节点不是低成本的三节点。** 两节点的多数派也是 2：任一节点或两者之间网络失效都无法仅凭成员视角安全区分「对方死了」与「自己被隔离」，因此不能同时做到自动继续写和避免双主。第三个独立投票者／见证机制可以帮助形成多数派，但它自身的故障域、延迟与能力必须纳入验证；不能把超时猜测当 quorum。

选主只决定谁获得角色；fencing 负责让旧写入者失去能力。安全切换至少需要：

1. 多数派确认旧成员不可继续参与决策。
2. 旧 Primary 在少数派侧拒绝写，或由外部基础设施隔离其写路径。
3. 新 Primary 唯一且可写。
4. Router 刷新拓扑，应用重建连接。
5. UNKNOWN 按 `request_id` 对账，成员随后追平。

Router 只消费控制面产出的拓扑并路由新连接；它既不发起成员协议选举，也不会把旧 session 搬到新 Primary。若旧 Primary 没有被 fencing，增加 Router 不能修复 split-brain 风险。

## 6. 一次提交必须拆开的七个边界

1. Primary execution
2. write-set generation／propagation
3. ordering／certification
4. local commit
5. client success
6. Secondary apply
7. Secondary read visibility

这些边界不能压成「复制成功」四个字。控制协议可能在 ordering／certification 后允许 local commit；客户端响应可能在 commit 后丢失；Secondary 即使收到并 ACK，也可能尚未 apply；即使 apply，具体读路径仍可能受 session、一致性设置或 Router 选择影响。

面试或设计评审时应沿链逐段问：故障落在哪两个边界之间、谁已有持久副本、客户端看到哪一种状态、重试是否复用业务键、读路径要等待哪一个可见性条件。

## 7. RPO／RTO 与分段测量

- `RPO = 故障后缺失且曾被确认成功的业务结果数`；本 Lab 的通过值是 `0`。
- `客户端观测 RTO = 故障窗后首次 SUCCESS 时间 - 故障前最后一次 SUCCESS 时间`。
- `总 RTO = 检测 + view change／选主 + backlog fence + Router topology refresh + 应用重连`。

| 时间点 | 从哪里取证 |
|---|---|
| fault begin／active／end | `evidence/events.jsonl` |
| 最后一次故障前成功 | `ledger-*.jsonl` |
| 检测、选主、可写与 Router ready | `evidence/timeline.jsonl`（由成员状态、直连可写探针与 Router 探针产生） |
| Router 后第一次成功 | 对应 worker ledger |
| 成员全部追平 | verifier 的成员 ID 集比较 |

测量工作表应在演练前填写目标，在演练后填写证据，而不是只写「约 30 秒」：

| 项目 | 目标／预算 | 实测 | 证据文件 | 是否通过／差异解释 |
|---|---:|---:|---|---|
| RPO | 0 个已确认结果 |  |  |  |
| 检测 |  |  |  |  |
| view change／选主 |  |  |  |  |
| backlog fence |  |  |  |  |
| Router topology refresh |  |  |  |  |
| 应用重连 |  |  |  |  |
| 客户端观测 RTO |  |  |  |  |
| 成员完全追平 |  |  |  |  |

服务恢复与成员修复是两个时钟：入口已经恢复 SUCCESS 时，离群成员可能仍在 rejoin／apply。必须分别报告，不能用「Cluster 最终健康」反推业务中断时间。

## 8. HA、Backup／PITR、DR、Read Scaling 的边界

| 能力 | 核心问题 | 典型机制 | 不能替代 |
|---|---|---|---|
| HA | 当前写入节点／进程故障后，如何保持唯一写方向并恢复服务 | 冗余成员、quorum、选主、fencing、入口冗余 | 历史版本恢复、整域灾难恢复 |
| Backup／PITR | 已提交的误删、损坏或勒索后，如何恢复到正确历史点 | 全备／增量备份、binlog、隔离恢复、校验 | 自动故障转移、低 RTO |
| DR | 整个站点／区域失效后，业务在哪里、以什么 RPO／RTO 恢复 | 跨故障域复制、备份复制、DNS／流量切换、DR Runbook | 本地域节点 HA、应用幂等 |
| Read Scaling | 如何增加读吞吐或隔离查询负载 | 只读副本、路由、缓存、读模型 | 写 HA、读新鲜度保证、PITR |

HA 会忠实复制一个合法提交的误删，因此更多在线副本可能更快地得到同一个错误状态。PITR 要从可信备份恢复，再按精确日志边界重放到 destructive transaction 之前；恢复实例必须隔离核对。DR 还要覆盖身份、密钥、网络、应用依赖和流量入口，不是「再放一台 MySQL」。

## 9. 从需求反推方案的决策表

选择流程固定为：**constraints → execution chain → cost／risk → baseline／trade-off → verification／recovery**。先列硬约束，再逐段推演提交和故障链；之后才比较产品。

| 约束／问题 | 必须得到的答案 | 基线选择 | 成本／风险与 trade-off | 验证／恢复 |
|---|---|---|---|---|
| 可接受 RPO | 哪些已确认事务允许丢；成功边界在哪里 | 核心写通常要求 RPO=0，并保留 UNKNOWN 对账 | 更强远端确认增加延迟，跨域 RTT 更明显 | 故障后比较 acknowledged ID 集；缺失数代入 RPO |
| 可接受 RTO | 检测、选主、路由、重连各有多少预算 | 分段预算，不接受单一宣传数字 | 检测太激进会误判；太保守会延长中断 | 连续 workload＋事件时间线；分别量服务恢复和成员追平 |
| 写入一致性 | 分区时哪一侧可写；旧 Primary 如何失权 | 单写方向＋多数派＋fencing | 可用性必须服从避免双写的安全边界 | 主从隔离，证明多数派可写、少数派拒写 |
| 成员数 | 能容忍几个故障；是否有独立第三票 | 三投票成员是常见最小 HA 基线 | 两节点失一即无 quorum；见证也有故障域与运维成本 | 逐个成员／链路故障，检查唯一 Primary 与停写行为 |
| 故障域 | 进程、主机、机架、AZ、region 哪些在范围内 | 成员跨所声明的独立故障域 | 距离扩大 RTT／抖动；共享存储／网络会造成相关故障 | 故障域级演练，不能用容器 kill 证明 AZ 容灾 |
| 读语义 | 是否要求 read-your-writes、强一致或容忍陈旧 | 明确路由与等待屏障；默认不把 ACK 当可读 | 更强读语义可能等待 apply，减少读扩展收益 | 带版本／GTID 的读验证；量 apply backlog |
| 入口可用性 | 单 Router／LB 故障时如何重连 | 至少两个独立入口＋应用连接重建 | 多入口仍不能迁移现存 session | 杀一个入口，验证另一入口与 UNKNOWN 对账 |
| 历史恢复 | 误删、逻辑损坏、勒索的恢复点和保留期 | 定期全备＋连续日志＋隔离 PITR | 存储、演练时间、密钥与保留成本 | 定期 restore drill，逐行核对并设计回迁／回滚 |
| 整域灾难 | 是否允许跨域数据损失；谁批准切换 | 独立 DR 设计与 runbook | 异步跨域有 RPO；同步跨域有延迟／相关性风险 | 区域级演练、流量切换、回切与业务对账 |

若约束只要求开发环境快速重建，就不应伪装成生产 HA；若要求 AZ 故障仍写，则必须把投票成员、入口、存储和应用依赖跨 AZ 放置并实测。产品能力清单只能回答「有什么 primitive」，不能替代端到端责任链。

## 10. 用本专题验证这些结论

下表只把已经完成的演练作为**支持证据**；未被该演练直接注入的生产故障域、跨域 DR 和真实硬件持久性仍是架构推论或待验证项。本机 archive 均被 Git ignore，run ID 是本地索引而不是仓库内可移植的证据包。

| 证据 | 本机 Git-ignored 索引／状态 | 直接支持的边界 | 不证明什么 |
|---|---|---|---|
| Scenario 01 planned switchover | `evidence/runs/planned-switchover/20260726T094213Z/`，PASS | 旧 session 会断；新连接经 Router 找到唯一新 Primary；SUCCESS ID 收敛 | Router 能迁移旧 session；生产网络 RTO |
| Scenario 02 Primary crash | `evidence/runs/primary-crash/20260726T095829Z/`，PASS | crash 后重新选主、应用重连、旧成员 rejoin | 任意双故障仍可写 |
| Scenario 03 Primary partition | `evidence/runs/primary-partition/20260726T100107Z/`，PASS | 少数派旧 Primary 被 fencing，多数派唯一写 | 跨 AZ 网络模型已验证 |
| Scenario 04 quorum loss | `evidence/runs/quorum-loss/20260728T051412Z/`，PASS | `quorum_blocked` 后零 SUCCESS；安全 complete-outage 恢复与 ID 对账 | lost quorum 时陈旧读是强一致读；可以双边强开 |
| Scenario 05 slow member | `evidence/runs/slow-member/20260728T052238Z/`，PASS | applier queue 超阈值；服务时钟与追平时钟分离 | 任意负载下延迟一定上升；真实磁盘瓶颈 |
| Scenario 06 Router failure | `evidence/runs/router-failure/20260728T052430Z/`，PASS | 一个入口失败时另一个入口继续；UNKNOWN 可对账 | Router 负责选主；单个客户端无断线 |
| Scenario 07 member rejoin | `evidence/runs/member-rejoin/20260728T052648Z/`，PASS | 离群成员 rejoin／ONLINE 与客户端恢复是不同边界 | 节点上线即已追平 |
| Scenario 08 HA cannot replace PITR | `evidence/runs/ha-cannot-replace-pitr/20260728T062708Z/`，PASS | 误删传播到全部在线成员；隔离 PITR 按精确位置恢复完整行 | HA 会自动撤销业务误操作；跨文件／跨域恢复 |
| Task 9 complete-outage drill | `evidence/complete-outage/`，PASS；最终 lifecycle `2026-07-26T13:39:50Z`–`13:40:16Z` | GTID seed 方向检查、dry-run 后 actual、唯一可写 Primary、Router rollback probe、逐字节 ID 相等 | `force:true` 安全；这是带独立 run ID 的 Scenario archive |

上述相对路径均以 `mysql-handson/00-lab/ha/` 为根。Scenario 的细节和证据清单见 [InnoDB Cluster 场景目录](innodb-cluster/scenarios/)；复制机制本身仍以 [Chapter 09 README](README.md) 为 canonical 来源。

本地 Compose 只能验证成员协议、路由、客户端重连和数据结果；它不能证明三台容器拥有独立电源、磁盘、交换机或可用区。生产结论必须重新验证故障域、网络 RTT／抖动、存储持久性和备份可恢复性。

## 11. 自测题

1. 两个数据库节点为什么不能在失去任一节点后自动继续写，同时又保证不发生 split-brain？

   <details><summary>答案</summary>

   两节点的多数派是 2；节点无法只靠本地观察区分「对方故障」与「自己被网络隔离」。若两边都自行继续写就会 split-brain，因此失去 quorum 必须停写。负责层是**控制面／成员协议**；若使用第三票，还必须验证其独立故障域。

   </details>

2. 客户端 SQL 已发送后连接断开，为什么不能直接当 FAILURE 并生成新订单号重试？

   <details><summary>答案</summary>

   断线可能发生在 commit 后、响应前，此时数据库已提交而客户端只知道 UNKNOWN。负责层是**应用面**：复用原 `request_id` 查询／幂等重试并对账；路由面只负责重连。

   </details>

3. 副本已经 ACK，为什么仍可能读不到刚写的数据？

   <details><summary>答案</summary>

   ACK 可能只表示 receiver 已接收并持久化复制日志，不表示 applier 已完成，更不表示目标读路径已跨过可见性屏障。负责层依次是**数据面 receive／ACK、Secondary apply 与 read visibility**；应用要选择明确的读一致性策略。

   </details>

4. MySQL Router 是否负责选出新 Primary，并把原连接无缝搬过去？

   <details><summary>答案</summary>

   否。选主与成员资格由**控制面／成员协议**负责；Router 属于**路由面**，读取拓扑并为新连接选择端点。旧 TCP／数据库 session 的断开、连接重建和 bounded retry 由**应用面**负责。

   </details>

5. 三个在线副本为什么不能替代 PITR？

   <details><summary>答案</summary>

   合法提交的误删会由**数据面**复制到所有成员，HA 只保持当前状态可用；恢复历史正确版本由**存储／恢复系统**负责，依赖可信备份、binlog、隔离恢复和核对。HA 与 Backup／PITR 的成功边界不同。

   </details>
