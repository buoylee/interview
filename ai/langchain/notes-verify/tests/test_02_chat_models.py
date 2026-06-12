"""校验 `ai/langchain/02-chat-models.md` 的关键声称。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制,用 langchain_core 内置假模型,确定性、无需 key、始终绿。
- live 测试(`@pytest.mark.live`):调真实 OpenAI(gpt-4o-mini),无 key 时自动 skip。

跑法:
    uv run pytest tests/test_02_chat_models.py            # 仅离线
    uv run pytest tests/test_02_chat_models.py -m live    # 真实 OpenAI(需 key)
"""

from typing import ClassVar

import pytest

# 笔记 §二 用的就是 `from langchain.messages import ...`,这条 import 路径在 v1.x 仍有效
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.messages.utils import convert_to_messages
from langchain_core.outputs import ChatGeneration, ChatResult


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #

# §二 2.1 —— 四种核心 Message 各自映射到一个 role
def test_message_types_map_to_roles():
    assert SystemMessage(content="s").type == "system"
    assert HumanMessage(content="h").type == "human"
    assert AIMessage(content="a").type == "ai"
    assert ToolMessage(content="t", tool_call_id="call_1").type == "tool"


# §二 2.2 —— 元组简写 ("system", ...) 等价于 Message 对象
def test_tuple_shorthand_equals_message_objects():
    from_tuples = convert_to_messages([("system", "你是翻译专家"), ("human", "翻译:我爱编程")])
    explicit = [SystemMessage(content="你是翻译专家"), HumanMessage(content="翻译:我爱编程")]
    assert [type(m) for m in from_tuples] == [type(m) for m in explicit]
    assert [m.content for m in from_tuples] == [m.content for m in explicit]


# §二 2.4 —— ToolMessage 必须带 tool_call_id,且与 AIMessage.tool_calls 的 id 配对
def test_toolmessage_requires_matching_tool_call_id():
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "call_abc123", "name": "get_weather", "args": {"city": "北京"}}],
    )
    tool = ToolMessage(content="北京: 晴天, 25°C", tool_call_id="call_abc123")
    assert tool.tool_call_id == ai.tool_calls[0]["id"]  # 请求-响应配对
    # tool_call_id 是必填:缺了直接构造失败
    with pytest.raises(Exception):
        ToolMessage(content="缺 id")


# §四 4.5 —— invoke / stream / batch 的返回类型
def test_invoke_stream_batch_return_types():
    # invoke -> 单个 AIMessage
    assert isinstance(GenericFakeChatModel(messages=iter(["hi"])).invoke("x"), AIMessage)
    # stream -> 逐 chunk 的迭代器,每个是 AIMessageChunk
    chunks = list(GenericFakeChatModel(messages=iter(["a b c"])).stream("x"))
    assert chunks and all(isinstance(c, AIMessageChunk) for c in chunks)
    # batch -> list[AIMessage],长度与输入一致
    out = GenericFakeChatModel(messages=iter(["p", "q"])).batch(["1", "2"])
    assert isinstance(out, list) and [type(m) for m in out] == [AIMessage, AIMessage]


# §四 4.2 —— 流式 chunk 用 `+` 累加即可重建完整文本
def test_aimessagechunk_concatenation():
    chunks = list(GenericFakeChatModel(messages=iter(["你好 世界"])).stream("x"))
    acc = chunks[0]
    for c in chunks[1:]:
        acc = acc + c
    assert isinstance(acc, AIMessageChunk)
    assert acc.content == "你好 世界"


# §六 6.3 —— 主模型抛错时 with_fallbacks 自动切到备用模型
def test_with_fallbacks_switches_on_error():
    class Boom(GenericFakeChatModel):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("primary down")

    primary = Boom(messages=iter(["never"]))
    fallback = GenericFakeChatModel(messages=iter(["from fallback"]))
    resilient = primary.with_fallbacks([fallback])
    assert resilient.invoke("hi").content == "from fallback"


# §七 —— init_chat_model 按模型名/显式 provider 推断出 ChatOpenAI
def test_init_chat_model_infers_provider():
    from langchain.chat_models import init_chat_model
    from langchain_openai import ChatOpenAI

    # 传 dummy key:构造不发网络请求,只在 invoke 时才真正调用
    explicit = init_chat_model("gpt-4o", model_provider="openai", api_key="sk-test-dummy")
    inferred = init_chat_model("gpt-4o-mini", api_key="sk-test-dummy")  # 由名字推断 provider
    assert isinstance(explicit, ChatOpenAI)
    assert isinstance(inferred, ChatOpenAI)


# §五 —— 纯文本 content 是 str;多模态 content 是 list[dict],每项带 type
def test_multimodal_content_is_list_of_dict():
    assert isinstance(HumanMessage(content="纯文本").content, str)
    mm = HumanMessage(
        content=[
            {"type": "text", "text": "描述这张图片"},
            {"type": "image_url", "image_url": {"url": "https://example.com/i.jpg"}},
        ]
    )
    assert isinstance(mm.content, list)
    assert {part["type"] for part in mm.content} == {"text", "image_url"}


# §六 6.1 —— 相同输入命中缓存,底层模型只被真正调用一次
# 注意:笔记写的 `from langchain.globals import set_llm_cache` 在 v1.x 已失效,
#       正确路径是 `from langchain_core.globals import set_llm_cache`(见 README 笔记纠偏)。
def test_inmemory_cache_skips_second_call():
    from langchain_core.caches import InMemoryCache
    from langchain_core.globals import set_llm_cache

    class CountingFake(GenericFakeChatModel):
        calls: ClassVar[int] = 0

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            CountingFake.calls += 1
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="answer"))])

    set_llm_cache(InMemoryCache())
    try:
        model = CountingFake(messages=iter(["x"]))
        model.invoke("一样的问题")
        model.invoke("一样的问题")
        assert CountingFake.calls == 1  # 第二次命中缓存,没再调底层
        model.invoke("不一样的问题")
        assert CountingFake.calls == 2  # 不同输入才会再调一次
    finally:
        set_llm_cache(None)  # 别污染全局状态


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


@pytest.fixture
def live_llm():
    from langchain_openai import ChatOpenAI

    # 小 max_tokens 控成本;temperature=0 让输出尽量稳定
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=16)


# §四 4.1 / §二 2.3 —— 真实 invoke 返回 AIMessage,且 usage_metadata 有值
@pytest.mark.live
def test_live_invoke_returns_aimessage_with_usage(live_llm):
    resp = live_llm.invoke("用一个词回答:LangChain 是什么?")
    assert isinstance(resp, AIMessage)
    assert resp.content.strip()
    assert resp.usage_metadata is not None
    assert resp.usage_metadata["total_tokens"] > 0


# §四 4.2 —— 真实 stream 吐出多个 chunk,拼起来非空;stream_usage 开启后末 chunk 带 usage
@pytest.mark.live
def test_live_stream_reconstructs_and_reports_usage():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=16, stream_usage=True)
    chunks = list(llm.stream("从 1 数到 5"))
    assert len(chunks) >= 1
    full = "".join(str(c.content) for c in chunks)
    assert full.strip()
    # stream_usage=True 时,usage 出现在(通常是最后一个)chunk 上
    assert any(c.usage_metadata for c in chunks)


# §八 8.3 / §二 2.3 —— usage_metadata 的 input + output == total
@pytest.mark.live
def test_live_usage_totals_add_up(live_llm):
    um = live_llm.invoke("hi").usage_metadata
    assert um["input_tokens"] + um["output_tokens"] == um["total_tokens"]
