# 第4章：RAG with LangChain — 用 LangChain 构建检索增强生成

> 你已在 Part 1 学过 RAG 原理，本章聚焦于 **用 LangChain 组件实现 RAG**，将理论落地为代码。

---

## 一、LangChain RAG 组件全景

```
文档 → DocumentLoader → TextSplitter → Embeddings → VectorStore
                                                         ↓
用户 Query → (Query Transform) → Retriever → (Reranker) → Prompt + Context → LLM → 回答
```

> 带括号的 `(Query Transform)` / `(Reranker)` 是**可选**节点。`Query Transform` = 检索前对 query 的上下文消解 / 改写,要不要做、怎么做见 [第八节](#八query-transformation--用户原始-query-要不要重写);`Reranker` = 检索后对结果重排。

### 1.1 组件对应关系

| RAG 环节 | LangChain 组件 | 常用实现 |
|----------|---------------|----------|
| 文档加载 | `DocumentLoader` | PyPDFLoader, WebBaseLoader, TextLoader |
| 文档分块 | `TextSplitter` | RecursiveCharacterTextSplitter |
| 向量化 | `Embeddings` | OpenAIEmbeddings, HuggingFaceEmbeddings |
| 向量存储 | `VectorStore` | Chroma, FAISS, Qdrant, Pinecone |
| 检索 | `Retriever` | VectorStoreRetriever, MultiQueryRetriever |
| 生成 | `ChatModel + Prompt` | ChatOpenAI + ChatPromptTemplate |

---

## 二、Document & DocumentLoader

### 2.1 Document 对象

```python
from langchain_core.documents import Document

# Document = 页内容 + 元数据
doc = Document(
    page_content="LangChain 是一个 LLM 应用框架...",
    metadata={
        "source": "langchain_docs.pdf",
        "page": 1,
        "author": "LangChain Team",
    }
)
```

**Document 内部到底装了什么(别靠猜):** 它是个 Pydantic 对象,核心**只有两个字段**——

- **`page_content: str`** —— 这块文本的**纯字符串**内容。注意:**这里永远是字符串,不存向量**。向量(embedding)是后面灌进向量库时**另算、另存**的(见 [五、VectorStore](#五vectorstore--向量存储)),向量库内部维护「向量 ↔ Document」的映射,**Document 对象本身从头到尾不带向量**。
- **`metadata: dict`** —— 一个随你塞的字典。常见键由上游决定:Loader 放 `source`/`page`/`row`,Splitter 可加 `start_index`,你也能手动补 `author`/`category` 等业务字段。

(另有两个基本不用管的字段:可选的 `id`、固定的 `type="Document"`,序列化时才用到。)

**`metadata` 是 chunk 的「身份证」——RAG 能做引用溯源全靠它。** 它在整条管道里**一路不丢**:Loader 写入 → Splitter 复制给每个块 → 向量库连同向量一起存 → 检索回来的 `Document` 仍带着它。所以最后你能对每段 context 反查「出自哪个文件、第几页」(见 [6.1 的 `format_docs`](#61-最简-rag) 怎么把 `source` 拼进答案),也能拿它做检索过滤(见 [8.3 的 Self-Query](#83-第二类查询变换--可选的质量优化))。一句话:**metadata 是「溯源 + 过滤」一物两用,是 RAG 比裸 LLM 更可信的根基**——前提是你在加载/切块阶段把这些信息保留进去了。

### 2.2 常用 Loader

```python
# PDF
from langchain_community.document_loaders import PyPDFLoader
loader = PyPDFLoader("document.pdf")
docs = loader.load()  # list[Document], 每页一个 Document

# 网页
from langchain_community.document_loaders import WebBaseLoader
loader = WebBaseLoader("https://python.langchain.com/docs/")
docs = loader.load()

# Markdown
from langchain_community.document_loaders import UnstructuredMarkdownLoader
loader = UnstructuredMarkdownLoader("README.md")
docs = loader.load()

# CSV
from langchain_community.document_loaders.csv_loader import CSVLoader
loader = CSVLoader("data.csv")
docs = loader.load()  # 每行一个 Document

# 目录批量加载
from langchain_community.document_loaders import DirectoryLoader
loader = DirectoryLoader("./docs/", glob="**/*.md")
docs = loader.load()
```

### 2.3 面试要点

> **Q: DocumentLoader 的 load() 和 lazy_load() 有什么区别？**
>
> A: `load()` 一次性加载所有文档到内存，适合小文件；`lazy_load()` 返回迭代器，逐个文档处理，**大文件/大目录必须用 lazy_load()** 避免 OOM。

> 📖 **深入**：`DocumentLoader` 只是把各种格式统一成 `Document` 的**薄包装层**。文档解析本身(PDF 文字层 vs 扫描件、表格逆向重建、OCR vs 视觉大模型、各格式选型与本地/API 取舍)是一门独立学问,见 [文档解析与提取 — 面试笔记](../document-parsing/文档解析-面试笔记.md)。

---

## 三、TextSplitter — 文档分块

### 3.1 RecursiveCharacterTextSplitter (推荐默认)

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter  # v1.x：独立包 langchain_text_splitters（旧的 langchain.text_splitter 已移除）

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,       # 每个块最多 500 字符
    chunk_overlap=50,     # 块之间重叠 50 字符 (保留上下文)
    separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],  # 分隔符优先级
    length_function=len,  # 用字符数计算长度
)

chunks = splitter.split_documents(docs)
print(f"原始 {len(docs)} 个文档 → 分成 {len(chunks)} 个块")
```

**分隔符优先级**：先尝试按段落 `\n\n` 分，分不完按行 `\n`，再按句号，最后按字符。

**`chunks` 是什么、从哪来(顺着上一步看):** `split_documents(docs)` 的输入 `docs` 和输出 `chunks` **是同一种类型——都是 `list[Document]`**。切块只是把「每页/每文件一个」的粗粒度 `Document`,切成「每段 ~500 字符一个」的细粒度 `Document`:粒度变细,类型不变。两个关键细节:

- **metadata 会自动从父文档复制到每个 chunk**:切完之后每个 chunk 仍然知道自己「来自哪个文件、哪一页」——这就是上面 [2.1 溯源](#21-document-对象) 能成立的原因。想再精确到「这段在原文的第几个字符」,给 splitter 加 `add_start_index=True`,它会往每个 chunk 的 metadata 写 `start_index`。
- **检索的最小单位是 chunk,不是原始 docs**:之后无论灌进向量库还是 BM25(见 [七](#七高级-retriever)),装进检索库的都是这批 `chunks`。

> ⚠️ **一个命名坑**:`docs` 这个名字在 RAG 代码里被复用了两次,初学很容易绕晕——Loader 刚加载出来的叫 `docs`(全部原文),而检索器返回的结果**也常被命名为 `docs`**(`docs = retriever.invoke(q)`)。但后者其实是 `chunks` 的一个**子集**:检索器从「全部 chunks」里挑出跟 query 最相关的 top-k 个 `Document` 还给你。所以 `len(chunks)` 可能是几千,`len(检索回来的 docs)` 就是 `k`(比如 5)。**两者结构完全一样(都是 `list[Document]`),差别只是「全部」vs「这次命中的几个」。**

### 3.2 按 Token 分块

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter  # v1.x：独立包 langchain_text_splitters（旧的 langchain.text_splitter 已移除）

splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",  # OpenAI 的编码器
    chunk_size=256,               # 256 tokens
    chunk_overlap=32,
)
```

### 3.3 语义分块 (高级)

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

splitter = SemanticChunker(
    OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile",
)
chunks = splitter.split_documents(docs)
```

### 3.4 面试高频

> **Q: chunk_size 和 chunk_overlap 怎么设？**
>
> A: **chunk_size**: 推荐 400-512 tokens (或 500-1000 字符)。太小丢失上下文，太大引入噪声。研究表明 ~2500 tokens 有 "上下文悬崖"。**chunk_overlap**: 一般设为 chunk_size 的 10-20%。overlap 的目的是让跨块的语句不被截断。对于代码，可以适当增大 overlap。
>
> 这几个数字的来历(避免误读):
>
> - **512 是实测甜区,不是拍脑袋**：原理上 embedding 把整块文本压成一个向量,块越长语义被平均稀释、检索越不准；实测上 2026 基准里 recursive 512-token 分块准确率最高 (~69%)。"500-1000 字符" 和 "400-512 tokens" 是同一区间的两种度量 (英文 ~4 字符/token)。
> - **2500 是"上限警告",不是推荐值**：上下文越长检索反而越退化 (context rot,和 "lost in the middle" 同源),所以它解释的是"为什么别把 chunk_size 设大",别误当成可选块大小。
> - **没有唯一最优,看 query 类型**：事实型问答偏小块 (128-256,要精准),推理/总结偏大块 (512+,要完整)。上面的推荐值是默认起点。
> - **overlap 10-20% 是工程惯例**：纯粹为了接住压在边界的句子,没论文严格证明这个比例；太大只会重复内容、浪费索引和 context。

---

## 四、Embeddings — 向量化

### 4.1 常用模型

```python
# OpenAI (最简单)
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 本地 HuggingFace 模型
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-large-zh-v1.5")

# 使用
vector = embeddings.embed_query("什么是 LangChain?")
print(f"维度: {len(vector)}")  # 1536 (text-embedding-3-small)

vectors = embeddings.embed_documents(["文档1", "文档2", "文档3"])
```

---

## 五、VectorStore — 向量存储

### 5.1 Chroma (开发推荐)

```python
from langchain_community.vectorstores import Chroma

# 创建并填充
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=OpenAIEmbeddings(),
    persist_directory="./chroma_db",  # 持久化到磁盘
)

# 相似度搜索
results = vectorstore.similarity_search("什么是 RAG?", k=5)
for doc in results:
    print(f"[{doc.metadata.get('source')}] {doc.page_content[:100]}")

# 带分数的搜索
results = vectorstore.similarity_search_with_score("什么是 RAG?", k=5)
for doc, score in results:
    print(f"Score: {score:.4f} | {doc.page_content[:50]}")
```

### 5.2 FAISS (高性能本地)

```python
from langchain_community.vectorstores import FAISS

vectorstore = FAISS.from_documents(chunks, OpenAIEmbeddings())

# 保存/加载
vectorstore.save_local("./faiss_index")
vectorstore = FAISS.load_local("./faiss_index", OpenAIEmbeddings())
```

### 5.3 转为 Retriever

#### 先搞清楚: Retriever 是什么

**Retriever 是一个接口(抽象),契约只有一条: 吃一个 query 字符串, 吐一组 `Document`。**

```python
docs: list[Document] = retriever.invoke("什么是 RAG?")
```

类比 Java, 它就是个 `interface Retriever { List<Document> invoke(String query); }`。**背后用什么实现它不在乎**——可以是向量库、BM25 关键词检索、Web 搜索, 甚至查 SQL。这就是为什么本章第七节那一堆 `MultiQueryRetriever / EnsembleRetriever / ParentDocumentRetriever` 能随意替换: 它们都实现同一个接口, 对你的 chain 来说长得一模一样。

#### VectorStore 和 Retriever 的关系

- **`VectorStore`** = 真正存向量的库, 功能多(增删改查、带分数搜索、MMR…)
- **`Retriever`** = 在它外面套的一层**最小统一接口**(只剩 `invoke(query) → docs`)
- **`as_retriever()`** = 「把这个胖库, 包成那个瘦接口」

**为什么要包一层?** 因为 LCEL 管道只认 `Runnable`(`invoke` 进、`invoke` 出)。`VectorStore` 接口太胖塞不进管道, 削成 `Retriever` 这个标准形状才能接进 `retriever | format_docs | ...`。

#### Retriever vs Tool (面试爱问)

两者都是「给 LLM 补充外部信息」, 但**决策权和时机不同**:

| | Retriever | Tool |
|---|---|---|
| 谁决定要不要用 | **你**(写死在 chain 里, 每次必检索) | **LLM**(自己判断要不要调、调哪个) |
| 在流程里的位置 | LLM **之前**(先检索, 结果塞进 prompt) | LLM **之中/之后**(LLM 先开口要, 你再执行) |
| 典型形态 | RAG 的固定一步 | Agent 手里的一件武器 |
| 接口契约 | `str → list[Document]` | `结构化参数 → 任意结果` |

一句话: **Retriever 是「我替 LLM 提前查好资料」, Tool 是「LLM 自己说它要查, 我照办」**。RAG 用前者, Agent 用后者, Agentic RAG 把检索也包成 Tool 交给 LLM 决定。

#### 用法

```python
# VectorStore → Retriever (在 LCEL 链中使用)
retriever = vectorstore.as_retriever(
    search_type="similarity",      # 或 "mmr" (最大边际相关性)
    search_kwargs={
        "k": 5,                    # 返回 5 个结果
        "score_threshold": 0.7,    # 最低相关性阈值
    }
)

# Retriever 是 Runnable, 可以直接在 LCEL 中使用
docs = retriever.invoke("什么是 RAG?")
```

---

## 六、完整 RAG Chain

### 6.1 最简 RAG

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 1. 构建向量存储 (假设已有 chunks)
vectorstore = Chroma.from_documents(chunks, OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 2. 格式化检索结果
def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[来源: {d.metadata.get('source', '未知')}]\n{d.page_content}"
        for d in docs
    )

# 3. Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个知识问答助手。基于以下检索到的上下文回答用户问题。
如果上下文中没有相关信息，请明确说 "根据现有资料无法回答"，不要编造。

上下文:
{context}"""),
    ("human", "{question}"),
])

# 4. 组合 Chain
llm = ChatOpenAI(model="gpt-4o", temperature=0)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 5. 使用
answer = rag_chain.invoke("什么是 LangChain?")
print(answer)
```

### 6.2 带历史的 RAG (Conversational RAG)

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", """基于上下文回答问题。

上下文: {context}"""),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

# 需要把历史消息和当前问题一起传入
rag_chain = (
    RunnablePassthrough.assign(
        context=lambda x: format_docs(retriever.invoke(x["question"]))
    )
    | prompt
    | llm
    | StrOutputParser()
)

result = rag_chain.invoke({
    "question": "它支持哪些模型？",
    "history": [
        ("human", "什么是 LangChain？"),
        ("ai", "LangChain 是一个 LLM 应用开发框架..."),
    ],
})
```

---

## 七、高级 Retriever

### 7.1 MultiQueryRetriever — 多查询检索

```python
from langchain.retrievers.multi_query import MultiQueryRetriever

# LLM 自动生成多个查询变体，合并检索结果
multi_retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(),
    llm=ChatOpenAI(temperature=0),
)

# "什么是 RAG?" → LLM 生成:
# - "RAG 的定义是什么?"
# - "检索增强生成的原理?"
# - "RAG 如何工作?"
# 分别检索，合并去重
docs = multi_retriever.invoke("什么是 RAG?")
```

### 7.2 EnsembleRetriever — 混合检索

```python
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# BM25 (关键词检索)
bm25_retriever = BM25Retriever.from_documents(chunks, k=5)

# 向量检索
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 混合 (RRF 融合)
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.4, 0.6],  # BM25 权重 0.4, 向量权重 0.6
)

docs = ensemble_retriever.invoke("LangChain LCEL 管道符")
# BM25 擅长精确匹配 "LCEL"
# 向量擅长语义匹配 "管道符"
# 混合效果最好
```

> **为什么 `BM25Retriever.from_documents(chunks)` 直接吃 chunks,不像向量检索那样「先 `from_documents` 进库、再 `as_retriever()`」?** 因为 BM25 是**自包含的内存检索器**——它内部直接把 chunks 建成一个**内存倒排索引**(底层是 `rank_bm25`:记录「词 → 哪些 chunk 出现过、词频多少」),chunks 本身也存在这个对象里。换句话说 **`BM25Retriever` 自己就是那个「库」**,没有独立的外部 DB,所以 chunks 直接喂给它就行。这正是 [5.3](#53-转为-retriever) 说的「Retriever 背后用什么实现它不在乎」的一个具体例子:向量检索是「胖库 + `as_retriever()` 薄包装」**两个对象**,BM25 把存储和查询揉成了**一个对象**。
>
> 内存版只适合小语料(几千~几万 chunk)。真上量、要持久化和分布式时,关键词检索会换成 **Elasticsearch / OpenSearch**(那才是真 DB),配 `ElasticsearchRetriever`——此时就回到「chunks 写进 DB → retriever 从 DB 撈」的标准模型了。

### 7.3 ContextualCompressionRetriever — 上下文压缩

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

compressor = LLMChainExtractor.from_llm(llm)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=retriever,
)

# 检索到的文档会被 LLM 压缩，只保留与 query 相关的部分
docs = compression_retriever.invoke("什么是 LCEL?")
```

### 7.4 ParentDocumentRetriever — 父文档检索

```python
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore

# 用小块检索，返回大块 (父文档)
store = InMemoryStore()
parent_retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=store,
    child_splitter=RecursiveCharacterTextSplitter(chunk_size=200),
    parent_splitter=RecursiveCharacterTextSplitter(chunk_size=1000),
)
parent_retriever.add_documents(docs)
```

---

## 八、Query Transformation — 用户原始 query 要不要重写?

> 这是 RAG 里 junior 和 senior 的一道分水岭。坑在于「要不要重写」这个提法本身——它把两件性质完全不同的事混成了一个开关。拆开之后答案立刻清晰。

### 8.1 先拆概念:「重写」其实是两类东西

| | 第一类:**上下文消解** (contextualization / condensation) | 第二类:**查询变换** (query transformation) |
|---|---|---|
| 解决的问题 | 多轮对话里,follow-up 句子离开上下文就没法用 | 单句 query 和语料「不在同一个语言空间」 |
| 例子 | 「它支持退款吗?」→「ProductX 支持退款吗?」 | 「登不上去」→ 同时检索「认证失败 / token 过期 / 401」 |
| 性质 | **近乎必须做**(chat RAG 的刚需) | **可选的质量优化**(有明确成本) |
| 风险 | 低(只补指代,不改意图) | 中高(改写器会扭曲意图) |

> 你纠结的「要不要重写」，把这两个混在一起了。一旦拆开：**第一类多轮场景下几乎一定要做；第二类是有成本的优化，按需上。**

### 8.2 第一类:上下文消解 — 多轮场景的刚需

**为什么是刚需(底层原因):** embedding 是对「整句话的语义」做向量化。当用户问「**它**的价格呢?」,这句话单独拿去 embed,向量落在一个语义极模糊的位置(「它」是谁?),检索结果基本是噪声。

所以在把 query 丢进 retriever **之前**,必须拿「对话历史 + 当前句」让 LLM 先还原成一个**独立可理解的问句**(standalone question)。这一步的核心逻辑只有一句话:

```python
from langchain.chains import create_history_aware_retriever  # 经典 helper;现代写法可在 LangGraph 节点里手写同样逻辑
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

condense_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "根据对话历史,把用户最后的问题改写成一个不依赖上下文、可独立理解的问题。"
     "只输出改写后的问题本身,不要回答它;如果本来就独立,原样返回。"),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# 电池版:内部逻辑 = 「有历史 → 先 condense 再检索;无历史 → 直接检索」
history_aware_retriever = create_history_aware_retriever(llm, retriever, condense_prompt)
```

> **注意那个隐含的 `if 有历史`**：第一轮没历史时**不该**白白多花一次 LLM 调用——`create_history_aware_retriever` 内部就帮你做了这个短路。这是常见的工程细节,手写时别漏。

**为什么这一类风险低:** 它只是「补全指代、接上下文」,不改变用户核心意图,出错空间小、收益巨大。所以它是 chat RAG 的标配(对应 [6.2 带历史的 RAG](#62-带历史的-rag-conversational-rag),那里是「把历史一起塞进生成 prompt」,这里是更前置的「把历史揉进检索 query」,两者经常同时存在)。

### 8.3 第二类:查询变换 — 可选的质量优化

核心痛点都是「原始 query 和文档的措辞对不上」。常见手法:

| 手法 | 一句话原理 | LangChain 对应 |
|------|-----------|---------------|
| **Multi-Query** | LLM 生成 N 种说法,各自检索取并集 | `MultiQueryRetriever`(见 [7.1](#71-multiqueryretriever--多查询检索)) |
| **HyDE** | 先编一个**假答案**,拿假答案去 embed 检索 | 手写 3 行 / `HypotheticalDocumentEmbedder` |
| **Decomposition** | 把多跳问题拆成子问题分别检索 | 自定义 chain |
| **Step-back** | 先退一步问一个更上位的问题补背景 | 自定义 prompt |
| **Self-Query** | 把自然语言里的过滤条件翻成结构化 metadata filter | `SelfQueryRetriever` |

**HyDE 的直觉很妙,值得单独讲**——为什么编个假答案反而更好检索?

```python
# HyDE 手写版:核心就是「先编一个假答案,拿假答案的向量去检索」
hyde_prompt = ChatPromptTemplate.from_template(
    "请直接写一段话回答下面的问题(不确定也照写,这段只用来检索、不会展示给用户):\n{question}"
)
generate_hypo = hyde_prompt | llm | StrOutputParser()

def hyde_retrieve(question: str, k: int = 5):
    hypo_doc = generate_hypo.invoke({"question": question})  # 假答案(可能有错,不要紧)
    return vectorstore.similarity_search(hypo_doc, k=k)       # 用假答案的向量去检索真文档
```

> 底层直觉:**一段假答案在向量空间里,比一个问句更靠近真正的答案文档**。因为「答案」和「答案」措辞相似,而「问句」和「答案」措辞天然有距离(疑问句 vs 陈述句)。HyDE 用一次 LLM 调用把 query「平移」到答案所在的语义区域,代价是假答案如果方向全错会把检索带偏。

**Self-Query** 则是另一条路——不扩写语义,而是把 query 里的**硬条件**抽出来变成 metadata 过滤:

```python
# "去年的财报怎么说?" → LLM 拆成: filter(year == 2025) + 语义检索("财报")
# 既精确(年份是硬过滤)又语义(财报走向量)
```

### 8.4 代价面:为什么不能无脑重写(senior 必讲)

每加一个第二类变换 = 至少一次**串行**、卡在检索前的 LLM 调用。代价具体是:

1. **意图漂移(最致命)**:改写器会「好心」地泛化或扭曲意图。用户问一个很具体的东西,被抹成一个宽泛问题,检索全跑偏。
2. **延迟**:检索前多一次 LLM 调用,几百 ms 到数秒,直接压在用户体感的关键路径上(multi-query 还是 N 倍)。
3. **成本**:LLM 调用数量翻倍甚至 N 倍。
4. **摧毁精确匹配信号**:用户要是输了个精确的**错误码 / SKU / 函数名**,改写很容易把那个关键 literal token「优化」没了——而这恰恰是 BM25/混合检索本来能精准命中的。

### 8.5 production 决策框架

> 面试时能显出层次的就是这一节——不是「上不上」,而是「按什么顺序、按什么条件上」。

1. **多轮 → 一定做上下文消解(8.2)**。这是底线,低风险高收益。
2. **第二类别无脑上**。先问:痛点到底是「召回不够」还是别的?很多时候 **混合检索 (dense + BM25) + 重排 (cross-encoder reranker)** 的提升,比花式改写更大、更稳、更便宜。**先上 reranker,再考虑改写。**(混合检索见 [7.2 EnsembleRetriever](#72-ensembleretriever--混合检索),它已经用 RRF 融合多路结果。)
3. **要改写就别丢掉原始 query**:原句 + 改写句**都拿去检索,结果用 RRF 融合**。这样即便改写跑偏,原句还能兜底,精确匹配信号也不丢——直接复用 `EnsembleRetriever` 的融合机制即可。
4. **用一个便宜的 router/分类器决定要不要重型改写**:简单 query 直接走,复杂 query 才进变换管线。别让每个 query 都付全套成本。
5. **一定要量化**:加任何一个改写阶段前后,测 `context_precision` / recall@k(就是下一节 [九、RAG 评估](#九rag-评估) 的指标)。凭感觉加阶段是 RAG 最常见的过度工程。

### 8.6 面试一句话版

> 「重写不是一个开关,是两件事:**对话上下文消解**在多轮场景是刚需、低风险、必做;**查询变换**(multi-query / HyDE / 分解)是有延迟和意图漂移代价的质量优化,要靠召回指标和路由按需开。而且我通常会先用混合检索 + reranker 把基本盘打稳,再考虑改写,并且永远保留原始 query 做 RRF 融合兜底。」

---

## 九、RAG 评估

```python
# 用 RAGAS 评估
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision],
)
print(result)
```

---

## 十、练习任务

### 基础练习
- [ ] 加载一个 PDF，分块，存入 Chroma，实现最简 RAG
- [ ] 用 `similarity_search_with_score()` 查看检索结果的相关性分数
- [ ] 比较不同 chunk_size (256, 512, 1024) 的效果

### 进阶练习
- [ ] 实现 EnsembleRetriever (BM25 + 向量混合检索)
- [ ] 用 MultiQueryRetriever 实现多查询检索
- [ ] 实现带历史的对话式 RAG
- [ ] 用 `create_history_aware_retriever` 做上下文消解,验证「它的价格呢?」能被改写成独立问句
- [ ] 手写 HyDE(假答案 → 检索),对比直接用原始 query 的召回差异

### 面试模拟
- [ ] 画完整的 RAG 数据流 (从文档加载到生成回答)
- [ ] 比较不同 Retriever 策略的优劣
- [ ] 解释 chunk_size 和 chunk_overlap 的设置策略
- [ ] 回答「用户原始 query 要不要重写?」——拆成上下文消解 vs 查询变换两类,并说清各自的代价与决策顺序(见第八节)

---

> **本章掌握后，你应该能**：用 LangChain 组件实现完整的 RAG Pipeline，使用高级检索策略，并评估 RAG 效果。
