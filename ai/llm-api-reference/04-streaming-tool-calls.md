# 流式工具调用的执行模型(边收边执行 / 并行 / 框架封装)

> 定位:跨三套 API 的**应用层**深入篇。01/02/03 是单接口的入参/出参速查;这篇回答一个常被问倒的问题——
> **流式返回工具调用时,能不能「收到一个就马上执行」、并行执行多个?这层谁帮你做、做到哪一步?**
> 适用:自己写 Agent 工具执行器、对接 OpenAI 兼容层、或想搞清楚 LangChain/LangGraph 到底封装了什么。
> 底层协议是 SSE,报文/排障见 [`../network/sse.md`](../network/sse.md)。

---

## 1. 先厘清两个被混为一谈的概念

「异步实时并发工具调用」其实是两层东西,分清楚答案就清楚了:

| | 它是什么 | 谁决定 |
|---|---|---|
| **并行工具调用**(parallel tool calls) | **同一轮** LLM 输出里,模型一次吐出多个 tool call | 模型基于**同一份 context 一次性**决定;这几个 tool **互相看不到对方结果** |
| **边流边执行**(streaming dispatch) | 这些 tool call 是逐段 streaming 回来的,client 不必等整轮收完,**某个 tool 参数收完整就先派发执行**,同时后面的还在 stream | 纯 **client 端优化**,API 本身就把数据逐段给你了 |

**结论:你想要的「收到完整 index 0 就执行 index 0,收到完整 index 1 再执行 index 1」三套 API 都支持。** 因为同一轮里这些 tool 互不依赖对方结果,提前执行是安全的——不会和模型的决策抢跑。

> ⚠️ **唯一做不到的事**:你**不能**在「同一个 response 流的中途」塞回某个 tool 的结果、让模型在**同一次输出里**据此再生出新的 tool call。
> 「执行 → 把结果喂回去 → 模型再决定下一步」这一步**必然是新的一次 HTTP 请求(下一轮 turn)**。没有任何主流 API 会在生成中途暂停等你的 tool result 再续写同一个 response。
> (例外:Claude 的 server-side 工具如 web_search/code_execution 在它那侧自跑,靠 `pause_turn` 续,但那不是你 client 执行的工具。)

---

## 2. 核心:怎么知道「这个 tool 收完整了」

这是最容易踩坑、也是三套 API 差异最大的地方。判定信号分**显式**和**推断**两种:

| API | 「index N 的参数收完整、可派发」的信号 | 类型 | 最后一个 tool 能否提前派发 |
|---|---|---|---|
| **Chat Completions** | 下一个 `index` 出现(0→1),或最终 `finish_reason:"tool_calls"` | **推断**(无专门 done 事件) | ❌ 只能等结尾的 `finish_reason` |
| **Responses** | `response.output_item.done`(或 `response.function_call_arguments.done`) | **显式** | ✅ 每个 item 都有 done |
| **Claude Messages** | 该块的 `content_block_stop` | **显式** | ✅ 每个块(含最后一个)都有 stop |

记忆:**Claude / Responses 给你「这个 tool 完了」的明确事件,连最后一个都有;Chat Completions 没有,只能靠「下一个 index 冒出来」反推,所以最后一个 tool 只能等整流结束才能执行。** 这是 Chat Completions 相对吃亏的一点。

---

## 3. 三套报文实例(并行两 tool,标出「可派发」时刻)

例子统一:模型同时要调 `get_weather(city)` 和 `get_time(tz)`。基础单流见 01/03,这里只聚焦**并行 + 边界 + 执行时机**。

### Chat Completions —— 靠 `index` 区分、靠 `index` 递增反推完成

```
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_a","type":"function",
  "function":{"name":"get_weather","arguments":""}}]}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"city\":"}}]}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"北京\"}"}}]}}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":1,"id":"call_b","type":"function",
  "function":{"name":"get_time","arguments":""}}]}}]}   ← index 跳到 1 ⇒ 此刻可派发 call_a
data: {"choices":[{"delta":{"tool_calls":[{"index":1,"function":{"arguments":"{\"tz\":\"Asia/Shanghai\"}"}}]}}]}
data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}   ← 此刻才能派发 call_b(最后一个)
data: [DONE]
```

- `arguments` 是**逐片拼接的字符串**,要按 `index` 累加后 `json.loads`。
- 回填:每个结果一条 `role:"tool"` 消息(带 `tool_call_id`)。

### Responses —— 每个 function_call 是 item,有显式 `done`

