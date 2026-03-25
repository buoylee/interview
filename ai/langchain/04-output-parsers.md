# 第1章：Output Parsers — 结构化输出

> 让 LLM 输出结构化数据而非自由文本，是 AI 应用工程化的关键能力。

---

## 一、为什么需要结构化输出

### 1.1 问题

LLM 默认输出自由文本，但应用程序需要的是**结构化数据**（JSON、对象、列表）。

```python
# LLM 原始输出 — 不可靠，格式随机
"用户的情绪是积极的，置信度大约80%，关键词有'好用'、'推荐'"

# 我们需要的 — 可编程处理
{"sentiment": "积极", "confidence": 0.8, "keywords": ["好用", "推荐"]}
```

### 1.2 LangChain 提供的两类方案

| 方案 | 原理 | 推荐度 |
|------|------|--------|
| **`with_structured_output()`** | 利用模型原生的 Function Calling/Tool Calling | ⭐⭐⭐ **强烈推荐** |
| **Output Parsers** | 在 Prompt 中加格式说明 + 后处理解析 | ⭐⭐ 备选方案 |

---

## 二、`with_structured_output()` — 推荐方式

### 2.1 基本用法 — Pydantic 模型

```python
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# 定义输出结构
class SentimentResult(BaseModel):
    """情感分析结果"""
    sentiment: str = Field(description="情感倾向: 积极/消极/中立")
    confidence: float = Field(description="置信度 0.0-1.0")
    keywords: list[str] = Field(description="关键词列表")
    summary: str = Field(description="一句话总结")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 绑定结构化输出
structured_llm = llm.with_structured_output(SentimentResult)

# 调用 — 直接返回 Pydantic 对象！
result = structured_llm.invoke("这款手机太好用了，电池续航很长，推荐购买！")

print(result.sentiment)    # "积极"
print(result.confidence)   # 0.95
print(result.keywords)     # ["好用", "电池续航", "推荐"]
print(result.summary)      # "用户对手机高度满意"
print(type(result))        # <class 'SentimentResult'>  ← 真正的 Python 对象
```

### 2.2 原理解析 (面试必知)

```
with_structured_output() 的底层机制：

1. 把 Pydantic 模型 → 转换为 JSON Schema
2. 通过模型的 Tool Calling / Function Calling 接口发送 Schema
3. 模型被约束只能输出符合 Schema 的 JSON
4. LangChain 自动将 JSON → 反序列化为 Pydantic 对象

关键: 这不是 "让 LLM 输出 JSON 然后解析"
      而是 "利用模型原生能力约束输出格式"
      → 更可靠，失败率更低
```

### 2.3 TypedDict 方式

不想用 Pydantic 时，可以用 TypedDict。

```python
from typing import TypedDict, Annotated

class SentimentResult(TypedDict):
    """情感分析结果"""
    sentiment: Annotated[str, "情感倾向"]
    confidence: Annotated[float, "置信度"]
    keywords: Annotated[list[str], "关键词"]

structured_llm = llm.with_structured_output(SentimentResult)
result = structured_llm.invoke("这个产品不好用")
# result 是普通 dict: {"sentiment": "消极", "confidence": 0.9, ...}
```

### 2.4 JSON Schema 方式

```python
json_schema = {
    "title": "SentimentResult",
    "description": "情感分析结果",
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "description": "积极/消极/中立"},
        "confidence": {"type": "number", "description": "置信度"},
    },
    "required": ["sentiment", "confidence"],
}

structured_llm = llm.with_structured_output(json_schema)
```

### 2.5 method 参数

```python
# 两种底层实现方式
structured_llm = llm.with_structured_output(
    SentimentResult,
    method="function_calling"  # 默认, 用 Function Calling
)

structured_llm = llm.with_structured_output(
    SentimentResult,
    method="json_mode"  # 用 JSON Mode (部分模型支持)
)

# 区别:
# function_calling: 更可靠，有 schema 校验
# json_mode: 更自由，但需要在 prompt 中说明格式
```

### 2.6 include_raw — 获取原始响应

```python
structured_llm = llm.with_structured_output(SentimentResult, include_raw=True)
result = structured_llm.invoke("很棒的产品")

# result 包含:
# {
#   "raw": AIMessage(...),           ← 原始 AIMessage
#   "parsed": SentimentResult(...),  ← 解析后的对象
#   "parsing_error": None            ← 解析错误 (如果有)
# }
```

### 2.7 面试深度问题

> **Q: `with_structured_output()` 和 Output Parser 有什么本质区别？**
>
> A: `with_structured_output()` 利用模型的**原生 Tool/Function Calling 能力**，模型在生成时就被 JSON Schema 约束，输出格式由模型保证。Output Parser 则是在 Prompt 中告诉模型 "请输出 JSON"，然后在收到文本后用代码解析——这依赖模型 "遵守指令" 的能力，更容易出错。**生产环境优先用 `with_structured_output()`**，只有当模型不支持 Function Calling 时才用 Output Parser。

---

## 三、Output Parsers — 传统方式

### 3.1 StrOutputParser — 提取纯文本

```python
from langchain_core.output_parsers import StrOutputParser

chain = prompt | llm | StrOutputParser()
result = chain.invoke({"input": "hello"})
# result 是 str, 而非 AIMessage
```

**用途**：最简单的 Parser，将 AIMessage 转为 str。几乎所有 LCEL 链都会用到。

### 3.2 JsonOutputParser

