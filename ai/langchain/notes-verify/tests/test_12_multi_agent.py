"""校验 `ai/langchain/12-multi-agent.md` 的关键声称。

本章讲多 Agent 协作(Supervisor / Swarm-handoff / Map-Reduce / 共享 State)。
笔记代码用了真实 LLM(create_react_agent + ChatOpenAI),但这些都是「包装」;
真正的多 Agent **机制** 是 langgraph 核心的:
- `Command(goto=..., update=...)` —— 一步内「路由 + 改 state」(handoff 第一原语)
- supervisor 节点按决策路由到不同 worker,worker 写共享(reducer)channel
- `Send` map-reduce 扇出
这些都能用「纯 Python 节点 / 固定决策」离线、确定性地证明,无需 LLM、无需 key。

每个测试上方注释指向它所证明的笔记章节(`# §X.Y — <claim>`)。

笔记 import 路径核对(实测 langgraph 1.2.4 / langchain 1.3.7):
- `from langgraph.types import Command, Send` —— 有效(§二/§六)。
- `from langgraph.graph import StateGraph, MessagesState, START, END` —— 有效。
- `from langgraph.prebuilt import create_react_agent` —— 有效(§二/§三 用到)。
- 笔记 §二/§三 的 prebuilt 库 `langgraph_supervisor` / `langgraph-swarm` —— **未安装**
  (是独立 PyPI 包,非 langgraph 核心)。因此本文件不测那两个库,改测它们底层
  依赖的、langgraph 核心自带的 `Command(goto=...)` handoff/supervisor 原语。

跑法:
    uv run pytest tests/test_12_multi_agent.py            # 仅离线(机制)
    uv run pytest tests/test_12_multi_agent.py -m live    # 真实 OpenAI(需 key)
"""

from operator import add
from typing import Annotated, Literal, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, Send

# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §二 2.2 / §三 3.2 —— handoff 第一原语:节点返回 `Command(goto="other", update={...})`
#   在「一步内」既路由到目标节点、又更新 state。无需为该跳预先 add_edge。
def test_command_goto_routes_and_updates_in_one_step():
    class State(TypedDict):
        trail: Annotated[list, add]
        note: str

    def node_a(state: State) -> Command[Literal["b"]]:
        # 关键:goto 决定下一跳,update 同时改 state,二者一次完成
        return Command(goto="b", update={"trail": ["a"], "note": "from_a"})

    def node_b(state: State):
        # 证明 update 已生效:b 看得到 a 写入的 note
        return {"trail": ["b"], "note": state["note"] + "+b"}

    g = StateGraph(State)
    g.add_node("a", node_a)
    g.add_node("b", node_b)
    g.add_edge(START, "a")
    # 注意:没有 add_edge("a", "b") —— 路由完全由 Command(goto=) 驱动
    g.add_edge("b", END)
    app = g.compile()

    out = app.invoke({"trail": [], "note": ""})
    assert out["trail"] == ["a", "b"]  # b 确实在 a 之后跑了 → 路由成功
    assert out["note"] == "from_a+b"  # b 读到了 a 的 update → 更新已应用


# §二 2.2 —— Command(goto=) 的目标无需静态边;返回类型注解(Command[Literal[...]])
#   只影响图可视化,运行期路由不依赖它。证明 handoff 是「动态」跳转。
def test_command_goto_needs_no_static_edge_and_annotation_optional():
    class State(TypedDict):
        trail: Annotated[list, add]

    def a(state: State):  # 故意不写 Command[Literal[...]] 注解
        return Command(goto="b", update={"trail": ["a"]})

    def b(state: State):
        return {"trail": ["b"]}

    g = StateGraph(State)
    g.add_node("a", a)
    g.add_node("b", b)
    g.add_edge(START, "a")
    g.add_edge("b", END)
    app = g.compile()

    out = app.invoke({"trail": []})
    assert out["trail"] == ["a", "b"]  # 无注解、无静态边,仍然路由到 b


