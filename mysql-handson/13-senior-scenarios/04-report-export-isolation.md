# 大型报表与导出：如何不拖垮 OLTP

> **状态：`SCALED_REPRODUCED (S=10000 orders, 30000 items)`**
>
> 2026-08-03 已在 Docker 内完成 10,000 orders／30,000 items 缩小实验；结果只代表该本机容器环境，不代表千万行或生产容量。

## 先给结论

大型报表不是“把 SQL 优化快一点”就结束。资深工程师会依次处理：

```text
定义一致性与时效要求
→ 决定数据放在哪里读
→ 固定 query shape 与唯一顺序
→ 选择 buffered 或 streaming/chunked
→ 给 OLTP 设置资源与停止边界
→ 验证结果完整性
→ 设计重试、checkpoint 与发布
```

一般建议：

- 允许分钟级陈旧：优先 dedicated reporting replica 或 analytical store。
- 必须读 Primary：使用 async job、确定性顺序、bounded batch 和明确的 OLTP budget。
- 要求精确 as-of：使用真正的 snapshot/version source；不要把一个 high watermark 当成万能快照。
- 输出很大：数据库读取与用户下载分开。先生成 immutable artifact，再让用户下载。

## 1. 先定义问题

面试时不要一上来回答“加索引”或“放从库”。先确认：

1. 结果是同步 HTTP response，还是可以做 async job？
2. 需要同一个精确时间点的 values，还是只要求固定 membership？
3. 可以接受多少 replica lag／staleness？
4. 预计多少 rows、多少 bytes、多久执行一次？
5. 导出期间 source rows 会 INSERT、UPDATE 或 DELETE 吗？
6. OLTP 可以接受多少 latency/error 增量？
7. consumer 很慢或断线时，数据库 cursor 可以保持多久？
8. 失败后从头重跑，还是从 checkpoint 恢复？

这八个答案决定的是架构，不只是 SQL 写法。

### 三种正确性要求

| 要求 | 真正需要的边界 | 常见错误 |
|---|---|---|
| 固定查询上界 | immutable、insertion-monotone cursor key | 认为任意 `MAX(id)` 都能阻止 backdated insert |
| 固定 membership | materialized ID set、snapshot 或 versioned source | 每批开新 transaction，却假设成员不会改变 |
| 固定 values | 同一 MVCC snapshot、数据库 snapshot 或历史版本 | 只保存最后一个 cursor，忽略已存在 row 的 update/delete |

如果后来插入的 row 可以带着更早的 `created_at`，即使它小于第一次记录的 high watermark，resume 时仍可能进入新的 ReadView。watermark 是 query upper bound，不自动等于完整 snapshot。

## 2. 数据与索引

假设导出 order 与 item 明细：

```sql
CREATE TABLE report_order (
  id         BIGINT PRIMARY KEY,
  created_at DATETIME(6) NOT NULL,
  status     VARCHAR(16) NOT NULL,
  KEY idx_created_id (created_at, id)
) ENGINE=InnoDB;

CREATE TABLE report_item (
  id         BIGINT PRIMARY KEY,
  order_id   BIGINT NOT NULL,
  qty        INT NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  KEY idx_order_id (order_id, id),
  FOREIGN KEY (order_id) REFERENCES report_order(id)
) ENGINE=InnoDB;
```

Demo 使用的 query shape：

```sql
SELECT o.id, i.id, o.created_at, o.status, i.qty, i.unit_price
FROM report_order AS o
JOIN report_item AS i ON i.order_id = o.id
ORDER BY o.created_at, o.id, i.id;
```

### 为什么顺序必须唯一

只写 `ORDER BY created_at` 不够：多个 order 可以拥有同一时间。完整顺序是 `(created_at, id, item_id)`，因此相同数据每次都能产生相同 bytes 和 SHA-256。

如果 production 使用 keyset pagination，下一批边界应来自最后一个完整 unique tuple，例如：

```sql
WHERE (o.created_at, o.id) > (?, ?)
  AND (o.created_at, o.id) <= (?, ?)
ORDER BY o.created_at, o.id
LIMIT ?;
```

item 明细则还要维持 `item_id` 的唯一顺序。不要使用深 `LIMIT offset,n`：offset 越深，Server 越需要扫描并丢弃前面的 rows。分页机制详见 [ch08 deep pagination](../08-sql-tuning/scenarios/03-deep-pagination-deferred-join.md)。

### 索引不是越宽越好

- `(created_at,id)` 帮助 order 的范围定位和稳定顺序。
- `(order_id,id)` 帮助从 order 定位 items 并稳定 item 顺序。
- 把所有 select columns 都塞进 covering index 可能减少回表，却会放大写入、buffer pool 与维护成本。
- JOIN、filesort、temporary table 是否发生，应由 `EXPLAIN ANALYZE` 与实际 status delta 判断，不靠想象。完整机制由 [ch08 SQL tuning](../08-sql-tuning/README.md) 负责。

