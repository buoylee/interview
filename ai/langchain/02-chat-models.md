# 第1章：Chat Models — LLM 统一调用接口

> LangChain 的核心价值之一：用统一接口调用任何 LLM，切换模型只需改一行代码。

---

## 一、Chat Model 是什么

### 1.1 定位

Chat Model 是 LangChain 中**最基础的组件**，它将各种 LLM（OpenAI、Anthropic、Google、本地模型等）封装为统一接口。

```
你的代码 ──→ LangChain Chat Model (统一接口) ──→ OpenAI / Anthropic / Ollama / ...
                                                  ↑
                                            只需切换这里
```

### 1.2 为什么需要统一接口？

| 没有 LangChain | 有 LangChain |
|----------------|--------------|
| `openai.ChatCompletion.create(...)` | `ChatOpenAI().invoke(...)` |
| `anthropic.messages.create(...)` | `ChatAnthropic().invoke(...)` |
| 每家 API 格式不同 | 统一的 `.invoke()/.stream()/.batch()` |
| 切换模型要改大量代码 | 改一行初始化代码即可 |
| 自己处理重试、缓存 | 框架内置支持 |

### 1.3 面试高频问题

> **Q: LangChain 的 Chat Model 和直接用 OpenAI SDK 有什么区别？**
>
> A: Chat Model 是 LLM 的统一抽象层。核心优势：(1) 统一接口，切换模型无需改业务代码；(2) 内置 Runnable 接口 (invoke/stream/batch)；(3) 与 LCEL、Tools、Agent 等 LangChain 组件无缝集成；(4) 内置 callbacks、tracing、caching 等生产特性。代价是多一层抽象，简单场景可能 overkill。

---

## 二、核心 Message 类型

LangChain 使用 **Message 对象** 表示对话中的每条消息，这与 OpenAI 的 `messages` 数组概念一致。

### 2.1 四种核心 Message

```python
from langchain.messages import (
    SystemMessage,    # 系统指令 — 定义 AI 的角色和行为规则
    HumanMessage,     # 用户消息 — 用户说的话
    AIMessage,        # AI 回复 — 模型生成的回答
    ToolMessage,      # 工具结果 — 工具执行后的返回值
)
```

| Message 类型 | 对应 OpenAI role | 用途 | 示例 |
|-------------|-----------------|------|------|
| `SystemMessage` | `system` | 设定 AI 角色、行为约束 | "你是一个翻译助手，只输出翻译结果" |
| `HumanMessage` | `user` | 用户的输入 | "把这句话翻译成英文" |
| `AIMessage` | `assistant` | AI 的回复 | "Here is the translation..." |
| `ToolMessage` | `tool` | 工具调用的返回结果 | `{"temperature": 25, "city": "Beijing"}` |

### 2.2 构造消息的两种方式

```python
# 方式1: Message 对象 (推荐，类型安全)
from langchain.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage(content="你是一个翻译专家"),
    HumanMessage(content="翻译：我爱编程"),
]

# 方式2: 元组简写 (快速开发)
messages = [
    ("system", "你是一个翻译专家"),
    ("human", "翻译：我爱编程"),
]
```

### 2.3 AIMessage 的重要属性

```python
response = llm.invoke(messages)

# response 是一个 AIMessage 对象
print(response.content)          # 文本回复内容
print(response.tool_calls)       # 工具调用列表 (如果有)
print(response.usage_metadata)   # Token 使用信息
print(response.response_metadata) # 模型返回的元数据
print(response.id)               # 消息 ID
```

**`usage_metadata` 结构**（面试常问）:
```python
{
    "input_tokens": 28,        # 输入 token 数
    "output_tokens": 15,       # 输出 token 数
    "total_tokens": 43,        # 总 token 数
    "input_token_details": {
        "cache_read": 0        # 缓存命中的 token
    },
    "output_token_details": {
        "reasoning": 0         # 推理 token (o1/o3 模型)
    }
}
```

### 2.4 面试深度问题

> **Q: ToolMessage 和 AIMessage 中的 tool_calls 有什么关系？**
>
> A: 这是一个**请求-响应对**。当 LLM 决定调用工具时，`AIMessage.tool_calls` 描述要调用什么工具、传什么参数；你执行完工具后，用 `ToolMessage` 把结果返回给 LLM。`ToolMessage` 必须包含 `tool_call_id` 与对应的 `tool_calls` 条目匹配。

