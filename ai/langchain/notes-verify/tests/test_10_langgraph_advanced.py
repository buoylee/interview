"""校验 `ai/langchain/10-langgraph-advanced.md` 的关键声称。

本章(Checkpointing / Human-in-the-loop / Streaming / SubGraph)几乎全是「编排机制」,
可离线确定性证明 —— 无需 LLM、无需 key。每个测试上方注释指向它所证明的笔记章节
(`# §X.Y — <claim>`)。

笔记的 import 路径核对(实测 langgraph 1.2.4):
- `from langgraph.checkpoint.memory import MemorySaver` —— 有效(`InMemorySaver` 是同模块别名,二者皆可)。
- `from langgraph.types import interrupt, Command` —— 有效(§1.2)。
- `from langgraph.graph import StateGraph, START, END, MessagesState` —— 有效。
- `graph.get_state(config)` 返回 `StateSnapshot`,有 `.values` / `.next` / `.config`(§1.3)。

笔记纠偏(notes-drift,详见 README / 本文件注释):
- §1.4 称「没有 Checkpointer 就不能用 interrupt()」。实测更精确:无 checkpointer 时
  `interrupt()` 仍会「暂停」(节点 body 后续不执行、结果带 `__interrupt__`),
  真正失效的是「恢复」—— `Command(resume=...)` 抛 RuntimeError,`get_state` 抛 ValueError。
  即:无 checkpointer 可暂停、不可恢复,HITL 闭环跑不通。见 test_interrupt_without_checkpointer_*。

跑法:
    uv run pytest tests/test_10_langgraph_advanced.py            # 仅离线(本章无 live)
"""

from operator import add
from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key(本章无 live 测试)
# --------------------------------------------------------------------------- #


# §1.2 / §1.3 —— Checkpointing 核心:同一 thread_id 跨多次 invoke,state 持久化并累积;
#                不同 thread_id 各自独立、从头开始(面试核心 gotcha:thread_id 是会话隔离键)。
def test_checkpointer_persists_state_across_invokes_per_thread():
    class State(TypedDict):
        count: Annotated[int, add]
        trail: Annotated[list, add]

    def bump(state: State):
        return {"count": 1, "trail": ["bump"]}

    g = StateGraph(State)
    g.add_node("bump", bump)
    g.add_edge(START, "bump")
    g.add_edge("bump", END)
    app = g.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "session_1"}}
    out1 = app.invoke({"count": 0, "trail": []}, config=cfg)
    out2 = app.invoke({"count": 0, "trail": []}, config=cfg)  # 同一线程:接着上次的 state
    assert out1 == {"count": 1, "trail": ["bump"]}
    assert out2 == {"count": 2, "trail": ["bump", "bump"]}  # 累积,不是重置

    # 不同 thread_id → 全新会话,从头开始(隔离)
    cfg2 = {"configurable": {"thread_id": "session_2"}}
    out3 = app.invoke({"count": 0, "trail": []}, config=cfg2)
    assert out3 == {"count": 1, "trail": ["bump"]}  # 没被 session_1 的历史污染


# §1.3 —— get_state(config) 返回 StateSnapshot:.values 是当前 state,
#         .next 是「下一步要跑的节点」(图跑完后为空元组)。
def test_get_state_returns_snapshot_with_values_and_next():
    class State(TypedDict):
        n: Annotated[int, add]

    def step(state: State):
        return {"n": 1}

    g = StateGraph(State)
    g.add_node("step", step)
    g.add_edge(START, "step")
    g.add_edge("step", END)
    app = g.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "snap1"}}
    app.invoke({"n": 0}, config=cfg)
    snap = app.get_state(cfg)
    assert type(snap).__name__ == "StateSnapshot"
    assert snap.values == {"n": 1}  # 保存的 state
    assert snap.next == ()  # 已跑完,没有待执行节点
    # checkpoint_id 被写回 config,可用于时间旅行定位
    assert "checkpoint_id" in snap.config["configurable"]