## 3. 一致性边界

### RR snapshot 能保证什么

InnoDB `REPEATABLE READ` 下，普通 consistent read 在同一 transaction 中复用 ReadView。一次 export 若从开始到结束都使用同一 ReadView，可以读取一致的 committed versions。

但它有代价：

- 长 transaction 持有旧 ReadView；
- purge 不能清除仍可能被它读取的 undo versions；
- `History list length` 可能上升；
- 大量 update/delete 时，undo tablespace 和读取旧版本的成本都会增加。

因此 MVCC snapshot 是正确性工具，不是免费的资源隔离。底层机制见 [ch05 MVCC](../05-mvcc-and-transaction/README.md)。

### `fetchmany()` 不会自动缩短 snapshot

把 client 从 `fetchall()` 改成 `fetchmany(1000)`，只会限制 client 一次持有的 rows。如果它们仍属于同一 transaction／cursor，数据库 snapshot 仍可能持续整个 export。

若要按 batch 提交并释放 snapshot，就必须接受每批可能看到不同版本，或先把 membership/version materialize。不能同时声称“每批独立 transaction”与“整个文件是同一个 as-of snapshot”，除非另有 version source。

### Current read 与 consistent read

普通 `SELECT` 可以是 snapshot consistent read；`SELECT ... FOR UPDATE`、`UPDATE`、`DELETE` 属于 current read，会读取并锁定当前版本。报表 export 通常不应该用锁定读来强行冻结线上数据，否则它会直接与 OLTP 竞争锁。

## 4. 执行策略

### Buffered

```python
rows = cursor.fetchall()
```

优点：代码直观，适合小结果。缺点：client memory 大致随结果 rows/bytes 增长；千万级结果可能导致 OOM、长 GC pause 或 container memory kill。

### Chunked streaming

```python
while batch := cursor.fetchmany(1000):
    write_rows(batch)
```

优点：client memory 随 batch size 有界，可以逐批写文件和记录 checkpoint。代价是更多循环与状态管理；而且正如上一节所述，它不自动缩短数据库 transaction 或 MVCC lifetime。

### 推荐的 production execution chain

```text
create async job
→ capture membership/snapshot boundary
→ keyset read bounded batch
→ write deterministic part
→ record cursor + rows + SHA
→ repeat
→ verify total/distinct/aggregate
→ atomic publish immutable artifact
```

数据库读取与下载必须解耦。consumer 下载慢，不应该让 database cursor 跟着保持几小时。

## 5. 隔离 OLTP

### 放在哪里执行

| 位置 | 适合情况 | 主要风险 |
|---|---|---|
| Primary | 极低 staleness、低频小结果且容量已验证 | 与交易共享 CPU、I/O、buffer pool |
| Shared replica | 可接受 lag、频率不高 | 与 replication applier 和线上 read 竞争 |
| Dedicated reporting replica | 报表固定且频繁 | 成本、lag、snapshot 与故障管理 |
| Analytical store | 大聚合、历史分析、宽扫描 | CDC lag、schema evolution、reconciliation |

“放从库”不是完整答案。必须说明：

- 如何证明目标 GTID/binlog position 已经 receive、apply 并可见；
- export 是否会拖慢 applier；
- lag 超过 budget 时是等待、失败还是降级；
- reporting replica 故障时是否允许回 Primary。

复制边界见 [ch09 replication and HA](../09-replication-and-ha/README.md)。

### Primary 上的最低保护

- async job，不占用同步请求连接；
- connection pool 单独限额；
- batch size、并发数和执行时间有上限；
- 低峰调度；
- 监控 query latency、rows examined、temporary tables、I/O 与 undo；
- OLTP latency/error 超过 budget 时停止，而不是继续“等它跑完”。

## 6. 如何观测

必须把 correctness 和 performance 分开：

### Correctness

- row count 是否符合预期；
- first/last key 是否正确；
- key 是否唯一且严格有序；
- buffered/chunked SHA-256 是否一致；
- aggregate fingerprint 是否与 source 相符；
- artifact 只有完成验证后才发布。

### OLTP safety

- transaction P50/P95/P99；
- error/timeout/deadlock；
- throughput；
- active connections 与 thread queue；
- buffer pool miss、I/O latency；
- undo history／purge lag；
- replica receive/apply lag。

本章的小实验只记录 elapsed time 和 OLTP counter 是否前进。OLTP counter 增加只证明 demo 中仍有写入完成，不证明 latency SLO，也不能外推生产环境安全。

## 7. Docker 缩小实验

实验固定使用：

- `10,000` orders；
- `30,000` items；
- `1,000` OLTP probe rows；
- buffered `fetchall()`；
- chunked `fetchmany(1000)`。

执行：

```bash
cd mysql-handson/00-lab/senior-scenarios
./run-demo.sh test
./run-demo.sh run
./run-demo.sh cleanup
```