# §二 2.2 —— Supervisor 模式:supervisor 节点按「决策」路由到不同 worker;
#   worker 跑完用 Command(goto="supervisor") 把控制权交回;Command(goto=END) 终止。
#   全程用固定决策替代 LLM,证明 supervisor↔worker 的环路控制流。
def test_supervisor_routes_to_workers_and_returns_control():
    class State(TypedDict):
        task: str
        trail: Annotated[list, add]
        done: bool

    def supervisor(state: State) -> Command[Literal["research", "writer", "__end__"]]:
        if state.get("done"):
            return Command(goto=END)  # §二 2.2:decision == FINISH → goto=END
        # 模拟 with_structured_output 的决策结果(此处用确定性规则替代 LLM)
        if state["task"] == "need_info":
            return Command(goto="research", update={"trail": ["sup->research"]})
        return Command(goto="writer", update={"trail": ["sup->writer"]})

    def research(state: State) -> Command[Literal["supervisor"]]:
        # 干完活,改 task 让 supervisor 下一轮派给 writer,控制权交回 supervisor
        return Command(
            goto="supervisor",
            update={"trail": ["research"], "task": "write", "done": False},
        )

    def writer(state: State) -> Command[Literal["supervisor"]]:
        return Command(goto="supervisor", update={"trail": ["writer"], "done": True})

    g = StateGraph(State)
    g.add_node("supervisor", supervisor)
    g.add_node("research", research)
    g.add_node("writer", writer)
    g.add_edge(START, "supervisor")  # §二 2.2:入口进 supervisor
    app = g.compile()

    out = app.invoke({"task": "need_info", "trail": [], "done": False})
    # supervisor 先派 research,research 回 supervisor,再派 writer,writer 回 supervisor→END
    assert out["trail"] == ["sup->research", "research", "sup->writer", "writer"]
    assert out["done"] is True  # 整个环路正常收口


# §五 5.1 —— 共享 State:多个 agent 节点写同一个带 reducer 的 channel(add_messages),
#   输出被「累加」而非覆盖;name 字段标记来源 agent(§二 2.2 的 name 用法)。
def test_shared_state_reducer_accumulates_across_agents():
    def agent1(state: MessagesState):
        return {"messages": [AIMessage(content="from agent1", name="agent1")]}

    def agent2(state: MessagesState):
        return {"messages": [AIMessage(content="from agent2", name="agent2")]}

    g = StateGraph(MessagesState)
    g.add_node("agent1", agent1)
    g.add_node("agent2", agent2)
    g.add_edge(START, "agent1")
    g.add_edge("agent1", "agent2")
    g.add_edge("agent2", END)

    out = g.compile().invoke({"messages": [HumanMessage(content="start")]})
    # 初始 human + agent1 + agent2 = 3 条,reducer 累加而非覆盖
    assert [getattr(m, "name", None) for m in out["messages"]] == [None, "agent1", "agent2"]
    assert len(out["messages"]) == 3


# §三 3.2 —— Swarm handoff:agent 节点发出 transfer_to_<X> 工具调用,
#   route_after_agent 读 last_msg.tool_calls,按 transfer_to_ 前缀路由到目标 agent;
#   没有 transfer 工具调用时返回 END。证明去中心化交接的路由逻辑(笔记原样函数)。
def test_swarm_handoff_routes_by_transfer_tool_call():
    # 笔记 §三 3.2 原样的路由函数
    def route_after_agent(state, agent_name):
        last_msg = state["messages"][-1]
        for tc in last_msg.tool_calls or []:
            if tc["name"].startswith("transfer_to_"):
                return tc["name"].replace("transfer_to_", "")
        return END

    def sales(state: MessagesState):
        # sales 决定交给 support(发一个 transfer_to_support 工具调用)
        return {
            "messages": [
                AIMessage(content="", tool_calls=[{"id": "c1", "name": "transfer_to_support", "args": {}}])
            ]
        }

    def support(state: MessagesState):
        return {"messages": [AIMessage(content="support handled", name="support")]}

    def billing(state: MessagesState):
        return {"messages": [AIMessage(content="billing handled", name="billing")]}

    g = StateGraph(MessagesState)
    g.add_node("sales", sales)
    g.add_node("support", support)
    g.add_node("billing", billing)
    g.add_edge(START, "sales")
    g.add_conditional_edges("sales", lambda s: route_after_agent(s, "sales"), ["support", "billing", END])
    g.add_edge("support", END)
    g.add_edge("billing", END)

    out = g.compile().invoke({"messages": [HumanMessage(content="I have a tech issue")]})
    # transfer_to_support → 路由到 support,而非 billing
    assert out["messages"][-1].name == "support"
    assert out["messages"][-1].content == "support handled"