# §1.2 / §1.3 —— interrupt() 暂停图:第一次 invoke 在调用 interrupt 的节点处停下,
#                结果带 `__interrupt__`(payload 即传给 interrupt 的值),get_state().next
#                指向被暂停的节点;此时节点 body 中 interrupt 之后的代码尚未执行。
def test_interrupt_pauses_graph_at_node():
    class State(TypedDict):
        trail: Annotated[list, add]
        decision: str

    def before(state: State):
        return {"trail": ["before"]}

    def gate(state: State):
        ans = interrupt({"question": "是否批准?"})  # 暂停点
        return {"trail": ["gate"], "decision": ans}  # interrupt 之后:暂停时不执行

    def after(state: State):
        return {"trail": ["after"]}

    g = StateGraph(State)
    g.add_node("before", before)
    g.add_node("gate", gate)
    g.add_node("after", after)
    g.add_edge(START, "before")
    g.add_edge("before", "gate")
    g.add_edge("gate", "after")
    g.add_edge("after", END)
    app = g.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "hitl1"}}
    paused = app.invoke({"trail": [], "decision": ""}, config=cfg)

    # before 跑完了,但 gate 在 interrupt 处停住:trail 只有 before,decision 仍为空
    assert paused["trail"] == ["before"]
    assert paused["decision"] == ""
    # 结果里带 __interrupt__,payload 就是传给 interrupt() 的字典
    assert "__interrupt__" in paused
    assert paused["__interrupt__"][0].value == {"question": "是否批准?"}
    # get_state().next 指向暂停在的节点
    assert app.get_state(cfg).next == ("gate",)


# §1.3 —— Command(resume=...) 从暂停点恢复:interrupt() 的返回值 == resume 传入的值,
#         节点 body 继续执行,图跑到底(.next 清空)。
def test_command_resume_continues_from_interrupt():
    class State(TypedDict):
        trail: Annotated[list, add]
        decision: str

    def gate(state: State):
        ans = interrupt({"question": "approve?"})
        return {"trail": ["gate"], "decision": ans}

    def execute(state: State):
        return {"trail": ["execute"]}

    g = StateGraph(State)
    g.add_node("gate", gate)
    g.add_node("execute", execute)
    g.add_edge(START, "gate")
    g.add_edge("gate", "execute")
    g.add_edge("execute", END)
    app = g.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "hitl2"}}
    app.invoke({"trail": [], "decision": ""}, config=cfg)  # 暂停在 gate

    resumed = app.invoke(Command(resume="approve"), config=cfg)  # 恢复
    # interrupt() 返回值就是 resume 的值;gate 之后 execute 也跑了
    assert resumed["decision"] == "approve"
    assert resumed["trail"] == ["gate", "execute"]
    assert app.get_state(cfg).next == ()  # 跑到底


# §1.4 纠偏 —— 笔记称「没有 Checkpointer 就不能用 interrupt()」。实测更精确:
#              无 checkpointer 时 interrupt() 仍会「暂停」(body 后续不执行、带 __interrupt__),
#              失效的是「恢复」环节。这里先证明「暂停」这一半在无 checkpointer 时也成立。
def test_interrupt_without_checkpointer_still_pauses():
    class State(TypedDict):
        trail: Annotated[list, add]

    def gate(state: State):
        interrupt({"q": "?"})
        return {"trail": ["gate"]}  # 暂停时不执行

    g = StateGraph(State)
    g.add_node("gate", gate)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    app = g.compile()  # 没有 checkpointer

    out = app.invoke({"trail": []})
    assert "__interrupt__" in out  # 仍然暂停
    assert out["trail"] == []  # gate 的 body 没跑完