代码与资源边界见 [report/export Docker demo](../00-lab/senior-scenarios/README.md)。

成功条件：

```text
buffered rows = chunked rows = 30,000
buffered first/last key = chunked first/last key
buffered SHA-256 = chunked SHA-256
buffered OLTP counter delta > 0
chunked OLTP counter delta > 0
```

所有运行时、MySQL、Python、seed data 和 TSV 都在 scoped Docker resources 内。这个结果只是本机小规模行为观察，不能外推到千万行、其他硬件、其他 schema 或 production capacity。

### 2026-08-03 观察结果

环境是 `mysql:8.0.36` 与 `python:3.13-slim`；MySQL/runner 都限制为 `2 CPUs`、`2 GiB`、`256 PIDs`。

| 模式 | rows | elapsed | OLTP counter delta | first/last key | SHA-256 |
|---|---:|---:|---:|---|---|
| buffered | 30,000 | 0.068059s | 58 | `(1,1)` / `(10000,30000)` | `b188a6bb93c6cdb3720b2c3594de1e6bfeeabb55e07b5b35442e726dc6981e3e` |
| chunked | 30,000 | 0.207583s | 72 | `(1,1)` / `(10000,30000)` | `b188a6bb93c6cdb3720b2c3594de1e6bfeeabb55e07b5b35442e726dc6981e3e` |

这次实验只证明：固定 source、相同 query/order/format 下，两种读取方式产生相同 bytes，而且两个 export 区间都有 OLTP update 完成。chunked 在这次小数据上反而更慢；它的主要价值是 bounded client memory 和可分批处理，不是保证更快。实验没有量测 OLTP latency percentile、undo 压力或生产并发，因此不能外推容量与 SLO。

## 8. 失败与恢复

简单 demo 可以 `cleanup` 后重跑；production job 则至少需要：

1. stable job ID 与参数 fingerprint；
2. 已完成 part 的 cursor、row count 与 SHA；
3. retry 时先验证 checkpoint 对应的 artifact bytes；
4. deterministic query order；
5. `.tmp` 写完并 flush 后再 atomic rename；
6. success manifest 发布前验证 total、distinct 与 aggregate；
7. cancel/timeout 后关闭 cursor、transaction 和 connection；
8. 明确定义失败 artifact 的保留期限与 cleanup owner。

### 不能含糊的 UNKNOWN

如果 client 在 publish/commit 附近断线，不能直接当成失败重做。先按 job ID 查询 state 与 artifact manifest：

- 已成功发布：返回同一个 immutable artifact；
- 明确未发布：从合法 checkpoint 继续或重跑；
- 无法判断：保持 `UNKNOWN`，先 reconciliation，不并行生成第二份“可能成功”的结果。

## 9. 面试回答模板

### 30 秒

> 我会先确认一致性、staleness、结果大小和 OLTP budget。允许陈旧时优先放 dedicated reporting replica 或 analytical store；必须读 Primary 时做 async job，以唯一 keyset 顺序和 bounded `fetchmany()` 生成 artifact。`fetchmany()` 只限制 client memory，不自动缩短 MVCC snapshot，所以还要明确 membership/version boundary 与 undo 成本。执行时隔离连接和资源，监控 OLTP latency/error、I/O 与 purge；最后用 rows、order、distinct、aggregate 和 SHA 验证，验证后才原子发布。

### 3–5 分钟展开顺序

1. 定义 consistency：membership、values、staleness。
2. 选择 placement：Primary、shared/dedicated replica、analytical store。
3. 由 access path 设计 `(created_at,id)` 与 `(order_id,id)` 索引。
4. 使用唯一 keyset，不使用深 offset。
5. 区分 buffered memory 与 chunked snapshot lifetime。
6. 设计 checkpoint、idempotency、atomic publish。
7. 分开验证 correctness 与 OLTP safety。
8. 说明失败、UNKNOWN、resume 与 cleanup。

## 常见追问

**为什么不能只加 `LIMIT 1000`？**

`LIMIT` 限制返回 rows，但不能保证前面的 scan、sort、temporary table 或 JOIN 工作量有界；必须结合 access path 与 `EXPLAIN ANALYZE`。

**为什么不用深 offset？**

Server 仍需找到并丢弃 offset 前面的 rows。keyset 用最后一个 unique tuple 直接定位下一段。

**chunked 一定比 buffered 快吗？**

不一定。chunked 的主要收益是 bounded client memory、可 checkpoint 和较小 burst；它可能因循环、写盘或 sleep 耗时更久。

**从库一定不会影响线上吗？**

不会直接占 Primary 的 read CPU，但会与 applier、其他读流量竞争，并可能扩大 lag。必须有 receive/apply/visibility 与容量 gate。

**如何证明没有漏单或重复？**

固定 membership/version boundary，使用唯一顺序；每个 part 记录 cursor、rows、SHA，最终再检查 total、distinct、aggregate 与 artifact hash。只看“程序 exit 0”不够。