```python
# AIMessage 中的 tool_calls (LLM 的请求)
ai_msg = llm_with_tools.invoke("北京天气怎么样？")
# ai_msg.tool_calls = [
#     {"id": "call_abc123", "name": "get_weather", "args": {"city": "北京"}}
# ]

# ToolMessage (你的响应)
from langchain.messages import ToolMessage
tool_msg = ToolMessage(
    content="北京: 晴天, 25°C",
    tool_call_id="call_abc123"  # 必须匹配!
)
```

---

## 三、Chat Model 初始化与配置

### 3.1 主流模型接入

```python
# OpenAI
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4096,
    api_key="sk-...",          # 或设置环境变量 OPENAI_API_KEY
    base_url="https://...",    # 自定义 API 地址 (用于代理)
)

# Anthropic
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    temperature=0.7,
    max_tokens=4096,
)

# Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.7,
)

# 本地模型 (Ollama)
from langchain_ollama import ChatOllama
llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0.7,
    base_url="http://localhost:11434",
)

# 通用初始化 (自动检测模型提供商)
from langchain.chat_models import init_chat_model
llm = init_chat_model("gpt-4o", model_provider="openai", temperature=0.7)
```

### 3.2 关键参数详解

| 参数            | 类型          | 说明                    | 面试要点                         |
| ------------- | ----------- | --------------------- | ---------------------------- |
| `model`       | str         | 模型名称                  | 不同模型能力差异大                    |
| `temperature` | float (0-2) | 随机性。0=确定性，1=平衡，>1=创意  | **0 用于代码/事实类任务, 0.7 用于创意任务** |
| `max_tokens`  | int         | 最大输出 token 数          | 不是越大越好，影响成本和延迟               |
| `top_p`       | float (0-1) | 核采样。与 temperature 二选一 | 一般不同时调两个                     |
| `stop`        | list[str]   | 遇到这些字符串时停止生成          | Agent 中常用于控制输出格式             |
| `timeout`     | float       | 超时时间 (秒)              | 生产环境必设                       |
| `max_retries` | int         | 失败重试次数                | 默认 2，生产建议 3                  |
| `api_key`     | str         | API 密钥                | 推荐用环境变量而非硬编码                 |
| `base_url`    | str         | 自定义 API 地址            | 用于代理、本地部署模型                  |

### 3.3 面试深度问题

> **Q: temperature 和 top_p 的区别是什么？应该怎么设？**
>
> A: 两者都控制生成的随机性，但机制不同：
> - **temperature**: 调整概率分布的 "锐度"。低 temperature 让高概率 token 更突出 (更确定)，高 temperature 让分布更平坦 (更随机)。
> - **top_p (nucleus sampling)**: 只从累积概率前 p% 的 token 中采样。top_p=0.1 意味着只考虑占前 10% 概率的 token。
> - **最佳实践**: 只调一个，不要同时调两个 (OpenAI 官方建议)。代码/结构化输出用 temperature=0，对话用 0.7，创意写作用 0.9-1.0。

---

## 四、三种调用方式

LangChain 的所有组件都实现了 `Runnable` 接口，提供三种核心调用方式。

### 4.1 `invoke()` — 同步单次调用

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")

# 最简调用
response = llm.invoke("什么是 LangChain?")
print(response.content)

# 传入消息列表
from langchain.messages import SystemMessage, HumanMessage
messages = [
    SystemMessage(content="你是一个 Python 专家，用中文回答"),
    HumanMessage(content="解释 decorator 的原理"),
]
response = llm.invoke(messages)
print(response.content)
print(response.usage_metadata)  # 查看 token 用量
```

### 4.2 `stream()` — 流式输出

```python
# 流式输出 — 逐 token 返回，用户体验更好
for chunk in llm.stream("用 Python 写一个快排"):
    print(chunk.content, end="", flush=True)
```

**chunk 的结构**:
```python
for chunk in llm.stream("hello"):
    # chunk 是 AIMessageChunk 对象
    print(chunk.content)           # 本次 chunk 的文本片段
    print(chunk.usage_metadata)    # 最后一个 chunk 才有 (需开启 stream_usage)
```

**开启流式 token 统计** (面试加分):
```python
llm = ChatOpenAI(model="gpt-4o", stream_usage=True)

