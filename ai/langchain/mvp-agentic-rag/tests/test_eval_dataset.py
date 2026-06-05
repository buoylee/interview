from mvp_agentic_rag.eval.dataset import GoldenCase, load_golden


def test_load_golden(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id":"c1","question":"q1","must_include":["A"],"expected_route":"kb_rag"}\n'
        '{"id":"c2","question":"q2","must_include":[],"should_refuse":true}\n',
        encoding="utf-8",
    )
    cases = load_golden(str(p))
    assert len(cases) == 2
    assert cases[0].id == "c1"
    assert cases[0].expected_route == "kb_rag"
    assert cases[0].should_refuse is False     # 默认
    assert cases[1].should_refuse is True
    assert cases[1].expected_route is None      # 默认


def test_golden_case_defaults():
    c = GoldenCase(id="x", question="q", must_include=["A"])
    assert c.expected_route is None
    assert c.expected_citation_docs is None
    assert c.should_refuse is False
