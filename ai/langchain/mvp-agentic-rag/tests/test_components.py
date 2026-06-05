from mvp_agentic_rag.retrieval.types import RetrievedChunk
from tests.fakes import FakeLLM


def _chunk(i, content):
    return RetrievedChunk(id=i, doc_id="d", chunk_idx=i, content=content, metadata={})


def test_llm_router_returns_decision():
    from mvp_agentic_rag.agent.components import LLMRouter, RouteDecision

    router = LLMRouter(FakeLLM(structured_value=RouteDecision(next="kb_rag")))
    assert router.route([]) == "kb_rag"


def test_llm_doc_grader_returns_bool():
    from mvp_agentic_rag.agent.components import LLMDocGrader, GradeDecision

    grader = LLMDocGrader(FakeLLM(structured_value=GradeDecision(relevant=True)))
    assert grader.grade("q", [_chunk(1, "c")]) is True


def test_llm_query_rewriter_returns_text():
    from mvp_agentic_rag.agent.components import LLMQueryRewriter

    rw = LLMQueryRewriter(FakeLLM(text="rephrased query"))
    assert rw.rewrite("orig") == "rephrased query"


def test_llm_answer_generator_returns_text():
    from mvp_agentic_rag.agent.components import LLMAnswerGenerator

    gen = LLMAnswerGenerator(FakeLLM(text="answer [1]"))
    assert gen.generate("q", [_chunk(1, "c")]) == "answer [1]"


def test_llm_grounding_checker_returns_bool():
    from mvp_agentic_rag.agent.components import LLMGroundingChecker, GroundingDecision

    g = LLMGroundingChecker(FakeLLM(structured_value=GroundingDecision(grounded=False)))
    assert g.check("ans", [_chunk(1, "c")]) is False
