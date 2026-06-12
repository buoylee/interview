"""校验 `ai/langchain/04-output-parsers.md` 的关键声称。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制。Output parsing 本质是确定性的——喂 parser 已知字符串,或把
  `GenericFakeChatModel` 吐固定文本后接 parser,断言解析结果。无需 key、始终绿。
- live 测试(`@pytest.mark.live`):调真实 OpenAI(gpt-4o-mini),无 key 时自动 skip。

跑法:
    uv run pytest tests/test_04_output_parsers.py            # 仅离线
    uv run pytest tests/test_04_output_parsers.py -m live    # 真实 OpenAI(需 key)

笔记纠偏(import 路径漂移,见文末测试与 README):
- §3.3/§3.4 等用 `from langchain_core.output_parsers import PydanticOutputParser`,
  在 langchain-core 1.x 仍有效——本文件全用 `langchain_core.output_parsers`。
- §6.2 写 `from langchain.output_parsers import RetryOutputParser`,该模块在 v1.x
  已不存在;RetryOutputParser 现迁到 `langchain_classic.output_parsers`(见对应测试)。
"""

import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import (
    CommaSeparatedListOutputParser,
    JsonOutputParser,
    PydanticOutputParser,
    StrOutputParser,
)
from pydantic import BaseModel, Field


# 全文件复用的输出结构(对应 §3.2/§3.3 的 Movie)
class Movie(BaseModel):
    title: str = Field(description="电影名称")
    year: int = Field(description="上映年份")
    rating: float = Field(description="评分")


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §3.1 —— StrOutputParser 把 AIMessage 转成 str(提取 .content)
def test_str_output_parser_extracts_content_as_str():
    out = StrOutputParser().invoke(AIMessage(content="hello world"))
    # 返回值是 str(实现上是 str 的子类 TextAccessor,isinstance 仍为 True)
    assert isinstance(out, str)
    assert out == "hello world"  # 取的就是 AIMessage 的 content,不是整个 message


# §3.2 —— JsonOutputParser 把 JSON 文本解析成 dict;还能剥掉 ```json 围栏
def test_json_output_parser_to_dict():
    parser = JsonOutputParser()
    assert parser.parse('{"title": "肖申克的救赎", "year": 1994, "rating": 9.7}') == {
        "title": "肖申克的救赎",
        "year": 1994,
        "rating": 9.7,
    }
    assert isinstance(parser.parse('{"a": 1}'), dict)
    # 模型常把 JSON 包在 markdown 代码块里——parser 会自动剥掉围栏
    assert parser.parse('```json\n{"x": 10}\n```') == {"x": 10}


# §3.3 —— PydanticOutputParser 解析成强类型对象(带字段类型)
def test_pydantic_output_parser_to_typed_object():
    parser = PydanticOutputParser(pydantic_object=Movie)
    obj = parser.parse('{"title": "肖申克的救赎", "year": 1994, "rating": 9.7}')
    assert isinstance(obj, Movie)  # 真正的 Python 对象,不是 dict
    assert obj.title == "肖申克的救赎"
    assert obj.year == 1994 and isinstance(obj.year, int)  # 类型校验生效


# §3.4 —— CommaSeparatedListOutputParser 把逗号分隔文本切成 list[str]
def test_comma_separated_list_parser_to_list():
    parser = CommaSeparatedListOutputParser()
    assert parser.parse("苹果, 香蕉, 橙子") == ["苹果", "香蕉", "橙子"]
    assert isinstance(parser.parse("a, b"), list)


# §3.3 —— get_format_instructions() 返回非空提示串,且就是笔记引用的那句话
def test_format_instructions_non_empty_prompt_string():
    # 每种 parser 的 format_instructions 都非空
    for parser in (
        PydanticOutputParser(pydantic_object=Movie),
        JsonOutputParser(pydantic_object=Movie),
        CommaSeparatedListOutputParser(),
    ):
        fi = parser.get_format_instructions()
        assert isinstance(fi, str) and fi.strip()

    # §3.3 明确引用的开头句子,逐字核对
    pyd_fi = PydanticOutputParser(pydantic_object=Movie).get_format_instructions()
    assert pyd_fi.startswith(
        "The output should be formatted as a JSON instance that conforms to the"
    )
    assert "title" in pyd_fi  # schema 被嵌进了指令里


