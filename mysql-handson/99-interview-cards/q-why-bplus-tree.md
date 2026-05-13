# 为什么 MySQL/InnoDB 用 B+ 树做索引？

## 一句话回答

为了**最小化磁盘 IO 次数**：B+ 树扇出大（一页 16KB 能放 1000+ 个键），三层就能装千万级数据，对应 3 次 IO；叶子节点有序链表让范围查询和排序无需回到根。

## 三层论证

1. **树高决定 IO 次数**。10^7 行：二叉树 23 层（23 次 IO），B 树 ≈ 4 层，B+ 树 3 层。
2. **B+ 树 vs B 树**：B+ 树内部节点只存键不存数据，扇出更大；叶子有序双向链表，范围扫描沿链表走，不用回到上层。
3. **B+ 树 vs Hash**：Hash 不支持范围和排序，且哈希冲突让最坏情况退化。

## 证据链接

- 三层 B+ 树容量实测：[Scenario 01](../03-indexing/scenarios/01-bplus-tree-three-layers.md)
- 覆盖索引省回表的代价对比：[Scenario 03](../03-indexing/scenarios/03-covering-index-saves-roundtrip.md)
- 章节原理：[03-indexing §3.1](../03-indexing/README.md)

## 易追问的延伸

- **Q: 那为什么主键不要用 UUID？** → UUID 无序，每次插入导致页分裂频繁；自增 BIGINT 顺序写入，页紧凑。
- **Q: 为什么页大小是 16KB？** → 平衡：太小→树变高；太大→单次 IO 慢。16KB 是磁盘 IO 的甜点。
- **Q: 8.0 移除了 Query Cache，那 InnoDB 还有什么缓存？** → Buffer Pool（热页）、Change Buffer（非唯一二级索引的写延迟应用）、Adaptive Hash Index（热点 B+ 树路径变成 hash）。
