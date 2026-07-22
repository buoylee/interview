# 设计：MySQL → Canal → Elasticsearch 最终一致性实战

> 日期：2026-07-22
>
> 状态：已确认，待实现计划
>
> 项目位置：mysql-es-cdc-handson/
>
> 目标读者：希望真正验证 CDC、派生索引与最终一致性边界的后端工程师和架构师

## 1. 结论与术语

Canal 应称为基于 MySQL binlog 的 CDC（Change Data Capture，变更数据捕获）工具或增量数据订阅组件。若把 canal-server、消息队列、Adapter 和下游消费端作为一个整体，也可以称为 CDC 数据同步链路，但不能把 Canal 单独称为“最终一致性方案”。

本项目要用实验回答两个问题：

1. Canal 提供什么能力，它对最终一致性有什么作用？
2. 在 MySQL 是事实源、Elasticsearch 是派生搜索索引时，还必须加入什么能力，整个系统才能在明确前提下达到可验证的最终一致性？

核心结论固定如下：

- Canal 负责发现并传递 MySQL 已提交的行变更，是最终一致性链路的重要输入层。
- Canal 本身不理解业务投影，不负责 Elasticsearch 写入的逐项成功、幂等、乱序防护、死信、对账、修复或全量重建。
- “MySQL 与 Elasticsearch 最终一致”是端到端系统属性，不是某一个中间件的产品属性。
- 本项目不宣称 exactly-once。目标语义是 at-least-once 传递，加确定性投影、版本防护、可重试消费、DLQ、独立对账和可重建索引。
- 当 binlog 或 Kafka 日志出现不可回放缺口时，增量链路不能自行补回历史事件；系统必须显式进入 REBUILD_REQUIRED，并从 MySQL 当前事实状态重建 Elasticsearch。若缺口位于 Canal 的 MySQL 源位点，还必须先有证据地重建一个有效 Canal cursor，不能只重建 ES。

## 2. 背景与问题边界

常见方案把 MySQL binlog 接到 Canal，再把变更写入 Elasticsearch，随后用“基于 binlog，所以不会漏数据”描述可靠性。这个说法缺少端到端边界：

- MySQL 事务提交后，Canal 是否已经收到、解析并持久化了位置？
- Canal 把事件交给 Kafka 或 Adapter 后，何时确认成功？
- Elasticsearch Bulk 请求整体返回成功时，是否检查了每一个 item？
- 消费者在 Elasticsearch 成功之后、Kafka offset 提交之前崩溃，重复事件是否安全？
- 同一商品的旧事件晚到，是否会覆盖新状态？
- 映射错误进入 DLQ 后，系统是否仍然错误地显示为“健康”？
- binlog 被清理、Kafka retention 过期或者 offset 丢失后，如何恢复？
- Elasticsearch 被人工改坏，谁能独立发现并修复？
- 全量初始化期间仍有增量写入时，如何保证扫描和切换之间没有数据缺口？

本项目不靠配置截图回答这些问题，而是建立一套故障驱动、可重复执行、产出机器可读证据的本地实验。

## 3. 一致性合同

### 3.1 事实源与派生状态

- MySQL 是唯一事实源（source of truth）。
- Elasticsearch 是可丢弃、可重建的派生读模型（derived projection）。
- product-service 只提交 MySQL 事务，不在请求事务中双写 Elasticsearch 或 Kafka。
- 搜索结果的正确性由 MySQL 当前事实状态和确定性投影函数定义，不能反过来以 Elasticsearch 内容定义事实。

### 3.2 精确定义

设：

- W 是一个已提交的 MySQL 源水位。
- S(W) 是该水位对应的 MySQL 一致性快照。
- P 是独立定义的商品搜索投影函数。
- E(t) 是时刻 t 可由搜索别名读取的 Elasticsearch 状态。

在写入停止于 W，且第 3.4 节的恢复前提成立时，系统必须存在有限时刻 T，使得所有 t ≥ T：

1. 每个有效商品在 E(t) 中恰好有一个文档；
2. 文档的全部受管字段和值等于 P(S(W))；
3. 文档的 source_revision 等于 MySQL 对应商品的 revision；
4. 已失效商品不会由搜索别名返回；
5. 不存在 MySQL 中没有对应有效商品的额外可搜索文档；
6. 不存在未解决 DLQ，且对账差异为零。

