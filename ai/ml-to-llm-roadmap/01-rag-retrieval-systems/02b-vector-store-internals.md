# 向量库内部:一个 chunk 怎么存、怎么被搜出来

> 这是 [`02-indexing-embedding-retrieval.md`](./02-indexing-embedding-retrieval.md) 的深水区回填。那篇在「向量怎么建索引」停住了,留了句「HNSW/IVF-PQ…第一遍不必先背参数」就 defer 掉。本篇把那一层补上,对应 [RAG 资深主线](../../rag-roadmap.md) **阶段 2 缺口㉢**。

## 这篇解决什么问题

`Chroma.from_documents(...)` / `collection.insert(...)` 是个黑盒。面试官真正想听的是黑盒里那一行长什么样、怎么被搜出来。本篇回答五件事:

1. 一个 chunk 在库里到底存成什么?
2. 不建索引会怎样(brute-force)?什么时候它反而是对的?
3. ANN 索引(HNSW / IVF-PQ)内部存了什么、用什么换什么?
4. 加了 metadata 过滤,为什么召回会「性能塌陷」?
5. 高并发和规模上去了,怎么扩?pgvector 够不够、什么时候换 Milvus?

## 两个锚:看见 vs 生产

内部原理(HNSW、IVF-PQ)是**引擎无关**的——HNSW 在哪儿都是 HNSW。所以下面用两个具体引擎当样例,各取所长:

| 锚 | 用谁 | 负责 | 为什么 |
|---|---|---|---|
| **透明锚**(看见那一行) | **pgvector** | §1~§2 | SQL 能直接 `SELECT` 出来,把「具体怎么存」讲到最实 |
| **生产主轴**(规模 / 并发) | **Milvus** | §3~§7 | 原生分布式分片、读写分离,扛高并发;索引动物园最全,讲 IVF-PQ 给得出真实配置 |

> Qdrant 不单独当锚,只在 §7 选型里作为「自托管最简单」的中间档出现。

---

## §1 一行 = 什么

用 pgvector 看最清楚,它就是张普通的 Postgres 表:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id        bigserial PRIMARY KEY,
  content   text,            -- chunk 原始文字:最后要原样塞进 prompt 给模型读
  metadata  jsonb,           -- source / page / department / date / permission ...
  embedding vector(1536)     -- pgvector 列类型,物理上 = 1536 个 float4 ≈ 6KB/行
);
```

一个 chunk = 一行 `(id, 原文, 标签, 向量)`。最该记住的一条:

> **文字和向量是分开存的,两个都要存。**

- `embedding` 只用来**算距离、被找到**。它是有损压缩 + **不可逆**——你没法从 1536 个浮点还原出原文。
- `content` 才是最后**给 LLM 看**的东西。检索命中后返回的是 content,不是向量。
- 所以:向量负责「被找到」,原文负责「被读到」,缺一不可。很多人以为「文字 embedding 完就没了」,这是面试里第一个会被纠的点。

类比你的 SQL 脑:它就是一张表,主键 + `text` 列 + `jsonb` 列 + 一个定长 `float[]` 列。没有魔法,魔法在 §3 的二级索引里。

Milvus 里同一行叫一个 **entity**,字段集合叫 schema,本质完全一样:

```python
from pymilvus import MilvusClient, DataType

client = MilvusClient("milvus_demo.db")   # Milvus Lite:本地一个文件,等价 pgvector 单机起步

schema = client.create_schema()
schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
schema.add_field("content", DataType.VARCHAR, max_length=4096)    # 原文
schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=1536)    # 向量
schema.add_field("department", DataType.VARCHAR, max_length=64)   # 标量字段 = metadata,用于过滤
client.create_collection("documents", schema=schema)
```

区别只是物理形态:pgvector 存成 heap 表的一行,Milvus 存成分布式 segment(§6 讲)。逻辑上都是「原文 + 向量 + 标量字段」。

---

## §2 不建索引会怎样:暴力扫描

没建索引时,检索就是**全表顺序扫描**,对每一行算一次距离:

```sql
SELECT content, metadata
FROM documents
ORDER BY embedding <=> $1      -- $1 = 查询向量
LIMIT 5;
```

pgvector 的三个距离算子(对应不同 metric):

| 算子 | 含义 | 何时用 |
|---|---|---|
| `<->` | L2(欧氏距离) | 归一化向量上与余弦等价 |
| `<=>` | 余弦距离 | 文本检索最常用 |
| `<#>` | 负内积 | 配合已归一化向量 |

