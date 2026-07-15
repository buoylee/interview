from pathlib import Path

EXPECTED_EVIDENCE = {
    "environment.md",
    "ch01-engine-execution.md",
    "ch02-schema-types.md",
    "ch03-expression-compiler.md",
    "ch04-core-dml-results.md",
    "ch05-connection-transactions.md",
    "ch06-pooling-capacity.md",
}
REQUIRED_HEADINGS = {
    "## Hypothesis",
    "## Setup",
    "## Command",
    "## Observation",
    "## Explanation",
    "## Decision",
    "## Caveat",
}


def test_committed_evidence_manifest_is_complete() -> None:
    evidence_dir = Path(__file__).parents[2] / "evidence"
    assert {path.name for path in evidence_dir.glob("*.md")} == EXPECTED_EVIDENCE
    for path in evidence_dir.glob("*.md"):
        rendered = path.read_text(encoding="utf-8")
        assert set(rendered.splitlines()) >= REQUIRED_HEADINGS
        command_section = rendered.split("## Command\n\n", maxsplit=1)[1].split(
            "\n## Observation", maxsplit=1
        )[0]
        command_lines = [
            line for line in command_section.splitlines() if line.startswith("- ")
        ]
        assert len(command_lines) == 1