# §1.4 纠偏 —— 「不能用 interrupt()」的真正含义:无 checkpointer 时「恢复」跑不通 ——
#              Command(resume=...) 抛 RuntimeError,get_state 抛 ValueError(没有持久化状态可恢复)。
#              即:无 checkpointer 可暂停、不可恢复,HITL 闭环跑不通。
def test_interrupt_without_checkpointer_cannot_resume_or_inspect():
    class State(TypedDict):
        trail: Annotated[list, add]

    def gate(state: State):
        ans = interrupt({"q": "?"})
        return {"trail": ["gate"], "ans": ans}

    g = StateGraph(State)
    g.add_node("gate", gate)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    app = g.compile()  # 没有 checkpointer

    cfg = {"configurable": {"thread_id": "no_cp"}}
    app.invoke({"trail": []}, config=cfg)  # 暂停

    # 恢复:抛 RuntimeError(没有 checkpointer 存不了暂停点)
    with pytest.raises(RuntimeError):
        app.invoke(Command(resume="ok"), config=cfg)
    # 查看状态:抛 ValueError(没有 checkpointer 就没有可查的快照)
    with pytest.raises(ValueError):
        app.get_state(cfg)


# §1.3(compile-time 变体)—— interrupt_before=[节点] 在「进入该节点前」暂停;
#                            传 None 给 invoke 即从暂停点恢复(无需 Command,因为不需要回传值)。
def test_interrupt_before_compile_pauses_then_resumes_on_none():
    class State(TypedDict):
        trail: Annotated[list, add]

    def s1(state: State):
        return {"trail": ["s1"]}

    def s2(state: State):
        return {"trail": ["s2"]}

    g = StateGraph(State)
    g.add_node("s1", s1)
    g.add_node("s2", s2)
    g.add_edge(START, "s1")
    g.add_edge("s1", "s2")
    g.add_edge("s2", END)
    app = g.compile(checkpointer=MemorySaver(), interrupt_before=["s2"])

    cfg = {"configurable": {"thread_id": "ib1"}}
    paused = app.invoke({"trail": []}, config=cfg)
    assert paused["trail"] == ["s1"]  # 停在进入 s2 之前
    assert app.get_state(cfg).next == ("s2",)

    resumed = app.invoke(None, config=cfg)  # 传 None 恢复
    assert resumed["trail"] == ["s1", "s2"]
    assert app.get_state(cfg).next == ()


# §2.1 —— stream_mode="values" 每步 yield「完整 state 快照」;
#         stream_mode="updates" 每步 yield「{节点名: 该节点的增量}」。
#         这是两种模式的形状差异(面试常问:values 是全量、updates 是按节点的 delta)。
def test_stream_modes_values_vs_updates_shapes():
    class State(TypedDict):
        trail: Annotated[list, add]
        n: int

    def s1(state: State):
        return {"trail": ["s1"], "n": state["n"] + 1}

    def s2(state: State):
        return {"trail": ["s2"], "n": state["n"] + 1}

    g = StateGraph(State)
    g.add_node("s1", s1)
    g.add_node("s2", s2)
    g.add_edge(START, "s1")
    g.add_edge("s1", "s2")
    g.add_edge("s2", END)
    app = g.compile()

    # values:每个事件是完整 state(含初始快照),逐步累积
    values = list(app.stream({"trail": [], "n": 0}, stream_mode="values"))
    assert all(set(ev.keys()) == {"trail", "n"} for ev in values)  # 全量 state 形状
    assert values[-1] == {"trail": ["s1", "s2"], "n": 2}  # 末事件 = 最终全量 state
    assert [ev["n"] for ev in values] == [0, 1, 2]  # 含初始 0,逐步推进

    # updates:每个事件是 {节点名: 增量},只含该节点返回的字段
    updates = list(app.stream({"trail": [], "n": 0}, stream_mode="updates"))
    assert [list(ev.keys())[0] for ev in updates] == ["s1", "s2"]  # 按节点名分组
    assert updates[0] == {"s1": {"trail": ["s1"], "n": 1}}  # 仅 s1 的 delta
    assert updates[1] == {"s2": {"trail": ["s2"], "n": 2}}


