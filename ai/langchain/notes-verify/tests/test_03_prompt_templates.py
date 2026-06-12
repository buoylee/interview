"""校验 `ai/langchain/03-prompt-templates.md` 的关键声称。

每个测试上方注释指向它所证明的笔记章节。
- 本章基本全是纯机制(模板格式化),离线、确定性、无需 key,始终绿。
- 需要 chat model 接线时用 langchain_core 内置假模型 GenericFakeChatModel。
- 本章不涉及真实 LLM 行为,因此没有 live 测试。

跑法:
    uv run pytest tests/test_03_prompt_templates.py            # 全离线
"""

import pytest

# 笔记 §三 3.1(line 112)用的就是 `from langchain.messages import ...`,v1.x 仍有效
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompt_values import ChatPromptValue, StringPromptValue
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)

# --------------------------------------------------------------------------- #
# 离线:纯模板机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §一 1.1 / §二 2.1 —— PromptTemplate(字符串模板) vs ChatPromptTemplate(消息模板):
#   两者 invoke 返回的 PromptValue 类型不同;.format / .input_variables 行为各异
def test_prompt_template_vs_chat_prompt_template():
    # PromptTemplate:字符串模板,.format() 返回 str,.invoke() 返回 StringPromptValue
    str_tmpl = PromptTemplate.from_template("解释{concept}，给{audience}听")
    assert set(str_tmpl.input_variables) == {"concept", "audience"}  # 自动推断变量
    assert str_tmpl.format(concept="装饰器", audience="新手") == "解释装饰器，给新手听"
    sv = str_tmpl.invoke({"concept": "装饰器", "audience": "新手"})
    assert isinstance(sv, StringPromptValue)
    assert sv.to_string() == "解释装饰器，给新手听"

    # ChatPromptTemplate:消息模板,.invoke() 返回 ChatPromptValue(里面是 Message 列表)
    chat_tmpl = ChatPromptTemplate.from_template("hi {x}")
    assert isinstance(chat_tmpl.invoke({"x": "a"}), ChatPromptValue)


# §二 2.1 —— from_messages():input_variables 从 {占位符} 自动推断;
#   invoke({...}) 返回 ChatPromptValue,展开为对应角色的 Message 列表
def test_from_messages_infers_vars_and_formats_messages():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "你是一个{role}，用{language}回答"),
            ("human", "{question}"),
        ]
    )
    # 三个占位符都被推断为输入变量(顺序按字母排序,故用集合比较)
    assert set(prompt.input_variables) == {"role", "language", "question"}

    value = prompt.invoke({"role": "Python 专家", "language": "中文", "question": "什么是装饰器?"})
    assert isinstance(value, ChatPromptValue)
    messages = value.to_messages()
    assert [type(m) for m in messages] == [SystemMessage, HumanMessage]
    # 变量被代入 content
    assert messages[0].content == "你是一个Python 专家，用中文回答"
    assert messages[1].content == "什么是装饰器?"


# §二 2.1 / 2.3 —— from_template() 默认生成单条 HumanMessage(简单场景);
#   .format_messages(**kw) 与 .invoke({...}) 等价,只是签名不同
def test_from_template_defaults_to_human_and_format_messages():
    prompt = ChatPromptTemplate.from_template("解释{concept}")
    assert prompt.input_variables == ["concept"]
    msgs = prompt.invoke({"concept": "闭包"}).to_messages()
    assert [type(m) for m in msgs] == [HumanMessage]  # 默认就是 HumanMessage

    # format_messages(关键字参数) 等价于 invoke(字典)
    via_kwargs = prompt.format_messages(concept="闭包")
    assert [(type(m), m.content) for m in via_kwargs] == [(type(m), m.content) for m in msgs]


# §二 2.2 —— 元组角色简写映射到对应 Message 类型:
#   system→SystemMessage, human→HumanMessage, ai→AIMessage
def test_tuple_roles_map_to_message_types():
    prompt = ChatPromptTemplate.from_messages(
        [("system", "系统指令"), ("human", "用户消息"), ("ai", "AI 回复")]
    )
    msgs = prompt.invoke({}).to_messages()
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage]
    assert [m.content for m in msgs] == ["系统指令", "用户消息", "AI 回复"]


# §三 3.1 / 3.4 —— MessagesPlaceholder 插入的是「消息对象列表」(每个带 role),
#   而非字符串变量;占位符名进入 input_variables
def test_messages_placeholder_injects_message_objects():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "你是一个有帮助的助手"),
            MessagesPlaceholder("history"),
            ("human", "{input}"),
        ]
    )
    assert set(prompt.input_variables) == {"history", "input"}

    msgs = prompt.invoke(
        {
            "history": [HumanMessage(content="你好"), AIMessage(content="你好！")],
            "input": "记得吗？",
        }
    ).to_messages()
    # 历史的两条 Message 被原样插在中间,保留各自 role(不是拼成一条字符串)
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in msgs] == ["你是一个有帮助的助手", "你好", "你好！", "记得吗？"]


# §三 3.2 —— ("placeholder", "{name}") 简写完全等价于 MessagesPlaceholder("name")
def test_placeholder_shorthand_equals_messages_placeholder():
    history = [HumanMessage(content="你好"), AIMessage(content="你好！")]
    explicit = ChatPromptTemplate.from_messages(
        [("system", "助手"), MessagesPlaceholder("history"), ("human", "{input}")]
    )
    shorthand = ChatPromptTemplate.from_messages(
        [("system", "助手"), ("placeholder", "{history}"), ("human", "{input}")]
    )
    a = explicit.invoke({"history": history, "input": "x"}).to_messages()
    b = shorthand.invoke({"history": history, "input": "x"}).to_messages()
    assert [(type(m), m.content) for m in a] == [(type(m), m.content) for m in b]