持续写入时不要求 Elasticsearch 与不可冻结的“此刻 MySQL”瞬时相等。系统改为按水位验收：对于任意已经封闭的 W，只要日志仍可回放，所有不晚于 W 的商品 revision 最终都必须被应用或被更新的 revision 安全覆盖。

### 3.3 删除的精确定义

在线增量链路使用逻辑 tombstone 文档：

- searchable=false；
- 保留 product_id 与最新 source_revision；
- 搜索别名只暴露 searchable=true 的文档；
- 晚到旧事件不能重新激活已经删除的商品。

全量重建也必须为每个已失效商品写入精确的 tombstone，不允许为了压缩索引而物理省略。原因是 Elasticsearch 删除文档后只在有限窗口内保留删除版本；若版本信息已经回收，延迟更久的旧写可能把已经删除的商品重新创建出来。Elasticsearch Delete API 说明该窗口由 index.gc_deletes 控制，默认值为 60 秒：<https://www.elastic.co/guide/en/elasticsearch/reference/8.19/docs-delete.html>

因此所有可服务的索引 generation 都采用唯一删除模式：

- 失效商品必须存在 searchable=false 的 tombstone；
- tombstone 的 source_revision 必须等于 MySQL 最新 revision；
- tombstone 与普通文档使用相同的 external version 防护；
- 搜索别名只暴露 searchable=true 的文档。

这会保留额外文档，但删除版本屏障不再依赖 index.gc_deletes 等有限保留窗口，验证器也只有一个明确的预期物理状态。

### 3.4 最终一致性成立的恢复前提

只有同时满足以下条件，系统才可以声称会收敛：

- MySQL 已提交事务的 binlog 在 Canal 成功发布前没有被清理。
- Kafka 记录在消费者、DLQ replay 或 rebuild replayer 完成前仍在 retention 范围内。
- MySQL 使用 ROW binlog，并在兼容性测试中固定和验证 binlog_row_image 等关键配置。
- Canal partitionHash 使用 product_id 计算目标 Kafka partition，因而同一商品落入同一 partition；消费者不依赖 Kafka record key。
- 投影逻辑对同一 MySQL 状态是确定性的。
- Elasticsearch、Kafka、Canal 和消费者最终恢复可用。
- 数据或 mapping 错误可以被修正，DLQ 会被处理，而不是永久搁置。
- 一旦检测到不可回放缺口，运维流程会执行全量重建。
- MySQL 当前事实状态本身仍完整可读。

如果这些条件不成立，系统必须显示 DEGRADED 或 REBUILD_REQUIRED，不得继续显示 HEALTHY，也不得声称自动保证最终一致。

全量重建可以恢复“当前搜索投影”，但不能凭空恢复已经从 binlog 和 Kafka 同时消失的历史事件。本项目验证的是当前状态收敛，不是永久事件历史。

## 4. Canal 能力边界

### 4.1 Canal 提供的能力

本项目使用 Canal 的以下能力：

- 以 MySQL replica 类似的方式订阅 binlog；
- 解析已经写入 binlog 的数据库行变更；
- 保存和恢复增量消费位置；
- 将变更通过 Canal 协议或 Kafka 等目标向下游发布；
- 在第一阶段通过 Canal Adapter 把简单表映射到独立 Elasticsearch 索引，建立黑盒基线。

Canal 因此直接降低了“应用事务提交后，如何可靠发现数据变化”的难度。它避免在 product-service 中加入 MySQL 与 Elasticsearch 双写，但这只是端到端最终一致性的一个环节。

### 4.2 Canal 不提供的端到端保证

不能仅凭“使用 Canal”推导出以下结论：

- 每个业务聚合都能被正确投影为 Elasticsearch 文档；
- 多表状态能按业务一致性快照组合；
- Elasticsearch Bulk 的每个 item 都成功；
- 重复投递、消费者崩溃和旧事件晚到不会破坏新状态；
- poison message 一定会被修复；
- binlog 或 Kafka retention 缺口会自动恢复；
- 人工改坏 Elasticsearch 后一定能被发现；
- 全量扫描与增量切换之间没有缺口；
- 业务查询具备 read-your-writes；
- 链路具备 exactly-once。

M1 必须把 Canal Adapter 当作黑盒，通过故障实验测量它的确认、重试、重启恢复和 Bulk 部分失败行为。设计不得先把未经实验的行为写成保证。

## 5. 总体架构

