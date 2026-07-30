# 从 access patterns 设计 schema：多租户高写入 record 表

| 结论／证据 | 等级 | 当前含义 |
|---|---|---|
| 由 access pattern、B+ 树与索引维护成本导出的 baseline 设计 | `REASONED` | 已说明推导，未声称本机测量。 |
| baseline 与 over-indexed 的同源资料比较 | `READY_UNRUN` | Task 4 才执行并填入 `EXPLAIN ANALYZE`、大小与写入证据；本文件的假设不改写。 |

## 陌生题目

请为一个**多租户、写入密集**的 record 表设计 schema。它必须同时支持：

1. `id` 精确点查；
2. `tenant_id + status + created_at + id` 稳定倒序翻页；
3. tenant 内 `external_request_id` 唯一；
4. `amount`／`currency`／`status` 有数据库可执行约束；
5. `payload` 是冷字段，不进入主列表索引；
6. `created_at` 到期后可归档；
7. 峰值写入会被每个 secondary index 放大。

不是先罗列「常见索引」，而是从这些读写路径与不变式反推每一个 key；没有命名 access pattern 的索引不成立。

## 先停下来回答

30 秒先给出可验证的 baseline：`id` 用窄的全局唯一 `BIGINT` 主键；tenant 内幂等／唯一性用 `(tenant_id, external_request_id)`；列表按等值前缀再接 `(created_at DESC, id DESC)`，即 `idx_tenant_status_created`。`payload` 不覆盖进列表索引，写入路径只维护必要的两棵 secondary B+ tree。随后用 `EXPLAIN ANALYZE`、`INDEX_LENGTH` 和同源批次的写入时间／redo 证据比较 baseline 与 over-indexed 表，而不是凭印象宣称快多少。

## 澄清问题

- 每个 tenant 的总量、`status` 分布、分页深度、QPS／写峰值各是多少？列表是否一定带 `status`，是否还会按其他条件查询？
- `external_request_id` 的最大长度、字符集与重放语义为何？它是 client idempotency key，还是业务自然编号？
- `created_at` 是业务事件时间还是数据库写入时间？跨时区展示与范围查询的语义是什么？
- legal hold 的来源、审计要求和解除流程为何？到期 archive 是否要能按 tenant／时间回查？
- 是否存在跨 tenant 管理查询、二级索引 DDL 窗口、分区／分片门槛与恢复 RPO/RTO？

未回答前只承诺本文件的两个 query contract；不能把未出现的报表、全文搜索或跨 tenant 筛选偷偷优化进 schema。

## 业务不变式与完成标准

- `id` 全局唯一且不可变；
- `(tenant_id, external_request_id)` 唯一；
- `amount >= 0`；
- `currency` 恰为三个 ASCII 字符；
- `status` 只能为 `0,1,2,3`；
- 分页总序为 `(created_at DESC, id DESC)`；
- retention 不删除 `legal_hold` 记录；
- 没有命名 access pattern 的索引没有正当性。

完成不只是 DDL 能创建：两表必须保留相同业务不变式、同一输入资料返回相同行；代表列表查询满足定义的顺序与 limit。S 级比较仍是 `READY_UNRUN`，Task 4 将把实际 SQL、版本、资料量、`EXPLAIN ANALYZE`、`INDEX_LENGTH`、写入耗时与 redo 观察填为证据。

## 跨章执行链

一次 insert 先改 clustered record，再对每个 secondary key 维护相应 B+ tree，产生 undo、redo 与 binlog；峰值时额外树的页修改也会增加 Buffer Pool 脏页与 checkpoint 压力。查询则从选择性足够的 `(tenant_id, status, created_at, id)` 叶子按所需方向读出，再因投影不含 `payload` 避免为冷 JSON 扩宽索引。

- [ch02 InnoDB storage](../02-innodb-storage/README.md)：clustered／secondary 叶记录、页与 Buffer Pool 的 owner。
- [ch03 indexing](../03-indexing/README.md)：复合索引的等值前缀、排序与 covering 边界的 owner。
- [ch04 execution and Explain](../04-execution-and-explain/README.md)：以 `EXPLAIN ANALYZE` 核验实际访问路径的 owner。
- [ch07 logs and crash safety](../07-logs-and-crashsafe/README.md)：undo、redo、binlog 与写入持久化成本的 owner。
- [ch10 sharding and scaling](../10-sharding-and-scaling/README.md)：retention、分区、分片与扩展边界的 owner。

这里仅组装这些机制来回答设计题，不复制各章的机制正文。

## 成本与瓶颈模型

```text
secondary leaf entry ≈ secondary key bytes + primary-key bytes + record overhead
write work per row ≈ 1 clustered-tree change + N secondary-tree changes + undo + redo + binlog
index decision = named access pattern benefit - write/storage/cache/DDL cost
```