# §三 3.3 —— optional=True 的 placeholder 不传也不报错;必填(默认)不传则 KeyError
def test_optional_placeholder_is_skippable():
    optional = ChatPromptTemplate.from_messages(
        [
            ("system", "你是一个助手"),
            MessagesPlaceholder("history", optional=True),
            ("human", "{input}"),
        ]
    )
    # optional 的占位符不进入必填 input_variables,缺省时安全跳过
    assert "history" not in optional.input_variables
    msgs = optional.invoke({"input": "hello"}).to_messages()
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage]

    # 对比:必填 placeholder 不传值会在 invoke 时抛 KeyError
    required = ChatPromptTemplate.from_messages(
        [("system", "s"), MessagesPlaceholder("history"), ("human", "{input}")]
    )
    with pytest.raises(KeyError):
        required.invoke({"input": "hello"})


# §五 5.1 / 5.2 —— partial() 预填充部分变量(返回新模板,被填的变量从 input_variables 移除);
#   partial 的值可以是字符串,也可以是「调用时求值」的函数
def test_partial_prefills_variables():
    prompt = ChatPromptTemplate.from_messages(
        [("system", "你是{company}的客服，用{language}回答"), ("human", "{question}")]
    )
    assert set(prompt.input_variables) == {"company", "language", "question"}

    # 用字符串预填充:剩下只需 question
    partial_prompt = prompt.partial(company="鹅厂", language="中文")
    assert partial_prompt.input_variables == ["question"]
    sys_content = partial_prompt.invoke({"question": "退货政策?"}).to_messages()[0].content
    assert sys_content == "你是鹅厂的客服，用中文回答"

    # 用函数预填充:函数在格式化时被调用求值
    def get_time():
        return "FIXED_TIME"

    timed = ChatPromptTemplate.from_messages(
        [("system", "当前时间是 {time}。"), ("human", "{input}")]
    ).partial(time=get_time)
    assert timed.input_variables == ["input"]
    assert timed.invoke({"input": "x"}).to_messages()[0].content == "当前时间是 FIXED_TIME。"


# §四 4.1 / 4.2 —— FewShotChatMessagePromptTemplate 把每个 example 用 example_prompt
#   展开成 human/ai 对,夹在 system 与实际输入之间;只有 {text} 是外部输入变量
def test_few_shot_chat_message_prompt_template():
    examples = [
        {"input": "太棒了", "output": "积极"},
        {"input": "很差劲", "output": "消极"},
        {"input": "还可以", "output": "中立"},
    ]
    example_prompt = ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")])
    few_shot = FewShotChatMessagePromptTemplate(example_prompt=example_prompt, examples=examples)
    final_prompt = ChatPromptTemplate.from_messages(
        [("system", "你是一个情感分析专家"), few_shot, ("human", "{text}")]
    )
    # examples 的字段(input/output)被 few_shot 内部消化,不暴露为外部变量
    assert final_prompt.input_variables == ["text"]

    msgs = final_prompt.invoke({"text": "性价比很高"}).to_messages()
    # 1 条 system + 3*(human+ai) 示例 + 1 条实际 human = 8 条
    assert [type(m) for m in msgs] == [
        SystemMessage,
        HumanMessage, AIMessage,  # 示例 1
        HumanMessage, AIMessage,  # 示例 2
        HumanMessage, AIMessage,  # 示例 3
        HumanMessage,             # 实际输入
    ]
    assert msgs[-1].content == "性价比很高"


# §六 6.2 —— 模板里的字面花括号要用 {{ }} 转义,否则会被当成变量;
#   转义后 {{ → { ,且不进入 input_variables
def test_literal_braces_must_be_escaped():
    prompt = ChatPromptTemplate.from_messages(
        [("system", '严格输出 JSON：{{"sentiment": "积极|消极|中立"}}'), ("human", "{text}")]
    )
    # 只有 {text} 是变量;{{ }} 是字面量,不算变量
    assert prompt.input_variables == ["text"]
    sys_content = prompt.invoke({"text": "好"}).to_messages()[0].content
    assert sys_content == '严格输出 JSON：{"sentiment": "积极|消极|中立"}'


# §七 —— prompt 是 Runnable,可用 `|` 串成链:prompt | model 把格式化后的消息喂给模型;
#   再接 StrOutputParser 把 AIMessage 抽成纯文本字符串
def test_prompt_pipes_into_model_via_lcel():
    prompt = ChatPromptTemplate.from_messages(
        [("system", "你是一个翻译助手"), ("human", "翻译成{lang}: {text}")]
    )

    # prompt | model:链的输出是模型返回的 AIMessage
    model = GenericFakeChatModel(messages=iter(["I love programming"]))
    out = (prompt | model).invoke({"lang": "英文", "text": "我爱编程"})
    assert isinstance(out, AIMessage)
    assert out.content == "I love programming"

    # 再接 StrOutputParser:输出抽成纯文本(是 str 子类,可直接当字符串用)
    model2 = GenericFakeChatModel(messages=iter(["I love programming"]))
    text = (prompt | model2 | StrOutputParser()).invoke({"lang": "英文", "text": "我爱编程"})
    assert isinstance(text, str)
    assert text == "I love programming"
