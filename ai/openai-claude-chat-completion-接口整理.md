# OpenAI / Claude 接口选型与迁移说明

更新时间：2026-04-17

这篇文档不替代官方 API reference，只做三件事：

- 告诉你新需求和老代码分别该选哪套接口
- 给出最小可运行示例
- 汇总官方入口，后续查具体参数直接跳过去

> 流式响应（`stream: true`）的底层协议是 SSE，报文格式和排障见 [`../network/sse.md`](../network/sse.md) 第 6 / 第 7 节。

## 1. 选型说明

### OpenAI 新需求：`responses`

默认用 `POST /v1/responses`。

适用场景：

- 新做聊天产品、Agent、工作流
- 要用内建 tools
- 要做状态延续
- 要做结构化输出
- 想跟 OpenAI 后续能力保持同一路线

团队约定：

- system prompt 优先放 `instructions`
- 多轮优先用 `previous_response_id`
- 结构化输出优先用 `text.format`
- 这是 OpenAI 新功能的默认落点

### OpenAI 老代码：`chat/completions`

已有链路继续维护 `POST /v1/chat/completions`。

适用场景：

- 已经围绕 `messages[]` 跑得稳定
- 主要是普通聊天或简单工具调用
- 很看重跨厂商兼容面

团队约定：

- 老链路不强制迁
- 新增复杂能力时，再单独开 `responses`
- 不要把新的主流程默认继续建在 `chat/completions` 上

### Claude 新需求：`messages`

默认用 `POST /v1/messages`。

适用场景：

- 新做 Claude 原生集成
- 需要 PDF、citations、extended thinking、prompt caching、原生 tools

团队约定：

- system prompt 放顶层 `system`
- 多轮历史自己显式传入
- 不要优先走 OpenAI compatibility layer

补充说明：

- Claude 的 OpenAI SDK compatibility 主要用于测试、迁移、对比
- 如果要拿完整能力，回到原生 `messages`

## 2. 最小示例

### OpenAI `responses`

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "instructions": "You are a helpful assistant.",
    "input": "Hello!"
  }'
```

### OpenAI `chat/completions`

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

#### OpenAI `chat/completions` Python 非流式（最小版）

非流式返回完整对象，直接读 `choices[0].message.content`。

```python
from openai import OpenAI

client = OpenAI()

completion = client.chat.completions.create(
    model="gpt-5.4",
    messages=[
        {"role": "developer", "content": "You are a helpful assistant."},
        {"role": "user", "content": "用一句话解释 SSE。"},
    ],
)

print(completion.choices[0].message.content)
```

#### OpenAI `chat/completions` Python 流式（最小版）

流式要加 `stream=True`。返回的是一串 chunk，增量内容在 `choices[0].delta.content`，不是 `message.content`。

```python
from openai import OpenAI

client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-5.4",
    messages=[
        {"role": "developer", "content": "You are a helpful assistant."},
        {"role": "user", "content": "分 3 句解释 SSE。"},
    ],
    stream=True,
)

full_text = ""

for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
    full_text += delta

print()
print(full_text)
```

#### OpenAI `chat/completions` Python 非流式（带异常处理）

下面这个版本更接近生产环境：补了客户端初始化、超时、限流、网络异常、HTTP 非 2xx、`request_id` 日志。

```python
import openai
from openai import OpenAI


def main() -> None:
    try:
        client = OpenAI(
            timeout=20.0,
            max_retries=2,
        )
    except openai.OpenAIError as exc:
        print(f"客户端初始化失败: {exc}")
        return

    try:
        completion = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "用一句话解释 SSE。"},
            ],
        )

        text = completion.choices[0].message.content or ""
        print(text)
        print(f"request_id={completion._request_id}")

    except openai.RateLimitError as exc:
        print(f"触发限流，稍后重试: {exc}")
    except openai.APITimeoutError as exc:
        print(f"请求超时: {exc}")
    except openai.APIConnectionError as exc:
        print(f"网络连接失败: {exc}")
        if exc.__cause__ is not None:
            print(f"底层异常: {exc.__cause__}")
    except openai.APIStatusError as exc:
        print(f"HTTP {exc.status_code}, request_id={exc.request_id}")
        print(exc.response)
    except openai.APIError as exc:
        print(f"OpenAI SDK 异常: {exc}")
    except Exception as exc:
        print(f"未预期异常: {exc}")