**没建索引时,这条就是 brute-force**:Postgres 对表里每一行都算一次 `<=>`,排序取前 5。复杂度 O(N×D)(N=行数,D=维度)。

什么时候 brute-force 反而是对的:

- **N 小(几万行以内)**:全扫毫秒级,而且结果是**精确 top-k**,零近似误差。这时上 ANN 索引纯属浪费,还白白损失召回率。
- 面试点:**ANN 不是「更好的检索」,是「用精度换速度的妥协」。N 不大就别妥协。** FAISS 里这对应 `IndexFlatL2`,Milvus 里对应 `FLAT` 索引——它们就是「暴力但精确」,是衡量召回率的 baseline。

N 一大(百万、千万、亿),每查都 O(N) 全扫就崩了。这才需要 ANN 索引把它压到亚线性。

---

## §3 ANN 索引之一:HNSW(图)

**HNSW** = Hierarchical Navigable Small World,一个分层的近邻图。pgvector 默认、Qdrant、Milvus 都支持。

**机制**:

- 每个向量是图里一个**节点**,连到它最近的若干邻居(边)。
- **多层**:顶层稀疏(少数节点、长跳),越往下越密(全部节点、短跳)——像跳表的图版。
- **搜索** = 从顶层入口点出发,贪心地往离 query 更近的邻居跳;本层跳不动了就下一层精化,到底层收敛出 top-k。每次查只走「一条路径附近」的少数节点,不碰全图 → 亚线性。

**三个旋钮**(各引擎名字略不同,概念一致):

| 参数 | 调什么 | 调大 → |
|---|---|---|
| `M` | 每个节点的邻居数(图的度) | 召回↑、内存↑、构建慢 |
| `ef_construction` | 建图时每步保留的候选数 | 图质量↑、构建慢 |
| `ef_search`(查询期) | 查询时维护的候选列表大小 | 召回↑、延迟↑ |

最关键的直觉:**`ef_search` 是查询期的「召回 vs 延迟」实时旋钮**——同一个索引,调大就更准更慢,调小就更快更糙,**不用重建索引**。pgvector 里是 `SET hnsw.ef_search = 100;`。

**为什么 HNSW 吃内存**:图的邻接表 + 全部原始向量基本都要常驻 RAM 才快。所以「向量库吃内存」主要吃在这。这也是 **pgvector 在十亿级吃力的原因之一**:单个 Postgres 实例内存装不下那么大的图;Milvus 能把图分片到多台(§6)。

**建索引的代价 = 精确变近似**:

```sql
-- pgvector:建完这条,§2 的 ORDER BY 就从精确变近似
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

建之前 brute-force 给的是**真 top-5**;建之后 HNSW 给的是**大概率正确的 top-5**——可能漏掉真正第 3 近的那个。漏掉的比例就是召回率损失。**这是有意的取舍**:用一点召回率换几个数量级的速度。

> 面试官问「加了向量索引为什么结果会变」——答案就是这。

Milvus 建 HNSW:

```python
index_params = client.prepare_index_params()
index_params.add_index(field_name="embedding", index_type="HNSW",
                       metric_type="COSINE", params={"M": 16, "efConstruction": 64})
client.create_index("documents", index_params)
```

---

## §4 ANN 索引之二:IVF-PQ(倒排 + 量化)

另一条路线,FAISS / Milvus 的看家。它是**两个独立动作**:IVF 减少「要比的数量」,PQ 压缩「每个向量的体积」。

**IVF(Inverted File,倒排桶)= 少比一点**:

- 建索引时用 k-means 把所有向量聚成 `nlist` 个簇,每个向量归到最近的簇心。
- 查询时只在离 query 最近的 `nprobe` 个簇里找,**不碰其余簇**。比如 `nlist=1024`、`nprobe=16`,只比了约 1.5% 的向量。
- `nprobe` 就是 IVF 的「召回 vs 速度」旋钮(类比 HNSW 的 `ef_search`):probe 越多越准越慢。

**PQ(Product Quantization,乘积量化)= 每个向量压小**:

- 把 1536 维向量切成 `m` 段(比如 m=96,每段 16 维),每段用一本 256 项的码本量化成 **1 个字节**的码号。
- 于是一个 6KB(1536×float32)的向量被压成 ~96 字节,**省约 60 倍内存**,代价是距离变成近似(用码本质心算)。
- 这就是 **FAISS / Milvus 能把十亿向量塞进有限内存的核心**:HNSW 存全精度向量装不下,IVF-PQ 压完才装得下。

```python
index_params.add_index(field_name="embedding", index_type="IVF_PQ",
        metric_type="L2", params={"nlist": 1024, "m": 96, "nbits": 8})
