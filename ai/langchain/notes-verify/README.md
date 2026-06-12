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

| 章节 | 测试模块 | 状态 |
|---|---|---|
| 02-chat-models | `tests/test_02_chat_models.py` | ✅ 试点完成(9 离线 + 3 live) |
| 01,03–12 | — | 待铺开(模板已锁定) |

## 笔记纠偏(校验过程中发现的失效写法)

> 这些是 v1.x(本套件锁定 `langchain 1.3.7` / `langchain-core 1.4.5`)上笔记代码已失效的地方,
> 正是"可执行校验"才暴露得出来的价值。

- **02 §六 6.1 缓存**:笔记写 `from langchain.globals import set_llm_cache` —— v1.x 下
  `langchain.globals` 模块已不存在。正确路径:`from langchain_core.globals import set_llm_cache`。
  (`InMemoryCache` 可从 `langchain_core.caches` 或 `langchain_community.cache` 导入。)
