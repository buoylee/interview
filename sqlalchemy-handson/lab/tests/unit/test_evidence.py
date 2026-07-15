from pathlib import Path

from scenarios._evidence import Evidence, write_evidence


def test_evidence_writer_emits_every_required_section(tmp_path: Path) -> None:
    target = tmp_path / "evidence.md"
    evidence = Evidence(
        title="Example",
        hypothesis=("one prediction",),
        setup=("one setup fact",),
        observation=("one observation",),
        explanation=("one explanation",),
        decision=("one decision",),
        caveat=("one caveat",),
    )

    write_evidence(target, evidence)

    rendered = target.read_text(encoding="utf-8")
    for heading in (
        "## Hypothesis",
        "## Setup",
        "## Observation",
        "## Explanation",
        "## Decision",
        "## Caveat",
    ):
        assert heading in rendered
