from langgraph.prebuilt import create_react_agent


def build_web_agent(chat_model, tools):
    """库外/兜底专家:预构建 ReAct agent。
    生产用真实 chat 模型 + web_search 等工具;返回一个可 invoke({"messages": [...]}) 的图。"""
    return create_react_agent(chat_model, tools)
