DEFAULT_MEMBERS = ("kb_rag", "web", "human_review")


def make_supervisor_node(router, *, members: tuple[str, ...] = DEFAULT_MEMBERS):
    valid = set(members) | {"FINISH"}

    def supervisor(state) -> dict:
        if state.get("step_budget", 0) <= 0:
            return {"next": "FINISH"}
        decision = router.route(list(state["messages"]))
        if decision not in valid:
            decision = "FINISH"
        return {"next": decision, "step_budget": state["step_budget"] - 1}

    return supervisor
