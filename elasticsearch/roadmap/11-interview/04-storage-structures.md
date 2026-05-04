# ES 存储结构原理追问

> **目标**：把倒排索引、Term Dictionary、FST、Posting List、Doc Values、Stored Fields、Fielddata、Segment 这些底层结构讲清楚。面试中重点解释它们分别解决什么问题，以及代价是什么。

## Q1：什么是倒排索引？

### 一句话答案

倒排索引是从 term 到文档列表的映射，让搜索引擎可以通过关键词快速找到包含它的文档，而不是逐条扫描所有文档。

### 核心链路

```text
document text
-> analyzer produces terms
-> term -> doc IDs
-> query term lookup
-> candidate documents
```

### 为什么这样设计

全文搜索的核心问题是“给定词，找文档”。倒排索引直接按这个访问模式组织数据，因此比按文档逐条扫描更适合搜索。

### 常见追问

**倒排索引和 B+ 树有什么区别？**

B+ 树更适合范围查询、排序和主键查找；倒排索引更适合多 term 的全文检索和相关性排序。

### 生产场景怎么说

搜索商品标题、文章正文、日志 message 时，用倒排索引能快速定位候选文档；订单号、状态、租户号这类精确字段则更依赖 keyword 和过滤。

### 关联章节

- 阶段 1：倒排索引直觉
- 阶段 3：分词
- 阶段 6：Lucene 底层结构

## Q2：Term Dictionary、FST、Posting List 分别是什么？

### 一句话答案

Term Dictionary 保存所有 term，FST 帮助快速定位 term，Posting List 保存包含该 term 的文档 ID 及相关信息。

### 核心链路

```text
query term
-> FST narrows term lookup
-> Term Dictionary confirms exact term
-> Posting List returns doc IDs
-> BM25 uses term frequency, norms and collection statistics
```

### 为什么这样设计

Term 数量可能很大，不能低效扫描全部 term。FST 以较小内存支持快速前缀定位，Posting List 则把候选文档压缩存储，支持高效交并集和打分。

### 常见追问

**Posting List 里只有 doc ID 吗？**

不止。Posting List 通常至少有 doc ID，也可能包含词频、positions、offset 等信息，具体取决于字段索引配置。普通 BM25 打分主要依赖词频，再结合 norms 和 collection statistics；positions 主要用于短语和邻近查询，offset 主要用于高亮。

**skip data 是什么？**

这是深挖内容。Posting List 很长时，可以用跳跃结构加速跳过不可能匹配的 doc 区间，避免逐个 doc ID 扫描。

### 生产场景怎么说

如果 wildcard、regexp、前缀查询使用不当，可能导致 term 枚举范围过大，即使倒排索引存在也会慢。生产上应限制这类查询或用 edge_ngram、completion 等更合适的建模方式。

### 关联章节

- 阶段 4：模式匹配查询
- 阶段 6：FST、Posting List

## Q3：Doc Values 为什么适合排序和聚合？

### 一句话答案

Doc Values 是面向列的磁盘结构，按字段组织每个文档的值，适合排序、聚合和脚本访问这类“按字段扫描很多文档”的场景。

### 核心链路

```text
inverted index:
term -> doc IDs

doc values:
doc ID -> field value

aggregation/sort:
matching doc IDs -> read field values -> compute buckets/order
```

### 为什么这样设计

倒排索引适合从 term 找文档，但聚合和排序经常是拿到一批 doc ID 后读取某个字段值。Doc Values 按列存储，减少 heap 压力，并更适合这种访问模式。

### 常见追问

**为什么 keyword 字段适合聚合？**

keyword 保留整体值，并默认支持 Doc Values，聚合时可以稳定读取字段值。

**text 字段为什么不能直接聚合？**

text 字段被分词后不再代表原始整体值。若强行对 text 聚合，通常需要启用 Fielddata，会占用大量 heap。

### 生产场景怎么说

