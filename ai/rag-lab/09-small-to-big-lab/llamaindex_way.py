"""用 LlamaIndex 现成的 AutoMergingRetriever 做同一件事。

对照 retrievers.py 里手写的 portable_small_to_big：思路一模一样
（小块检索 → 同节命中够多就上卷父块），只是这里用框架封装好的件。

只在 bge 模式下被 run.py 调用；需要：
  pip install llama-index llama-index-embeddings-huggingface
"""

from chunking import Chunk


def run_llamaindex(docs, queries, k):
    from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
    from llama_index.core.retrievers import AutoMergingRetriever
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    # 用和裸实现相同的 bge 模型；关掉 LLM，避免 llama-index 默认去连 OpenAI
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
    Settings.llm = None

    # 每个 doc 拼成一篇全文，交给层级 parser 自己切大/中/小块
    li_docs = []
    for doc in docs:
        parts = []
        for sec in doc["sections"]:
            parts.append(sec["heading"] + "\n" + "\n".join(sec["paras"]))
        li_docs.append(Document(text="\n\n".join(parts), doc_id=doc["doc_id"]))

    # chunk_sizes 是 token 数（降序）。这组让叶子≈段落级（小块），父块≈整节，
    # 正好对应 small-to-big。语料更大时按文档结构往上调。
    parser = HierarchicalNodeParser.from_defaults(chunk_sizes=[256, 128, 64])
    nodes = parser.get_nodes_from_documents(li_docs)
    leaf_nodes = get_leaf_nodes(nodes)

    storage_context = StorageContext.from_defaults()
    storage_context.docstore.add_documents(nodes)

    index = VectorStoreIndex(leaf_nodes, storage_context=storage_context)
    base_retriever = index.as_retriever(similarity_top_k=k * 3)
    retriever = AutoMergingRetriever(base_retriever, storage_context, verbose=False)

    results = []
    for q in queries:
        nodes_out = retriever.retrieve(q)
        chunks = [
            Chunk(id="li", text=n.get_content(), doc_id="", section_id="", kind="li")
            for n in nodes_out[:k]
        ]
        results.append(chunks)
    return results
