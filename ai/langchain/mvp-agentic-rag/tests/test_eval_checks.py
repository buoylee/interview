from mvp_agentic_rag.eval.checks import (
    check_must_include, check_route, check_citations, check_refusal, CaseResult,
)


def test_must_include():
    assert check_must_include("HPA scales pods by CPU", ["HPA", "CPU"]) is True
    assert check_must_include("HPA scales pods", ["HPA", "CPU"]) is False
    # case-insensitive contract: uppercase term should match lowercase answer
    assert check_must_include("we use hnsw index", ["HNSW"]) is True


def test_route():
    assert check_route("kb_rag", "kb_rag") is True
    assert check_route("web", "kb_rag") is False
    assert check_route("anything", None) is True  # 不指定则跳过


def test_citations():
    cits = [{"doc_id": "k8s.md"}, {"doc_id": "pg.md"}]
    assert check_citations(cits, ["k8s.md"]) is True
    assert check_citations(cits, ["missing.md"]) is False
    assert check_citations([], None) is True


def test_refusal():
    assert check_refusal("未找到足够依据,无法回答(依据不足)。", should_refuse=True) is True
    assert check_refusal("HPA scales pods", should_refuse=False) is True
    assert check_refusal("HPA scales pods", should_refuse=True) is False


def test_case_result_passed():
    ok = CaseResult(must_include_ok=True, route_ok=True, citation_ok=True, refusal_ok=True)
    bad = CaseResult(must_include_ok=False, route_ok=True, citation_ok=True, refusal_ok=True)
    assert ok.passed is True
    assert bad.passed is False
