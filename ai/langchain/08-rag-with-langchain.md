# 第4章：RAG with LangChain — 用 LangChain 构建检索增强生成

> 你已在 Part 1 学过 RAG 原理，本章聚焦于 **用 LangChain 组件实现 RAG**，将理论落地为代码。

---

## 一、LangChain RAG 组件全景

```
文档 → DocumentLoader → TextSplitter → Embeddings → VectorStore
                                                         ↓
用户 Query → Retriever → (Reranker) → Prompt + Context → LLM → 回答
```

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

---

## 三、TextSplitter — 文档分块

### 3.1 RecursiveCharacterTextSplitter (推荐默认)

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

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

### 3.2 按 Token 分块

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

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

## 八、RAG 评估

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

## 九、练习任务

### 基础练习
- [ ] 加载一个 PDF，分块，存入 Chroma，实现最简 RAG
- [ ] 用 `similarity_search_with_score()` 查看检索结果的相关性分数
- [ ] 比较不同 chunk_size (256, 512, 1024) 的效果

### 进阶练习
- [ ] 实现 EnsembleRetriever (BM25 + 向量混合检索)
- [ ] 用 MultiQueryRetriever 实现多查询检索
- [ ] 实现带历史的对话式 RAG

### 面试模拟
- [ ] 画完整的 RAG 数据流 (从文档加载到生成回答)
- [ ] 比较不同 Retriever 策略的优劣
- [ ] 解释 chunk_size 和 chunk_overlap 的设置策略

---

> **本章掌握后，你应该能**：用 LangChain 组件实现完整的 RAG Pipeline，使用高级检索策略，并评估 RAG 效果。
