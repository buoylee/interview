def test_web_search_tool_shape():
    from mvp_agentic_rag.agent.tools import web_search

    assert web_search.name == "web_search"
    assert web_search.description
    out = web_search.invoke({"query": "weather"})
    assert isinstance(out, str)


def test_build_web_agent_is_callable():
    # 仅验证工厂存在且可导入(构造需要真模型,不在此断言行为)
    from mvp_agentic_rag.agent.subgraphs.web import build_web_agent

    assert callable(build_web_agent)
