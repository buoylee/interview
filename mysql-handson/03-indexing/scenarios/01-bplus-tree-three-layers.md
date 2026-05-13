# Scenario 01: B+ 树三层能放多少行

## 我想验证的问题

InnoDB 默认页大小是 16KB。如果一棵 B+ 树只有 3 层（root + 中间层 + 叶子层），主键是 BIGINT（8 字节），它能放多少行数据？「索引最多 3 层」这句话是从哪来的？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**。基于你目前的理解（不要查），把下列空格填上：
>
> - 一页 16KB，一个「指针 + 主键」对大约占 _____ 字节（如果主键是 BIGINT），所以一页能放约 _____ 个非叶子节点条目（向上取整）。
> - 三层 B+ 树：root × 中间 × 叶子，每个叶子页能放约 _____ 行（如果一行平均 1KB）。
> - 三层总行数估算 ≈ _____ 行。
> - 我以为答案是 1000 万级 / 1 亿级 / 10 亿级？为什么？
>
> 这一段填完就 commit 一次（"prediction only"），再开始下面的步骤。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`
- schema：`init/01-create-schema.sql`（用 `sbtest1` 表，主键 INT 默认自增）
- 注意：本 scenario 不需要灌很多数据，主要是查 `information_schema` 估算

## 步骤

1. 起 lab：`make up`
2. 灌少量数据，用来观察页结构：`make load ROWS=10000`
3. 查表的存储参数和实际页数：

```sql
SELECT NAME, FILE_SIZE, ALLOCATED_SIZE
FROM information_schema.INNODB_TABLESPACES
WHERE NAME LIKE 'sbtest%';

SELECT TABLE_NAME, INDEX_NAME, STAT_NAME, STAT_VALUE, STAT_DESCRIPTION
FROM mysql.innodb_index_stats
WHERE TABLE_NAME = 'sbtest1';
```
4. 查每行实际占多少字节：

```sql
SHOW TABLE STATUS LIKE 'sbtest1'\G
```

   看 `Avg_row_length`、`Data_length`、`Index_length`。
5. 估算公式：
   - 非叶子节点：每个条目 ≈ 主键大小 + 6 字节（页号指针） = 8+6=14 字节（BIGINT 主键）。一页 16384 字节，约能放 16384/14 ≈ 1170 个条目。
   - 叶子节点：每页能放 16384/Avg_row_length 行。
   - 三层总行数 = 1170 × 1170 × (16384/Avg_row_length)
6. 把估算结果与 `mysql.innodb_index_stats` 里 `n_leaf_pages`、`size`、`n_diff_pfx*` 等指标对照。

## 实机告诉我（跑完当天填）

```
<贴 SHOW TABLE STATUS 输出片段>
<贴 innodb_index_stats 关键行>
```

观察到的关键事实：

- ...

## ⚠️ 预期 vs 实机落差

- 我以为：……
- 实际：……
- 我学到：……

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
