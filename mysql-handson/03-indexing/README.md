# 索引（Indexing）

## 1. 核心问题

索引是「在不全表扫的前提下，快速定位行」的数据结构。本章解决三件事：
**(a)** 为什么 MySQL/InnoDB 用 B+ 树，不用其他结构；
**(b)** 怎么读懂一条 SQL 走没走索引、走的是哪个；
**(c)** 写 SQL 和建表时，怎样的索引设计才能跑得快。

## 2. 直觉理解

想像一本 1000 页的字典，没有索引你要从头翻；按拼音排序的目录是「一层索引」，能让你跳到大概页数；如果目录本身又有「字头索引」（A 在前 50 页，B 在 51-100…），就是「两层索引」。InnoDB 的 B+ 树就是这种**多层目录**，但有两个关键特点：

- **目录不是一本，是两本**：一本按主键排（叫聚簇索引，叶子节点直接存整行数据），其余的都是「指向主键的目录」（二级索引，叶子节点只存主键值，要回去聚簇索引再查一次，叫「回表」）
- **每一页 16KB**：所以三层 B+ 树能放下大约几千万行（具体数字见 Scenario 01）

## 3. 原理深入

> 写完 Scenarios 01-05 之后回来补这一节，引用 scenario 数据。

待补的子节：
- 3.1 B+ 树 vs B 树 vs 红黑树 vs Hash：为什么选 B+ 树
- 3.2 聚簇索引 vs 二级索引：叶子节点存什么、回表是什么
- 3.3 联合索引 + 最左前缀
- 3.4 覆盖索引（covering index）省回表
- 3.5 索引下推（Index Condition Pushdown，ICP）
- 3.6 Multi-Range Read（MRR）
- 3.7 索引为什么会失效（前导通配、隐式类型转换、对列做函数运算、OR 跨列）

## 4. 日常开发应用

> 写完 Scenarios 02-05 之后补。重点：建表时怎么定主键、怎么定联合索引顺序、什么时候加覆盖索引、不要让 ORM 自动生成奇怪的 SQL。

## 5. 调优实战

> 写完 Scenarios 02-05 之后补。case：
> - 拿到一条慢 SQL，先看 explain 的 type/key/rows/Extra 四列
> - 怀疑索引没走，用 optimizer_trace 看成本估算
> - 改不动 SQL 时，怎么加 hint（force index / use index / 8.0 的 optimizer hint）

## 6. 面试高频考点

> 写完后补。常见对比表：
> - 聚簇 vs 非聚簇 / 主键索引 vs 唯一索引
> - 何时回表 / 何时不回表
> - 联合索引顺序的两条原则（区分度 + 最左前缀使用率）
> - "为什么用 B+ 树" 三句话答法

## 7. 一句话总结

> 写完后补。3-5 行。

## Scenarios

- [01 - B+ 树三层能放多少行](scenarios/01-bplus-tree-three-layers.md)
- [02 - 联合索引最左前缀失效](scenarios/02-leftmost-prefix-violation.md)
- [03 - 覆盖索引省回表](scenarios/03-covering-index-saves-roundtrip.md)
- [04 - 索引下推（ICP）开关前后对比](scenarios/04-icp-on-off-comparison.md)
- [05 - 隐式类型转换让索引失效](scenarios/05-implicit-type-conversion-kills-index.md)
