from langchain_core.tools import StructuredTool

from mvp_agentic_rag.retrieval.types import RetrievedChunk


def _format(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "未在知识库中找到相关内容。"
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[{i}] (来源: {c.doc_id}#chunk{c.chunk_idx})\n{c.content}")
    return "\n\n".join(lines)


def make_retrieve_kb_tool(retriever) -> StructuredTool:
    def retrieve_kb(query: str) -> str:
        """搜索企业知识库,返回最相关的若干片段(含来源标注)。
        当用户的问题需要依据内部文档/知识库回答时调用。"""
        return _format(retriever.retrieve(query))

    return StructuredTool.from_function(
        func=retrieve_kb,
        name="retrieve_kb",
        description=(
            "搜索企业知识库,返回最相关片段(含来源标注)。"
            "当问题需要依据内部文档回答时调用。"
        ),
    )
