from pathlib import Path

from mvp_agentic_rag.eval.dataset import load_golden

GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden" / "cases.jsonl"
SAMPLE_DOCS = Path(__file__).resolve().parents[1] / "sample_docs"


def test_golden_set_loads_and_has_enough_cases():
    cases = load_golden(str(GOLDEN))
    assert len(cases) >= 20


def test_golden_ids_unique():
    cases = load_golden(str(GOLDEN))
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))


def test_citation_docs_exist_in_corpus():
    for case in load_golden(str(GOLDEN)):
        for doc in case.expected_citation_docs or []:
            assert (SAMPLE_DOCS / doc).exists(), f"{case.id}: {doc} 不在语料里"


def test_must_include_terms_appear_in_cited_docs():
    """must_include 的词若指定了引用文档,至少要在该文档里出现过(否则正确答案不可能包含它)。"""
    for case in load_golden(str(GOLDEN)):
        if not case.must_include or not case.expected_citation_docs:
            continue
        corpus = "".join((SAMPLE_DOCS / d).read_text(encoding="utf-8") for d in case.expected_citation_docs)
        for term in case.must_include:
            assert term in corpus, f"{case.id}: must_include '{term}' 不在引用文档中"


def test_refusal_cases_have_no_kb_expectations():
    for case in load_golden(str(GOLDEN)):
        if case.should_refuse:
            assert not case.must_include and not case.expected_citation_docs
