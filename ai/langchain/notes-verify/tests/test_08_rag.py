"""校验 `ai/langchain/08-rag-with-langchain.md` 的关键声称。

RAG 拆开来,绝大部分是确定性、离线、无需 key 的机制 —— 分块、向量化、检索、
链形状。所以离线测试给得很厚,把面试必背的 RAG pipeline 每一环钉成可跑断言。
向量化全程用 langchain_core 内置的 DeterministicFakeEmbedding(同输入→同向量),
向量库用 InMemoryVectorStore,都不碰 OpenAIEmbeddings / Chroma / FAISS(那些要 key
或要装额外后端)。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制,确定性、无需 key、始终绿。
- live 测试(`@pytest.mark.live`):只保留假模型证明不了的 —— 真 LLM 接进 RAG 链,
  从检索到的上下文里答出来。无 OPENAI_API_KEY 时自动 skip。

跑法:
    uv run pytest tests/test_08_rag.py            # 仅离线
    uv run pytest tests/test_08_rag.py -m live    # 真实 OpenAI(需 key)

笔记纠偏(import 漂移):笔记 §3.1/§3.2/§7.4 写的
    from langchain.text_splitter import RecursiveCharacterTextSplitter
在 v1.x 已失效(ModuleNotFoundError: No module named 'langchain.text_splitter')。
正确路径是 `from langchain_text_splitters import RecursiveCharacterTextSplitter`。
笔记 §5 用 `from langchain_community.vectorstores import Chroma`,运行时还需另装
chromadb 后端;离线测试改用 langchain_core 内置 InMemoryVectorStore(机制等价、零依赖)。
"""

import pytest

# 笔记 §3.1 用 `from langchain.text_splitter import ...`,v1.x 已失效,见模块 docstring。
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

# 笔记 §4 用 OpenAIEmbeddings(要 key);离线用确定性假 embedding,同输入→同向量。
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

# 笔记 §5 用 Chroma(要装 chromadb);离线用 core 内置 InMemoryVectorStore,机制等价。
from langchain_core.vectorstores import InMemoryVectorStore


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §二 2.1 —— Document = page_content + metadata,两者都原样挂在对象上
def test_document_carries_content_and_metadata():
    doc = Document(
        page_content="LangChain 是一个 LLM 应用框架",
        metadata={"source": "langchain_docs.pdf", "page": 1},
    )
    assert doc.page_content == "LangChain 是一个 LLM 应用框架"
    assert doc.metadata == {"source": "langchain_docs.pdf", "page": 1}


# §三 3.1 —— RecursiveCharacterTextSplitter 切出的块:每块 <= chunk_size,
#            且相邻块共享 chunk_overlap 个字符的重叠(保上下文不被截断)
def test_recursive_splitter_honors_size_and_overlap():
    # 用无自然分隔符的纯字符串,逼 splitter 退到按字符切 —— 重叠边界完全确定
    text = "".join(chr(ord("A") + (i % 26)) for i in range(120))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=30, chunk_overlap=10, separators=[""]
    )
    chunks = splitter.split_text(text)

    assert len(chunks) > 1  # 120 字符、块 30 → 切成多块
    assert all(len(c) <= 30 for c in chunks)  # 没有块超过 chunk_size
    # 相邻块:前块末尾 10 字符 == 后块开头 10 字符(就是 overlap)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-10:] == nxt[:10]


# §三 3.1 —— split_documents 在切分时把每个块的 metadata 从源 Document 继承下来
def test_split_documents_preserves_metadata_and_returns_documents():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(90))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=30, chunk_overlap=5, separators=[""]
    )
    src = [Document(page_content=text, metadata={"source": "doc1", "page": 7})]
    chunks = splitter.split_documents(src)

    assert len(chunks) > 1
    assert all(isinstance(c, Document) for c in chunks)
    # 每个切出来的块都带着源文档的 metadata
    assert all(c.metadata == {"source": "doc1", "page": 7} for c in chunks)


# §三 3.1 —— CharacterTextSplitter 按单一 separator 合并切分;块控制在 chunk_size 内
def test_character_splitter_splits_on_separator():
    text = "句子一。句子二。句子三。句子四。句子五"
    splitter = CharacterTextSplitter(separator="。", chunk_size=8, chunk_overlap=0)
    chunks = splitter.split_text(text)

    assert len(chunks) > 1  # chunk_size=8 装不下整段,必被切开
    assert all(len(c) <= 8 for c in chunks)  # 每块 <= chunk_size


# §四 4.1 —— Embeddings 是确定性的:同一文本两次 embed_query 得到同一向量;
#            向量维度等于配置的 size;embed_documents 批量返回等长向量
def test_embeddings_are_deterministic_and_sized():
    emb = DeterministicFakeEmbedding(size=32)
    v1 = emb.embed_query("什么是 LangChain?")
    v2 = emb.embed_query("什么是 LangChain?")
    assert len(v1) == 32  # 维度 = size
    assert v1 == v2  # 同输入 → 同向量(确定性)

    vecs = emb.embed_documents(["文档1", "文档2", "文档3"])
    assert len(vecs) == 3  # 每个文档一个向量
    assert all(len(v) == 32 for v in vecs)


