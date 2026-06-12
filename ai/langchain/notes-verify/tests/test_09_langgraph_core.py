"""校验 `ai/langchain/09-langgraph-core.md` 的关键声称。

本章是「状态图编排」的纯机制,几乎全部可离线确定性证明 —— 无需 LLM、无需 key。
每个测试上方注释指向它所证明的笔记章节(`# §X.Y — <claim>`)。

笔记的 import 路径核对(实测 langgraph 1.2.4):
- `from langgraph.graph import StateGraph, START, END, MessagesState` —— 全部有效。
- 笔记用 `from langgraph.graph import add_messages`(见 §2.1 / §5.2)—— 该路径仍可用,
  但 reducer 的「正经」位置是 `langgraph.graph.message`,本文件统一用后者。
- `START == "__start__"`, `END == "__end__"`(实测常量值)。

跑法:
    uv run pytest tests/test_09_langgraph_core.py            # 仅离线(本章无 live)
"""

from operator import add
from typing import Annotated, Literal, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import add_messages

# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key(本章无 live 测试)
# --------------------------------------------------------------------------- #


# §2.5 / §3.1 —— 最小图:StateGraph(State) + node + START/END 边 → compile → invoke
#                返回的是「合并后的最终 state」(节点的部分更新被合进初始 state)
def test_build_compile_invoke_returns_merged_state():
    class State(TypedDict):
        value: str
        n: int

    def node_a(state: State):
        # 节点只返回需要更新的字段(§2.4 关键理解),不必返回完整 State
        return {"value": "a", "n": state["n"] + 1}

    g = StateGraph(State)
    g.add_node("a", node_a)
    g.add_edge(START, "a")  # §2.5 入口
    g.add_edge("a", END)  # §2.5 出口
    app = g.compile()

    out = app.invoke({"value": "init", "n": 0})
    assert out == {"value": "a", "n": 1}  # value 被节点覆盖,n 自增到 1


# §2.5 —— START / END 是有固定字面值的特殊常量(不是普通节点名)
def test_start_end_constants():
    assert START == "__start__"
    assert END == "__end__"


# §2.2 / §2.3 —— 普通(无 Reducer)channel:节点返回值「覆盖」旧值,历史丢失
#                这是面试核心 gotcha 的反面教材。
def test_plain_channel_is_overwritten():
    class State(TypedDict):
        items: list  # 没有 Annotated reducer

    def node(state: State):
        return {"items": ["new"]}

    g = StateGraph(State)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)

    out = g.compile().invoke({"items": ["old"]})
    assert out["items"] == ["new"]  # 旧的 ["old"] 被整个覆盖掉


# §2.2 / §2.3 —— 带 Reducer 的 channel:用 reducer 合并而非覆盖
#                operator.add 对 list 是拼接,对 int 是相加。
def test_reducer_channel_merges_not_overwrites():
    class State(TypedDict):
        items: Annotated[list, add]  # list + list = 拼接
        count: Annotated[int, add]  # int + int = 相加

    def node(state: State):
        return {"items": ["new"], "count": 5}

    g = StateGraph(State)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)

    out = g.compile().invoke({"items": ["old"], "count": 10})
    assert out["items"] == ["old", "new"]  # 拼接,不丢历史
    assert out["count"] == 15  # 10 + 5


# §2.1 / §2.3 —— add_messages reducer:追加消息、且给没有 id 的消息自动分配 id
def test_add_messages_appends_and_assigns_ids():
    class State(TypedDict):
        messages: Annotated[list, add_messages]

    def add_ai(state: State):
        return {"messages": [AIMessage(content="hi from ai")]}

    g = StateGraph(State)
    g.add_node("ai", add_ai)
    g.add_edge(START, "ai")
    g.add_edge("ai", END)

    out = g.compile().invoke({"messages": [HumanMessage(content="hello")]})
    assert [m.type for m in out["messages"]] == ["human", "ai"]  # 追加,非覆盖
    assert all(m.id is not None for m in out["messages"])  # 自动分配 id


# §2.3 —— add_messages 的「按 id 去重/替换」语义:
#         相同 id 的新消息会「替换」旧消息(而非再追加一条);不同 id 才追加。
def test_add_messages_same_id_replaces():
    base = add_messages([], [HumanMessage(content="original", id="fixed-1")])
    assert [(m.content, m.id) for m in base] == [("original", "fixed-1")]

    # 相同 id → 原地替换内容,长度不变
    replaced = add_messages(base, [HumanMessage(content="replaced", id="fixed-1")])
    assert len(replaced) == 1
    assert replaced[0].content == "replaced"

    # 不同 id → 追加,长度增加
    appended = add_messages(base, [HumanMessage(content="second", id="fixed-2")])
    assert len(appended) == 2
    assert [m.content for m in appended] == ["original", "second"]


# §2.1 —— 内置 MessagesState 等价于 {messages: Annotated[list, add_messages]}
def test_messagesstate_uses_add_messages_reducer():
    # 注解以 ForwardRef 字符串形式保存,内容指明 reducer 是 add_messages
    ann = MessagesState.__annotations__["messages"]
    assert "add_messages" in str(ann)

    # 用 MessagesState 直接建图,验证 messages 走的是追加语义
    def add_one(state: MessagesState):
        return {"messages": [AIMessage(content="x")]}

    g = StateGraph(MessagesState)
    g.add_node("n", add_one)
    g.add_edge(START, "n")
    g.add_edge("n", END)

    out = g.compile().invoke({"messages": [HumanMessage(content="hi")]})
    assert len(out["messages"]) == 2  # 追加而非覆盖,证明 reducer 生效