if __name__ == "__main__":
    main()
```

#### OpenAI `chat/completions` Python 流式（带异常处理）

流式场景更要保留 partial output，因为异常可能发生在输出一半时。

```python
import openai
from openai import OpenAI


def main() -> None:
    try:
        client = OpenAI(
            timeout=20.0,
            max_retries=2,
        )
    except openai.OpenAIError as exc:
        print(f"客户端初始化失败: {exc}")
        return

    full_text: list[str] = []
    stream = None

    try:
        stream = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "分 3 句解释 SSE。"},
            ],
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta.content or ""

            if delta:
                print(delta, end="", flush=True)
                full_text.append(delta)

        print()
        print("final_text:", "".join(full_text))

    except KeyboardInterrupt:
        print("\n用户中断，保留已收到的 partial output")
        print("partial_text:", "".join(full_text))
    except openai.RateLimitError as exc:
        print(f"\n触发限流，稍后重试: {exc}")
        print("partial_text:", "".join(full_text))
    except openai.APITimeoutError as exc:
        print(f"\n请求超时: {exc}")
        print("partial_text:", "".join(full_text))
    except openai.APIConnectionError as exc:
        print(f"\n网络连接失败: {exc}")
        if exc.__cause__ is not None:
            print(f"底层异常: {exc.__cause__}")
        print("partial_text:", "".join(full_text))
    except openai.APIStatusError as exc:
        print(f"\nHTTP {exc.status_code}, request_id={exc.request_id}")
        print(exc.response)
        print("partial_text:", "".join(full_text))
    except openai.APIError as exc:
        print(f"\nOpenAI SDK 异常: {exc}")
        print("partial_text:", "".join(full_text))
    except Exception as exc:
        print(f"\n未预期异常: {exc}")
        print("partial_text:", "".join(full_text))
    finally:
        if stream is not None:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
```

#### OpenAI `chat/completions` FastAPI 自定义 Chat SSE 接口（推荐）

如果你要在服务端封装一个“自己的 chat 流式接口”，更推荐把 OpenAI 上游 chunk 转成你自己的 SSE 事件协议，而不是把 `choices[0].delta` 原样暴露给前端。

下面这个示例统一返回 3 类事件：

- `delta`：增量文本
- `done`：正常结束，附带完整文本和 `finish_reason`
- `error`：异常结束，附带错误类型、错误消息、`partial_text`

这个接口虽然返回的是 `text/event-stream`，但因为 chat 请求通常是 `POST`，前端更常见的消费方式其实是 `fetch` 读取流，而不是直接用浏览器原生 `EventSource`。

```python
import asyncio
import json
from typing import Any

import openai
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

app = FastAPI()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "gpt-5.4"
    messages: list[ChatMessage]
    temperature: float | None = None
    reasoning_effort: str | None = None


def encode_sse(event: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@app.post("/api/chat/stream")
async def stream_chat(body: ChatRequest, request: Request) -> StreamingResponse:
    async def event_generator():
        full_text: list[str] = []
        finish_reason: str | None = None
        stream = None

        # 这里按请求初始化 client，是为了把初始化异常也统一成 SSE error 事件。
        # 如果你的服务启动时就能保证配置正确，也可以把 client 提升成全局单例。
        try:
            client = AsyncOpenAI(
                timeout=20.0,
                max_retries=2,
            )
        except openai.OpenAIError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "client_init_error",
                    "message": str(exc),
                    "partial_text": "",
                },
            )
            return

        try:
            create_kwargs = {
                "model": body.model,
                "messages": [msg.model_dump() for msg in body.messages],
                "stream": True,
            }

            if body.temperature is not None:
                create_kwargs["temperature"] = body.temperature
            if body.reasoning_effort is not None:
                create_kwargs["reasoning_effort"] = body.reasoning_effort

            stream = await client.chat.completions.create(**create_kwargs)

            async for chunk in stream:
                if await request.is_disconnected():
                    return

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                delta = choice.delta.content or ""
                if not delta:
                    continue

                full_text.append(delta)
                yield encode_sse("delta", {"delta": delta})

            if not await request.is_disconnected():
                yield encode_sse(
                    "done",
                    {
                        "finish_reason": finish_reason or "stop",
                        "text": "".join(full_text),
                    },
                )

        except asyncio.CancelledError:
            raise
        except openai.RateLimitError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "rate_limit",
                    "message": str(exc),
                    "partial_text": "".join(full_text),
                },
            )
        except openai.APITimeoutError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "timeout",
                    "message": str(exc),
                    "partial_text": "".join(full_text),
                },
            )
        except openai.APIConnectionError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "connection_error",
                    "message": str(exc),
                    "partial_text": "".join(full_text),
                },
            )
        except openai.APIStatusError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "api_status_error",
                    "message": f"HTTP {exc.status_code}",
                    "status_code": exc.status_code,
                    "request_id": exc.request_id,
                    "partial_text": "".join(full_text),
                },
            )
        except openai.APIError as exc:
            yield encode_sse(
                "error",
                {
                    "error": "openai_error",
                    "message": str(exc),
                    "partial_text": "".join(full_text),
                },
            )
        except Exception as exc:
            yield encode_sse(
                "error",
                {
                    "error": "internal_error",
                    "message": str(exc),
                    "partial_text": "".join(full_text),
                },
            )
        finally:
            if stream is not None:
                await stream.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

