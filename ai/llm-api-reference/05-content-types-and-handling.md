# 返回内容类型 & 处理(thinking / 多模态 / 工具结果 / 结构化 / refusal)

> 定位:跨三套 API 的 content 维度横向对照——**一次响应里可能出现哪些东西、各自怎么读、怎么回传**;输入侧能放什么也一并列。
> 01/02/03 是单接口入参/出参速查,04 讲流式工具调用的执行调度;这篇补「内容类型」这一刀。**每个 API 各自的完整清单 + 代码**见 01/02/03 各自的「§8 返回内容类型 & 处理」。
> 底层协议见 [`../network/sse.md`](../network/sse.md)。

---

## 1. 处理通则(三条心法,先记这个)

1. **取文本别假设位置**。输出要么是 typed 数组(Claude `content[]`、Responses `output[]`),要么是单 message(Chat Completions)。
   - **遍历按 `type` 取**,别 `content[0].text`——开思考时第一个常是 thinking/reasoning 块。
   - Chat Completions 的 `message.content` 是字符串,但**纯工具调用 / refusal 时是 `null`**,直接用会炸。
2. **多轮回传要带「整条 assistant 输出」**,不是只取正文。thinking/reasoning 块、tool 调用、签名都要原样带回去,否则下一轮**报错或丢推理链降智**(详见 §4)。
3. **写一个分发器**:`for block in ...: match block.type` 把 text / thinking / tool_use / 工具结果块 / 引用 分开处理,而不是只盯正文。

---

## 2. 输入能放什么(× 三者)

| 输入类型 | Chat Completions | Responses | Claude Messages |
|---|---|---|---|
| 文本 | `{"type":"text"}` | `{"type":"input_text"}` | `{"type":"text"}` |
| 图片 | `{"type":"image_url","image_url":{url\|dataURI,"detail"}}` | `{"type":"input_image","image_url"\|"file_id","detail"}` | `{"type":"image","source":{base64+media_type\|url\|file_id}}` |
| 音频 | ✅ `{"type":"input_audio","input_audio":{data,format}}`(需 `gpt-4o-audio`) | ⚠️ 主力在 Realtime API,Responses 文本/图/文件为主 | ❌ 不支持 |
| 视频 | ❌ | ❌ | ❌ |
| PDF / 文件 | ✅ `{"type":"file","file":{file_id\|file_data\|filename}}` | ✅ `{"type":"input_file","file_id"\|filename+file_data}` | ✅ `{"type":"document","source":{base64 PDF\|file_id}}`(支持 citations) |

- **视频:三者都没有原生视频输入**(那是 Gemini 的能力)。变通:client 端**抽帧成多张图**再当图片传(自己控采样率,token 会涨)。
- 图片 token 成本:Chat Completions/Responses 的 `detail:"high"` 会切 tile、token 暴涨;Claude 高分辨率(Opus 4.7+ 长边 ≤2576px)单图最多 ~4784 token。大图按需 client 端先降采样。

---

## 3. 输出可能返回什么(× 三者)

| 输出类型 | Chat Completions | Responses | Claude Messages |
|---|---|---|---|
| 正文 | `message.content`(**str 或 null**) | `output_text` + `message` item 里 `output_text` | `content[]` 里 `text` 块 |
| 思考/推理 | ❌ 不返回,仅 `reasoning_tokens` **计数** | `reasoning` item(summary;raw 加密) | `thinking` 块(summary + signature) |
| 工具调用 | `tool_calls`(见 04) | `function_call` item | `tool_use` 块 |
| 音频输出 | ✅ `message.audio{id,data,transcript}` | ⚠️ 有限(Realtime 为主) | ❌ |
| 图像生成 | ❌(走 Images API) | ✅ 内建 `image_generation_call.result`(b64) | ❌ |
| 生成文件 | ❌ | ✅ code_interpreter 产物(file) | ✅ code execution / skills 产物(file_id → Files API 下) |
| 引用来源 | ⚠️ 搜索模型的 `annotations` | `output_text.annotations`(`url_citation`) | `text` 块的 `citations` 数组 |
| 安全拒绝 | `message.refusal` 字段 + `finish_reason:content_filter` | message 里 `refusal` 部件 | `stop_reason:"refusal"`(HTTP 200) |

---

## 4. thinking / reasoning —— 返回形态 + replay 规则(最容易踩)

### 返回形态

| | Chat Completions | Responses | Claude Messages |
|---|---|---|---|
| 推理过程可见? | ❌ 全隐藏,只给 `completion_tokens_details.reasoning_tokens` 计数 | 摘要可见:`reasoning` item 的 `summary[]`(raw 加密隐藏) | 摘要可见:`thinking` 块(raw 永不返回) |
| 控制深度 | `reasoning_effort: low/medium/high` | `reasoning:{effort, summary:"auto/concise/detailed"}` | `thinking:{type:"adaptive"}` + `output_config.effort` |
| 块/项形态 | 无 | `{"type":"reasoning","id","summary":[{type:"summary_text",text}],"content?":[{type:"reasoning_text"}]}` | `{"type":"thinking","thinking":"...","signature":"..."}`(或安全场景 `redacted_thinking` 加密块) |
| 摘要默认 | — | 不给 summary 就没文本 | 4.7/4.8/Fable 默认 `display:"omitted"`(文本空、签名在);要文本设 `display:"summarized"` |

### replay 规则(多轮 / 工具循环里务必照做)

