from mvp_agentic_rag.eval.dataset import GoldenCase
from mvp_agentic_rag.eval.runner import run_eval, EvalReport


def _cases():
    return [
        GoldenCase(id="c1", question="autoscaling?", must_include=["HPA"],
                   expected_route="kb_rag", expected_citation_docs=["k8s.md"]),
        GoldenCase(id="c2", question="secret?", must_include=[], should_refuse=True),
    ]


def good_runner(question):
    if "autoscaling" in question:
        return {"answer": "HPA scales pods", "route": "kb_rag",
                "citations": [{"doc_id": "k8s.md"}]}
    return {"answer": "无法回答(依据不足)", "route": "kb_rag", "citations": []}


def bad_runner(question):
    # c1 漏了 HPA、引用错 → 失败
    return {"answer": "scaling stuff", "route": "web", "citations": [], }


def test_run_eval_all_pass():
    report = run_eval(good_runner, _cases())
    assert isinstance(report, EvalReport)
    assert report.passed_count == 2
    assert report.pass_rate == 1.0


def test_run_eval_detects_failures():
    report = run_eval(bad_runner, _cases())
    # c1 fails(must_include/route/citation),c2: bad_runner 没拒答但 should_refuse → fail
    assert report.passed_count == 0
    assert report.pass_rate == 0.0


def test_ci_gate_stub_agent_meets_threshold():
    # CI 门:确定性 stub 全过,pass_rate 必须达标(>=0.9)
    report = run_eval(good_runner, _cases())
    assert report.pass_rate >= 0.9
