"""校验 `ai/langchain/01-langchain-learning-path.md` 的关键声称。

本章是"路线图/总览"章节,绝大部分内容是学习计划与时长安排(纯叙述,不可断言)。
只有少数声称是运行期可验证的"结构性事实",这里把它们钉成断言:

1. 生态分层(总览框图):笔记点名的几个包确实可导入。
2. "LangChain Agent 底层用 LangGraph 实现"(总览框图最后一行)—— 这是本章最硬的
   架构声称,用 `create_agent` 返回 `CompiledStateGraph` 直接证明。
3. §1.5 Runnable 统一接口:所有组件共享 `.invoke/.stream/.batch`(及异步版)。
4. §1.5 Message 四类(System/Human/AI/Tool)都是 BaseMessage 子类。
5. 总览 / §1.2 init_chat_model 作为统一初始化入口,推断出 provider 专属类。

其余(学习顺序、天数、检查清单、推荐资源、LangChain vs LangGraph 类比表)都是
不可断言的叙述,本模块刻意不为凑数造测试。

本章没有需要真实 API key 的声称 —— 全部离线、确定性、始终绿,无 live 测试。

跑法:
    uv run pytest tests/test_01_learning_path.py            # 全部离线
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable, RunnableLambda


# --------------------------------------------------------------------------- #
# 离线:纯结构性事实,确定性,无需 API key
# --------------------------------------------------------------------------- #


# 总览(生态框图)—— 笔记点名的几个核心包都能导入,确实存在于当前生态里。
# 注意 notes-drift:笔记还点名了 `langchain-community`(v0.4.x,floor 仍满足)与
# `langsmith`,这里只校验"装得上、导得进",版本号不卡死(笔记给的是 >=0.3 这类下限)。
def test_ecosystem_packages_importable():
    import importlib

    # 笔记总览框图明确点名的 5 个 + §1.1 安装的集成包
    named = [
        "langchain_core",      # 核心抽象
        "langchain",           # 高层框架
        "langchain_community",  # 第三方集成
        "langgraph",           # 底层编排引擎
        "langsmith",           # 可观测性
        "langchain_openai",    # §1.1 集成包
    ]
    for pkg in named:
        mod = importlib.import_module(pkg)  # 导不进会直接抛 ImportError -> 测试失败
        assert mod is not None


# §1.5 / 总览 —— "Runnable 是所有组件的基础接口,支持 .invoke/.stream/.batch"。
# 用一个假聊天模型 + 一条 LCEL 链,两者都满足 isinstance(Runnable) 且方法俱全。
def test_runnable_is_universal_interface():
    fake = GenericFakeChatModel(messages=iter(["hi"]))
    chain = RunnableLambda(lambda x: x + 1) | RunnableLambda(lambda x: x * 2)

    # 笔记 §1.5 表格列的三个核心方法 + 它们的异步对应版
    core_methods = ["invoke", "stream", "batch", "ainvoke", "astream", "abatch"]

    for component in (fake, chain):
        assert isinstance(component, Runnable)
        for meth in core_methods:
            assert callable(getattr(component, meth, None)), f"{component} 缺 {meth}"

    # 链本身可跑,证明"链也是 Runnable,可嵌套组合"
    assert chain.invoke(3) == 8  # (3+1)*2


# 总览框图最后一行 —— "LangChain Agent 底层用 LangGraph 实现"。
# 本章最硬的架构声称:v1.x 的 langchain.agents.create_agent 直接返回一个
# langgraph 的 CompiledStateGraph(同时它也是 langchain_core 的 Runnable)。
# notes-drift:笔记 §3.2 写的 `create_react_agent()`/`AgentExecutor` 在 v1.x 的
# langchain.agents 里已不存在;统一入口现在是 `create_agent`(底层仍是 LangGraph)。
def test_langchain_agent_is_built_on_langgraph():
    from langchain.agents import create_agent
    from langchain_core.tools import tool
    from langgraph.graph.state import CompiledStateGraph

    @tool
    def add(a: int, b: int) -> int:
        """把两个整数相加。"""
        return a + b

    # 用假模型构建,无需 key、无网络
    agent = create_agent(GenericFakeChatModel(messages=iter(["hi"])), tools=[add])

    # 证 1:langchain 造出来的 Agent 就是一张编译好的 LangGraph 图
    assert isinstance(agent, CompiledStateGraph)
    assert type(agent).__module__.startswith("langgraph")
    # 证 2:同一对象又是 langchain_core 的 Runnable —— 生态在 Runnable 上闭环
    assert isinstance(agent, Runnable)
    # 证 3:图特有的能力在(可视化/拿图结构),坐实"底层是图"
    assert callable(agent.get_graph)


# §1.5 表 —— Message 的四种基本单元(System/Human/AI/Tool)都继承自 BaseMessage,
# 各自映射到固定 role。这是后续所有章节(prompt/tool/agent)消息流转的地基。
def test_message_types_are_basemessage_subclasses():
    # Message 对象不可哈希,用 (实例, 期望 role) 的列表而非 dict
    cases = [
        (SystemMessage(content="s"), "system"),
        (HumanMessage(content="h"), "human"),
        (AIMessage(content="a"), "ai"),
        (ToolMessage(content="t", tool_call_id="call_1"), "tool"),
    ]
    for msg, role in cases:
        assert isinstance(msg, BaseMessage)
        assert msg.type == role


# 总览 / §1.2 —— init_chat_model 作为"统一初始化入口",按 provider 返回专属类。
# 传 dummy key:构造期不发网络请求,只校验返回类型是 provider 专属的 BaseChatModel。
def test_init_chat_model_is_unified_initializer():
    from langchain.chat_models import init_chat_model
    from langchain_openai import ChatOpenAI

    model = init_chat_model(
        "gpt-4o-mini", model_provider="openai", api_key="sk-test-dummy"
    )
    assert isinstance(model, ChatOpenAI)
    assert isinstance(model, BaseChatModel)  # 落在统一的 ChatModel 抽象下
    assert isinstance(model, Runnable)       # 因而也共享 Runnable 接口