~~~text
write request
    |
    v
product-service ---> MySQL ---> binlog ---> canal-server
                       |                       |
                       |                       +-- M1: Canal ES Adapter
                       |                       |        |
                       |                       |        v
                       |                       |   products_adapter_v1
                       |                       |
                       |                       +-- M2+: Kafka
                       |                                |
                       |                                v
                       |                     search-sync-consumer
                       |                                |
                       |                                v
                       |                         products_v2 / next generation
                       |
                       +------> consistency-verifier <------ Elasticsearch
                                      |
                                      +------> repair / rebuild

fault runner + Toxiproxy
    |
    +-- network faults, process crashes, corruptions, offset and retention faults
~~~

### 5.1 组件职责

product-service：

- 对外提供商品、分类、库存和删除操作；
- 在一个 MySQL 事务内修改业务表并递增受影响商品的 revision；
- 不调用 Elasticsearch，不直接发布 Kafka 事件。

canal-server：

- 捕获和解析 MySQL binlog；
- M1 把事件交给 Adapter；
- M2 以后把 revision 变化发布到 Kafka。

Canal ES Adapter：

- 只用于 M1 的简单单表同步基线；
- 写入独立索引 products_adapter_v1；
- 不作为最终可靠消费者的实现。

Kafka：

- 解耦 Canal 与自定义消费者；
- 提供可回放的增量日志；
- 以 product_id 分区，保留同一商品的顺序；
- retention 是恢复能力的一部分，而不只是容量配置。

search-sync-consumer：

- 收到 revision 事件后，从 MySQL 重新读取该商品的当前完整状态；
- 生成确定性 Elasticsearch 文档；
- 负责逐项成功检查、revision 防护、重试、DLQ、offset 和 replay；
- 不把原始多表 CDC 事件直接拼接成可能处于不同事务时刻的半成品文档。

consistency-verifier：

- 独立读取 MySQL 和 Elasticsearch；
- 独立实现预期投影，不复用消费者的 mapping 代码；
- 检出 missing、extra、modified、stale revision 和 deletion mismatch；
- 执行受控 repair，或者把系统升级为 REBUILD_REQUIRED。

fault runner：

- 用显式 failpoint 控制消费者崩溃窗口；
- 用 Toxiproxy 控制网络中断、超时和恢复；
- 控制 Canal、Kafka、消费者和 Elasticsearch 的停止与重启；
- 生成场景输入、故障和恢复证据。

### 5.2 为什么消费者重新读取 MySQL

搜索文档来自 products、categories、inventory 等多张表。若消费者只拼接原始 CDC 行事件，就必须自行解决跨表顺序、事务边界、缓存丢失和重放问题。

本项目把 CDC 事件当作“这个 product_id 需要刷新”的失效信号。消费者收到信号后，在一个 MySQL 一致性读事务中读取当前完整状态。这样允许旧事件直接刷新到最新状态，也使投影函数只面对一个确定的源快照。

代价是增加 MySQL 回读压力。它是本实验为了优先验证正确性而接受的取舍，不代表所有生产规模都应使用相同方案。

## 6. 数据模型与版本协议

### 6.1 MySQL 表

products：

- id
- sku
- name
- description
- category_id
- price_cents
- status
- updated_at

categories：

- id
- name
- updated_at

inventory：

- product_id
- available_quantity
- reserved_quantity
- updated_at

product_search_revision：

- product_id，主键
- revision，针对单个商品单调递增
- active
- updated_at

所有影响搜索文档的正常业务事务都必须在同一个 MySQL 事务中递增对应 product_id 的 revision：

- 商品字段变化：递增该商品；
- 库存变化：递增该商品；
- 分类改名：递增该分类下所有受影响商品；
- 删除：采用软删除，设置 active=false 并递增 revision。

直接绕过 product-service 修改业务表属于契约外写入。周期性对账仍应发现这种漂移，但正常增量延迟 SLO 不对这种写入负责。

### 6.2 Kafka 事件

Canal 1.1.8 使用 product_id 作为 partition hash 输入，但发送 ProducerRecord 时 record key 为 null。消费者必须从 Canal flat message 的 data 中解析 product_id，不能读取 record.key 作为业务 ID。官方实现位置：<https://github.com/alibaba/canal/blob/canal-1.1.8/connector/kafka-connector/src/main/java/com/alibaba/otter/canal/connector/kafka/producer/CanalKafkaProducer.java#L200-L266>

