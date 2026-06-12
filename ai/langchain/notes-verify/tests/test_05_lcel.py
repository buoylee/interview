"""校验 `ai/langchain/05-lcel-deep-dive.md` 的关键声称。

本章是全套里最"纯机制"的一章 —— 几乎所有声称都是确定性、离线、无需 key 的
Runnable 行为。所以离线测试给得很厚(~10 个),把面试必背的 Runnable 机制 +
经典 gotcha 全部钉成可跑的断言。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制,用 langchain_core 内置 Runnable + GenericFakeChatModel,
  确定性、无需 key、始终绿。链全部由 lambda + 假模型搭出来,结果完全可定。
- live 测试(`@pytest.mark.live`):只保留一个假模型证明不了的东西 ——
  真实 `prompt | llm | StrOutputParser()` 端到端返回非空串。无 key 时自动 skip。

跑法:
    uv run pytest tests/test_05_lcel.py            # 仅离线
    uv run pytest tests/test_05_lcel.py -m live    # 真实 OpenAI(需 key)
"""

import pytest

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §三 3.1 —— RunnablePassthrough() 原封不动透传输入(dict 或 str 都一样)
def test_passthrough_returns_input_unchanged():
    assert RunnablePassthrough().invoke("什么是 RAG?") == "什么是 RAG?"
    payload = {"a": 1, "b": 2}
    out = RunnablePassthrough().invoke(payload)
    assert out == {"a": 1, "b": 2}


# §三 3.2 —— RunnablePassthrough.assign(...) 是经典 gotcha:
#            保留所有旧 key,同时追加新 key(不是覆盖、不是只留新的)
def test_passthrough_assign_keeps_old_keys_and_adds_new():
    chain = RunnablePassthrough.assign(
        word_count=lambda x: len(x["question"]),
        upper=lambda x: x["question"].upper(),
    )
    result = chain.invoke({"question": "rag"})
    # 旧 key 原样保留
    assert result["question"] == "rag"
    # 新 key 追加进来
    assert result["word_count"] == 3
    assert result["upper"] == "RAG"
    # 没多没少:就是 旧 ∪ 新
    assert set(result) == {"question", "word_count", "upper"}


# §三 3.3 —— RunnableParallel 并行跑各分支,返回以分支名为 key 的 dict;
#            而 `dict 简写 | next` 里那个 dict 会被自动转成 RunnableParallel
def test_runnable_parallel_and_dict_shorthand():
    parallel = RunnableParallel(
        doubled=lambda x: x * 2,
        squared=lambda x: x * x,
    )
    assert parallel.invoke(3) == {"doubled": 6, "squared": 9}
    assert isinstance(parallel, RunnableParallel)

    # dict 简写出现在 `|` 链里:第一步被自动 coerce 成 RunnableParallel
    chain = {"doubled": lambda x: x * 2, "squared": lambda x: x * x} | RunnableLambda(
        lambda d: d
    )
    assert isinstance(chain.steps[0], RunnableParallel)
    assert chain.invoke(3) == {"doubled": 6, "squared": 9}


# §三 3.4 —— RunnableLambda 把普通函数变成 Runnable;
#            在 `|` 链里裸函数会被 LCEL 自动包装成 RunnableLambda(无需显式)
def test_runnable_lambda_wraps_and_autowraps():
    rl = RunnableLambda(lambda x: x + 1)
    assert isinstance(rl, Runnable)
    assert rl.invoke(5) == 6

    # 链尾用裸 lambda:LCEL 自动包成 RunnableLambda
    chain = RunnableLambda(lambda x: x + 1) | (lambda x: x * 10)
    assert [type(s).__name__ for s in chain.steps] == ["RunnableLambda", "RunnableLambda"]
    assert chain.invoke(2) == 30  # (2+1)*10


# §三 3.5 —— RunnableBranch 按条件挑分支;最后一个不带条件的是默认分支
def test_runnable_branch_routes_by_condition():
    branch = RunnableBranch(
        (lambda x: "代码" in x, lambda x: "CODE"),
        (lambda x: "翻译" in x, lambda x: "TRANS"),
        lambda x: "GENERAL",  # 默认
    )
    assert branch.invoke("帮我写一段代码") == "CODE"
    assert branch.invoke("帮我翻译这句") == "TRANS"
    assert branch.invoke("随便聊聊") == "GENERAL"  # 命中默认分支


