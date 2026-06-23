# Scenario 02: binlog 格式 ROW vs STATEMENT —— 一条 SQL 改 1 万行，binlog 差多少

## 我想验证的问题

`binlog_format` 选 ROW 还是 STATEMENT，对 binlog 体积影响有多大？拿「一条 UPDATE 改 1 万行」做实验，量一量两种格式各让 binlog 长多少字节。

## 预期（基于 ch07 §3.5 推算）

- **STATEMENT**：只记**那一条 SQL 原文**。不管它影响 1 行还是 100 万行，binlog 增量都是几百字节。优点是省空间；缺点是含 `NOW()`/`UUID()`/触发器等非确定性时主从会算出不同结果。
- **ROW**：记**每一个被改的行的前后镜像**。改 1 万行就写 1 万行的 before/after image，体积 = O(行数 × 行宽)，可能几百 KB 到几 MB。优点是绝对确定、主从一致；缺点是大批量 DML 时 binlog 暴涨。

预期：同样改 1 万行，ROW 的 binlog 增量比 STATEMENT 大几个数量级。

## 环境

- 表：`up2`，`city='Taipei'` 和 `city='Tokyo'` 各 1 万行
- 用 `SHOW MASTER STATUS` 的 `Position` 在 UPDATE 前后取 binlog 偏移，差值 = 这条语句写入的 binlog 字节数

## 步骤

```sql
-- STATEMENT
SET SESSION binlog_format=STATEMENT;
-- pos_before = SHOW MASTER STATUS 的 Position
UPDATE up2 SET age=age+1 WHERE city='Taipei';   -- 改 1 万行
-- pos_after，增量 = after - before

-- ROW
SET SESSION binlog_format=ROW;
UPDATE up2 SET age=age+1 WHERE city='Tokyo';     -- 同样改 1 万行
-- 再取增量
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
STATEMENT: 1 万行 UPDATE → binlog 增量      339 字节   (只记一条 SQL 原文)
ROW:       1 万行 UPDATE → binlog 增量  477,940 字节   (记 1 万行的前后镜像)

倍数: ROW / STATEMENT ≈ 1409 倍
```

补充观察：

- 早些时把 UPDATE 写成 `SET age=age`（值不变），**ROW 格式增量是 0 字节**——因为没有行真的改变，ROW 不记任何镜像；而 STATEMENT 照样记那条 SQL（几百字节）。这反过来印证了两种格式「记什么」的本质差别。

## ⚠️ 预期 vs 实机落差

- 预期方向对，1409 倍的差距比直觉还夸张。亲手量过就懂了一个生产陷阱：**ROW 格式下，一条「看似无害」的批量 UPDATE/DELETE 会瞬间写出几百 MB binlog**，可能撑爆磁盘、或让从库 IO 线程拉取/重放变慢造成主从延迟（ch09）。
- 工程权衡落地：
  - 生产默认 **ROW**（数据一致性优先，8.0 默认就是 ROW），但**大批量 DML 要分批**（每批几千行 + sleep），别一条语句扫全表。
  - `binlog_row_image=minimal` 可以只记被改列 + 主键，显著压小 ROW binlog（代价是某些场景下闪回/审计信息变少）。
  - STATEMENT 省空间但有非确定性坑（且 RC 隔离级别下不被允许），MIXED 是「能 STATEMENT 就 STATEMENT、有风险才切 ROW」的折衷。

## 连到的面试卡

- `99-interview-cards/q-binlog-row-vs-statement.md`