最小事件语义包含：

- product_id；
- revision；
- active；
- MySQL 事务或 binlog 诊断元数据；
- schema_version；
- event_id，能够稳定映射到 topic、partition、offset 或源位置。

消费者不相信事件中携带的业务字段是最终文档，只用它定位需要重新读取的商品和诊断源水位。

### 6.3 Elasticsearch 文档

文档 id 固定为 product_id，受管字段包括：

- product_id
- sku
- name
- description
- category_id
- category_name
- price_cents
- available_quantity
- searchable
- source_revision
- source_updated_at

消费者使用 source_revision 作为 Elasticsearch external version 或等价的条件更新依据：

- 新 revision 可以覆盖旧 revision；
- 相同 revision 的重复写必须是幂等的；
- 更旧 revision 只能被记录为 stale attempt，不能覆盖新状态；
- 409 等预期版本冲突要和真正写入失败分开计数。

投影必须是确定性的。同一个 MySQL 一致性状态和相同 schema_version 必须生成逐字段相同的文档。

## 7. 里程碑

### M0：可复现实验环境

交付：

- Docker Compose 启动 MySQL、Canal、Kafka、Elasticsearch 和 Toxiproxy；
- product-service、consistency-verifier 基础骨架；
- 固定版本和 image digest 的 manifest；
- deterministic seed data；
- 健康检查和一条端到端 smoke test；
- make up、make down、make verify 等统一入口。

验收：

- 新环境可以从零启动；
- 所有依赖都达到 readiness，而不只是进程存活；
- 版本与关键配置被记录；
- smoke test 可以证明 MySQL binlog 已被 Canal 读取并到达预期下游。

### M1：Canal ES Adapter 黑盒基线

交付：

- products 单表基础字段同步到 products_adapter_v1；
- insert、update、delete 基础实验；
- Canal、Adapter、Elasticsearch 重启实验；
- Adapter Bulk 部分失败和 mapping 错误实验；
- 对实际确认与恢复行为的证据记录。

目标不是证明 Adapter 足够，而是精确回答它能覆盖哪些场景、在哪个边界停止。

### M2：Canal → Kafka → 自定义消费者

交付：

- Canal 把 product_search_revision 变化发布到 Kafka；
- search-sync-consumer 按 product_id 消费；
- 消费者在 MySQL 一致性读中重新加载多表当前状态；
- 文档写入 products_v2；
- 搜索别名指向自定义消费者索引。

验收覆盖商品、库存、分类、删除四种变化，且最终文档逐字段等于独立计算的预期投影。

### M3：可靠消费语义

交付：

- Elasticsearch 成功后才推进 Kafka offset；
- 检查每个 Bulk item，而非只检查 HTTP 状态；
- 每 partition 只提交连续且已经 settled 的 offset 前缀；
- product_id 分区和 revision 防护；
- 有界重试与退避；
- DLQ、DLQ replay 和确定性去重 key；
- 显式 failpoint。

M3 完成后可以安全处理重复投递、正常重启、主要消费者崩溃窗口和可修复 poison message。

### M4：独立对账与修复

交付：

- 扫描 MySQL 计算 ExpectedDocument；
- 检出 missing、extra、modified、stale revision 和 deletion mismatch；
- 小范围差异可按 product_id 修复；
- 未解决 DLQ、Canal 离线超过 binlog retention、Kafka offset 超出 retention 时升级状态；
- 对账与消费者投影实现相互独立。

若消费者 mapping 本身有 bug，不能让复用同一 mapping 的“验证器”给出伪 PASS。

### M5：全量初始化、重建与无缺口切换

交付：

- 新建带 generation 的物理索引；
- 从 MySQL 一致性快照批量构建；
- 从保守 Kafka 起始 offsets 追增量；
- revision 防护；
- 对账通过后原子切换 alias；
- 失败时保持旧索引可服务并支持重试。

M5 的基线算法见第 10 节。

### M6：统一故障矩阵与最终结论

交付：

- 所有场景统一通过 make scenario SCENARIO=... 执行；
- 每个场景生成机器可读 evidence；
- 自动区分 PASS、DEGRADED 和 REBUILD_REQUIRED；
- README 给出“Canal 能保证什么、不能保证什么、加入哪些能力后系统为何会收敛”的证据化结论。

只有在一致性前提、恢复动作和验证证据都明确时，场景才可以标记 PASS。

