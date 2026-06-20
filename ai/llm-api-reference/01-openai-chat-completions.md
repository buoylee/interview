# OpenAI Chat Completions API 入参/出参速查

> 定位:OpenAI 的**经典、无状态**对话接口,生态最广(几乎所有第三方/兼容层都按它来)。
> 新项目 OpenAI 官方推荐用 [Responses API](./02-openai-responses.md);老代码、要跨厂商兼容仍用它。
> Endpoint:`POST https://api.openai.com/v1/chat/completions`
> 鉴权:`Authorization: Bearer $OPENAI_API_KEY`

```python
from openai import OpenAI
client = OpenAI()
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
```

---

## 1. 核心入参

| 参数 | 类型 | 高频 | 说明 / 注意 |
|---|---|---|---|
| `model` | str | ✅必填 | 模型 id |
| `messages` | array | ✅必填 | 对话历史,见下表。**无状态:每次要带全量历史** |
| `max_completion_tokens` | int | ✅ | 输出上限。**新名**;`max_tokens` 已 deprecated(o 系列推理模型只认 `max_completion_tokens`) |
| `temperature` | float | ✅ | 0~2,默认 1。推理模型(o 系列)不支持,传了报错 |
| `top_p` | float | | 与 temperature 二选一调 |
| `stream` | bool | ✅ | 是否流式 |
| `stream_options` | obj | ✅ | `{"include_usage": true}` 才会在流式最后吐 usage(否则流式拿不到 token 数) |
| `tools` | array | ✅ | 函数/工具定义,见工具章节 |
| `tool_choice` | str/obj | ✅ | `auto`/`none`/`required`/`{"type":"function","function":{"name":"x"}}` |
| `parallel_tool_calls` | bool | | 默认 true,一次可并行多个 tool call |
| `response_format` | obj | ✅ | 结构化输出:`{"type":"json_object"}` 或 `{"type":"json_schema","json_schema":{...}}` |
| `reasoning_effort` | str | | 推理模型专用:`low`/`medium`/`high` |
| `stop` | str/array | | 自定义停止串(最多 4 个) |
| `n` | int | | 返回几个候选(Claude/Responses 都没有这个) |
| `seed` | int | | 尽量复现(非保证) |
| `frequency_penalty`/`presence_penalty` | float | | -2~2,降重复 |
| `logprobs`/`top_logprobs` | bool/int | | 返回 token 概率 |
| `user` | str | | 终端用户标识(滥用监控) |

### messages 结构
```jsonc
[
  {"role": "system",    "content": "你是助手"},   // 或 "developer"(新)
  {"role": "user",      "content": "问题"},
  {"role": "assistant", "content": "回答", "tool_calls": [...]},
  {"role": "tool",      "tool_call_id": "call_x", "content": "工具结果"}
]
```
- 角色:`system`/`developer`(系统指令)、`user`、`assistant`、`tool`。
- `system` 是 **messages 里的一条**(对比 Claude 的顶层 `system`)。
- 工具结果用 **`role:"tool"` 单独一条**,靠 `tool_call_id` 回填。

---

## 2. 多模态入参

`content` 从字符串改成 **parts 数组**:
```jsonc
"content": [
  {"type": "text", "text": "这张图是什么?"},
  {"type": "image_url",
   "image_url": {"url": "https://...", "detail": "auto"}},        // 或 data:image/png;base64,xxx
  {"type": "input_audio", "input_audio": {"data": "<b64>", "format": "wav"}}
]
```
- 图片:`image_url`(URL 或 base64 dataURI),`detail`=`low`/`high`/`auto`。
- `detail:"high"` 会切片成多 tile,token 涨很多。

---

## 3. 工具调用(function calling)

### 定义(入参 `tools`)
```jsonc
"tools": [{
  "type": "function",
  "function": {                              // ← 嵌套在 function 下(Responses 是扁平的)
    "name": "get_weather",
    "description": "查询天气",
    "parameters": {                          // 标准 JSON Schema
      "type": "object",
      "properties": {"city": {"type": "string"}},
      "required": ["city"]
    },
    "strict": true                           // 严格遵守 schema
  }
}]
```

### 回环(出参 → 回填)
模型返回 `finish_reason:"tool_calls"`,`message.tool_calls[]`:
```jsonc
"tool_calls": [{
  "id": "call_abc",
  "type": "function",
  "function": {"name": "get_weather", "arguments": "{\"city\":\"北京\"}"}  // arguments 是 JSON 字符串!
}]
```
→ 你执行后,把 assistant 那条(含 tool_calls)+ 一条 `role:"tool"` 结果都追加进 messages,再请求一次。
- **`arguments` 是字符串**,要 `json.loads` 再用。

---

## 4. 非流式出参