for chunk in llm.stream("hello"):
    if chunk.usage_metadata:
        print(f"Tokens: {chunk.usage_metadata}")
```

### 4.3 `batch()` — 批量调用

```python
# 批量调用 — 并行处理多个请求
questions = [
    "什么是 LangChain?",
    "什么是 LangGraph?",
    "什么是 LCEL?",
]
responses = llm.batch(questions)

for q, r in zip(questions, responses):
    print(f"Q: {q}\nA: {r.content}\n")
```

**控制并发数**:
```python
# max_concurrency 控制并行度，避免触发 rate limit
responses = llm.batch(
    questions,
    config={"max_concurrency": 3}
)
```

### 4.4 异步版本

```python
import asyncio

async def main():
    # ainvoke
    response = await llm.ainvoke("hello")

    # astream
    async for chunk in llm.astream("hello"):
        print(chunk.content, end="")

    # abatch
    responses = await llm.abatch(["q1", "q2", "q3"])

asyncio.run(main())
```

### 4.5 面试对比总结

| 方法 | 用途 | 返回类型 | 适用场景 |
|------|------|----------|----------|
| `invoke()` | 单次同步调用 | `AIMessage` | 后端处理、简单查询 |
| `stream()` | 流式输出 | `Iterator[AIMessageChunk]` | 聊天 UI、实时显示 |
| `batch()` | 批量并行 | `list[AIMessage]` | 批处理、评估、数据处理 |
| `ainvoke()` | 单次异步 | `AIMessage` | Web 服务器 (FastAPI) |
| `astream()` | 异步流式 | `AsyncIterator[AIMessageChunk]` | 异步 Web 流式 |
| `abatch()` | 异步批量 | `list[AIMessage]` | 异步批处理 |

---

## 五、多模态支持

### 5.1 发送图片

```python
from langchain.messages import HumanMessage