## 8. 消费确认与崩溃语义

### 8.1 单批处理边界

正常处理顺序固定为：

~~~text
Kafka poll
  -> 按 product_id 读取 MySQL 当前一致性状态
  -> 生成确定性文档
  -> Elasticsearch Bulk
  -> 检查每一个 Bulk item
  -> 成功，或把失败记录可靠写入 DLQ
  -> 仅提交各 partition 已连续 settled 的 offset 前缀
~~~

settled 只表示原事件已经写入 Elasticsearch，或已经可靠进入 DLQ。进入 DLQ 不等于数据已经一致：

- 只要 DLQ 未解决，系统至少是 DEGRADED；
- 最终场景不得在 unresolved DLQ > 0 时 PASS；
- DLQ replay 成功或对账修复后，才可以恢复 HEALTHY。

DLQ key 使用原 topic-partition-offset 或等价稳定标识。若进程在 DLQ 发布后、offset 提交前崩溃，重复 DLQ 记录必须可识别，不能形成无法判断的多条独立故障。

### 8.2 崩溃窗口

| 崩溃位置 | 恢复后的预期行为 |
|---|---|
| Elasticsearch 写入前 | Kafka 事件重放，正常处理 |
| Elasticsearch 成功后、offset 提交前 | 事件重放；相同 revision 幂等 |
| Bulk 部分成功后 | 逐 item 处理；失败 item 未 settled 前不得越过其 offset |
| DLQ 发布前 | offset 不提交，原事件重放 |
| DLQ 发布后、offset 提交前 | DLQ 可能重复，但稳定 key 可去重；原事件最终 settled |
| offset 提交后 | 对应事件必须已经成功写入或可靠进入 DLQ |

任何实现只要出现“先提交 offset，后确认 Elasticsearch 或 DLQ”的路径，就违反本设计。

## 9. 错误分类与恢复策略

| 类别 | 示例 | 自动动作 | 最终状态 |
|---|---|---|---|
| transient | Elasticsearch timeout、Kafka 短暂不可用 | 有界重试、退避、保持 offset | CATCHING_UP，恢复后可回 HEALTHY |
| replay | 消费者在 offset 提交前崩溃 | 重放、revision 幂等 | 可自动恢复 |
| data / poison | mapping 冲突、无法解析的记录 | 有界重试后 DLQ | DEGRADED，处理 DLQ 后恢复 |
| stale event | 旧 revision 晚到 | 拒绝覆盖、记录 metric | 若无其他差异仍可 HEALTHY |
| log gap | binlog 被清理、Kafka retention 过期、offset 丢失 | 禁止静默跳过；Kafka 缺口要求全量重建，MySQL binlog 缺口还要求先重建有效 Canal cursor | REBUILD_REQUIRED |
| projection drift | 消费者 bug、人工修改 ES | 独立对账，按范围 repair 或 rebuild | DEGRADED 或 REBUILD_REQUIRED |
| permanent outage | 依赖永久不可用 | 持续暴露失败，不承诺收敛 | DEGRADED |
| source loss | MySQL 事实数据损坏或丢失 | 超出本项目恢复能力 | 无法保证 |

重试必须分类，不能对所有错误无限重试。mapping 错误永久占住 partition 和静默跳过错误同样不可接受。

## 10. 全量重建与增量无缺口切换

### 10.1 构建阶段

1. 创建新物理索引 products_v{generation}，写入 schema_version、deletion_mode=tombstone 和构建 manifest。
2. 在打开 MySQL 扫描快照之前，记录 revision topic 每个 partition 的当前 Kafka end offset，记为 O_start。
3. 打开 MySQL 一致性快照，扫描全部商品 revision；active 商品写入完整搜索文档，inactive 商品写入带 snapshot revision 的 tombstone。
4. 启动 shadow replayer，从每个 partition 的 O_start 开始向新索引追增量。
5. shadow replayer 对每条事件重新读取 MySQL 当前状态，并使用 revision 防护。扫描与重放的重复是安全的。

O_start 必须早于数据库快照建立。这样：

- O_start 之前已提交的事务会出现在 MySQL 快照中；
- O_start 之后提交或才发布到 Kafka 的事务会被 shadow replayer 覆盖；
- 两边同时覆盖的事务只是幂等重复；
- Kafka retention 必须覆盖从 O_start 到追平的完整窗口。

