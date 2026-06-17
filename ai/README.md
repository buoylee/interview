# AI 学习笔记

## 目录结构

```
ai/
├── agent-memory/              # RAG + Agent 记忆系统
│   ├── 01-rag-learning-path.md          # RAG 基础 (检索增强生成)
│   ├── 02-agent-memory-learning-path.md # Agent 记忆体系
│   ├── 03-advanced-rag-theory.md        # RAG 进阶理论
│   └── 04-memory-system-tech-glossary.md # 记忆系统术语表
│
├── coding-agent/              # Coding Agent 构建
│   ├── build-guide.md         # 学习版: 从零手撸，理解原理 (Phase 1-6)
│   └── production-guide.md    # 生产版: 多模型、可靠、安全、可持续使用
│
├── agent-platform/             # 企业 Agent 平台工程方案
│   ├── agent-local-vs-cloud-selection.md # 本地/云上选型与主流工具调研
│   └── cloud-agent-architecture.md       # 云上 Agent 最终落地架构
│
└── a2a-protocol/               # A2A(Agent2Agent)协议 实战自学
    ├── README.md               # 现状/心智模型/MCP 关系/框架接入/面试卡片
    ├── hello_server.py         # 最小 A2A 服务端骨架(v1.0)
    └── hello_client.py         # 最小 A2A 客户端骨架(v1.0)
```

## 补充主题

- `openai-claude-chat-completion-接口整理.md` — OpenAI / Claude 的接口选型、三段最小示例和官方链接索引
- `agent-platform/` — Agent 平台选型、云上架构、安全治理、RAG、工具网关、评测与发布方案
- `a2a-protocol/` — A2A 协议(agent↔agent 互通的事实标准)上手:Java/Go 对照心智模型、最小可跑 demo、A2A vs MCP、框架接入、面试卡片
- `ml-labs/` — 动手训练 labs(面试核心 A 轨 + robotics B 轨),runnable 产物;首个 A3 房价回归讲透 ML 基本功(过拟合/正则/指标/数据泄漏)

## 学习顺序

### 路线 A: RAG 系统(从零到资深)
**总纲**:[`rag-roadmap.md`](rag-roadmap.md) — 把散落在 `ml-to-llm-roadmap/01-rag-retrieval-systems/`(原理)、`langchain/08-rag-with-langchain.md`(实现)、`rag-lab/`(调试)、`langchain/mvp-agentic-rag/`(生产 MVP)四簇材料串成一条「读→建→量→深挖」的主线,先读它再分簇深入。

> 早期 RAG + 记忆材料在 `agent-memory/01`→`04`,内容与上面原理簇有重叠,可作为补充阅读。

### 路线 B: 构建 Coding Agent
1. `coding-agent/build-guide.md` — 先动手搭原型，理解 agent 原理
2. `coding-agent/production-guide.md` — 再升级为生产级架构

### 路线 C: 企业 Agent 平台落地
1. `agent-platform/agent-local-vs-cloud-selection.md` — 先做本地/云上/混合方案和工具选型
2. `agent-platform/cloud-agent-architecture.md` — 再看最终云上架构、组件拆分和治理方案

Coding Agent 两个版本的区别:

| 维度 | 学习版 | 生产版 |
|------|--------|--------|
| 目的 | 理解原理 | 真实可用 |
| 模型 | 单一 SDK (Anthropic) | 多模型适配层 |
| 输出 | 等完才显示 | 流式逐 token |
| 错误 | crash | 重试、降级、自愈 |
| 安全 | 无 | 权限分级 + 注入防御 |
| 成本 | 不关心 | caching + 预算 + 路由 |
| MCP | 手写 JSON-RPC | 官方 SDK |