# 方式1: URL
message = HumanMessage(
    content=[
        {"type": "text", "text": "描述这张图片"},
        {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
    ]
)

# 方式2: Base64
import base64
with open("photo.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

message = HumanMessage(
    content=[
        {"type": "text", "text": "这是什么?"},
        {"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{image_data}"
        }},
    ]
)

response = llm.invoke([message])
```

### 5.2 面试加分点

> **Q: 多模态消息与纯文本消息的 content 有什么区别？**
>
> A: 纯文本时 `content` 是 `str`；多模态时 `content` 是 `list[dict]`，每个 dict 有 `type` 字段区分文本和图片。这是 OpenAI 的 Vision API 格式，LangChain 直接透传。

---

## 六、高级特性

### 6.1 Caching — 缓存

重复相同输入时，避免重复调用 LLM，节省成本。

```python
from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache, SQLiteCache

# 内存缓存 (开发用)
set_llm_cache(InMemoryCache())

# SQLite 缓存 (持久化)
set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# 第一次调用 — 正常请求 LLM
response = llm.invoke("什么是 LangChain?")  # 耗时 ~2s

# 第二次调用 — 命中缓存
response = llm.invoke("什么是 LangChain?")  # 耗时 ~0s
```

### 6.2 Callbacks — 回调系统

用于追踪、日志、监控。

```python
from langchain.callbacks import StdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler

# 内置: 打印到控制台
response = llm.invoke("hello", config={"callbacks": [StdOutCallbackHandler()]})

# 自定义回调
class MyCallback(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print(f"🚀 LLM 开始调用, 输入: {prompts}")

    def on_llm_end(self, response, **kwargs):
        print(f"✅ LLM 调用完成")
        # 可以在这里记录 token 用量、延迟等

    def on_llm_error(self, error, **kwargs):
        print(f"❌ LLM 调用失败: {error}")

response = llm.invoke("hello", config={"callbacks": [MyCallback()]})
```

### 6.3 Fallback — 降级策略

```python
# 主模型失败时自动切换备用模型
primary = ChatOpenAI(model="gpt-4o")
fallback = ChatAnthropic(model="claude-sonnet-4-20250514")

llm_with_fallback = primary.with_fallbacks([fallback])

# gpt-4o 失败时自动切换到 Claude
response = llm_with_fallback.invoke("hello")
```

### 6.4 Rate Limiting — 速率限制

```python
from langchain_core.rate_limiters import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(
    requests_per_second=1,     # 每秒最多 1 次
    check_every_n_seconds=0.1, # 检查间隔
    max_bucket_size=10,        # 令牌桶大小
)

llm = ChatOpenAI(model="gpt-4o", rate_limiter=rate_limiter)
```

---

## 七、`init_chat_model()` — 通用初始化

**面试重点**: 这是 LangChain 推荐的「模型无关」初始化方式，适合需要动态切换模型的场景。

```python
from langchain.chat_models import init_chat_model

# 自动根据 model 名称推断 provider
llm = init_chat_model("gpt-4o")           # → ChatOpenAI
llm = init_chat_model("claude-sonnet-4-20250514")    # → ChatAnthropic
llm = init_chat_model("gemini-2.0-flash") # → ChatGoogleGenerativeAI

# 显式指定 provider
llm = init_chat_model("my-custom-model", model_provider="openai", base_url="...")

# 可配置化 — 从配置文件/环境变量中读取模型名称
import os
llm = init_chat_model(
    os.getenv("LLM_MODEL", "gpt-4o"),
    temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
)
```

**适用场景**：
- 多租户系统 (不同客户用不同模型)
- A/B 测试 (对比不同模型效果)
- 配置驱动的模型选择

---

## 八、生产环境最佳实践

### 8.1 环境变量管理

```bash
# .env 文件
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=4096
```

```python
from dotenv import load_dotenv
load_dotenv()

# LangChain 自动从环境变量读取 API key
llm = ChatOpenAI(model="gpt-4o")  # 不需要显式传 api_key
```

### 8.2 错误处理

```python
from langchain_core.exceptions import OutputParserException
from openai import RateLimitError, APIError

try:
    response = llm.invoke(messages)
except RateLimitError:
    # 触发速率限制 — 等待后重试或切换模型
    response = fallback_llm.invoke(messages)
except APIError as e:
    # API 错误 — 记录日志
    logger.error(f"LLM API error: {e}")
    raise
```

### 8.3 Token 管理

```python
# 获取 token 数 (调用前估算)
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
num_tokens = llm.get_num_tokens("这句话有多少 token?")
print(f"Token count: {num_tokens}")

# 调用后获取实际用量
response = llm.invoke("hello")
print(response.usage_metadata)
# {'input_tokens': 8, 'output_tokens': 12, 'total_tokens': 20}
```

### 8.4 超时与重试配置

```python
llm = ChatOpenAI(
    model="gpt-4o",
    timeout=30,         # 30 秒超时
    max_retries=3,      # 最多重试 3 次
    request_timeout=60, # 请求级超时
)
```

---

## 九、不同场景的模型选择建议

| 场景 | 推荐模型 | temperature | 理由 |
|------|----------|-------------|------|
| 代码生成 | GPT-4o, Claude Sonnet | 0 | 需要确定性输出 |
| 对话聊天 | GPT-4o-mini, Claude Haiku | 0.7 | 平衡质量和成本 |
| 创意写作 | Claude Sonnet, GPT-4o | 0.9-1.0 | 需要多样性 |
| 数据提取 | GPT-4o-mini | 0 | 结构化输出，低成本 |
| Agent/工具调用 | GPT-4o, Claude Sonnet | 0 | 需要精确遵循指令 |

---

## 十、练习任务

### 基础练习
- [ ] 用 `ChatOpenAI` 创建一个翻译助手，系统消息要求只输出翻译结果
- [ ] 用 `.stream()` 实现流式输出到控制台
- [ ] 用 `.batch()` 批量翻译 5 个句子
- [ ] 用 `usage_metadata` 统计一次对话的总 token 消耗

### 进阶练习
- [ ] 实现模型降级：GPT-4o → Claude Sonnet → GPT-4o-mini
- [ ] 实现一个多轮对话 (手动管理消息历史)
- [ ] 用 `init_chat_model()` 实现可配置的模型选择
- [ ] 发送一张图片让模型描述 (多模态)

### 面试模拟
- [ ] 解释 LangChain Chat Model 的 Runnable 接口
- [ ] 比较 invoke/stream/batch 的使用场景
- [ ] 说明 temperature 和 top_p 的区别和最佳实践
- [ ] 描述生产环境中 Chat Model 的最佳配置

---

> **本章掌握后，你应该能**：用 LangChain 调用任意 LLM，管理消息历史，处理流式输出，并知道生产环境的最佳实践。