# §三 3.2 —— route_after_agent 的「无 transfer 工具调用 → END」分支:
#   当 agent 直接作答(无 transfer_to_* 工具调用)时,路由返回 END,对话不再交接。
def test_swarm_route_returns_end_when_no_transfer():
    def route_after_agent(state, agent_name):
        last_msg = state["messages"][-1]
        for tc in last_msg.tool_calls or []:
            if tc["name"].startswith("transfer_to_"):
                return tc["name"].replace("transfer_to_", "")
        return END

    # agent 直接作答,无 tool_calls
    final_answer = AIMessage(content="这是销售直接给出的答复", name="sales")
    state = {"messages": [HumanMessage(content="想买产品"), final_answer]}
    assert route_after_agent(state, "sales") == END


# §六 —— Map-Reduce:`Send("worker", {...})` 从 START 扇出 N 份,每份独立跑 worker;
#   worker 写带 add reducer 的 results channel,summarize 汇总。证明并行 map → reduce。
def test_map_reduce_send_fans_out_to_workers():
    class ResearchState(TypedDict):
        topics: list
        results: Annotated[list, add]  # add reducer 收集各 worker 输出

    def fan_out(state: ResearchState):
        # 每个 topic 一个 Send,扇出到 worker(笔记 §六 原样)
        return [Send("worker", {"topic": t}) for t in state["topics"]]

    def worker(state):
        return {"results": [f"researched: {state['topic']}"]}

    def summarize(state: ResearchState):
        return {"results": [f"summary of {len(state['results'])} items"]}

    g = StateGraph(ResearchState)
    g.add_node("worker", worker)
    g.add_node("summarize", summarize)
    g.add_conditional_edges(START, fan_out, ["worker"])  # 从 START 扇出
    g.add_edge("worker", "summarize")
    g.add_edge("summarize", END)

    out = g.compile().invoke({"topics": ["a", "b", "c"], "results": []})
    # 3 个 worker 各产出一条 + summarize 一条 = 4 条;顺序不保证,故排序比较
    assert sorted(out["results"]) == [
        "researched: a",
        "researched: b",
        "researched: c",
        "summary of 3 items",
    ]


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §二 2.2 —— supervisor 用真实 LLM(with_structured_output)做路由决策。
#   这是唯一真正需要 LLM 的环节:验证 LLM 能按指令把请求路由到正确的 worker。
@pytest.mark.live
def test_live_supervisor_routes_with_real_llm():
    from langchain_openai import ChatOpenAI

    class Decision(TypedDict):
        next: Literal["research", "writer"]

    class State(TypedDict):
        request: str
        handled_by: str

    def supervisor(state: State) -> Command[Literal["research", "writer"]]:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(Decision)
        decision = llm.invoke(
            "你是团队协调者。团队成员:research(信息收集)、writer(撰写文稿)。"
            "根据用户请求选择下一步该谁来做。\n用户请求:" + state["request"]
        )
        return Command(goto=decision["next"])

    def research(state: State):
        return {"handled_by": "research"}

    def writer(state: State):
        return {"handled_by": "writer"}

    g = StateGraph(State)
    g.add_node("supervisor", supervisor)
    g.add_node("research", research)
    g.add_node("writer", writer)
    g.add_edge(START, "supervisor")
    g.add_edge("research", END)
    g.add_edge("writer", END)
    app = g.compile()

    # 明显的「信息收集」请求 → 应路由到 research
    out = app.invoke({"request": "去网上查一下竞品公司最近的融资情况", "handled_by": ""})
    assert out["handled_by"] == "research"