因此选择窄 `BIGINT` primary key：InnoDB secondary leaf 会重复 primary key，key 越宽，每棵 secondary tree 的体积、cache 占用、页分裂与写入成本越大。`payload` 放进列表覆盖索引会把冷 JSON 复制到每个 leaf，既没有现有列表投影的收益，也放大 storage、cache 与写路径；它应在以 `id` 取得需要详情时回表读取。

`uk_tenant_request` 的首要目的不是加速查询，而是让数据库拒绝同 tenant 的重复 external request，保护不变式；查询加速只是 unique key 的附带性质。代表列表中的两个等值条件位于复合 key 左端，随后 `(created_at DESC, id DESC)` 与 order 一致，适合 keyset pagination，避免 offset 越深扫描越多。

## 推荐基准方案

以下形状、名称与 key 顺序是 Task 4 的可直接执行契约：

```sql
CREATE DATABASE IF NOT EXISTS mysql_senior_scenarios
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mysql_senior_scenarios;

CREATE TABLE tenant_record_baseline (
  id                  BIGINT UNSIGNED NOT NULL,
  tenant_id           BIGINT UNSIGNED NOT NULL,
  external_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status              TINYINT UNSIGNED NOT NULL,
  amount              DECIMAL(18,2) NOT NULL,
  currency            CHAR(3) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  created_at          DATETIME(6) NOT NULL,
  updated_at          DATETIME(6) NOT NULL,
  legal_hold          BOOLEAN NOT NULL DEFAULT FALSE,
  payload             JSON NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_tenant_request (tenant_id, external_request_id),
  KEY idx_tenant_status_created (tenant_id, status, created_at DESC, id DESC),
  CONSTRAINT chk_tenant_record_status CHECK (status IN (0,1,2,3)),
  CONSTRAINT chk_tenant_record_amount CHECK (amount >= 0),
  CONSTRAINT chk_tenant_record_currency CHECK (CHAR_LENGTH(currency) = 3)
) ENGINE=InnoDB;
```

```sql
SELECT id, tenant_id, status, amount, currency, created_at
FROM tenant_record_baseline
WHERE id = ?;

SELECT id, status, amount, currency, created_at
FROM tenant_record_baseline
WHERE tenant_id = ?
  AND status = ?
  AND (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

`DECIMAL(18,2)` 表示金额的十进位精确值，避免二进制 floating point 的累计／比较误差。`DATETIME(6)` 保存无时区的微秒业务时间；若需求是瞬间语义与时区转换，应明确以 UTC、应用层转换或 `TIMESTAMP` 的范围／转换语义取舍，不能把两者混为一谈。CHECK 表达式能守住当前行内域值；跨表存在性与级联关系才是 foreign key 的范围，是否采用还要评估写耦合、锁与迁移边界。

## 替代方案与取舍

- **surrogate vs natural key**：保留全局窄 surrogate `id` 作 primary key；`external_request_id` 具有 tenant 局部自然语义，因此由 unique constraint 表达，不让可变／较宽文本成为每个 secondary leaf 的重复 primary key。
- **normalization vs snapshot columns**：稳定、共享的实体可正常化；若 record 必须保留当时的金额／币别／状态语义，可保留受约束 snapshot，不能因为「避免重复」而让历史解释依赖后来改变的外表。
- **cold-column split**：若详情读取也稀少但 JSON 明显拖大热页，可将 `payload` 拆为以 `id` 为主键的一对一表；代价是详情多一次访问，列表仍不需要它。
- **何时不做 covering index**：当前投影的 `amount,currency` 若纳入 idx 会减少回表，却让每次写都维护更宽 leaf；在写密集、列表页小、回表代价可接受且字段将变化时，宁可不覆盖。只有稳定且高频的读路径以测量证明收益超过写／存储成本时才考虑。
- **partitioning**：只有 retention 的时间边界和主查询／清理键也与分区键对齐时才考虑；它不是替代索引，且 unique key、查询裁剪、运维与 archive 流程都要同时满足。tenant 热点、容量与扩容问题越过单机边界时，再依 [ch10 sharding and scaling](../10-sharding-and-scaling/README.md) 评估 shard key，而不是预先分片。

## 执行计划与停止条件

1. 用同一确定性 source rows 建立 baseline 与对照表，先验收约束拒绝非法 `status`、负金额、非三字符 currency 及 tenant 内重复 request。
2. 对代表查询执行 `EXPLAIN ANALYZE`，检查使用的 key、实际 rows／loops、排序与返回顺序；不以 `EXPLAIN` 估算代替实际分析。
3. 对两表逐一记录 `information_schema.TABLES` 的 `INDEX_LENGTH`，并在等价数据与同一 server 条件下记录写入耗时、redo 相关观察与错误。
4. 验证每页以最后 `(created_at,id)` 为 cursor 时没有重复或漏行，并比较两表的结果集。
5. 停止条件：约束、结果等价或排序不成立即停止性能解释；资料量、server 版本、缓存状态、并发、redo／binlog 口径不一致时停止比率比较并重建可比环境。

不能把单次 wall-clock 当成普遍吞吐结论；redo 指标应记录具体取得方法和前后差值。任何 client timeout／断连后的 insert 都先按 `(tenant_id, external_request_id)` 查证，结果是 `UNKNOWN`，不是可盲目重跑的 `FAILED`。

## 缩小规模实验与证据

对照表只多出以下冗余 key；其余 columns 与 required keys 必须与 baseline 相同：

```sql
CREATE TABLE tenant_record_overindexed LIKE tenant_record_baseline;
ALTER TABLE tenant_record_overindexed
  ADD KEY idx_status (status),
  ADD KEY idx_created (created_at),
  ADD KEY idx_tenant_created (tenant_id, created_at, id),
  ADD KEY idx_currency (currency),
  ADD KEY idx_wide_listing
    (tenant_id, status, created_at, id, amount, currency);
