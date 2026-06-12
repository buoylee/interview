# OpenAI Responses API 入参/出参速查

> 定位:OpenAI 的**新一代、有状态**接口,官方对新项目的首选。
> 把"对话 + 工具 + 推理 + 内置工具(web/file/code)"统一成一个 endpoint,服务端可存会话状态。
> Endpoint:`POST https://api.openai.com/v1/responses`
> 鉴权:`Authorization: Bearer $OPENAI_API_KEY`

```python
from openai import OpenAI
client = OpenAI()
resp = client.responses.create(
    model="gpt-4o",
    instructions="你是助手",      # 系统指令(顶层)
    input="你好",                 # 可以是字符串,也可以是 items 数组
)
print(resp.output_text)           # SDK 聚合好的纯文本
```

---

## 1. 核心入参

| 参数 | 类型 | 高频 | 说明 / 注意 |
|---|---|---|---|
| `model` | str | ✅必填 | 模型 id |
| `input` | str/array | ✅必填 | 输入:简单场景给字符串;复杂给 items 数组(见下) |
| `instructions` | str | ✅ | 系统级指令(**顶层参数**,等价于 system) |
| `max_output_tokens` | int | ✅ | 输出上限(注意名字:不是 max_tokens) |
| `temperature` / `top_p` | float | | 采样;推理模型不支持 temperature |
| `stream` | bool | ✅ | 流式,事件语义化(见流式章节) |
| `store` | bool | ✅ | 默认 **true**,服务端保存本次 response(供下次 chain) |
| `previous_response_id` | str | ✅ | 接上一轮 `resp.id`,**服务端续接历史 → 本次只发新输入** |
| `tools` | array | ✅ | 函数工具 + 内置工具,见工具章节 |
| `tool_choice` | str/obj | ✅ | `auto`/`none`/`required`/`{"type":"function","name":"x"}` |
| `parallel_tool_calls` | bool | | 默认 true |
| `reasoning` | obj | ✅ | 推理模型:`{"effort":"low|medium|high","summary":"auto|concise|detailed"}` |
| `text` | obj | ✅ | 输出格式:`{"format":{"type":"text|json_schema|json_object", ...}}` |
| `include` | array | | 额外返回字段(如 `reasoning.encrypted_content`、日志概率) |
| `background` | bool | | 异步后台跑长任务,先返回 `in_progress`,之后轮询/流式 |
| `max_tool_calls` | int | | 工具调用次数上限 |
| `metadata` | obj | | 自定义键值 |

### input 的 items 形态
```jsonc
"input": [
  {"role": "user", "content": [
    {"type": "input_text",  "text": "这张图是什么"},
    {"type": "input_image", "image_url": "https://..."}        // 或 {"file_id": "..."}
  ]},
  {"type": "function_call_output", "call_id": "fc_x", "output": "工具结果"}  // 工具回填(扁平 item,不是 role)
]
```
- 输入文本类型是 `input_text` / `input_image` / `input_file`(输出侧是 `output_text`)。
- 工具结果是一个 `function_call_output` **item**,不是某个 role 的消息。

---

## 2. 多模态入参

在 `input` 的 content parts 里:
```jsonc
{"type": "input_text",  "text": "..."}
{"type": "input_image", "image_url": "https://... 或 data:image/png;base64,xxx", "detail": "auto"}
{"type": "input_file",  "file_id": "file_xxx"}        // 也可 filename + file_data(b64)
```

---

## 3. 工具调用

### 函数工具定义(注意:扁平!)
```jsonc
"tools": [{
  "type": "function",
  "name": "get_weather",          // ← 直接在顶层,不再嵌套 function:{}(对比 Chat Completions)
  "description": "查询天气",
  "parameters": {"type":"object","properties":{"city":{"type":"string"}},"required":["city"]},
  "strict": true
}]
```

### 内置工具(服务端托管,Chat Completions 没有)
```jsonc
{"type": "web_search_preview"}      // 联网搜索
{"type": "file_search", "vector_store_ids": ["vs_x"]}
{"type": "code_interpreter", "container": {"type":"auto"}}
{"type": "computer_use_preview", ...}
{"type": "mcp", "server_label": "x", "server_url": "https://..."}
```

