# 现有技术栈 → 国际主流技术栈：差距分析

> 公司现有技术栈：OneAPI + R2R + Open Assistant API
> 目标：过渡到国际主流认可的方案

---

## 一、现有技术栈逐项分析

### 1. OneAPI（songquanpeng/one-api）

| 维度 | 说明 |
|------|------|
| **是什么** | 国内开发者（JustSong）开发的 LLM API 代理/网关，将多个 LLM 提供商（OpenAI、Claude、国内模型）统一到一个 OpenAI 兼容接口后面 |
| **功能** | 统一 API、负载均衡、额度管理、多模型切换 |
| **国际认可度** | ❌ **低**。GitHub 上虽然 star 高（主要中文用户），但在国际 AI 工程圈几乎不被讨论。文档和社区以中文为主 |
| **需要替换吗？** | ⚠️ 看需求 |

**国际主流替代方案：**

| 替代方案 | Stars | 特点 | 推荐度 |
|---------|-------|------|--------|
| **LiteLLM** | 16k+ | ⭐ 国际最主流的 LLM proxy，支持 100+ 模型，OpenAI 兼容 API，Python SDK + 服务器模式，内置 logging/重试/成本追踪 | ⭐⭐⭐⭐⭐ |
| **Portkey AI Gateway** | 6k+ | 商业 + 开源，缓存/可观测性/限流/分析面板 | ⭐⭐⭐⭐ |
| **Kong AI Gateway** | — | 企业级 API 网关扩展，适合已用 Kong 的团队 | ⭐⭐⭐ |

> **推荐：LiteLLM** — 国际社区使用最广、功能最匹配、开源、文档英文为主。

---

### 2. R2R（RAG to Riches）

| 维度 | 说明 |
|------|------|
| **是什么** | SciPhi 开发的开箱即用 RAG 引擎，提供 RESTful API、用户管理、数据摄取管道、可观测性 |
| **功能** | 混合检索（BM25 + 向量 + HyDE）、多模态摄取、GraphRAG（知识图谱）、Agentic 推理、Deep Research API、内置 Dashboard |
| **国际认可度** | ✅ **中。** 是国际项目（美国 SciPhi 公司），在 2025 RAG 框架列表中经常被提及，但社区规模比 LlamaIndex/LangChain/Haystack 小很多 |
| **需要替换吗？** | ⚠️ 值得评估 |

**R2R 的优势（可以保留的理由）：**
- 开箱即用，API-first 设计
- 内置用户管理、认证、Dashboard
- 内置 GraphRAG
- 是国际项目，不存在"不被国际认可"的问题

**R2R 的劣势（考虑替换的理由）：**
- 社区比 LlamaIndex/Haystack **小一个数量级**（GitHub ~3k vs LlamaIndex 39k vs LangChain 100k）
- 黑盒程度高 — 开箱即用的代价是定制灵活性低
- 文档和教程少，遇到问题难找到解决方案
- 如果 SciPhi 公司方向调整或停维，风险较高

**和推荐方案的对比：**

| 维度 | R2R | LlamaIndex + 各组件 |
|------|-----|-------------------|
| 上手速度 | ✅ 更快（开箱即用） | 需要组装 |
| 定制灵活度 | ❌ 较低 | ✅ 每个环节可插拔 |
| 社区/生态 | 小 | ✅ 大 10 倍以上 |
| 可控性 | 中（依赖 R2R 的设计决策） | ✅ 高 |
| 长期风险 | ⚠️ 公司小，不确定性高 | ✅ 低（多个大社区/大公司支持） |
| 国际认可 | ✅ 有（但不是主流选择） | ✅ 是主流选择 |

---

### 3. Open Assistant API（MLT-OSS/open-assistant-api）

| 维度 | 说明 |
|------|------|
| **是什么** | 国内团队开发的开源 OpenAI Assistants API 兼容层，自部署，支持 LLM/RAG/Function Call |
| **功能** | 兼容 OpenAI Assistants API 接口、集成 OneAPI、支持 RAG 和工具调用 |
| **国际认可度** | ❌ **很低。** 国内社区项目，国际上几乎无人使用 |
| **需要替换吗？** | ✅ **是的** — 而且有一个更紧迫的原因 |