```
event: response.output_item.added
data: {"output_index":0,"item":{"type":"function_call","id":"fc_1","call_id":"call_a","name":"get_weather","arguments":""}}
event: response.function_call_arguments.delta
data: {"item_id":"fc_1","delta":"{\"city\":"}
event: response.output_item.done
data: {"output_index":0,"item":{"type":"function_call","call_id":"call_a","arguments":"{\"city\":\"北京\"}","status":"completed"}}   ← done ⇒ 立刻派发
event: response.output_item.added
data: {"output_index":1,"item":{"type":"function_call","id":"fc_2","call_id":"call_b","name":"get_time","arguments":""}}
...
event: response.completed
```

- 回填:每个结果一个 `function_call_output` item(带 `call_id`)。

### Claude Messages —— 每个 tool_use 是块,有显式 `content_block_stop`

```
event: content_block_start
data: {"index":0,"content_block":{"type":"tool_use","id":"toolu_a","name":"get_weather","input":{}}}
event: content_block_delta
data: {"index":0,"delta":{"type":"input_json_delta","partial_json":"{\"city\":"}}
event: content_block_delta
data: {"index":0,"delta":{"type":"input_json_delta","partial_json":"\"北京\"}"}}
event: content_block_stop
data: {"index":0}                              ← stop ⇒ 立刻派发 toolu_a
event: content_block_start
data: {"index":1,"content_block":{"type":"tool_use","id":"toolu_b","name":"get_time","input":{}}}
...
event: content_block_stop
data: {"index":1}                              ← 最后一个也有自己的 stop
event: message_delta
data: {"delta":{"stop_reason":"tool_use"}}
```

- 参数走 `input_json_delta.partial_json` 逐片拼;聚合后 `input` 是**对象**(不用 json.loads)。
- 回填:**所有 `tool_result` 必须放在「同一条」user 消息里**(拆成多条会训练 Claude 之后不再并行调用)。

---

## 4. 手写累加器 + 三个现实的坑

如果你真要绕过 SDK 自己解析(比如做 OpenAI 兼容层),Chat Completions 的累加逻辑长这样:

```python
acc = {}                                  # index -> {id, name, args:str}
for chunk in stream:                       # raw stream=True
    for t in (chunk.choices[0].delta.tool_calls or []):
        i = t.index
        if i not in acc:                   # 新 index 出现 ⇒ 前一个确定收完整
            if i - 1 in acc:
                dispatch(acc[i-1])         # 不阻塞:丢线程池 / goroutine
            acc[i] = {"id": t.id, "name": t.function.name, "args": ""}
        acc[i]["args"] += t.function.arguments or ""
    if chunk.choices[0].finish_reason == "tool_calls":
        dispatch(acc[max(acc)])            # 最后一个在这里才派发
# dispatch 内部先 json.loads(args) 成功再执行
```

**三个会让你「看了实际报文反而不确定」的坑:**

1. **无显式 done(坑最大)**:Chat Completions 没有「index 0 完成」事件,只能靠「index 1 冒出来」或「finish_reason」反推 ⇒ **最后一个 tool 拿不到提前量**。Claude/Responses 无此问题。
2. **短参数会塌缩**:参数很短(如 `get_time(tz)`)时,整个 `tool_calls` 可能在**结尾一两个 chunk 一次到位**,看起来根本没「慢慢流」——这正常。「边流边执行」省到的时间 = 你执行 tool 0 的耗时,和模型还在生成 tool 1/2 参数 token 的耗时**重叠的那部分**。**收益只在「工具多 / 参数大(如大段 code edit) / 工具本身慢(网络/DB)」时才明显。**
3. **用 `index` 对号,别假设 wire 顺序**:三套都给了 `index` 就是要你**按 index 累加**,而不是假设「0 全到齐才轮到 1」。实务上 OpenAI 确实按序、不交错地发(所以「看到 index 1 ⇒ index 0 完整」成立),但正确写法永远是 index 累加 + 上面那两个信号判完成——换个 OpenAI 兼容后端(vLLM/Groq 等)行为略有差异也不炸。

---

## 5. 别自己写:现成的库做到哪一步

**生产上这层基本不该手写。** 但要分清「累加」和「调度」——框架包了前者,不一定包后者:

| 层 | 帮你「累加成完整 tool call」 | 帮你「一轮内并行执行多个」 | 帮你「stream 中途提前派发」 |
|---|---|---|---|
| 官方 SDK `.stream()` helper | ✅ | ❌(只给数据) | ❌ |
| LangChain chunk 相加 | ✅(且跨厂商归一化) | ❌ | ❌ |
| LangGraph `ToolNode` / `create_agent` | ✅ | ✅(并发执行一条 message 里的多 tool) | ❌ |
| 你自己降到 raw stream | 自己写 | 自己写 | ✅(只有这条路能做到) |

### 5.1 官方 SDK 的 `.stream()` helper —— 自带累加器