# §3.1/§3.2/§3.3/§3.4 —— parser 接在模型后面组成 LCEL 链,解析的是模型输出
def test_parser_piped_onto_model_in_lcel():
    # StrOutputParser:链的输出是 str 而非 AIMessage(§3.1)
    str_chain = GenericFakeChatModel(messages=iter(["piped text"])) | StrOutputParser()
    str_out = str_chain.invoke("x")
    assert isinstance(str_out, str) and str_out == "piped text"

    # JsonOutputParser:模型吐 JSON 文本,链产出 dict(§3.2)
    json_chain = (
        GenericFakeChatModel(messages=iter(['{"title": "Inception", "year": 2010}']))
        | JsonOutputParser()
    )
    assert json_chain.invoke("x") == {"title": "Inception", "year": 2010}

    # CommaSeparatedListOutputParser:产出 list[str](§3.4)
    csv_chain = (
        GenericFakeChatModel(messages=iter(["red, green, blue"]))
        | CommaSeparatedListOutputParser()
    )
    assert csv_chain.invoke("x") == ["red", "green", "blue"]

    # PydanticOutputParser:产出强类型对象(§3.3)
    pyd_chain = (
        GenericFakeChatModel(messages=iter(['{"title": "Matrix", "year": 1999, "rating": 8.7}']))
        | PydanticOutputParser(pydantic_object=Movie)
    )
    pyd_out = pyd_chain.invoke("x")
    assert isinstance(pyd_out, Movie) and pyd_out.title == "Matrix"


# §2.1/§2.2 —— with_structured_output(Pydantic) 把模型包成 Runnable,
#             并在底层把 Pydantic 模型转成 JSON Schema 走 tool/function calling
#             (构造不发网络请求,可纯离线验证 schema 绑定)
def test_with_structured_output_binds_pydantic_as_json_schema():
    from langchain_openai import ChatOpenAI

    class SentimentResult(BaseModel):
        """情感分析结果"""

        sentiment: str = Field(description="积极/消极/中立")
        confidence: float = Field(description="置信度")

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key="sk-test-dummy")
    structured = llm.with_structured_output(SentimentResult)

    # 返回的是可 invoke 的 Runnable(§2.1)
    assert hasattr(structured, "invoke")

    # §2.2 原理:Pydantic -> JSON Schema -> 作为 function 绑定给模型
    fmt = structured.steps[0].kwargs["ls_structured_output_format"]
    fn = fmt["schema"]["function"]
    assert fn["name"] == "SentimentResult"
    assert fn["description"] == "情感分析结果"  # docstring 进了 description
    params = fn["parameters"]
    # Field(description=...) 被翻成 JSON Schema 的属性描述
    assert params["properties"]["sentiment"] == {"description": "积极/消极/中立", "type": "string"}
    assert params["properties"]["confidence"]["type"] == "number"  # float -> number
    assert set(params["required"]) == {"sentiment", "confidence"}
    # 整体可序列化为合法 JSON Schema
    assert json.loads(json.dumps(params))["type"] == "object"


# §2.3 —— with_structured_output(TypedDict) 同样能构造成 Runnable(不需 Pydantic)
def test_with_structured_output_accepts_typeddict():
    from typing import Annotated, TypedDict

    from langchain_openai import ChatOpenAI

    class SentimentResult(TypedDict):
        sentiment: Annotated[str, "情感倾向"]
        confidence: Annotated[float, "置信度"]

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key="sk-test-dummy")
    structured = llm.with_structured_output(SentimentResult)
    assert hasattr(structured, "invoke")
    # TypedDict 也被转成同样的 function schema(字段进 properties)
    fn = structured.steps[0].kwargs["ls_structured_output_format"]["schema"]["function"]
    assert fn["name"] == "SentimentResult"
    assert set(fn["parameters"]["properties"]) == {"sentiment", "confidence"}
    assert fn["parameters"]["properties"]["confidence"]["type"] == "number"  # float -> number


# §6.2 纠偏 —— 笔记写的 `from langchain.output_parsers import RetryOutputParser`
#             在 v1.x 已失效;正确路径是 langchain_classic.output_parsers
def test_retry_output_parser_import_path_drift():
    import importlib

    # 笔记里的旧路径已不存在
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("langchain.output_parsers")

    # 现在它在 langchain_classic 下
    mod = importlib.import_module("langchain_classic.output_parsers")
    assert hasattr(mod, "RetryOutputParser")


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §2.1 —— with_structured_output 真实调用直接返回 Pydantic 对象(字段类型正确)
@pytest.mark.live
def test_live_with_structured_output_returns_pydantic():
    from langchain_openai import ChatOpenAI

    class SentimentResult(BaseModel):
        sentiment: str = Field(description="情感倾向: positive/negative/neutral")
        confidence: float = Field(description="置信度 0.0-1.0")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=64)
    result = llm.with_structured_output(SentimentResult).invoke(
        "这款手机太好用了,电池续航很长,强烈推荐购买!"
    )
    assert isinstance(result, SentimentResult)  # 直接是对象,无需手动解析
    assert isinstance(result.confidence, float)
    assert result.sentiment.strip()


# §3.2 —— prompt | model | JsonOutputParser 端到端真的产出 dict
@pytest.mark.live
def test_live_model_plus_json_parser_yields_dict():
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    parser = JsonOutputParser(pydantic_object=Movie)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "提取电影信息,以 JSON 格式输出。\n{format_instructions}"),
            ("human", "{input}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=64)

    result = (prompt | llm | parser).invoke({"input": "肖申克的救赎是1994年上映的,评分9.7"})
    assert isinstance(result, dict)
    assert result["year"] == 1994