| | 谁留着推理链 | 你要不要回传 | 改了 / 丢了会怎样 |
|---|---|---|---|
| Chat Completions | 没人(无状态、每轮重想) | 不用 | 无影响(本来就不带) |
| Responses(有状态) | **服务端**(`store:true` + `previous_response_id`) | 不用(只发新输入) | — |
| Responses(无状态 `store:false`/ZDR) | 你 | **要**:把 `reasoning` item 放进下轮 `input`,且加 `include:["reasoning.encrypted_content"]` 拿加密内容一起带回 | 丢了 reasoning 链 → 工具循环降智 |
| Claude(同模型续接) | 你 | **铁律:原样回传 thinking 块**(含 `signature`、含空文本块) | 改了 → 400(签名校验失败) |
| Claude(换模型) | — | 不用(会被自动丢弃,**不计费**) | 无 |

> **工具循环里最常翻车的点**:那条「带 `tool_use` 要调工具」的 assistant 输出,**前面通常就挂着 thinking/reasoning 块**。回填工具结果时要把**整条 assistant `content`/`output` 追加回去**,而不是只追加 `tool_use`——否则 Claude 报签名错、Responses(无状态)丢链。

---

## 5. 多模态输入处理要点

- **图片**:三种字段名不同(`image_url` / `input_image` / `image`+`source`),base64 都要去掉换行;Claude base64 必须带 `media_type`。
- **音频输入**:只有 Chat Completions(`gpt-4o-audio` + `input_audio`)是普通请求里的一等公民;实时语音对话走 **Realtime API**(WebSocket/事件流),不是这三套对话接口。Claude 无音频。
- **PDF**:Chat Completions 用 `file` 部件、Responses 用 `input_file`、Claude 用 `document` 块(且 Claude 的 document 可开 `citations` 让回答带页码引用)。
- **视频**:见 §2——三者无原生,抽帧成图。

---

## 6. 多模态输出处理

### 音频输出(Chat Completions)
```python
resp = client.chat.completions.create(
    model="gpt-4o-audio-preview",
    modalities=["text", "audio"],
    audio={"voice": "alloy", "format": "wav"},
    messages=[{"role": "user", "content": "念一句欢迎语"}],
)
a = resp.choices[0].message.audio          # {id, data(b64), transcript, expires_at}
open("out.wav","wb").write(base64.b64decode(a.data))
# 多轮续接:下一轮 assistant 消息引用 {"role":"assistant","audio":{"id": a.id}}
```

### 图像生成(Responses 内建工具)
`tools=[{"type":"image_generation"}]` → `output[]` 里 `{"type":"image_generation_call","result":<b64>,"status":"completed"}`,解 b64 存盘。

### 生成文件(Responses code_interpreter / Claude code execution & skills)
模型把产物(`.xlsx`/`.pptx`/图表/csv)写进容器,响应给 **file_id**,再经 Files API 下载:
- Claude:`client.beta.files.download(file_id).write_to_file(path)`(产物来自 `bash_code_execution_tool_result` 的输出文件,或 skills)。
- Responses:`code_interpreter_call` 产物文件;取 outputs 需 `include:["code_interpreter_call.outputs"]`。

---

## 7. 结构化输出取值 + refusal / 安全内容

### 结构化输出取值
| | 入参 | 取值 |
|---|---|---|
| Chat Completions | `response_format:{type:"json_schema",json_schema:{...}}` | `message.content` 是 JSON 串;SDK `.parse()` → `message.parsed` |
| Responses | `text:{format:{type:"json_schema",...}}` | `output_text` 是 JSON;SDK `.parse()` → `output_parsed` |
| Claude | `output_config:{format:{type:"json_schema","schema":...}}` 或 strict tool | 首个 `text` 块是 JSON;`messages.parse()` → `parsed_output` |

⚠️ 撞 `max_tokens`/`length` 截断会吐**半截 JSON**,parse 前先判停止原因。结构化输出通常**不能与 citations 同开**(Claude 会 400)。

### refusal / 安全内容判别(通则:先判停止原因/refusal 字段,再读正文)
| | 怎么判 | 注意 |
|---|---|---|
| Chat Completions | `message.refusal` 有值(此时 `content` 为 null),或 `finish_reason:"content_filter"` | 流式有 `refusal.delta`/`.done` 事件 |
| Responses | message 里出现 `refusal` 内容部件 | 配合 `status` 看是否 incomplete |
| Claude | `stop_reason:"refusal"`(**HTTP 200**),`stop_details.category` 给类别 | **读 `content[0]` 前必须先判**,否则 index 越界;Fable 5 可配 `fallbacks` 自动转移到 Opus |

---

## 8. 一句话记忆

- **取值**:Claude/Responses 是 typed 数组,**遍历按 type 取**;Chat Completions 是单 message,`content` 可能为 `null`(纯工具/refusal)。
- **thinking**:Chat Completions 只给 token 数;Responses 给 `reasoning` item;Claude 给 `thinking` 块。**replay**:Claude 同模型必须原样回传(含签名),Responses 无状态要回传 reasoning item + `include encrypted_content`,Chat Completions 不用。
- **多模态输入**:图三者都行(字段不同);**音频只有 OpenAI(gpt-4o-audio)**;**视频三者都无原生,抽帧成图**;PDF 三者都行。
- **多模态输出**:音频输出=Chat Completions;图像生成=Responses 内建工具;生成文件=Responses/Claude(经 Files API 下);Claude 无音频/图像生成。
- **refusal**:**先判停止原因/refusal 字段再读正文**;Chat Completions 看 `message.refusal`+`content_filter`,Claude 看 `stop_reason:"refusal"`(HTTP 200)。

→ 单接口各自的完整清单见 [01 §8](./01-openai-chat-completions.md) / [02 §8](./02-openai-responses.md) / [03 §8](./03-claude-messages.md);流式工具调用执行模型见 [04](./04-streaming-tool-calls.md);三者横向对照见 [README.md](./README.md)。
