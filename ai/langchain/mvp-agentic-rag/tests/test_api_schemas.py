def test_chat_request_defaults():
    from mvp_agentic_rag.api.schemas import ChatRequest

    r = ChatRequest(message="hi")
    assert r.message == "hi"
    assert r.thread_id == "default"


def test_chat_response_shape():
    from mvp_agentic_rag.api.schemas import ChatResponse

    r = ChatResponse(response="ans", citations=[{"doc_id": "a.md"}], request_id="x")
    assert r.response == "ans"
    assert r.citations[0]["doc_id"] == "a.md"


def test_resume_request():
    from mvp_agentic_rag.api.schemas import ResumeRequest

    r = ResumeRequest(thread_id="t1", decision="approved")
    assert r.decision == "approved"
