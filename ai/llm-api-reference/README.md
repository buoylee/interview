# LLM 三大对话 API 入参/出参速查

面试/日常快速回忆用。每份单文件按「定位 → 核心入参 → 多模态 → 工具调用 → 非流式出参 → 流式出参 → usage/停止 → 易错点」组织。

- [01 OpenAI Chat Completions](./01-openai-chat-completions.md) — 经典、无状态、生态最广
- [02 OpenAI Responses](./02-openai-responses.md) — 新一代、有状态、内置工具
- [03 Claude Messages](./03-claude-messages.md) — Anthropic 唯一对话接口、无状态

> 另有 [../openai-claude-chat-completion-接口整理.md](../openai-claude-chat-completion-接口整理.md):偏选型/迁移 + 代码示例(SSE、异常处理),和本目录的纯参数速查互补。

---

## 一屏三者对照

| 维度 | Chat Completions | Responses | Claude Messages |
|---|---|---|---|
| Endpoint | `/v1/chat/completions` | `/v1/responses` | `/v1/messages` |
| 鉴权 | `Authorization: Bearer` | `Authorization: Bearer` | `x-api-key` + `anthropic-version` 头 |
| 状态 | 无状态 | **有状态**(`store`+`previous_response_id`) | 无状态 |
| 输入字段 | `messages` | `input`(+`instructions`) | `messages`(+`system`) |
| system 放哪 | messages 里 `role:system/developer` | 顶层 `instructions` | **顶层 `system` 参数** |
| 输出上限参数 | `max_completion_tokens` | `max_output_tokens` | **`max_tokens`(必填)** |
| 多候选 `n` | 有 | 无(只 1) | 无(只 1) |
| 工具定义 | `tools[].function.{name,parameters}`(嵌套) | `tools[].{name,parameters}`(**扁平**) | `tools[].{name,input_schema}` |
| 工具结果回填 | `role:"tool"` 一条 | `function_call_output` item | user 消息里 `tool_result` 块 |
| 工具入参形态 | `arguments` 是 **JSON 字符串** | `arguments` 是 **JSON 字符串** | `input` 是 **已解析对象** |
| tool_choice | `auto/none/required/{function}` | `auto/none/required/{name}` | `{type:auto/any/tool/none}` |
| 思考/推理 | `reasoning_effort` | `reasoning.{effort,summary}` | `thinking.{type}` + `output_config.effort` |
| 结构化输出 | `response_format` | `text.format` | `output_config.format` / strict tool |
| 内置工具(web/file/code) | ❌ | ✅(web_search/file_search/code_interpreter/mcp) | ✅(server-side tools,另算) |
| 提示缓存 | 自动(`cached_tokens`) | 自动(`cached_tokens`) | 手动 `cache_control` 打点 |
| 多模态文本/图 | `text` / `image_url` | `input_text` / `input_image` | `text` / `image`(+`source`) |
| 输出形态 | `choices[].message.content`(字符串) | `output[]`(typed items)+`output_text` | `content[]`(typed blocks) |
| 流式形态 | `chunk.delta`(**token 级增量**) | **语义事件** `response.*` | **语义事件** `message_*`/`content_block_*` |
| 流式 usage | 需 `stream_options.include_usage` | 在 `response.completed` 里 | 输入在 `message_start`,输出在 `message_delta` |
| 停止/状态 | `finish_reason` | `status`+`incomplete_details` | `stop_reason` |
| 用量字段 | `prompt_tokens`/`completion_tokens` | `input_tokens`/`output_tokens` | `input_tokens`/`output_tokens`(+cache 字段) |

---

## 停止原因对照

| 场景 | Chat Completions | Responses | Claude Messages |
|---|---|---|---|
| 正常结束 | `stop` | `status:completed` | `end_turn` |
| 撞输出上限 | `length` | `status:incomplete`(`incomplete_details`) | `max_tokens` |
| 命中停止串 | `stop` | — | `stop_sequence` |
| 要调工具 | `tool_calls` | output 含 `function_call` | `tool_use` |
| 安全拒绝 | `content_filter` / `refusal` | — | `refusal` |

---

## 一句话记忆

- **Chat Completions**:无状态、`messages` 里塞 system、工具嵌套在 `function` 下、`arguments` 是字符串、流式是 token 增量(usage 要手动开)。
- **Responses**:有状态(`previous_response_id` 续接)、`input`+`instructions`、工具扁平、输出是 typed items、流式是语义事件(usage 自带)。
- **Claude Messages**:`max_tokens` 必填、`system` 顶层、工具结果走 user 的 `tool_result` 块、`input` 是对象、流式 message/content_block 事件、新模型砍了采样参数。