# §2.5 / §6.2 —— add_conditional_edges:router 函数的返回值决定走哪个分支
def test_conditional_edges_route_by_router_return():
    class State(TypedDict):
        kind: str
        trail: Annotated[list, add]

    def classify(state: State):
        return {"trail": ["classify"]}

    def qa(state: State):
        return {"trail": ["qa"]}

    def task(state: State):
        return {"trail": ["task"]}

    def router(state: State) -> Literal["qa", "task"]:
        return "qa" if state["kind"] == "question" else "task"

    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("qa", qa)
    g.add_node("task", task)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", router, ["qa", "task"])
    g.add_edge("qa", END)
    g.add_edge("task", END)
    app = g.compile()

    assert app.invoke({"kind": "question", "trail": []})["trail"] == ["classify", "qa"]
    assert app.invoke({"kind": "job", "trail": []})["trail"] == ["classify", "task"]


# §6.3 —— Agent 循环:条件边可直接返回 END 终止;否则回到上游节点形成 loop
#         (router 返回 END 而非节点名时,图在该点退出)
def test_conditional_edge_can_return_end_to_terminate_loop():
    class State(TypedDict):
        steps: Annotated[list, add]
        stop: bool

    def agent(state: State):
        return {"steps": ["agent"]}

    def tool(state: State):
        return {"steps": ["tool"], "stop": True}  # 跑一次工具后置 stop

    def should_continue(state: State):
        return END if state.get("stop") else "tool"

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tool", tool)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", should_continue, ["tool", END])
    g.add_edge("tool", "agent")  # §6.3 循环回 agent
    app = g.compile()

    # agent(stop=False)→tool(置 stop)→agent(stop=True)→END
    out = app.invoke({"steps": [], "stop": False})
    assert out["steps"] == ["agent", "tool", "agent"]


# §6.1 —— 顺序执行:多节点串成链,state 一路 thread 下去
def test_sequential_nodes_thread_state():
    class State(TypedDict):
        trail: Annotated[list, add]
        n: int

    def make(name):
        def fn(state: State):
            return {"trail": [name], "n": state["n"] + 1}

        return fn

    g = StateGraph(State)
    for name in ("s1", "s2", "s3"):
        g.add_node(name, make(name))
    g.add_edge(START, "s1")
    g.add_edge("s1", "s2")
    g.add_edge("s2", "s3")
    g.add_edge("s3", END)

    out = g.compile().invoke({"trail": [], "n": 0})
    assert out["trail"] == ["s1", "s2", "s3"]  # 顺序流转
    assert out["n"] == 3  # state 累积穿过每个节点


# §6.4 —— 并行扇出→汇聚:一个节点扇出到多个并行节点,reducer 收集各分支输出,
#         merge 只在所有分支汇聚后跑一次。
def test_parallel_fanout_fanin_collects_with_reducer():
    class State(TypedDict):
        branches: Annotated[list, add]  # reducer 收集各并行分支的输出

    def start(state: State):
        return {}

    def make(name):
        def fn(state: State):
            return {"branches": [name]}

        return fn

    g = StateGraph(State)
    g.add_node("start", start)
    for name in ("research", "analyze", "summarize", "merge"):
        g.add_node(name, make(name))
    g.add_edge(START, "start")
    # 扇出
    g.add_edge("start", "research")
    g.add_edge("start", "analyze")
    g.add_edge("start", "summarize")
    # 汇聚
    g.add_edge("research", "merge")
    g.add_edge("analyze", "merge")
    g.add_edge("summarize", "merge")
    g.add_edge("merge", END)

    out = g.compile().invoke({"branches": []})
    # 三个并行分支都被 reducer 收集(顺序不保证,故用集合比较)
    assert set(out["branches"]) == {"research", "analyze", "summarize", "merge"}
    # merge 是汇聚点,只跑一次(不会每个上游各触发一次)
    assert out["branches"].count("merge") == 1


# §2.2 / §6.4 gotcha —— 并行分支同时写「普通(无 reducer)channel」会触发 InvalidUpdateError。
#                       这正是 §6.4 并行模式必须配 reducer(如 add_messages)的根本原因。
def test_concurrent_write_to_plain_channel_raises():
    class State(TypedDict):
        val: str  # 没有 reducer

    def start(state: State):
        return {}

    def b1(state: State):
        return {"val": "x"}

    def b2(state: State):
        return {"val": "y"}

    g = StateGraph(State)
    g.add_node("start", start)
    g.add_node("b1", b1)
    g.add_node("b2", b2)
    g.add_edge(START, "start")
    g.add_edge("start", "b1")  # b1 / b2 并行
    g.add_edge("start", "b2")
    g.add_edge("b1", END)
    g.add_edge("b2", END)
    app = g.compile()

    # 同一 superstep 内两个分支都想覆写无 reducer 的 val → 冲突
    with pytest.raises(InvalidUpdateError):
        app.invoke({"val": ""})
