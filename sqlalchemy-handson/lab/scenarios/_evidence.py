from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Evidence:
    title: str
    hypothesis: tuple[str, ...]
    setup: tuple[str, ...]
    command: str
    observation: tuple[str, ...]
    explanation: tuple[str, ...]
    decision: tuple[str, ...]
    caveat: tuple[str, ...]

    def render(self) -> str:
        sections = [f"# {self.title}", ""]
        for heading, values in (
            ("Hypothesis", self.hypothesis),
            ("Setup", self.setup),
            ("Command", (self.command,)),
            ("Observation", self.observation),
            ("Explanation", self.explanation),
            ("Decision", self.decision),
            ("Caveat", self.caveat),
        ):
            sections.extend((f"## {heading}", ""))
            sections.extend(f"- {value}" for value in values)
            sections.append("")
        return "\n".join(sections)


def write_evidence(path: Path, evidence: Evidence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(evidence.render(), encoding="utf-8")