### 回环
输出 `output[]` 里出现 `type:"function_call"` item(含 `call_id`、`name`、`arguments` 字符串)→ 你执行 → 把结果作为 `function_call_output` item 追加到 `input`(或配合 `previous_response_id`)再请求。

---

## 4. 非流式出参

```jsonc
{
  "id": "resp_xxx",
  "object": "response",
  "created_at": 1700000000,
  "status": "completed",          // in_progress | completed | failed | incomplete
  "model": "gpt-4o-...",
  "output": [                     // ← 有序的 typed item 数组
    {"type": "reasoning", "id": "rs_x", "summary": [...]},            // 推理模型才有
    {"type": "message", "id": "msg_x", "role": "assistant",
     "content": [{"type": "output_text", "text": "回答", "annotations": []}]},
    {"type": "function_call", "id":"fc_x","call_id":"call_x","name":"get_weather","arguments":"{...}"}
  ],
  "output_text": "回答",          // SDK 把所有 output_text 拼好的便捷字段
  "usage": {
    "input_tokens": 20,
    "input_tokens_details":  {"cached_tokens": 0},
    "output_tokens": 8,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 28
  },
  "incomplete_details": null,     // status=incomplete 时说明原因(如 max_output_tokens)
  "error": null
}
```
取文本:优先 `resp.output_text`;手动则遍历 `output` 里 `type=="message"` → `content` 里 `output_text`。

---

## 5. 流式出参(语义事件,非 token 增量)

每个 SSE 事件是**带类型的语义事件**,有 `type` 和 `sequence_number`:

```
event: response.created
data: {"type":"response.created","response":{...}}

event: response.output_item.added
data: {"type":"response.output_item.added","item":{"type":"message",...}}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"回"}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"答"}

event: response.output_text.done
data: {"type":"response.output_text.done","text":"回答"}

event: response.completed
data: {"type":"response.completed","response":{... 完整对象含 usage ...}}
```

**与非流式的差异要点:**
- 不是 token 增量行,而是**事件流**:`response.created` → `output_item.added` → `content_part.added` → `output_text.delta`(增量正文)→ `*.done` → `response.completed`。
- 工具参数:`response.function_call_arguments.delta` / `.done`。
- 推理摘要:`response.reasoning_summary_text.delta`。
- **usage 在 `response.completed` 事件的完整 response 对象里**(无需像 Chat Completions 那样手动开 include_usage)。
- 失败/未完成:`response.failed` / `response.incomplete`。

```python
with client.responses.stream(model="gpt-4o", input="写首诗") as stream:
    for event in stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="")
    final = stream.get_final_response()   # 完整对象 + usage
```

---

## 6. 状态 / 停止 相关字段

- **状态**:顶层 `status`(`completed`/`incomplete`/`failed`/`in_progress`);截断原因看 `incomplete_details`(对应 Chat Completions 的 `finish_reason`)。
- 每个工具/消息 item 自身也有 `status`。
- **有状态续接**:`store:true` 存,下轮传 `previous_response_id` 即可只发增量;链路上的中间 reasoning 也能被复用。

---

## 7. 易错点

- 字段名跟 Chat Completions 不一样:`input`(非 messages)、`instructions`(非 system)、`max_output_tokens`(非 max_tokens)、`text.format`(非 response_format)。
- 函数工具是**扁平**结构(`name` 在顶层),从 Chat Completions 迁移别照搬嵌套写法。
- 默认 `store:true` 会在服务端留存,合规/隐私敏感场景按需关掉。
- 用了 `previous_response_id` 就**别再重发历史**(否则重复);不用它就退化成手动带全量。
- 输入用 `input_text`/`input_image`,输出是 `output_text`,别混。
- 流式是语义事件,解析逻辑和 Chat Completions 的 `delta` 完全不同。

→ 三者横向对照见 [README.md](./README.md)
