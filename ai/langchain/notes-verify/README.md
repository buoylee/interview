# notes-verify — LangChain 笔记的可执行校验套件

把 `ai/langchain/` 各章教学笔记里的**关键声称**变成**通过的 pytest 断言**。

笔记里的代码片段大多是示意性的(带 `# 输出: ...` 注释但不真正执行),读多了发"虚"。
这个套件的作用:**每一章的核心机制都有一个测试模块在证明它确实如此**,可以指着说
"我的 LangChain 笔记不是纯文字 —— 每章都有通过的测试覆盖"。

## 设计

- **离线测试(~2/3)**:纯机制(Runnable、消息类型、解析器、缓存、fallback……),
  用 `langchain_core` 内置假模型做**确定性断言**,无需 API key、免费、始终绿。
  这是可信基线。
- **live 测试(~1/3,`@pytest.mark.live`)**:工具调用决策、真实流式、token 用量等
  只有真模型才能证明的东西,调**真实 OpenAI**(`gpt-4o-mini`,小 `max_tokens`,成本几分钱)。
  **没有 `OPENAI_API_KEY` 时自动 skip**,所以默认 `pytest` 在任何机器上都全绿。
- 每个测试上方注释指向它所证明的笔记章节(如 `# §四 4.5 — invoke/stream/batch 返回类型`)。

## 跑法

```bash
cd ai/langchain/notes-verify
uv sync --extra dev          # 首次:建 venv 装依赖

uv run pytest                # 仅离线测试,全绿(无需 key)
uv run pytest -v             # 看每条断言对应哪个声称

# 跑真实 OpenAI 部分:把 key 放进 .env(见 .env.example)或 export
export OPENAI_API_KEY=sk-...
uv run pytest -m live        # 只跑 live;无 key 会自动 skip
```

## 进度

全 12 章已覆盖:**112 个离线测试 + 12 个 live 测试**(`uv run pytest` → `112 passed, 12 skipped`)。

| 章节 | 测试模块 | 离线 | live |
|---|---|:--:|:--:|
| 01-langchain-learning-path | `tests/test_01_learning_path.py` | 5 | 0 |
| 02-chat-models | `tests/test_02_chat_models.py` | 9 | 3 |
| 03-prompt-templates | `tests/test_03_prompt_templates.py` | 11 | 0 |
| 04-output-parsers | `tests/test_04_output_parsers.py` | 9 | 2 |
| 05-lcel-deep-dive | `tests/test_05_lcel.py` | 11 | 1 |
| 06-tool-calling | `tests/test_06_tool_calling.py` | 11 | 2 |
| 07-agents | `tests/test_07_agents.py` | 8 | 1 |
| 08-rag-with-langchain | `tests/test_08_rag.py` | 9 | 1 |
| 09-langgraph-core | `tests/test_09_langgraph_core.py` | 12 | 0 |
| 10-langgraph-advanced | `tests/test_10_langgraph_advanced.py` | 11 | 0 |
| 11-production | `tests/test_11_production.py` | 9 | 1 |
| 12-multi-agent | `tests/test_12_multi_agent.py` | 7 | 1 |

> 01 是纲领/路线图章,多为非可断言的文字,只有 5 个真正可运行验证的点(诚实地小)。
> 11(生产化)有大量是运维指引(LangSmith/Langfuse/部署),只断言其中可运行的机制。

## 笔记纠偏(校验过程中发现的失效写法)

> 这些是 v1.x(本套件锁定 `langchain 1.3.7` / `langchain-core 1.4.5`)上笔记代码已失效的地方,
> 正是"可执行校验"才暴露得出来的价值。

**导入路径已失效(v1.x 模块迁移):**
- **02 §六6.1**:`from langchain.globals import set_llm_cache` → `langchain_core.globals`
  (`langchain.globals` 模块已不存在;`InMemoryCache` 用 `langchain_core.caches`)。
- **04 §6.2**:`from langchain.output_parsers import RetryOutputParser` → `langchain_classic.output_parsers`
  (`langchain.output_parsers` 模块已不存在)。
- **08 §3**:`from langchain.text_splitter import RecursiveCharacterTextSplitter` →
  `from langchain_text_splitters import ...`(`langchain.text_splitter` 模块已不存在)。
- **07 / 01 §3.2**:`from langgraph.prebuilt import create_react_agent` 仍可用但**已弃用**
  (`LangGraphDeprecatedSinceV10`),迁移目标 `from langchain.agents import create_agent`
  (LLM 节点名从 `agent` 改为 `model`)。旧版 `AgentExecutor` 已移出 `langchain.agents`,
  现位于 `langchain_classic.agents`。

**API 行为与笔记声称不符:**
- **06 §6.2**:`@tool(handle_tool_error=True)` 在 v1.x 直接 `TypeError`(该 kwarg 没了),
  笔记这处需改写(错误处理改为 invoke 层处理)。
- **06 §2.1**:`@tool` 的 `.description` 默认是**整个 docstring(含 `Args:` 块)**,不是首行摘要;
  要笔记说的「只取摘要」需 `@tool(parse_docstring=True)`。
- **10 §1.4**:笔记说「没有 Checkpointer 就不能用 interrupt()」不精确 —— 实测**仍会暂停**,
  只是 `Command(resume=...)` 和 `get_state()` 会报错(即:能暂停、不能恢复/查看,HITL 闭环走不通)。
- **11**:Chat Model 触发的回调是 `on_chat_model_start`,不是 `on_llm_start`(笔记未明说,顺带记录)。

**确认无误(笔记 import 正确,实测通过):** 03、05、09、12 章的所有 import 路径在 v1.x 仍有效。

> 注:`langchain_community` 导入时现在会发 sunset `DeprecationWarning`(迁移至独立集成包),
> 凡笔记里 `langchain_community.*` 的整合(Chroma/FAISS/社区工具/Langfuse 等)需留意。