> [!CAUTION]
> **OpenAI Assistants API 已于 2026 年 3 月被宣布废弃（deprecated），将于 2026 年 8 月 26 日关闭。** OpenAI 建议迁移到新的 Responses API。Open Assistant API 作为 Assistants API 的兼容层，其基础本身已被 OpenAI 放弃，继续使用有重大风险。

**国际主流替代方案取决于你们用 Assistants API 做什么：**

| 你们用来做什么 | 推荐替代 |
|--------------|---------|
| RAG（检索增强生成） | **LlamaIndex**（我们方案已覆盖） |
| Agent / Function Calling | **LangGraph** 或 **LlamaIndex Agents** |
| 对话管理 / 多轮会话 | LlamaIndex 的 Chat Engine / LangGraph |
| 统一 Assistant 平台 | 不需要专门的库，用 LlamaIndex + LangGraph 组合 |

---

## 二、差距总结

```
现有技术栈                    国际主流替换                  紧迫度
─────────────────────────────────────────────────────────────
OneAPI                    →  LiteLLM                     中
  (国内 LLM proxy)            (国际主流 LLM proxy)

R2R                       →  LlamaIndex + 各组件           中低
  (国际项目但社区小)            (国际主流 RAG 框架)
                              可以渐进替换，不急

Open Assistant API        →  LlamaIndex + LangGraph        🔴 高！
  (兼容已废弃的 Assistants API) (Assistants API 8月关闭)
                              必须尽快迁移
```

---

## 三、迁移优先级建议

### 🔴 P0 — 立即规划：Open Assistant API 迁移

**原因：** OpenAI Assistants API 将在 **2026 年 8 月 26 日关闭**，留给你们的时间只有 ~5 个月。

**迁移路径：**
1. 盘点你们通过 Open Assistant API 用了哪些功能（RAG? Function Calling? Code Interpreter?）
2. 将 RAG 部分迁移到 LlamaIndex
3. 将 Agent/Function Calling 部分迁移到 LangGraph 或 LlamaIndex Agents
4. 对话管理用 LlamaIndex Chat Engine

### 🟡 P1 — 近期替换：OneAPI → LiteLLM

**原因：** 功能上 OneAPI 能用，但不被国际社区认可，且 LiteLLM 功能更强、生态更好。

**迁移成本：** 低 — 两者都是 OpenAI 兼容 API proxy，切换主要是部署和配置层面。

### 🟢 P2 — 逐步评估：R2R → LlamaIndex

**原因：** R2R 本身是国际项目，不是"不被认可"的问题，而是"不是主流"的问题。如果 R2R 满足当前需求，可以先不换。

**迁移信号（出现以下情况时考虑替换）：**
- R2R 的黑盒限制了你们的定制需求
- 遇到问题在社区找不到解决方案
- 需要和更广泛的国际 AI 生态集成

---

## 四、迁移后的目标技术栈

```
┌──────────────────────────────────────────────────────┐
│              目标技术栈（国际主流）                      │
│                                                      │
│  LLM Proxy:    LiteLLM（替换 OneAPI）                 │
│  编排框架:      LlamaIndex（替换 R2R + Open Asst API） │
│  Agent 编排:    LangGraph（替换 Open Asst API）        │
│  文档解析:      Docling 或 LlamaParse                  │
│  Embedding:    OpenAI text-embedding-3                │
│  向量数据库:    pgvector（已有 ✅）                     │
│  BM25 检索:     LlamaIndex 内置 BM25Retriever         │
│  Reranker:     Cohere Rerank v3                      │
│  评估:         RAGAS                                  │
│  可观测性:      Langfuse                               │
└──────────────────────────────────────────────────────┘
```

---

## 五、和现有方案的对应关系图

```
现有                              目标
────────────────────────────────────────────
OneAPI ─────────────────────→ LiteLLM
  ↕ 统一 LLM 接口                ↕ 同样功能但国际主流

R2R ────────────────────────→ LlamaIndex
  ↕ 文档解析 + 检索 + 生成         ↕ 拆分为可插拔组件
                                  + Docling (解析)
                                  + pgvector (存储)
                                  + BM25Retriever (关键词)
                                  + Cohere Rerank (精排)

Open Assistant API ─────────→ LlamaIndex + LangGraph
  ↕ Assistants API 兼容层          ↕ 原生 Agent/RAG 框架
  ⚠️ 基础已被 OpenAI 废弃          ✅ 主流且活跃维护

(新增)                        → RAGAS (评估)
(新增)                        → Langfuse (可观测性)
```
