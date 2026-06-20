def test_chat_request_defaults():
    from mvp_agentic_rag.api.schemas import ChatRequest

    r = ChatRequest(message="hi")
    assert r.message == "hi"
    # 不传 → None,由 server 端按缺省生成新会话(不再共用固定 "default")
    assert r.thread_id is None


def test_chat_response_shape():
    from mvp_agentic_rag.api.schemas import ChatResponse

    r = ChatResponse(response="ans", citations=[{"doc_id": "a.md"}],
                     request_id="x", thread_id="t1")
    assert r.response == "ans"
    assert r.citations[0]["doc_id"] == "a.md"
    assert r.thread_id == "t1"


def test_resume_request():
    from mvp_agentic_rag.api.schemas import ResumeRequest

    r = ResumeRequest(thread_id="t1", decision="approved")
    assert r.decision == "approved"
