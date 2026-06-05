class StubRouter:
    def __init__(self, decision):
        self.decision = decision

    def route(self, messages):
        return self.decision


def test_supervisor_routes_and_decrements_budget():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("kb_rag"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 3})
    assert out["next"] == "kb_rag"
    assert out["step_budget"] == 2


def test_supervisor_finishes_when_budget_exhausted():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("kb_rag"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 0})
    assert out["next"] == "FINISH"


def test_supervisor_coerces_invalid_route_to_finish():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("nonsense"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 3})
    assert out["next"] == "FINISH"