# §五 5.1 —— similarity_search(query, k) 返回 k 个 Document;
#            语义最近(此处构造为精确匹配)的那个排第一
def test_vectorstore_similarity_search_ranks_exact_match_first():
    emb = DeterministicFakeEmbedding(size=64)
    vs = InMemoryVectorStore(emb)
    texts = [
        "量子计算利用叠加态进行并行运算",
        "猫是一种常见的家养哺乳动物",
        "RAG 检索增强生成把外部知识注入 LLM",
        "今天天气晴朗适合出门散步",
    ]
    vs.add_texts(texts)

    target = "RAG 检索增强生成把外部知识注入 LLM"
    results = vs.similarity_search(target, k=2)
    assert len(results) == 2  # 返回正好 k 个
    assert all(isinstance(d, Document) for d in results)
    assert results[0].page_content == target  # 精确匹配排第一


# §五 5.1 —— similarity_search_with_score 额外带相关性分数;精确匹配分数最高
def test_similarity_search_with_score_returns_scores():
    emb = DeterministicFakeEmbedding(size=64)
    vs = InMemoryVectorStore(emb)
    vs.add_texts(["北京是中国的首都", "巴黎是法国的首都", "光合作用发生在叶绿体"])

    scored = vs.similarity_search_with_score("北京是中国的首都", k=3)
    assert len(scored) == 3
    docs, scores = zip(*scored)
    assert all(isinstance(d, Document) for d in docs)
    assert all(isinstance(s, float) for s in scores)
    # InMemoryVectorStore 用余弦相似度,分数越大越相关 → 已按降序;精确匹配排第一
    assert scores[0] == max(scores)
    assert docs[0].page_content == "北京是中国的首都"


# §五 5.3 —— vectorstore.as_retriever(search_kwargs={"k": k}) 是个 Runnable;
#            .invoke(query) 返回长度为 k 的 list[Document]
def test_retriever_is_runnable_returning_k_documents():
    emb = DeterministicFakeEmbedding(size=64)
    vs = InMemoryVectorStore(emb)
    vs.add_documents(
        [
            Document(page_content="LangChain 是 LLM 应用框架", metadata={"source": "a"}),
            Document(page_content="埃菲尔铁塔位于巴黎", metadata={"source": "b"}),
            Document(page_content="光合作用发生在叶绿体", metadata={"source": "c"}),
        ]
    )
    retriever = vs.as_retriever(search_kwargs={"k": 2})

    docs = retriever.invoke("LangChain 是 LLM 应用框架")  # Retriever 是 Runnable
    assert isinstance(docs, list)
    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)
    # metadata 一路从 add_documents 透到检索结果
    assert docs[0].metadata == {"source": "a"}


# §六 6.1 —— 完整 RAG 链形状端到端:
#   {"context": retriever | format_docs, "question": Passthrough} | prompt | model | StrOutputParser
#   两分支并行 —— context 走检索、question 透传原始问题;假模型让 LLM 那步可定。
def test_rag_chain_shape_end_to_end_offline():
    emb = DeterministicFakeEmbedding(size=64)
    vs = InMemoryVectorStore(emb)
    vs.add_documents(
        [
            Document(page_content="LangChain 是一个 LLM 应用开发框架", metadata={"source": "intro"}),
            Document(page_content="埃菲尔铁塔位于巴黎", metadata={"source": "geo"}),
        ]
    )
    retriever = vs.as_retriever(search_kwargs={"k": 1})

    def format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    # 先单独验证"上下文确实被检索进来 + 原问题被透传":dict 用 RunnableParallel 承载
    setup = RunnableParallel(
        context=retriever | format_docs,
        question=RunnablePassthrough(),
    )
    q = "LangChain 是一个 LLM 应用开发框架"
    routed = setup.invoke(q)
    assert "LangChain" in routed["context"]  # 检索把相关文档放进了 context
    assert routed["question"] == q  # Passthrough 把原始问题原样带到下一步

    # 整链接上 prompt + 假模型 + StrOutputParser,端到端跑出字符串
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "基于以下上下文回答问题。\n\n上下文:\n{context}"),
            ("human", "{question}"),
        ]
    )
    model = GenericFakeChatModel(messages=iter(["这是基于上下文的答案"]))
    rag_chain = setup | prompt | model | StrOutputParser()

    answer = rag_chain.invoke(q)
    assert isinstance(answer, str)  # StrOutputParser 把 AIMessage 解成 str
    assert answer == "这是基于上下文的答案"  # 假模型让结果完全可定


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §六 6.1 —— 真 LLM 接进 RAG 链,从"检索到的上下文"里答出问题。
#   向量化仍用假 embedding + InMemoryVectorStore,只有 LLM 那一步是真的 ——
#   验证假模型证明不了的:真模型确实读了注入的 context 并据此作答。
@pytest.mark.live
def test_live_rag_chain_answers_from_retrieved_context():
    from langchain_openai import ChatOpenAI

    emb = DeterministicFakeEmbedding(size=256)
    vs = InMemoryVectorStore(emb)
    # 埋一个只有上下文里才有的"暗号"事实,逼模型从 context 取答案,而非靠先验
    secret = "Zephyrine 是公司内部知识库系统,版本号是 7.3.1"
    vs.add_texts([secret, "苹果是一种水果", "巴黎是法国的首都"])
    retriever = vs.as_retriever(search_kwargs={"k": 3})

    def format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "只根据下面的上下文回答,不要编造。\n\n上下文:\n{context}"),
            ("human", "{question}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=32)
    rag_chain = (
        RunnableParallel(context=retriever | format_docs, question=RunnablePassthrough())
        | prompt
        | llm
        | StrOutputParser()
    )

    answer = rag_chain.invoke("Zephyrine 的版本号是多少?")
    assert isinstance(answer, str)
    assert answer.strip()
    assert "7.3.1" in answer  # 版本号只在检索注入的 context 里出现 → 证明答自 context