实务建议：

- 对外暴露你自己的 `delta / done / error` 事件，比原样暴露 OpenAI chunk 更稳，前端不会绑死在 `choices[0].delta`
- `partial_text` 要始终带上，流式失败时前端可以决定是否保留半段答案
- 如果前端必须使用浏览器原生 `EventSource`，接口通常要改成 `GET`
- 大多数 chat 场景实际更适合 `POST + fetch` 读取 `text/event-stream`

#### OpenAI `chat/completions` Python 异常处理要点

以当前 Python SDK 为例（本机版本：`openai==1.98.0`），可以这样理解：

- `OpenAIError`：SDK 基类。客户端初始化失败也可能先落到这里，比如没配 `OPENAI_API_KEY`
- `APIConnectionError`：网络、DNS、代理、TLS、连接中断
- `APITimeoutError`：请求超时；它本身也是连接类异常的一种
- `APIStatusError`：所有 HTTP 非 2xx 的统一基类，可拿 `status_code`、`request_id`、`response`
- `BadRequestError`：`400`
- `AuthenticationError`：`401`
- `PermissionDeniedError`：`403`
- `NotFoundError`：`404`
- `ConflictError`：`409`
- `UnprocessableEntityError`：`422`
- `RateLimitError`：`429`
- `InternalServerError`：`>=500`

默认行为：

- 默认超时：`10` 分钟
- 默认自动重试：`2` 次
- 默认会自动重试的情况：连接错误、`408`、`409`、`429`、`>=500`

实务建议：

- 成功请求：记录 `response._request_id`
- 失败请求：记录 `exc.request_id`
- 流式输出：永远缓存 `full_text`，因为异常可能发生在中途
- 限流不要死循环重放；如果 SDK 默认重试后仍失败，再做业务级退避
- `APIStatusError` 至少要把 `status_code` 和 `request_id` 打出来，不然排障成本会很高

补充说明：

- 非流式：读 `message`
- 流式：读 `delta`
- 流式首个 chunk 可能只有 `role`，最后一个 chunk 通常才带 `finish_reason`

### Claude `messages`

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "system": "You are a helpful assistant.",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

## 3. 官方链接索引

### OpenAI

- Responses 迁移说明: https://developers.openai.com/api/docs/guides/migrate-to-responses
- Responses API reference: https://developers.openai.com/api/docs/api-reference/responses
- Chat Completions API reference: https://developers.openai.com/api/docs/api-reference/chat
- Streaming responses guide: https://developers.openai.com/api/docs/guides/streaming-responses
- Rate limits guide: https://developers.openai.com/api/docs/guides/rate-limits
- Debugging requests / request IDs: https://platform.openai.com/docs/api-reference/debugging-requests
- Prompt engineering / Reusable prompts: https://developers.openai.com/api/docs/guides/prompt-engineering#reusable-prompts

### Claude / Anthropic

- Messages API reference: https://platform.claude.com/docs/en/api/messages
- Using the Messages API: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- OpenAI SDK compatibility: https://platform.claude.com/docs/en/api/openai-sdk

## 4. 一句话总结

- OpenAI 新需求：`responses`
- OpenAI 老代码：`chat/completions`
- Claude 新需求：`messages`
- 查具体参数和边界行为：直接看官方文档