# 查询期:client.search(..., search_params={"nprobe": 16})
```

**HNSW vs IVF-PQ,一句话选型**:

| | HNSW | IVF-PQ |
|---|---|---|
| 召回 / 精度 | 高 | 中(PQ 有损) |
| 内存 | 大(全精度向量 + 图) | 小(PQ 压缩) |
| 适合规模 | 百万~千万,内存够 | 亿~十亿,内存紧 |
| 写入 / 更新 | 增量插入贵(要改图) | 批量重建友好 |
| 典型 | pgvector 默认、Qdrant | FAISS / Milvus 大库 |

还有 **DiskANN**(Milvus 也支持):为「内存装不下」设计,把图放 SSD、用少量内存导航。当「向量太多、又要 HNSW 级召回、又买不起那么多内存」时用它。

---

## §5 metadata 过滤塌陷(roadmap 缺口㉢ 点名的坑)

需求很常见:「只在 `department='HR'` 且 `date>2024` 的 chunk 里检索」。难点是:**ANN 索引(图 / 簇)是按全部向量建的,它不认识你的过滤条件**。两种朴素做法都有病:

- **post-filter(先 ANN,后过滤)**:取 ANN top-k,再扔掉不满足条件的。问题:HR 文档稀疏时,top-k 里可能**一个 HR 都没有** → 过滤完返回 0~2 条,**召回塌陷**。救法是 over-fetch(把 k 放大 10 倍再过滤),但延迟涨。
- **pre-filter(先过滤,后搜)**:先按条件圈出子集再搜。问题:子集不在 ANN 的图 / 簇结构上,等于**退化回暴力扫描**子集;命中越多越慢。

这就是「加了 metadata 过滤后召回 / 性能为什么会塌陷」:**不是 bug,是 ANN 结构和过滤天生打架**。

各家怎么救(讲得出来就是资深):

- **pgvector**:0.8 加了 **iterative index scan**——ANN 边走边过滤,候选不够就继续从索引取,缓解 post-filter「取空」;还有 **partial index**(`CREATE INDEX ... WHERE department='HR'`)给高频过滤值各建小索引。
- **Milvus**:标量字段建标量索引,filtered search 时把过滤**下推**到 segment 级先裁剪;高基数过滤用 **partition**(按 department 物理分区,查询只碰相关分区)。
- **Qdrant**:招牌就是 **filterable HNSW**——把 payload 过滤条件编进图的连边,让「带过滤的图搜索」不退化。这也是它在这题上是好教材的原因。

设计轴记一句:**过滤选择性高(留下很少)→ 倾向 pre-filter / partition;选择性低(留下很多)→ 倾向 post-filter + over-fetch。** 没有银弹,看数据分布。

---

## §6 运维与并发(高并发在这)

### 写入、删除、reindex

- **新增** chunk = 插一行 + 把它接进 HNSW 图(改邻居)/ 归簇。HNSW 增量插入要改图,**写放大**明显;IVF 大改一般攒批重建更划算。
- **删除** chunk:多数引擎不真删,先打 **tombstone(软删除标记)**,查询时跳过,后台再 compaction 真清。所以「删了为什么磁盘没掉、召回偶尔还命中旧的」——就是还没 compaction。
- **reindex**:换 embedding 模型 / 维度变了 / 参数大改 / 软删堆积导致图退化时,要重建。生产做法是**影子索引**:新索引在旁边建好 → 切流量 → 删旧的,避免停服。

### 并发与横向扩展(面试问「向量库怎么扛高并发」)

- **pgvector = 借 Postgres 的并发栈**:MVCC 让读写不互锁,连接池(PgBouncer)管住连接数,**读副本**横向扩查询 QPS。但——**没有原生分片**:单实例内存 / CPU 是上限,十亿级或超高写入要 Citus 或手动 sharding,运维变重。**这就是它的天花板。**
- **Milvus = 生来分布式**:proxy 接入层 + query / data / index 多类 worker node + 对象存储(放数据)+ etcd(放元数据)+ 消息队列(写日志)。**compute / storage 分离**:查询慢加 query node、写入大加 data node、建索引重加 index node,各自独立横向扩。这是它扛高并发、上十亿的根本,也是它运维复杂的根本。

一句话对照:**pgvector 靠「一台强机器 + 读副本」(纵向为主),Milvus 靠「一堆节点分片」(横向为主)。** 这正是「什么规模该从 pgvector 迁到 Milvus」的判断依据:**当单机装不下索引、或写入 / QPS 顶满单机时。**

---

## §7 选型:pgvector ↔ Qdrant ↔ Milvus

| | pgvector | Qdrant | Milvus |
|---|---|---|---|
| 形态 | Postgres 扩展 | Rust 单二进制 | 分布式集群 |
| 甜区规模 | ≤ 千万 | 百万~亿 | 亿~十亿 |
| 横向分片 | 无(靠 Citus) | 有(分布式模式) | 原生强 |
| 运维成本 | 最低(已有 PG) | 低(一个进程) | 高(多组件) |
| 过滤 | iterative scan / partial index | filterable HNSW(强) | 标量索引 + partition |
| 本地起步 | 已有 Postgres | 单 docker | Milvus Lite(一个文件) |
| 逃生票 | 极好(就是 PG) | 好(自托管简单) | 好(开源)但迁移重 |

选型心法:

- **检索不是关键路径、规模不大** → 直接 **pgvector**,别引新组件。团队已会 Postgres,**这就是最好的逃生票**:无新依赖,备份 / 权限 / 运维全复用。
- **检索是核心、规模中等、要强过滤** → **Qdrant**,自托管最简单,filterable HNSW 省心。
- **十亿级 / 超高 QPS / 要独立扩查询和写入** → **Milvus**,认它的运维复杂度。但**别为了「听起来生产级」在百万规模上来就 Milvus**——那是过度工程。
- **迁移成本**:三家都能放进 LangChain 同一个 `VectorStore` 接口后面,换库主要改 ingestion 和 index 配置,检索 API 基本不动。所以「先 pgvector 起步、大了再换」是低风险路径——**接口隔离好,逃生票才成立**。

---

## §8 面试 8 问

1. **一个 chunk 在向量库里到底存了什么?** → `(id, 原文, metadata, 向量)` 一行;原文和向量都存,向量不可逆、只用来找,原文用来给 LLM 读。
2. **不建索引能检索吗?** → 能,brute-force 全表算距离,O(N),**精确**;小库反而该用它(`FLAT` / `IndexFlat`),是召回 baseline。
3. **建了向量索引为什么结果会变?** → ANN 用精度换速度,HNSW / IVF 给的是近似 top-k,会漏;召回率损失是**有意的取舍**。
4. **HNSW 和 IVF-PQ 区别 / 怎么选?** → 图 vs 倒排桶+量化;HNSW 召回高吃内存(千万级),IVF-PQ 省内存(十亿级,PQ 有损)。
5. **ef_search / nprobe 是干嘛的?** → 查询期「召回 vs 延迟」旋钮,不重建索引就能调准度。
6. **加 metadata 过滤为什么召回 / 性能塌陷?** → ANN 结构按全量建、不认过滤;post-filter 取空、pre-filter 退化暴力;靠 iterative scan / partition / filterable-HNSW 救。
7. **向量库怎么扛高并发?pgvector 够吗?** → pgvector 借 PG 的 MVCC + 读副本扛 QPS 但**无原生分片**;高并发到分片规模换 Milvus(原生分布式、compute/storage 分离)。
8. **为什么不直接 pgvector 就好?** → 够小就该用它(最好的逃生票);天花板是无原生分片,单机装不下索引或写入顶满时才迁。

---

## §9 回到主线

你现在能把 02 那句被 defer 的「不必先背参数」完整展开了:一个 chunk 怎么存、怎么被 brute-force 找、ANN 怎么用精度换速度、过滤为什么塌、高并发怎么靠分片扩。

回到 [`rag-roadmap.md`](../../rag-roadmap.md) **阶段 2**,你应该能在白板上画出「一行的结构 + HNSW 一次搜索路径 + 过滤塌陷」,并答出上面 8 问。

下一步沿主线走 **阶段 3** → [Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md):候选召回之后,怎么排得更准。