```python
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class Movie(BaseModel):
    title: str = Field(description="电影名称")
    year: int = Field(description="上映年份")
    rating: float = Field(description="评分")

parser = JsonOutputParser(pydantic_object=Movie)

prompt = ChatPromptTemplate.from_messages([
    ("system", "提取电影信息，以 JSON 格式输出。\n{format_instructions}"),
    ("human", "{input}"),
])

# 注入格式说明
chain = prompt.partial(
    format_instructions=parser.get_format_instructions()
) | llm | parser

result = chain.invoke({"input": "肖申克的救赎是1994年上映的，评分9.7"})
# {"title": "肖申克的救赎", "year": 1994, "rating": 9.7}
```

### 3.3 PydanticOutputParser

```python
from langchain_core.output_parsers import PydanticOutputParser

parser = PydanticOutputParser(pydantic_object=Movie)

# get_format_instructions() 生成的指令示例:
# "The output should be formatted as a JSON instance that conforms to the
#  JSON schema below. {schema}"
```

### 3.4 CommaSeparatedListOutputParser

```python
from langchain_core.output_parsers import CommaSeparatedListOutputParser

parser = CommaSeparatedListOutputParser()
# 输出 "苹果, 香蕉, 橙子" → ["苹果", "香蕉", "橙子"]
```

### 3.5 面试对比表

| Parser | 输入 | 输出 | 适用场景 |
|--------|------|------|----------|
| `StrOutputParser` | AIMessage | str | 最基础，LCEL 链必备 |
| `JsonOutputParser` | AIMessage | dict | 需要 JSON 但模型不支持 FC |
| `PydanticOutputParser` | AIMessage | Pydantic obj | 需要类型校验 |
| `CommaSeparatedListOutputParser` | AIMessage | list[str] | 简单列表输出 |
| `with_structured_output()` | — | Pydantic/dict | **生产首选** |

---

## 四、Enum 类型 — 限定输出选项

```python
from enum import Enum

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class ClassificationResult(BaseModel):
    sentiment: Sentiment = Field(description="情感分类")
    reason: str = Field(description="分类理由")

structured_llm = llm.with_structured_output(ClassificationResult)
result = structured_llm.invoke("这个产品还不错")
# result.sentiment == Sentiment.POSITIVE
```

---

## 五、嵌套结构 — 复杂输出

```python
class Address(BaseModel):
    city: str
    district: str
    street: str

class Person(BaseModel):
    name: str
    age: int
    address: Address                    # 嵌套对象
    hobbies: list[str]                  # 列表
    scores: dict[str, float]            # 字典
    emergency_contact: Person | None    # 可选 + 自引用

structured_llm = llm.with_structured_output(Person)
result = structured_llm.invoke(
    "张三，25岁，住在北京朝阳区建国路100号，爱好篮球和编程，"
    "数学95分英语88分，紧急联系人是他妈妈李四42岁"
)
```

---

## 六、错误处理

### 6.1 解析失败的处理

```python
# with_structured_output 失败时返回 None
result = structured_llm.invoke("一些无关内容")
# 可能返回 None 或不完整的对象

# 用 include_raw=True 来调试
structured_llm = llm.with_structured_output(SentimentResult, include_raw=True)
result = structured_llm.invoke("test")
if result["parsing_error"]:
    print(f"解析失败: {result['parsing_error']}")
    print(f"原始输出: {result['raw'].content}")
```

### 6.2 重试策略

```python
from langchain.output_parsers import RetryOutputParser

# 解析失败时，把错误信息 + 原始输出发回 LLM 让它修正
retry_parser = RetryOutputParser.from_llm(
    parser=PydanticOutputParser(pydantic_object=Movie),
    llm=llm,
    max_retries=3,
)
```

---

## 七、实际应用模式

### 7.1 数据提取 Pipeline

```python
class InvoiceInfo(BaseModel):
    """发票信息提取"""
    company: str = Field(description="公司名称")
    amount: float = Field(description="金额")
    date: str = Field(description="日期 YYYY-MM-DD")
    items: list[str] = Field(description="商品/服务项目")

prompt = ChatPromptTemplate.from_messages([
    ("system", "从用户提供的发票文本中提取结构化信息"),
    ("human", "{invoice_text}"),
])

extraction_chain = prompt | llm.with_structured_output(InvoiceInfo)

result = extraction_chain.invoke({
    "invoice_text": "腾讯科技有限公司，2025年3月15日，"
                    "云服务器 ¥5000，CDN加速 ¥2000，总计 ¥7000"
})
```

### 7.2 分类路由

```python
from typing import Literal

class RouterDecision(BaseModel):
    """路由决策"""
    department: Literal["sales", "support", "billing"] = Field(
        description="应该路由到哪个部门"
    )
    urgency: Literal["low", "medium", "high"] = Field(
        description="紧急程度"
    )
    reason: str = Field(description="路由理由")

router = llm.with_structured_output(RouterDecision)
decision = router.invoke("我的订单已经一周没发货了，很着急！")
# decision.department == "support"
# decision.urgency == "high"
```

---

## 八、练习任务

### 基础练习
- [ ] 用 `with_structured_output()` 实现电影信息提取
- [ ] 用 Enum 类型限定情感分类的输出选项
- [ ] 用 `include_raw=True` 调试一个解析失败的 case

### 进阶练习
- [ ] 实现嵌套结构的数据提取 (如提取简历中的教育经历+工作经历)
- [ ] 实现一个分类路由器 (根据用户输入决定走哪个处理流程)
- [ ] 对比 `with_structured_output()` 和 `JsonOutputParser` 的准确率

### 面试模拟
- [ ] 解释 `with_structured_output()` 的底层原理
- [ ] 比较 Function Calling 方式和 Prompt + Parser 方式的优劣
- [ ] 描述处理结构化输出失败的策略

---

> **本章掌握后，你应该能**：让 LLM 可靠地输出结构化数据，处理复杂嵌套结构，并知道生产环境的最佳实践。
