from pathlib import Path

import agent_loop.tools as tools
from agent_loop.tools import SEARCH_DOCS, ToolSpec, search_docs


def test_toolspec_to_openai_format():
    spec = ToolSpec(name="t", description="d", parameters={"type": "object"}, handler=lambda: "x")
    assert spec.to_openai() == {
        "type": "function",
        "function": {"name": "t", "description": "d", "parameters": {"type": "object"}},
    }


def test_search_docs_returns_matching_paragraph(tmp_path: Path, monkeypatch):
    (tmp_path / "a.md").write_text("第一段讲 docker。\n\n这一段讲 pgvector 索引,有 hnsw 和 ivfflat。", encoding="utf-8")
    (tmp_path / "b.md").write_text("无关内容。", encoding="utf-8")
    monkeypatch.setattr(tools, "DOCS_DIR", tmp_path)
    out = search_docs("pgvector hnsw")
    assert "[a.md]" in out and "ivfflat" in out
    assert "无关内容" not in out


def test_search_docs_no_match(tmp_path: Path, monkeypatch):
    (tmp_path / "a.md").write_text("完全无关。", encoding="utf-8")
    monkeypatch.setattr(tools, "DOCS_DIR", tmp_path)
    assert search_docs("量子纠缠").startswith("NO_MATCH")


def test_search_docs_default_dir_points_at_mvp_sample_docs():
    assert (tools.DOCS_DIR / "postgres.md").exists()
    assert SEARCH_DOCS.name == "search_docs"
