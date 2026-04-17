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
└── coding-agent/              # Coding Agent 构建
    ├── build-guide.md         # 学习版: 从零手撸，理解原理 (Phase 1-6)
    └── production-guide.md    # 生产版: 多模型、可靠、安全、可持续使用
```

## 补充主题

- `openai-claude-chat-completion-接口整理.md` — OpenAI / Claude 的接口选型、三段最小示例和官方链接索引

## 学习顺序

### 路线 A: RAG + 记忆系统
`agent-memory/01` → `02` → `03` → `04`

### 路线 B: 构建 Coding Agent
1. `coding-agent/build-guide.md` — 先动手搭原型，理解 agent 原理
2. `coding-agent/production-guide.md` — 再升级为生产级架构

两个版本的区别:

| 维度 | 学习版 | 生产版 |
|------|--------|--------|
| 目的 | 理解原理 | 真实可用 |
| 模型 | 单一 SDK (Anthropic) | 多模型适配层 |
| 输出 | 等完才显示 | 流式逐 token |
| 错误 | crash | 重试、降级、自愈 |
| 安全 | 无 | 权限分级 + 注入防御 |
| 成本 | 不关心 | caching + 预算 + 路由 |
| MCP | 手写 JSON-RPC | 官方 SDK |
