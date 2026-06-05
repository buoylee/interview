from dataclasses import dataclass

REFUSAL_MARKERS = ("依据不足", "无法", "抱歉", "没有找到")


def check_must_include(answer: str, must_include: list[str]) -> bool:
    return all(s in answer for s in must_include)


def check_route(actual_route: str, expected_route: str | None) -> bool:
    return expected_route is None or actual_route == expected_route


def check_citations(citations: list[dict], expected_docs: list[str] | None) -> bool:
    if not expected_docs:
        return True
    got = {c.get("doc_id") for c in citations}
    return all(d in got for d in expected_docs)


def check_refusal(answer: str, should_refuse: bool, markers=REFUSAL_MARKERS) -> bool:
    refused = any(m in answer for m in markers)
    return refused == should_refuse


@dataclass
class CaseResult:
    must_include_ok: bool
    route_ok: bool
    citation_ok: bool
    refusal_ok: bool

    @property
    def passed(self) -> bool:
        return all([self.must_include_ok, self.route_ok, self.citation_ok, self.refusal_ok])
