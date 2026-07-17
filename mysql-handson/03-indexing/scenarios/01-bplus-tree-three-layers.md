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

所以「三层 B+ 树」能装**千万到亿级别**。这里的 3 层表示一次聚簇索引定位大约访问 3 个 B+ 树页，不是固定发生 3 次物理磁盘 IO；页命中 Buffer Pool 时是内存访问，走二级索引且需要回表时还会再访问聚簇索引。

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

- `Avg_row_length = 265`、`n_leaf_pages = 138` 都是统计口径下的近似值，可用于容量估算，不能据此声称每个叶子页“实际正好放 61 行”。页头、记录头、页目录、填充率以及统计采样都会让实值偏离简单除法。
- `size = 161` 表示索引占用的总页数，`n_leaf_pages = 138` 表示估算的叶子页数。不能把 `161 - 138 = 23` 直接解释成 23 个正在使用的非叶子节点，再据此推出树高；InnoDB 按页/extent 分配并会保留空间，而 `innodb_index_stats` 本身也不提供树高。
- 按容量粗估，138 个叶子页远低于一个 INT 根页可容纳的约 1638 个子页指针，因此这棵 1 万行索引**很可能**仍是 root + leaf 两层；这是容量推算，不是上述统计表直接测得的结论。
- 文件大小 10MB = 640 个 16KB 页；`ALLOCATED_SIZE = FILE_SIZE` 只说明文件空间已分配，不能推出索引页都已装满或没有内部保留空间。

## ⚠️ 预期 vs 实机落差

- 我以为：10000 行已经需要三层 B+ 树。
- 修正后：两层树升为三层的粗略阈值是“一个根页能指向的叶子页数 × 每个叶子页的记录数”，不是“扇出平方 ÷ 每页行数”。沿用上面的理想估算，BIGINT 主键约为 `1170 × 61 ≈ 7.1 万行`，INT 主键约为 `1638 × 61 ≈ 10 万行`；实际阈值受页开销、填充率、记录宽度和删除碎片影响。
- 我学到：树高取决于数据量和记录宽度；真正重要的是扇出大，让千万到亿级索引通常仍保持很低的树高。树高代表页访问层数，实际磁盘 IO 还取决于 Buffer Pool 是否命中。

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