```jsonc
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gpt-4o-2024-xx-xx",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "回答文本",       // 纯文本字符串(对比 Claude 的 content 数组)
      "tool_calls": null,           // 或上面的数组
      "refusal": null               // 安全拒绝时这里有内容,content 为 null
    },
    "finish_reason": "stop",
    "logprobs": null
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 8,
    "total_tokens": 28,
    "prompt_tokens_details":     {"cached_tokens": 0},      // 提示缓存命中数
    "completion_tokens_details": {"reasoning_tokens": 0}    // 推理模型思考 token
  }
}
```
取文本:`resp.choices[0].message.content`。

---

## 5. 流式出参(SSE)

`object` 变为 `chat.completion.chunk`,每个 chunk 在 `choices[].delta` 给**增量**:

```
data: {"choices":[{"delta":{"role":"assistant"},"index":0,"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"回"},"index":0,"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"答"},"index":0,"finish_reason":null}]}

data: {"choices":[{"delta":{},"index":0,"finish_reason":"stop"}]}

data: {"choices":[],"usage":{"prompt_tokens":20,"completion_tokens":8,"total_tokens":28}}

data: [DONE]
```

**与非流式的差异要点:**
- `message` → `delta`,内容是**逐 token 拼接**(自己累加 `delta.content`)。
- `finish_reason` 在最后一个有内容的 chunk 上。
- **usage 默认没有**;要 `stream_options={"include_usage":true}`,会在 `[DONE]` 前来一个 `choices:[]` 只带 usage 的 chunk。
- 工具调用流式:`delta.tool_calls[].function.arguments` 也是**逐片拼**,要按 `index` 累加成完整 JSON 串。
- 结束标记是字面量 `data: [DONE]`(不是 JSON)。

```python
stream = client.chat.completions.create(model="gpt-4o", messages=msgs,
    stream=True, stream_options={"include_usage": True})
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

---

## 6. finish_reason 取值

| 值 | 含义 |
|---|---|
| `stop` | 正常结束(或命中 stop 串) |
| `length` | 撞 `max_completion_tokens`,被截断 |
| `tool_calls` | 模型要调工具,去执行后回填 |
| `content_filter` | 内容被安全过滤 |
| `function_call` | 旧版 `functions` 字段的产物(已弃用) |

---

## 7. 易错点

- **无状态**:不存历史,每轮都要把全部 messages 重发(token 随对话线性增长)。
- `max_tokens` 对推理模型无效 → 统一用 `max_completion_tokens`。
- `temperature`/`top_p` 等采样参数在 o 系列推理模型上**传了会报错**。
- 流式不开 `include_usage` 就**拿不到 token 用量**。
- `tool_calls[].function.arguments` 和流式增量都是**字符串**,需要拼接 + `json.loads`。
- system 指令是 messages 里的一条,不是顶层参数(和 Claude 不同)。

---

## 8. 返回内容类型 & 处理

输出是**单个 `message`**(不是数组),可能带这些字段:

| 字段 | 何时出现 | 怎么处理 |
|---|---|---|
| `content`(str) | 普通回答 | **纯工具调用 / refusal 时为 `null`**,取值前判空 |
| `tool_calls` | `finish_reason:"tool_calls"` | 见 [04](./04-streaming-tool-calls.md);`arguments` 是字符串要 `json.loads` |
| `refusal`(str) | 安全拒绝 | 有值时 `content` 为 null;另见 `finish_reason:"content_filter"` |
| `audio` | 开了音频输出 | `{id,data(b64),transcript,expires_at}`,见下 |
| `annotations` | 搜索类模型(`*-search-*`) | URL 引用来源 |

- **思考/推理不返回**:o 系列 / gpt-5 的推理过程隐藏,只在 `usage.completion_tokens_details.reasoning_tokens` 给计数;`reasoning_effort` 控深度。无状态,**无需回传推理**。
- **音频输出**:`modalities=["text","audio"]` + `audio={"voice","format"}` → `message.audio.{data,transcript,id}`;解 b64 落盘,多轮续接用 `{"role":"assistant","audio":{"id":...}}` 引用。
- **音频 / PDF 输入**:音频 `{"type":"input_audio","input_audio":{data,format}}`(需 `gpt-4o-audio`);PDF `{"type":"file","file":{file_id|file_data|filename}}`。**视频不支持**(抽帧成图)。
- **结构化输出**:`response_format={"type":"json_schema",...}` → `content` 是 JSON 串;SDK `client.chat.completions.parse(...)` → `message.parsed`。
- **多轮回传**:把 assistant 那条(含 `tool_calls` / `audio.id`)整条追加回 `messages`。

→ 内容类型跨三者对照见 [05](./05-content-types-and-handling.md);三者横向对照见 [README.md](./README.md)