### 10.2 切换阶段

为了让最终逐字段验证面对一个封闭水位，M5 基线采用短暂写入闸门，而不是假装可以在无限并发写入下比较两个移动目标：

1. 临时关闭 product-service 的新写入入口。
2. 在 MySQL 写入 rebuild barrier，并等待 Canal 已经发布通过该源位置。
3. 记录每个 Kafka partition 的 O_barrier。
4. 等待旧索引消费者和 shadow replayer 都处理到各自的 O_barrier。
5. 暂停两条消费写入，运行全量独立对账。
6. 对账、DLQ 和状态检查全部通过后，原子切换搜索 alias 到新索引。
7. 将 shadow replayer 提升为主消费者，恢复消费并重新开放业务写入。

若第 5 或第 6 步失败：

- alias 保持指向旧索引；
- 恢复旧消费者；
- 记录失败证据；
- 修复或丢弃新 generation 后重新构建。

该算法保证无数据缺口，但不宣称零写入暂停。零暂停切换可作为后续扩展，不进入 v1 验收。

### 10.3 重建能恢复什么

重建能够恢复：

- binlog 或 Kafka 增量缺口后的当前 Elasticsearch 投影；
- 不兼容 mapping 变更；
- 大范围消费者投影 bug；
- Elasticsearch 物理损坏或人工漂移。

重建不能恢复：

- MySQL 已经不存在的历史版本；
- 未保存到任何事实源的事件语义；
- MySQL 本身损坏造成的事实丢失。

### 10.4 MySQL binlog 缺口后的 Canal cursor

全量重建只修复 Elasticsearch 当前投影，不会自动修复仍指向已清理 binlog 的 Canal 源位点。确认 MySQL binlog 缺口后，恢复流程必须：

1. 关闭并持有业务写闸门，排空进行中的事实变更；
2. 保存旧 Canal destination cursor、哈希和缺失 file/position 证据；
3. 记录当前有效 MySQL file/position/GTID；
4. 以一次性显式恢复模式让 Canal 落到当前有效位点，再恢复普通模式重启；
5. 通过每个 Kafka partition 的 barrier 证明新 cursor 后的首批事件可达；
6. 从新的 `O_start` 执行一致性快照、重叠 replay、验证与 alias 切换；
7. 只在新 generation PASS 后清除 LOG_GAP。

任何静默删除整个 Canal 数据目录、长期打开自动跳到最新位点，或只完成 ES rebuild 就恢复 HEALTHY 的做法都不满足本设计。

## 11. 测试设计

### 11.1 单元测试

- 多表状态到 Elasticsearch 文档的投影；
- revision 单调性和旧 revision 判定；
- soft delete 与 tombstone；
- Canal product_id partitionHash、null record key 与同商品同 partition 策略；
- 错误分类、retry budget 与 DLQ；
- 对账 diff 分类和 repair 决策；
- 所有 generation 的 tombstone 预期状态。

消费者和验证器各自拥有独立测试样本，避免共享实现把同一个 bug 同时固化。

### 11.2 组件集成测试

- product-service 与真实 MySQL 事务；
- Canal 与实际 MySQL binlog 配置；
- 消费者与真实 Kafka、MySQL、Elasticsearch；
- Elasticsearch Bulk 部分失败；
- Kafka offset 提交和重放；
- mapping 与 Canal 事件 schema 兼容；
- 对账器对 missing、extra、modified 和 stale 文档的识别。

Mock 只用于精确制造很难由外部依赖稳定触发的代码分支，不能替代关键中间件的真实行为验证。

### 11.3 端到端故障矩阵

必须覆盖：

1. Canal 正常重启；
2. Canal 离线但仍在 binlog retention 内；
3. Canal 离线超过 binlog retention；
4. Kafka 暂时不可用；
5. 消费 offset 已超出 Kafka retention；
6. 消费者在 Elasticsearch 前崩溃；
7. 消费者在 Elasticsearch 成功后、offset 提交前崩溃；
8. Elasticsearch Bulk 部分 item 失败；
9. 重复事件；
10. 旧 revision 晚到；
11. mapping conflict；
12. Elasticsearch 文档被人工删除或修改；
13. 分类改名影响多个商品；
14. 删除后旧事件重放；
15. 全量扫描期间持续写入；
16. rebuild 中途崩溃并重启；
17. 消费者 mapping bug 导致系统性错误；
18. DLQ replay 成功与再次失败。