做品牌、状态、城市、租户等聚合时，应使用 keyword 或数值字段。不要对大文本字段开 Fielddata 来聚合，应该建 `.keyword` 子字段或重新设计 mapping。

### 关联章节

- 阶段 2：Mapping
- 阶段 5：聚合
- 阶段 6：Doc Values

## 补充：Stored Fields 和 `_source` 解决什么问题？

### 一句话答案

Stored Fields 和 `_source` 主要解决“命中文档后怎么取回原始内容”的问题；它们服务于结果返回，不负责 term 检索，也不适合排序和聚合。

### 核心区别

```text
倒排索引:
term -> doc IDs, for search

Doc Values:
doc ID -> field value, for sort/aggregation/script

Stored Fields / _source:
doc ID -> stored original content, for fetch response
```

### 为什么这样设计

查询阶段先用倒排索引找候选文档，再按需用 `_source` 或 Stored Fields 取回需要返回的字段。Doc Values 是列式结构，适合批量读取某个字段做计算；Stored Fields 更像按文档取回内容，不是为大规模聚合扫描设计的。

### 常见追问

**`_source` 和 `store: true` 是一回事吗？**

不是。`_source` 保存原始 JSON，默认用于返回、update、reindex 和部分高亮场景；`store: true` 是把某个字段单独作为 Stored Field 存储，适合少数字段需要独立取回的场景，但会增加存储成本。

### 生产场景怎么说

不要为了排序、聚合去读取 `_source` 或 Stored Fields，应该依赖 Doc Values。大文档返回时可以用 `_source` filtering 限制字段，降低 fetch 阶段的 IO 和反序列化开销。

## Q4：Fielddata 为什么容易造成堆内存压力？

### 一句话答案

Fielddata 会把 text 字段的倒排结构加载并转换成便于按文档访问的内存结构，数据量大时会占用大量 JVM heap，容易触发 GC 或 circuit breaker。

### 核心链路

```text
text field aggregation/sort
-> fielddata loads terms into heap
-> heap usage rises
-> GC pressure or circuit breaker
```

### 为什么这样设计

text 字段默认是为全文搜索设计的，不是为聚合和排序设计的。Fielddata 是一种补救机制，但代价很高。

### 常见追问

**怎么避免 Fielddata 问题？**

建模时给需要聚合、排序的字符串字段增加 keyword 子字段；聚合使用 `field.keyword`，不要直接对 `field` 做 terms aggregation。

### 生产场景怎么说

如果线上 heap 突然升高，且慢查询或 profile 显示对 text 字段聚合排序，要立刻改查询使用 keyword 字段。长期修复是调整 mapping 并 reindex。

### 关联章节

- 阶段 2：text vs keyword
- 阶段 5：Doc Values 与 Fielddata
- 阶段 8：内存调优

## Q5：Segment 不可变有什么好处和代价？

### 一句话答案

Segment 不可变让搜索可以无锁并发、缓存更稳定、文件系统友好；代价是更新删除不能原地修改，会产生删除标记和 merge 成本。

### 核心链路

```text
immutable segment
-> concurrent search without modifying old data
-> update creates new version
-> delete creates delete marker
-> merge compacts segments and removes deleted docs
```

### 为什么这样设计

ES 这类搜索引擎通常优先保障读多写少场景下的搜索性能和并发读稳定性。不可变 segment 让读路径简单稳定，把写入和删除的复杂度转移到后台 merge。

### 常见追问

**删除文档会马上释放磁盘吗？**

不会。删除先是标记删除，等后续 merge 才会物理清理。

**更新频繁有什么影响？**

会增加删除标记和 merge 压力，进而影响 IO、CPU 和查询延迟。

### 生产场景怎么说

高频更新场景要谨慎使用 ES 作为主存储。可以通过批量更新、降低更新频率、拆分高频字段、优化 refresh 和 shard 设计来控制成本。

### 关联章节

- 阶段 6：Segment 生命周期
- 阶段 8：写入优化
