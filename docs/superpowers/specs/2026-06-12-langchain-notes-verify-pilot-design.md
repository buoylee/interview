# LangChain 笔记可执行校验套件 — 试点设计（02-chat-models）

> 2026-06-12 · 状态：已批准，待实现试点

## 1. 背景与问题

`ai/langchain/` 下 01–12 共 12 篇教学笔记（每篇 340–550 行），代码片段全部是**示意性**的：
带 `# 输出: ...` 注释声称结果，但没有任何东西真正执行。读完感觉"虚"——文档*断言*
`RunnablePassthrough.assign()` 会保留旧字段并加新字段，但你从未*看到*它真的这么做。

同目录的 `mvp-agentic-rag` 是反面：一个真实、34 个 pytest 测试覆盖的应用（含 `fakes.py` 假模型、
uv/Makefile/docker），但它没有和教学章节挂钩。

## 2. 目标

为每章笔记建立一个 **pytest 测试模块**，把文档里的关键声称变成**通过的断言**——
即"证明文档没说谎"（#1 的实质），用"面试可信的测试套件"（#3 的格式）交付。

成功标准：
- `pytest` 跑出全绿，可在面试中指着说"我的 LangChain 笔记不是纯文字，每章都有通过的测试模块证明机制"。
- 离线、确定性、免费即可验证 ~2/3 的内容（纯机制）。
- LLM 相关的 ~1/3 调**真实 OpenAI**，但默认无 key 时自动跳过，保证套件始终可绿。

非目标（YAGNI）：
- 不做"可玩 playground"（无断言、靠真实模型建直觉）——本套件是*证明*不是*把玩*。
- 不穷尽每个片段；只覆盖**面试必答**的核心机制 + gotcha（每章 ~5–10 个，基础章可略多）。
- 不重构现有笔记或 mvp 应用。

## 3. 关键决策（已与用户确认）

| 维度 | 决策 |
|---|---|
| 实质 | 证明文档声称（#1） |
| 格式 | pytest 套件，每章一个测试模块（#3） |
| 覆盖粒度 | 策展式「面试必答」，每章 ~5–10 个测试 |
| 纯机制 (~2/3) | 离线、确定性断言，无需 key |
| LLM 相关 (~1/3) | 调真实 OpenAI（`gpt-4o-mini`，小 `max_tokens`） |
| 结构 | 自包含同级项目 `ai/langchain/notes-verify/`（方案 A） |
| 节奏 | 先做 1 章试点（`02-chat-models`），跑通模板再铺开 |

## 4. 结构设计（方案 A：自包含同级项目）

```
ai/langchain/notes-verify/
├── pyproject.toml      # 依赖: langchain-core, langchain-openai, langchain, langgraph,
│                       #       pytest, pytest-asyncio；python >=3.12；自带 uv venv
├── conftest.py         # 注册 `live` marker + 无 key 时自动跳过 live；假模型 fixtures
├── .env.example        # OPENAI_API_KEY=
├── README.md           # 这是什么 / 怎么跑 / 面试可信度说明
└── tests/
    └── test_02_chat_models.py   # 试点；后续 test_03…test_12 同模板
```

运行方式：
- `uv run pytest` — 仅离线测试，任何人都全绿（可信基线）。
- `uv run pytest -m live` — 有 `OPENAI_API_KEY` 时额外跑真实 OpenAI 测试。

为什么 A：最契合"面试可信"目标——一个可指着看的自包含产物，与应用解耦，紧挨笔记；
`uv run pytest` 让第二个 venv 不成负担。假模型思路借用 mvp 的 `fakes.py`，优先用
`langchain_core` 内置 fakes（`GenericFakeChatModel` 等），仅在需要计数/抛错时写极小的自定义假模型。

## 5. 离线 / live 策略

- **默认 `pytest` 只跑离线测试**——确定性、无 key、始终绿，作为可信基线。
- **`@pytest.mark.live` 测试在 `OPENAI_API_KEY` 缺失时自动 skip**（conftest 的 `pytest_collection_modifyitems`
  钩子实现）。有 key 时命中 `gpt-4o-mini`、`max_tokens` 很小（成本几分钱）。
- 假模型测试复用 `langchain_core` 内置 fakes + 一个计数用的小假模型（同 mvp `fakes.py` 思路）。
- **每个测试带注释指向它所证明的文档章节声称**（如 `# §四 4.5 — invoke/stream/batch 返回类型`），
  使套件逐条映射回笔记。

## 6. 试点测试清单（基于 `02-chat-models.md` 实际内容）

### 离线 — 确定性，无 key（~9）

| 测试 | 证明（文档 §） |
|---|---|
| `test_message_types_map_to_roles` | §二 2.1 四种 Message → role |
| `test_tuple_shorthand_equals_message_objects` | §二 2.2 `("system",…)` ≡ `SystemMessage` |
| `test_toolmessage_requires_matching_tool_call_id` | §二 2.4 请求/响应配对，`tool_call_id` 必须匹配 |
| `test_invoke_stream_batch_return_types`（假模型） | §四 4.5 `AIMessage` / `Iterator[Chunk]` / `list` |
| `test_aimessagechunk_concatenation` | §四 4.2 chunk 用 `+` 合并成完整文本 |
| `test_with_fallbacks_switches_on_error`（假模型） | §六 6.3 主模型抛错 → fallback 应答 |
| `test_init_chat_model_infers_provider` | §七 `"gpt-4o"` → `ChatOpenAI`（无网络） |
| `test_multimodal_content_is_list_of_dict` | §五 纯文本 `str` vs 多模态 `list[dict]` |
| `test_inmemory_cache_skips_second_call`（计数假模型） | §六 6.1 相同输入 → 底层只调 1 次 |

### Live — 真实 OpenAI，`-m live`（~3）

| 测试 | 证明 |
|---|---|
| `test_live_invoke_returns_aimessage_with_usage` | 真实 `invoke` → `AIMessage`，`usage_metadata` 有值 |
| `test_live_stream_reconstructs_and_reports_usage` | 真实 `stream` 出多个 chunk；`stream_usage=True` → 末 chunk 带 usage |
| `test_live_usage_totals_add_up` | `input_tokens + output_tokens == total_tokens` |

共 ~12 个；基础章略多于 5–10 目标，可接受——它锁定模板供其余 11 章复用。低价值的可裁。

## 7. 验证（套件本身怎么算"做完"）

- `cd ai/langchain/notes-verify && uv sync && uv run pytest` → 离线测试全绿（无需 key）。
- 设 `OPENAI_API_KEY` 后 `uv run pytest -m live` → 3 个 live 测试全绿。
- README 写清两种跑法 + 面试可信度说明。

## 8. 风险与开放点

- **LangChain import 路径漂移**：笔记用 `from langchain.messages import ...`、
  `from langchain.chat_models import init_chat_model`、`from langchain.globals import set_llm_cache`、
  `from langchain_community.cache import InMemoryCache`。实现时以实际安装版本为准校正 import；
  若与笔记不一致，这本身就是一条有价值的"笔记纠偏"产出。
- **铺开到 11 章前先停**：试点跑通、模板确认后再决定后续章节顺序与每章清单（各自独立小迭代）。