```

实验状态：`READY_UNRUN`。在任何运行前，明确假设如下，Task 4 只能填 evidence／结论，不能伪造精确比例：

- 两表保持相同业务不变式，且返回相同行；
- 代表列表查询不应需要冗余单列索引；
- over-indexed 的 `INDEX_LENGTH` 应较大；
- 插入相同 source rows 不应写更少 redo 或更快完成，因为每棵额外 B+ tree 都必须维护；
- 精确比率在 Task 4 前未知，绝不编造。

最小 S 级证据包应保存：MySQL 版本与参数、生成资料与 row count、两张 `SHOW CREATE TABLE`、两条 `EXPLAIN ANALYZE`、分页结果／约束验证、`INDEX_LENGTH`，以及同 source rows 下的写入计时与 redo 前后值。缩小资料量的成功只能标为 `SCALED_REPRODUCED`，不能外推为生产峰值已经证明。

## 生产边界、恢复与回滚

归档／删除以 `created_at` 到期且 `legal_hold = FALSE` 为业务筛选，并采用可审计的 batch identity、watermark、小批次和可重跑 archive destination；先验证已归档的 row count／checksum，再删除原资料。legal hold 记录永不由 retention job 删除。大范围 delete、空间回收和归档实现细节由 [ch10 sharding and scaling](../10-sharding-and-scaling/README.md) 的容量边界及相关 owner 决定，不在此处假装有已运行操作。

新增 index 前先在副本／缩小环境测量，再按线上 DDL 风险、锁等待和磁盘余量制定窗口；若 MySQL 版本和变更方式支持，可先以 invisible index 降低 read-plan 风险后观察，最终再删除冗余 index。回滚不是「立刻删索引」的口号：保留 DDL 变更记录、备份／恢复点与停止阈值；若写放大或复制 lag 超阈值，停止后依已验证路径恢复到前一组索引。schema 变更过程应让应用可同时容忍新旧路径，避免把数据库 DDL 成功误当成业务切换完成。

## 面试输出

**30 秒：**我先确认 tenant 内列表是否固定按 status 与 `(created_at,id)` 倒序、写峰值和保留／legal-hold 规则。baseline 用全局 `BIGINT` 主键，`uk_tenant_request` 守 tenant 幂等唯一性，`idx_tenant_status_created (tenant_id,status,created_at DESC,id DESC)` 服务 keyset pagination；不把冷 `payload` 塞进索引。随后用 `EXPLAIN ANALYZE` 验证访问路径和排序，再以同源数据比较 `INDEX_LENGTH` 与写入／redo，决定是否有任何额外索引值得付出写放大。

**3–5 分钟：**我从 access patterns 与不变式先收敛，再选窄 surrogate primary key，因为每个 secondary leaf 都携带 primary key；列表等值前缀后接排序 key，使倒序 cursor 翻页可顺序读取。写一行是 clustered change 加 N 个 secondary changes，再加 undo、redo、binlog，所以只有 `uk_tenant_request` 和列表索引进入 baseline；`payload` 是冷字段，覆盖会扩宽所有 leaf。金额用 `DECIMAL`、时间先明确 `DATETIME(6)` 与 timestamp 的语义、CHECK 约束行内域值，FK 只在跨表关系值得耦合时使用。接着建 over-indexed 对照，核验相同行、`EXPLAIN ANALYZE`、`INDEX_LENGTH`、同源写入与 redo；预期更大、不会更快，但比例未运行前未知。上线则先做可回滚 migration、监测锁／写放大／replica lag，超阈值停止；archive 以 watermark、legal hold 与可验证归档保证可恢复。
