from langchain_core.messages import AIMessage

DEFAULT_MEMBERS = ("kb_rag", "web", "human_review")


def make_supervisor_node(router, *, members: tuple[str, ...] = DEFAULT_MEMBERS):
    valid = set(members) | {"FINISH"}
    default_member = members[0]  # 兜底专家(kb_rag)

    def supervisor(state) -> dict:
        # 终止判断【不交给 LLM】:只要已经有非空 AI 答案,就确定性结束。
        # 否则交给 LLM 决定"停"会空转——它对技术问题反复返回 kb_rag,直到 step_budget
        # 耗尽才被迫 FINISH(实测一个问题 kb_rag 被调 6 次、单次 /chat 41s)。
        has_answer = any(
            isinstance(m, AIMessage) and str(m.content).strip() for m in state["messages"]
        )
        if has_answer or state.get("step_budget", 0) <= 0:
            return {"next": "FINISH"}

        # 还没有答案 → 由 LLM 决定首轮派给哪个专家(kb_rag / web)。
        # 此时 FINISH / 未知值都不合理(没产出就停),一律兜底去检索。
        decision = router.route(list(state["messages"]))
        if decision not in valid or decision == "FINISH":
            decision = default_member
        return {"next": decision, "step_budget": state["step_budget"] - 1}

    return supervisor
