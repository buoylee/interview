from mvp_agentic_rag.agent.tools import make_retrieve_kb_tool
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class StubRetriever:
    def retrieve(self, query: str):
        return [
            RetrievedChunk(
                id=1, doc_id="guide.md", chunk_idx=0,
                content="autoscaling uses HPA", metadata={},
            )
        ]


def test_retrieve_kb_tool_formats_with_citation():
    tool = make_retrieve_kb_tool(StubRetriever())

    out = tool.invoke({"query": "autoscaling"})

    assert "autoscaling uses HPA" in out
    assert "guide.md" in out  # 引用来源


def test_retrieve_kb_tool_has_name_and_description():
    tool = make_retrieve_kb_tool(StubRetriever())
    assert tool.name == "retrieve_kb"
    assert tool.description