### 11.4 确定性 failpoint

消费者至少提供：

- AFTER_ES_BULK_SUCCESS
- BEFORE_KAFKA_OFFSET_COMMIT
- AFTER_DLQ_PUBLISH
- BEFORE_ALIAS_SWITCH

进程崩溃窗口必须由 failpoint 精确触发。网络错误由 Toxiproxy 控制。场景不得依赖随机 kill 或 sleep 10 一类时间猜测。

## 12. 场景协议与证据

统一入口：

- make up
- make verify
- make scenario SCENARIO={scenario-id}
- make evidence

每个场景固定执行：

1. 加载 deterministic seed；
2. 提交已记录的业务写入；
3. 注入指定故障；
4. 观察预期中间状态；
5. 恢复依赖或执行声明的恢复动作；
6. 等待明确条件成立，例如源水位通过、Kafka lag 为零；
7. 运行独立对账；
8. 检查 unresolved DLQ 和 pipeline state；
9. 写出 PASS、DEGRADED 或 REBUILD_REQUIRED。

禁止用固定 sleep 代替条件轮询。

每个场景生成：

~~~text
evidence/{scenario-id}/
├── manifest.json
├── input-commands.json
├── fault.json
├── mysql-snapshot.json
├── es-snapshot.json
├── kafka-offsets.json
├── differences.json
├── recovery-actions.json
└── result.json
~~~

result.json 至少记录：

- scenario_id；
- dependency_versions；
- consistency_preconditions；
- source_watermark；
- applied_offsets；
- unresolved_dlq_count；
- exact_diff_count；
- expected_pipeline_state；
- observed_pipeline_state；
- recovery_action；
- result；
- started_at 与 finished_at。

场景只有同时满足以下条件才能 PASS：

- 目标水位已经通过；
- Kafka lag 已按场景定义归零；
- unresolved DLQ 为零；
- 独立对账逐文档、逐字段、逐 revision 完全相等；
- 所有失效商品都有最新 revision 的 tombstone，且不会由搜索别名返回；
- 实际恢复路径符合场景预期；
- 没有通过跳过事件、删除证据或手工篡改预期结果制造成功。

## 13. 可观测性与状态机

### 13.1 Pipeline 状态

系统对外暴露以下状态：

- HEALTHY：前提成立，lag 在阈值内，无 unresolved DLQ，最近一次对账通过；
- CATCHING_UP：日志完整，正在追赶，可预期自动恢复；
- DEGRADED：存在 poison message、对账差异或永久性依赖问题，需要处理；
- REBUILD_REQUIRED：确认或无法排除日志缺口，增量恢复不再可信；
- REBUILDING：正在构建并验证新索引 generation。

“进程存活”不等于 HEALTHY。

### 13.2 指标

至少包括：

- Canal source position 或 heartbeat 水位；
- Canal → Kafka 发布延迟；
- Kafka consumer lag；
- Elasticsearch 写入延迟和 Bulk item failure；
- retry 次数与 retry exhausted；
- unresolved DLQ；
- stale revision attempt；
- reconciliation missing、extra、modified 和 stale 数；
- 最近一次完整验证时间和结果；
- 当前索引 generation；
- 当前 pipeline state。

指标标签禁止使用 product_id 等高基数字段。单商品诊断信息进入结构化日志和 evidence。

Spring Boot 服务使用 Micrometer 与 Actuator。Prometheus 和 Grafana 作为可选 Compose profile，不阻塞最小实验路径。

## 14. 技术基线

| 组件 | v1 基线 | 说明 |
|---|---:|---|
| Java | 21 LTS | 两个应用与验证器统一运行时 |
| Spring Boot | 4.1.0 | 应用框架基线 |
| Build | Maven Wrapper | 多模块可复现构建 |
| Canal | 1.1.8 | canal-server 与 M1 Adapter 基线 |
| MySQL | 8.4.8 LTS | 事实源 |
| Kafka | 4.1.2 | KRaft 单节点本地实验 |
| Elasticsearch | 8.17.0 | 与 Canal ES8 路径的实验兼容基线 |
| Toxiproxy | 2.12.0 | 可控网络故障 |
| Orchestration | Docker Compose v2 | 本地单机，不使用 Kubernetes |

版本来源：

