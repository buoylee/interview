from agent_loop.mcp_client import READ_DOC, call_mcp_tool


def test_read_doc_via_mcp_returns_file_content():
    out = call_mcp_tool("read_doc", {"filename": "postgres.md"})
    assert "postgres" in out.lower()


def test_read_doc_rejects_path_traversal():
    out = call_mcp_tool("read_doc", {"filename": "../pyproject.toml"})
    assert out.startswith("ERROR")


def test_read_doc_missing_file_lists_available():
    out = call_mcp_tool("read_doc", {"filename": "nope.md"})
    assert out.startswith("ERROR") and "postgres.md" in out


def test_read_doc_toolspec():
    assert READ_DOC.name == "read_doc"
    assert READ_DOC.parameters["required"] == ["filename"]