# §1.3 / 时间旅行 —— update_state(config, {...}) 手动改写已持久化的 state;
#                    读回 get_state 看到的是改写后的值(reducer 仍会作用,见下)。
def test_update_state_mutates_persisted_state():
    class State(TypedDict):
        trail: Annotated[list, add]
        val: str  # 普通 channel,无 reducer → update_state 直接覆盖

    def node(state: State):
        return {"trail": ["node"], "val": "from_node"}

    g = StateGraph(State)
    g.add_node("node", node)
    g.add_edge(START, "node")
    g.add_edge("node", END)
    app = g.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "tt1"}}
    app.invoke({"trail": [], "val": "init"}, config=cfg)
    assert app.get_state(cfg).values["val"] == "from_node"

    app.update_state(cfg, {"val": "manually_set"})  # 人工改写
    assert app.get_state(cfg).values["val"] == "manually_set"
    # trail(带 add reducer)未被这次 update 触碰,保持原值
    assert app.get_state(cfg).values["trail"] == ["node"]


# §3.2 / §3.3 —— 子图作为「父图节点内调用」:父节点 invoke 已编译的子图,
#                把子图输出 thread 回父 state(笔记 §3.3 的 call_research 写法)。
def test_subgraph_invoked_inside_parent_node():
    class SubState(TypedDict):
        topic: str
        findings: Annotated[list, add]

    def search(state: SubState):
        return {"findings": ["found:search"]}

    def analyze(state: SubState):
        return {"findings": ["found:analyze"]}

    sub = StateGraph(SubState)
    sub.add_node("search", search)
    sub.add_node("analyze", analyze)
    sub.add_edge(START, "search")
    sub.add_edge("search", "analyze")
    sub.add_edge("analyze", END)
    research_subgraph = sub.compile()

    class MainState(TypedDict):
        topic: str
        research_results: str

    def call_research(state: MainState):
        out = research_subgraph.invoke({"topic": state["topic"], "findings": []})
        return {"research_results": "\n".join(out["findings"])}

    main = StateGraph(MainState)
    main.add_node("research", call_research)
    main.add_edge(START, "research")
    main.add_edge("research", END)
    app = main.compile()

    out = app.invoke({"topic": "ai", "research_results": ""})
    # 子图两步都跑了,结果被汇回父 state
    assert out["research_results"] == "found:search\nfound:analyze"


# §3.1 / §3.3 —— 子图也可「直接作为父图节点」加入(共享 state schema 时):
#                编译后的图本身就是 Runnable,add_node 直接接受它,state 透传贯穿父子。
def test_compiled_subgraph_added_directly_as_node():
    class SharedState(TypedDict):
        steps: Annotated[list, add]

    sub = StateGraph(SharedState)
    sub.add_node("a", lambda s: {"steps": ["sub:a"]})
    sub.add_node("b", lambda s: {"steps": ["sub:b"]})
    sub.add_edge(START, "a")
    sub.add_edge("a", "b")
    sub.add_edge("b", END)
    compiled_sub = sub.compile()

    parent = StateGraph(SharedState)
    parent.add_node("pre", lambda s: {"steps": ["parent:pre"]})
    parent.add_node("sub", compiled_sub)  # 直接把编译好的子图当节点
    parent.add_edge(START, "pre")
    parent.add_edge("pre", "sub")
    parent.add_edge("sub", END)
    app = parent.compile()

    out = app.invoke({"steps": []})
    # state 透传:父节点 + 子图内两步都累积进同一个 steps(子图与父图共享 reducer channel)。
    # 注:直接把编译子图当节点 + add reducer 时,父节点已写入的值会被子图再次并入,
    #     故 "parent:pre" 出现两次(LangGraph 子图共享 channel 的已知行为)。这里只断言
    #     三段都到齐、且父节点先于子图两步(顺序透传),不依赖那次重复计数。
    assert "parent:pre" in out["steps"]
    assert ["sub:a", "sub:b"] == [s for s in out["steps"] if s.startswith("sub:")]
    # 父节点先于子图内部步骤(state 顺序贯穿父→子)
    assert out["steps"].index("parent:pre") < out["steps"].index("sub:a")
