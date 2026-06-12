"""校验 `ai/langchain/11-production.md`(生产化章)的关键声称。

本章是生产/运维章,大部分是概念性指南(LangSmith/Langfuse 接入、部署方案、
Docker、安全规则、API Key 管理),没有可在本地确定性复现的运行时机制 —— 这些
只读不测。真正"运行时可断言"的就那么几条:错误处理(retry/fallback/超时)、
监控 Callback、batch 并发上限、以及两个纯 Python 守护逻辑(token 预算、工具白名单)。
本文件只把这些钉成离线、无需 key、始终绿的断言。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制,用 langchain_core 内置 Runnable + 自定义假模型,确定性、无需 key。
- live 测试(`@pytest.mark.live`):只保留一个假模型证明不了的东西 ——
  真实 OpenAI 调用时 max_retries/usage_metadata 真的生效。无 key 时自动 skip。

跑法:
    uv run pytest tests/test_11_production.py            # 仅离线
    uv run pytest tests/test_11_production.py -m live    # 真实 OpenAI(需 key)
"""

from typing import ClassVar

import pytest

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda


# --------------------------------------------------------------------------- #
# 测试用假模型:GenericFakeChatModel 默认不带 usage_metadata,这里派生两个变体
# --------------------------------------------------------------------------- #


class UsageFake(GenericFakeChatModel):
    """每次返回固定 content + usage_metadata(input 7 / output 3 / total 10)。
    用于证明监控 Callback 能从 on_llm_end 里读到 token 用量。"""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = AIMessage(
            content="answer",
            usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])


class FlakyModel(GenericFakeChatModel):
    """前两次 _generate 抛错,第三次成功 —— 模拟瞬时 API 故障。
    用 ClassVar 计数(pydantic 模型不能随便加实例属性),证明重试真的发生。"""

    calls: ClassVar[int] = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        FlakyModel.calls += 1
        if FlakyModel.calls < 3:
            raise RuntimeError("transient API error")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="recovered"))])


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §三 3.1 —— Chain 级 .with_retry(stop_after_attempt=3):瞬时错误自动重试到成功
def test_with_retry_recovers_from_transient_error():
    FlakyModel.calls = 0
    try:
        model = FlakyModel(messages=iter(["x"]))
        # 笔记里同款参数;jitter 关掉只是为了测试别真睡指数退避
        retried = model.with_retry(stop_after_attempt=3, wait_exponential_jitter=False)
        out = retried.invoke("hi")
        assert out.content == "recovered"
        assert FlakyModel.calls == 3  # 前两次失败,第三次成功
    finally:
        FlakyModel.calls = 0  # 别污染下一个用例的类计数器


# §三 3.1 —— 重试次数耗尽仍失败,则把最后一次异常抛出来(不会无限重试)
def test_with_retry_exhausts_and_raises():
    FlakyModel.calls = 0
    try:
        model = FlakyModel(messages=iter(["x"]))
        # 只给 2 次:第 1、2 次都抛错,没机会走到第 3 次的成功分支
        retried = model.with_retry(stop_after_attempt=2, wait_exponential_jitter=False)
        with pytest.raises(RuntimeError):
            retried.invoke("hi")
        assert FlakyModel.calls == 2  # 恰好试了 2 次就放弃
    finally:
        FlakyModel.calls = 0


# §三 3.2 —— 链级 .with_fallbacks([fallback_chain]):主链抛错时整条切到备用链
#            (不止单模型 fallback —— 备用项可以是完整的 prompt|llm|parser 链)
def test_chain_level_with_fallbacks_switches_on_error():
    def boom(_):
        raise RuntimeError("primary chain down")

    primary_chain = RunnableLambda(boom)
    fallback_chain = (
        ChatPromptTemplate.from_messages([("human", "{q}")])
        | GenericFakeChatModel(messages=iter(["fb answer"]))
        | StrOutputParser()
    )
    robust = primary_chain.with_fallbacks([fallback_chain])
    assert robust.invoke({"q": "hello"}) == "fb answer"


# §三 3.3 —— config={"recursion_limit": N}:Graph 超过最大步数会抛 GraphRecursionError
#            (笔记把它当作 "Agent 最大步数",底层就是 LangGraph 的递归上限)
def test_recursion_limit_caps_graph_steps():
    from typing import TypedDict

    from langgraph.errors import GraphRecursionError
    from langgraph.graph import START, StateGraph

    class S(TypedDict):
        n: int

    g = StateGraph(S)
    g.add_node("inc", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "inc")
    g.add_conditional_edges("inc", lambda s: "inc")  # 永远绕回自己 -> 无限循环
    app = g.compile()

    with pytest.raises(GraphRecursionError):
        app.invoke({"n": 0}, config={"recursion_limit": 5})