# §一 1.1 / §四 4.1 —— `|` 组合:前一步输出自动喂给下一步;.invoke 跑完整条链
#                      链本身也是 Runnable(可嵌套)
def test_pipe_composition_threads_output_to_input():
    chain = (
        RunnableLambda(lambda x: x + 1)
        | RunnableLambda(lambda x: x * 2)
        | RunnableLambda(lambda x: f"={x}")
    )
    assert isinstance(chain, Runnable)
    assert chain.invoke(3) == "=8"  # ((3+1)*2) -> "=8"


# §七 7.2 —— with_fallbacks:主链抛错时自动切到备用链(用会抛错的 lambda,不碰真 LLM)
def test_with_fallbacks_switches_on_error():
    def boom(_):
        raise RuntimeError("primary down")

    primary = RunnableLambda(boom)
    fallback = RunnableLambda(lambda x: f"fallback:{x}")
    resilient = primary.with_fallbacks([fallback])
    assert resilient.invoke("hi") == "fallback:hi"


# §七 7.1 —— with_retry:瞬时错误会被自动重试,直到成功或耗尽次数
def test_with_retry_retries_until_success():
    # 用闭包计数,避免全局状态污染
    state = {"calls": 0}

    def flaky(_):
        state["calls"] += 1
        if state["calls"] < 3:
            raise ValueError("transient")
        return "ok"

    retried = RunnableLambda(flaky).with_retry(stop_after_attempt=3)
    assert retried.invoke("x") == "ok"
    assert state["calls"] == 3  # 前两次失败,第三次成功


# §五 —— .bind(...) 固定 kwargs:返回仍是 Runnable,且把 kwargs 记在 .kwargs 上
#         (常见用法:llm.bind(tools=...) / llm.bind(stop=...))
def test_bind_fixes_kwargs_on_chat_model():
    llm = GenericFakeChatModel(messages=iter(["hi"]))
    bound = llm.bind(stop=["\n\nHuman:"], temperature=0)
    assert isinstance(bound, Runnable)
    assert bound.kwargs == {"stop": ["\n\nHuman:"], "temperature": 0}
    assert bound.bound is llm  # 包裹的还是原模型


# §二 2.3 —— get_input_schema / get_output_schema 反映链声明的输入输出类型:
#            prompt 变量 {question} 体现在 input schema;StrOutputParser 结尾 -> str
def test_input_output_schemas_reflect_declared_types():
    prompt = ChatPromptTemplate.from_messages([("human", "Answer: {question}")])
    llm = GenericFakeChatModel(messages=iter(["resp"]))
    chain = prompt | llm | StrOutputParser()

    in_schema = chain.get_input_schema().model_json_schema()
    assert in_schema["properties"]["question"]["type"] == "string"
    assert in_schema["required"] == ["question"]

    out_schema = chain.get_output_schema().model_json_schema()
    assert out_schema["type"] == "string"  # StrOutputParser 输出 str


# §四 4.2 —— RAG 形 dict({context: retriever, question: Passthrough})端到端:
#            两个分支并行,Passthrough 透传原始问题,结果合成 dict 喂下一步;
#            并用假模型搭出 RunnableParallel,.batch 返回与输入等长的 list
def test_rag_shape_chain_and_batch_over_fakes():
    def fake_retriever(q):
        return f"DOCS[{q}]"

    chain = {
        "context": RunnableLambda(fake_retriever),
        "question": RunnablePassthrough(),
    } | RunnableLambda(lambda d: f"{d['question']} :: {d['context']}")

    assert chain.invoke("什么是 RAG?") == "什么是 RAG? :: DOCS[什么是 RAG?]"

    # 假模型并行分支:返回以分支名为 key 的 dict
    parallel = RunnableParallel(
        a=GenericFakeChatModel(messages=iter(["A_RESP"])) | StrOutputParser(),
        b=GenericFakeChatModel(messages=iter(["B_RESP"])) | StrOutputParser(),
    )
    assert parallel.invoke("anything") == {"a": "A_RESP", "b": "B_RESP"}

    # .batch 在一条链上跑:返回 list,长度与输入一致
    out = chain.batch(["q1", "q2", "q3"])
    assert isinstance(out, list) and len(out) == 3
    assert out[0] == "q1 :: DOCS[q1]"


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §一 1.1 / §四 4.1 / §八 8.1 —— 真实端到端链 prompt | llm | StrOutputParser():
#   假模型证明不了"真 LLM 接进 LCEL 也照常串联"。验证整条链 .invoke 返回非空 str。
@pytest.mark.live
def test_live_prompt_llm_parser_returns_nonempty_string():
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages([("human", "用一个词回答:{q}")])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=16)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({"q": "LangChain 是什么?"})
    assert isinstance(result, str)  # StrOutputParser 把 AIMessage 解成 str
    assert result.strip()  # 非空