- Canal releases：<https://github.com/alibaba/canal/releases>
- MySQL 8.4 release notes：<https://dev.mysql.com/doc/relnotes/mysql/8.4/en/>
- Kafka downloads：<https://kafka.apache.org/community/downloads/>
- Spring Boot：<https://spring.io/projects/spring-boot>
- Elasticsearch 8.17.0 image：<https://www.docker.elastic.co/r/elasticsearch/elasticsearch:8.17.0>
- Toxiproxy releases：<https://github.com/Shopify/toxiproxy/releases>

所有容器镜像都必须固定明确 tag，并在 M0 smoke test 通过后记录 digest；禁止使用 latest。若实现时发现组合不兼容，必须先用最小兼容性实验和证据更新本设计，不能静默漂移版本。

## 15. 目录与交付物

~~~text
mysql-es-cdc-handson/
├── README.md
├── Makefile
├── pom.xml
├── mvnw
├── mvnw.cmd
├── versions.env
├── docs/
│   ├── 00-goals-and-invariants.md
│   ├── 01-canal-boundary.md
│   ├── 02-reliable-pipeline.md
│   ├── 03-failure-model.md
│   ├── 04-reconciliation.md
│   └── 05-rebuild-runbook.md
├── product-service/
├── search-sync-consumer/
├── consistency-verifier/
├── infra/
│   ├── compose.yaml
│   ├── mysql/
│   ├── canal/
│   ├── canal-adapter/
│   ├── kafka/
│   ├── elasticsearch/
│   ├── toxiproxy/
│   └── observability/
├── scenarios/
│   ├── definitions/
│   ├── scripts/
│   └── failpoints/
├── tests/
│   ├── integration/
│   └── end-to-end/
└── evidence/
~~~

README 是从结论到实验的总入口；docs 解释机制和运行手册；scenarios 定义故障；evidence 保存机器可读结果。正文中的结论必须能回链到相应场景，而不是只给出概念描述。

项目完成骨架后，在以下既有文档加入入口链接并纠正过度保证式表述：

- elasticsearch/roadmap/09-data-sync/09-data-sync.md
- financial-consistency/05-patterns/06-transactional-message-cdc.md

对账原理继续复用 financial-consistency/07-reconciliation/README.md，不复制维护一份竞争版本。

## 16. 非目标

v1 不包含：

- Kubernetes、跨地域部署和生产级多副本高可用；
- 完整 TLS、IAM、secret rotation 与企业安全基线；
- 大规模吞吐压测、容量规划和生产 SLO 承诺；
- Debezium 对比实现；
- 通用 CDC 框架；
- exactly-once 声明；
- 搜索相关性调优或前端搜索页面；
- 把 Elasticsearch 当作写入事实源；
- 金融账务、余额或结算领域；
- 零写入暂停的索引切换；
- tombstone 的物理压缩或删除。未来若引入，必须另行设计不依赖 Elasticsearch 有限 delete-version 保留期的旧事件防复活屏障。

这些边界不削弱实验的正确性目标；它们防止项目在验证端到端一致性之前扩张成完整数据平台。

## 17. 完成定义

项目只有满足以下条件才算完成：

1. M0–M6 均有可执行入口和文档；
2. Canal Adapter 与自定义消费者的能力边界都有故障证据；
3. 消费者不存在先提交 offset、后确认 Elasticsearch 或 DLQ 的路径；
4. 重复、乱序、崩溃和 Bulk 部分失败均有确定性测试；
5. 独立验证器能发现故意植入的消费者 mapping bug；
6. 可回放故障能自动追平，不可回放缺口会明确进入 REBUILD_REQUIRED；
7. 全量重建在扫描期间有并发写入时仍能通过无缺口切换；
8. 每个最终场景都产出规定的 evidence；
9. make verify 在全新 checkout 上可重复通过；
10. README 用实验结果准确回答 Canal 提供什么、缺少什么，以及整个系统在什么前提下才会最终一致。

## 18. 实施约束

- 所有实现工作在分支 codex/mysql-es-cdc-handson 的隔离 worktree 中进行。
- 先完成书面实现计划，再按里程碑交付；本设计确认不等于授权跳过计划直接铺开全部代码。
- 每个里程碑必须先建立可失败的验收测试或场景，再实现让其通过。
- 不得为了让演示变绿而降低一致性定义、删掉故障场景或复用消费者代码实现验证器。
- 版本、语义或范围发生实质变化时，先更新本设计并重新确认。
