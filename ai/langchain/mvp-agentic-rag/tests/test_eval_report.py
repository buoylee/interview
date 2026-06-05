from mvp_agentic_rag.eval.checks import CaseResult
from mvp_agentic_rag.eval.runner import CaseEval, EvalReport
from mvp_agentic_rag.eval.report import to_json, to_markdown, diff_reports


def _report(pass_c1=True):
    return EvalReport([
        CaseEval("c1", CaseResult(pass_c1, True, True, True), "a1", "kb_rag"),
        CaseEval("c2", CaseResult(True, True, True, True), "a2", "web"),
    ])


def test_to_json_shape():
    j = to_json(_report())
    assert j["pass_rate"] == 1.0
    assert j["cases"]["c1"]["passed"] is True


def test_to_markdown_contains_summary():
    md = to_markdown(_report())
    assert "pass_rate" in md.lower() or "通过率" in md
    assert "c1" in md


def test_diff_detects_regression():
    prev = to_json(_report(pass_c1=True))
    curr = to_json(_report(pass_c1=False))
    regressions = diff_reports(prev, curr)
    assert "c1" in regressions  # 之前过、现在挂 → 回归