# §三 3.4 —— token 预算守护函数:累计 total_tokens 超阈值返回 END,否则返回 "continue"
#            (笔记给的是一段纯 Python 路由逻辑,这里照搬验证两个分支)
def test_token_budget_guard_routes_on_threshold():
    from langgraph.graph import END

    def check_token_budget(messages, max_tokens=100000):
        total = sum(
            msg.usage_metadata.get("total_tokens", 0)
            for msg in messages
            if hasattr(msg, "usage_metadata") and msg.usage_metadata
        )
        return END if total > max_tokens else "continue"

    over = [
        AIMessage(content="a", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 60000}),
        AIMessage(content="b", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 60000}),
    ]
    under = [AIMessage(content="a", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 100})]
    assert check_token_budget(over, max_tokens=100000) == END  # 12w > 10w,停
    assert check_token_budget(under, max_tokens=100000) == "continue"  # 远未超,继续


# §四 4.1 —— 工具输入校验(SQL 白名单守护):危险关键词被拦下,SELECT 放行
#            证明 @tool 包出来的工具内部的安全逻辑确实在 .invoke 时执行
def test_tool_input_validation_blocks_dangerous_sql():
    from langchain_core.tools import tool

    @tool
    def database_query(sql: str) -> str:
        """查询数据库(只允许 SELECT)"""
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
        if any(word in sql.upper() for word in forbidden):
            return "错误: 只允许 SELECT 查询"
        return f"OK ran: {sql}"

    assert database_query.invoke({"sql": "select * from t"}) == "OK ran: select * from t"
    assert database_query.invoke({"sql": "drop table users"}) == "错误: 只允许 SELECT 查询"
    # 大小写不敏感:小写 delete 也拦得住
    assert database_query.invoke({"sql": "delete from t"}) == "错误: 只允许 SELECT 查询"


# §七 —— 自定义 BaseCallbackHandler:on_llm_end 能从 response 里读到 usage_metadata
#         (笔记的 MonitoringCallback 就靠这个把 token 用量打到监控系统)
def test_monitoring_callback_reads_usage_on_llm_end():
    class MonitoringCallback(BaseCallbackHandler):
        recorded: ClassVar[list] = []

        def on_llm_end(self, response, **kwargs):
            usage = response.generations[0][0].message.usage_metadata
            if usage:
                MonitoringCallback.recorded.append(usage["total_tokens"])

    MonitoringCallback.recorded = []
    try:
        model = UsageFake(messages=iter(["x"]))
        model.invoke("hi", config={"callbacks": [MonitoringCallback()]})
        assert MonitoringCallback.recorded == [10]  # on_llm_end 拿到了 total_tokens=10
    finally:
        MonitoringCallback.recorded = []


# §一 1.2 / §七 —— RunnableConfig 的 tags / metadata / run_name 会一路传给 Callback
#                   (LangSmith/Langfuse/自定义监控都靠这条把每次运行打标、可检索)
def test_config_tags_and_metadata_propagate_to_callback():
    class Capture(BaseCallbackHandler):
        def __init__(self):
            self.tags = None
            self.metadata = None
            self.starts = 0

        def on_chain_start(self, serialized, inputs, **kwargs):
            self.starts += 1
            if self.tags is None:  # 只抓最外层那一次
                self.tags = kwargs.get("tags")
                self.metadata = kwargs.get("metadata")

    cap = Capture()
    chain = RunnableLambda(lambda x: x + 1) | RunnableLambda(lambda x: x * 2)
    out = chain.invoke(
        3,
        config={
            "callbacks": [cap],
            "tags": ["prod", "v2"],
            "metadata": {"user": "alice"},
            "run_name": "scoring",
        },
    )
    assert out == 8
    assert cap.starts >= 1
    assert cap.tags == ["prod", "v2"]  # tags 原样透传
    assert cap.metadata.get("user") == "alice"  # metadata 透传(框架可能再加 ls_* 键)


# §六 —— batch(..., config={"max_concurrency": N}):上限 N 限制同时在飞的任务数,
#         且结果完整、与输入等长、保序(性能优化表里"batch + max_concurrency"提高吞吐)
def test_batch_max_concurrency_caps_parallelism_and_keeps_order():
    import threading
    import time

    active = {"now": 0, "max": 0}
    lock = threading.Lock()

    def slow(x):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.03)
        with lock:
            active["now"] -= 1
        return x * 2

    out = RunnableLambda(slow).batch(list(range(8)), config={"max_concurrency": 2})
    assert out == [i * 2 for i in range(8)]  # 结果完整、保序
    assert active["max"] <= 2  # 同时在飞的从未超过上限 2


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §三 3.1 / §七 —— 真实 ChatOpenAI:max_retries 是合法构造参数且能正常 invoke;
#   返回的 AIMessage 带 usage_metadata(监控 Callback 真上线时读的就是它)。
#   假模型证明不了"真 LLM 这条路确实有 usage_metadata"。
@pytest.mark.live
def test_live_chatopenai_retries_param_and_usage_metadata():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=16, max_retries=2, timeout=30)
    resp = llm.invoke("用一个词回答:LangChain 是什么?")
    assert isinstance(resp, AIMessage)
    assert resp.content.strip()
    assert resp.usage_metadata is not None
    assert resp.usage_metadata["total_tokens"] > 0