- **OpenAI**:`client.chat.completions.stream()`(不是 raw `stream=True`)按 `index` 帮你累加,emit `tool_calls.function.arguments.delta`/`.done` 事件,`stream.get_final_completion()` 给拼好的 message。Responses 则是 `client.responses.stream()` + `get_final_response()`。
- **Anthropic**:`client.messages.stream()` 帮你拼 `input_json_delta.partial_json`,`stream.get_final_message()` 的 `tool_use` 块 `.input` 已是**解析好的 dict**。

### 5.2 LangChain —— `AIMessageChunk` 可相加,且**跨厂商归一化**(最值钱)

```python
gathered = None
for chunk in model_with_tools.stream("北京和东京天气?"):
    gathered = chunk if gathered is None else gathered + chunk   # 一路 + 就累加好
    print(gathered.tool_calls)        # args 随 chunk 从半截 → 完整 dict(LangChain 用 partial-json parser)
```

两个字段要分清:

| 字段 | 内容 | 用途 |
|---|---|---|
| `chunk.tool_call_chunks` | **原始碎片**:`args` 是 partial 字符串,带 `index`/`id`/`name` | 自己边流边显示时用 |
| `gathered.tool_calls` | **累加+解析后**:`args` 是 dict(中途可部分解析) | 最终派发执行用 |

**关键价值**:OpenAI 的(`arguments` 字符串 + `index`)和 Anthropic 的(`partial_json` + content block)是两种完全不同的 wire 格式,LangChain 把它们**归一成同一个 `tool_call_chunks` / `tool_calls` 形状**。换模型供应商,Agent 代码不用改。

### 5.3 LangGraph `ToolNode` —— 一轮内自动并行

`create_agent` / 预置 `ToolNode` 会在**整轮 assistant message 收完后**,把这一批 tool calls **并发执行**(同一条 message 里多个 tool 同时跑)。

### 5.4 ⚠️ 框架不帮你做的那一步

框架做的是「**收完一整轮 → 把这轮的多个 tool 并行执行**」;**不是**「index 0 收完就先跑、不等 index 1 还在 stream」。
那个 stream 中途提前派发的极致低延迟,**SDK / LangChain / LangGraph 都不会自动做**——要自己降到 raw stream(用第 2 节的边界信号 + 线程池/goroutine)。大部分 Agent 用「一轮内并行」就够,别为了它放弃框架。

---

## 6. LangChain 对三套 API 的兼容

| 模型类 | 底层 API | 怎么用 |
|---|---|---|
| `ChatAnthropic` | **原生就是 Messages API**(Anthropic 只有这一个) | 直接用;细粒度串流给 tool 标 `@tool(extras={"eager_input_streaming": True})` |
| `ChatOpenAI` | **默认 Chat Completions** | tool calling 开箱即用 |
| `ChatOpenAI(use_responses_api=True)` | **切到 Responses API** | 用到 Responses 专属能力(内建工具 web_search/code_interpreter、`previous_response_id`、reasoning)时也会**自动切** |

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-5-mini", use_responses_api=True)              # 切 Responses
llm.bind_tools([{"type": "code_interpreter", "container": {"type": "auto"}}])  # 用内建工具
```

不管底层是 Chat Completions、Responses,还是 Anthropic Messages,在 LangChain 抽象下 tool call 都统一成 `tool_calls` / `tool_call_chunks`,Agent 逻辑不变。

---

## 7. 一句话记忆

- 你要的「收到完整就执行、继续收到再执行」**三套都能做**;唯一禁区是**同一个 response 流中途塞回结果让它续写**(那必然是下一轮请求)。
- 「某 tool 收完整了」:**Claude `content_block_stop` / Responses `output_item.done` 是显式的(含最后一个);Chat Completions 靠 `index` 递增 + `finish_reason` 反推,最后一个没提前量。**
- 累加别手写:**SDK `.stream()` 或 LangChain `AIMessageChunk` 相加**;LangGraph `ToolNode` 还白送「一轮内并行执行」。
- 框架包到「累加 + 一轮内并行」为止;**「stream 中途提前派发」要自己降到 raw stream**——只在工具多/参数大/工具慢时才值得。
- LangChain 对三套都兼容:`ChatAnthropic`=Messages 原生,`ChatOpenAI`=默认 Chat Completions、`use_responses_api=True` 切 Responses,上层 `tool_calls` 统一。

→ 单接口参数速查见 [01](./01-openai-chat-completions.md) / [02](./02-openai-responses.md) / [03](./03-claude-messages.md);三者横向对照见 [README.md](./README.md);选型/迁移见 [../openai-claude-chat-completion-接口整理.md](../openai-claude-chat-completion-接口整理.md)。
