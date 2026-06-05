import json
from dataclasses import dataclass


@dataclass
class GoldenCase:
    id: str
    question: str
    must_include: list[str]
    expected_route: str | None = None
    expected_citation_docs: list[str] | None = None
    should_refuse: bool = False


def load_golden(path: str) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            cases.append(
                GoldenCase(
                    id=d["id"],
                    question=d["question"],
                    must_include=d.get("must_include", []),
                    expected_route=d.get("expected_route"),
                    expected_citation_docs=d.get("expected_citation_docs"),
                    should_refuse=d.get("should_refuse", False),
                )
            )
    return cases
