from langchain_core.messages import AIMessage
from langgraph.types import interrupt


def human_review_node(state) -> dict:
    """敏感动作前暂停,等待人工决定。interrupt 的返回值即 Command(resume=...) 传入的值。"""
    decision = interrupt(
        {"reason": "需要人工审核的敏感动作", "pending": _last_text(state["messages"])}
    )
    return {"messages": [AIMessage(content=f"[人工审核:{decision}] 已按审核结果处理。")], "next": "FINISH"}


def _last_text(messages) -> str:
    return messages[-1].content if messages else ""
