from dataclasses import dataclass

from mvp_agentic_rag.eval.checks import (
    CaseResult, check_citations, check_must_include, check_refusal, check_route,
)
from mvp_agentic_rag.eval.dataset import GoldenCase


@dataclass
class CaseEval:
    case_id: str
    result: CaseResult
    answer: str
    route: str


@dataclass
class EvalReport:
    cases: list[CaseEval]

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.cases if c.result.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / len(self.cases) if self.cases else 0.0


def run_eval(agent_runner, cases: list[GoldenCase]) -> EvalReport:
    """agent_runner(question) -> {"answer": str, "route": str, "citations": list[dict]}"""
    evals: list[CaseEval] = []
    for case in cases:
        out = agent_runner(case.question)
        answer = out.get("answer", "")
        route = out.get("route", "")
        citations = out.get("citations", [])
        result = CaseResult(
            must_include_ok=check_must_include(answer, case.must_include),
            route_ok=check_route(route, case.expected_route),
            citation_ok=check_citations(citations, case.expected_citation_docs),
            refusal_ok=check_refusal(answer, case.should_refuse),
        )
        evals.append(CaseEval(case_id=case.id, result=result, answer=answer, route=route))
    return EvalReport(evals)
