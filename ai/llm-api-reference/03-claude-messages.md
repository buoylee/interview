# Claude Messages API 入参/出参速查

> 定位:Anthropic Claude 的**唯一对话接口**,无状态。工具调用、结构化输出、思考都是这一个 endpoint 上的能力,不是单独 API。
> Endpoint:`POST https://api.anthropic.com/v1/messages`
> 鉴权(三个头):`x-api-key: $KEY`、`anthropic-version: 2023-06-01`、可选 `anthropic-beta: ...`
> 默认模型示例用 `claude-opus-4-8`。

```python
import anthropic
client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,                       # 必填!
    system="你是助手",                      # 顶层参数,不是 message
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.content[0].text)
```

---

## 1. 核心入参

| 参数 | 类型 | 高频 | 说明 / 注意 |
|---|---|---|---|
| `model` | str | ✅必填 | 模型 id |
| `max_tokens` | int | ✅**必填** | 输出上限。**Claude 这里是必填**(OpenAI 是可选) |
| `messages` | array | ✅必填 | 只含 `user`/`assistant` 两种 role,见下 |
| `system` | str/array | ✅ | 系统提示,**顶层参数**(不放进 messages) |
| `temperature` | float | | 0~1。Opus 4.7/4.8、Fable 5 上 `temperature/top_p/top_k` **已移除,传了 400** |
| `top_p`/`top_k` | | | 同上,新模型不可用 |
| `stream` | bool | ✅ | 流式 |
| `stop_sequences` | array | | 自定义停止串 |
| `tools` | array | ✅ | 工具定义,见工具章节 |
| `tool_choice` | obj | ✅ | `{"type":"auto|any|tool|none","name?":...,"disable_parallel_tool_use?":true}` |
| `thinking` | obj | ✅ | 扩展思考:`{"type":"adaptive","display":"summarized"}`(4.6+ 推荐;旧模型用 `enabled`+`budget_tokens`) |
| `output_config` | obj | ✅ | `{"effort":"low|medium|high|xhigh|max","format":{...}}`(effort 控制思考/花费;format 做结构化输出) |
| `metadata` | obj | | `{"user_id":"..."}` |
| `service_tier` | str | | 服务档位 |
| `cache_control` | obj | ✅ | 提示缓存(Claude 特色),前缀命中省钱 |

### messages 结构(只有 user / assistant)
```jsonc
[
  {"role": "user",      "content": "问题"},                 // 首条必须 user
  {"role": "assistant", "content": [{"type":"text","text":"回答"}]},
  {"role": "user",      "content": [{"type":"tool_result","tool_use_id":"toolu_x","content":"结果"}]}
]
```
- **没有 system role**;system 走顶层。
- **没有 tool role**;工具结果作为 **user 消息里的 `tool_result` 块**回填。
- content 可以是字符串或 **块数组**(text/image/document/tool_use/tool_result/thinking)。
- 必须 user 起头;相邻同 role 会被合并。

---

## 2. 多模态入参

content 块数组里:
```jsonc
{"type": "text", "text": "这张图是什么"}
{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "<b64>"}}
{"type": "image", "source": {"type": "url", "url": "https://..."}}
{"type": "image", "source": {"type": "file", "file_id": "file_xxx"}}          // 需 Files API beta
{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "<b64>"}}
```
- 图片是 `image` + **`source` 子对象**(base64 需带 `media_type`),不是 OpenAI 的 `image_url`。
- PDF 直接用 `document` 块。

---

## 3. 工具调用

### 定义(入参 `tools`)
```jsonc
"tools": [{
  "name": "get_weather",
  "description": "查询天气",
  "input_schema": {                         // ← 叫 input_schema(不是 parameters / function)
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"]
  }
}]
```

