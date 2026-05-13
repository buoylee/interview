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

## 预期（基于 ch03 §3 推算）

按 §3.1 的公式：一页 16KB = 16384 字节，sbtest1 的主键是 INT（4 字节），非叶子节点每个条目 = 4 + 6（页号指针）= 10 字节，扇出 ≈ 16384 / 10 = **1638**。如果主键是 BIGINT（8 字节），扇出 ≈ 16384 / 14 = **1170**。

叶子节点每行平均约 265 字节（c CHAR(120) + pad CHAR(60) + 少量 overhead），每页 ≈ 16384 / 265 ≈ **61 行**。

三层 B+ 树总行数估算：
- BIGINT 主键：1170 × 1170 × 61 ≈ **83,502,900 行**（约 8000 万）
- INT 主键：1638 × 1638 × 61 ≈ **163,665,684 行**（约 1.6 亿）

所以「三层 B+ 树」能装**千万到亿级别**，"索引最多 3 层"这句话的意思是大部分生产表（几千万行内）树高不超过 3，磁盘 IO 最多 3 次就能定位一行。

## 实机告诉我（跑完当天填）

```
-- ANALYZE TABLE sbtest1; SHOW TABLE STATUS LIKE 'sbtest1'\G
           Name: sbtest1
         Engine: InnoDB
     Row_format: Dynamic
           Rows: 9936
 Avg_row_length: 265
    Data_length: 2637824
   Index_length: 262144
Auto_increment: 10001

-- SELECT NAME, FILE_SIZE, ALLOCATED_SIZE FROM information_schema.INNODB_TABLESPACES WHERE NAME LIKE 'sbtest%'
NAME              FILE_SIZE    ALLOCATED_SIZE
sbtest/sbtest1    10485760     10485760

-- SELECT TABLE_NAME, INDEX_NAME, STAT_NAME, STAT_VALUE FROM mysql.innodb_index_stats WHERE TABLE_NAME = 'sbtest1'
TABLE_NAME  INDEX_NAME  STAT_NAME       STAT_VALUE  STAT_DESCRIPTION
sbtest1     PRIMARY     n_diff_pfx01    9680        id
sbtest1     PRIMARY     n_leaf_pages    138         Number of leaf pages in the index
sbtest1     PRIMARY     size            161         Number of pages in the index
sbtest1     k_1         n_diff_pfx01    10000       k
sbtest1     k_1         n_leaf_pages    15          Number of leaf pages in the index
sbtest1     k_1         size            16          Number of pages in the index
```

观察到的关键事实：

- `Avg_row_length = 265` 字节，每个叶子页实际放 ≈ 16384/265 = **61 行**，与预期一致。
- PRIMARY 索引：`n_leaf_pages = 138`，`size = 161`；非叶子页 = 161 − 138 = **23 页**。10000 行分布在 138 个叶子页，实际 rows/leaf ≈ 72.5。
- 整棵树高：23 个非叶子页可容纳指针 ≈ 23 × 1638 = 37674 条，远多于 138，说明这棵树实际只有**两层**（root 在内存 + 叶子层）。再大 ~100 倍才会触发第三层。
- 文件大小 10MB = 640 个 16KB 页，其中 `ALLOCATED_SIZE = FILE_SIZE` 表示没有空洞（Data_free 是 tablespace 级别预分配）。

## ⚠️ 预期 vs 实机落差

- 我以为：10000 行已经需要三层 B+ 树。
- 实际：10000 行只用了两层（138 个叶子页 + 23 个非叶子页，非叶子层直接是 root），三层 B+ 树需要至少 1638 × 1638 / 72 ≈ **37200** 行才会触发。"三层够装千万行"是说**上限**，不是说小表也三层。
- 我学到：树高取决于数据量，小表不需要三层；真正重要的是扇出大（1000+），确保在数亿行数据前都能控制在 3 次 IO 以内。

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