### 回环
模型返回 `stop_reason:"tool_use"`,content 里出现 `tool_use` 块:
```jsonc
{"type": "tool_use", "id": "toolu_abc", "name": "get_weather", "input": {"city": "北京"}}
```
- **`input` 是已解析好的对象**(不像 OpenAI 是 JSON 字符串)。
→ 把整条 assistant `content` 追加,再加一条 user 消息带 `tool_result`:
```jsonc
{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_abc","content":"晴 25°C","is_error":false}]}
```

---

## 4. 非流式出参

```jsonc
{
  "id": "msg_xxx",
  "type": "message",
  "role": "assistant",
  "model": "claude-opus-4-8",
  "content": [                              // ← 块数组(对比 OpenAI 的字符串/单 message)
    {"type": "thinking", "thinking": "...", "signature": "..."},   // 开思考时在最前
    {"type": "text", "text": "回答"},
    {"type": "tool_use", "id": "toolu_x", "name": "...", "input": {...}}
  ],
  "stop_reason": "end_turn",                // 见下表
  "stop_sequence": null,
  "usage": {
    "input_tokens": 20,
    "output_tokens": 8,
    "cache_creation_input_tokens": 0,       // 写缓存(~1.25x 价)
    "cache_read_input_tokens": 0            // 读缓存命中(~0.1x 价)
  }
}
```
取文本:遍历 `content` 取 `type=="text"` 的块(别直接 `content[0].text`,开思考时第一块是 thinking)。

---

## 5. 流式出参(语义事件)

SSE,事件类型化,顺序固定:

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_x","role":"assistant","usage":{"input_tokens":20,"output_tokens":1}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"回"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"答"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":8}}

event: message_stop
data: {"type":"message_stop"}
```

**与非流式的差异要点:**
- 结构是 **message_start → (content_block_start → 多个 content_block_delta → content_block_stop)×N → message_delta → message_stop**。
- delta 的子类型按块而定:正文 `text_delta`、工具参数 `input_json_delta`(`partial_json` 逐片拼)、思考 `thinking_delta` / `signature_delta`。
- **usage 分两处**:输入 token 在 `message_start`;**输出 token 累计在 `message_delta`**(最终值)。
- `stop_reason` 在 `message_delta`。
- 期间会穿插 `ping` 事件(忽略即可)。
- 多个内容块用 `index` 区分。

```python
with client.messages.stream(model="claude-opus-4-8", max_tokens=1024,
        messages=[{"role":"user","content":"写首诗"}]) as stream:
    for text in stream.text_stream:        # 便捷:只要正文增量
        print(text, end="")
    final = stream.get_final_message()     # 完整对象 + usage
```

---

## 6. stop_reason 取值

| 值 | 含义 |
|---|---|
| `end_turn` | 正常结束 |
| `max_tokens` | 撞 `max_tokens`,被截断 |
| `stop_sequence` | 命中自定义停止串 |
| `tool_use` | 要调工具,执行后回填 |
| `pause_turn` | 服务端工具循环暂停,原样回传可继续(agentic) |
| `refusal` | 安全拒绝;**读 content 前先判 stop_reason**,`stop_details` 给类别 |

---

## 7. 易错点

- **`max_tokens` 必填**;忘了直接报错(和 OpenAI 习惯不同)。
- **system 是顶层参数**,不要塞进 messages;messages 只有 user/assistant。
- 工具结果回填走 **user 消息的 `tool_result` 块**(没有 tool role)。
- 工具定义字段叫 **`input_schema`**;模型回的 **`input` 是对象**(不用再 json.loads)。
- 新模型(Opus 4.7/4.8、Fable 5)**不支持 `temperature/top_p/top_k`**,`budget_tokens` 也移除 → 用 `thinking:{type:"adaptive"}` + `output_config.effort`。
- 取正文别假设 `content[0]` 是文本,开思考时它是 thinking 块。
- 流式输出 token 数要从 `message_delta` 取,不在 `message_start`。
- 鉴权是 `x-api-key` + `anthropic-version` 头(不是 Bearer)。

→ 三者横向对照见 [README.md](./README.md)
