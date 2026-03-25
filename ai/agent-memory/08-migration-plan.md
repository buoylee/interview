# 完整迁移方案：替代 Open Assistant API + R2R

> 目标：用国际主流技术栈完全替代现有的 Open Assistant API + R2R
> 团队规模：10 人
> 已有基础设施：PostgreSQL（pgvector）

---

## 一、现有系统功能清单 → 替代映射

首先梳理 R2R + Open Assistant API 提供了什么功能，以及各由谁替代：

### R2R 功能映射

| R2R 功能 | 替代方案 | 说明 |
|---------|---------|------|
| 文档摄取（PDF/TXT/JSON/图片/音频） | **Docling** (IBM 开源) | 多格式解析，本地运行 |
| 文本分块 | **LlamaIndex** 内置 | 递归分块/语义分块 |
| 向量化 (Embedding) | **OpenAI text-embedding-3** | API 调用 |
| 向量存储 + 检索 | **pgvector**（已有 ✅） | 零额外运维 |
| BM25 关键词检索 | **LlamaIndex BM25Retriever** | 纯内存，内置 |
| 混合检索 (RRF) | **LlamaIndex QueryFusionRetriever** | 内置 RRF 融合 |
| HyDE 假设文档嵌入 | **LlamaIndex HyDEQueryTransform** | 内置 |
| 重排序 | **Cohere Rerank v3**（API）或 **bge-reranker**（本地） | |
| GraphRAG 知识图谱 | **LlamaIndex KnowledgeGraphIndex** 或 后续迭代 | 可先不做，P2 |
| 用户认证 + 权限 | **FastAPI** 自建（JWT + RBAC） | |
| REST API | **FastAPI** | Python 生态首选 API 框架 |
| Dashboard / 可观测性 | **Langfuse**（开源自部署） | Trace + 评估 + 指标 |
| 文档管理（CRUD） | **FastAPI** + **PostgreSQL** | 自建文档管理服务 |
| Collection 集合管理 | **PostgreSQL** 表设计 | 文档分组 + 权限隔离 |
| LLM 多模型集成 | **LiteLLM**（替换 OneAPI） | 统一 LLM 接口 |

### Open Assistant API 功能映射

| Open Assistant API 功能 | 替代方案 | 说明 |
|------------------------|---------|------|
| OpenAI Assistants API 兼容 | **不再需要** | Assistants API 已废弃(2026.08 关闭) |
| 对话管理 / 多轮会话 | **LlamaIndex Chat Engine** + **PostgreSQL** | 会话历史存 DB |
| RAG 检索增强 | **LlamaIndex**（上面已覆盖） | |
| Function Calling / 工具调用 | **LlamaIndex Agents** 或 **LangGraph** | |
| 与 OneAPI 集成 | **LiteLLM** | 替换 OneAPI |

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端 / 前端                              │
│            (Web App / Bot / 内部系统 / 第三方集成)                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI 服务层 (自建)                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  认证模块     │  │  文档管理     │  │  对话 / RAG 模块    │    │
│  │  JWT + RBAC  │  │  上传/删除    │  │  检索 + 生成        │    │
│  │              │  │  集合管理     │  │  Agent / 工具调用   │    │
│  └──────────────┘  └──────┬───────┘  └────────┬───────────┘    │
│                           │                    │                │
│  ┌────────────────────────┴────────────────────┴──────────┐    │
│  │                   LlamaIndex (核心引擎)                  │    │
│  │                                                        │    │
│  │  ┌─────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ │    │
│  │  │ 文档解析 │ │ 分块+索引   │ │ 混合检索  │ │ 生成    │ │    │
│  │  │ Docling  │ │ Chunking   │ │ Dense    │ │ Chat    │ │    │
│  │  │          │ │ + Index    │ │ + BM25   │ │ Engine  │ │    │
│  │  │          │ │            │ │ + RRF    │ │         │ │    │
│  │  └─────────┘ └────────────┘ └──────────┘ └─────────┘ │    │
│  └────────────────────────────────────────────────────────┘    │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────────┐
         │                  │                      │
         ▼                  ▼                      ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  PostgreSQL  │  │   LiteLLM    │  │     Langfuse          │
│  + pgvector  │  │  (LLM Proxy) │  │  (可观测性/评估)       │
│              │  │              │  │                       │
│ • 向量存储    │  │ • 统一 LLM   │  │ • 全链路 Trace         │
│ • 文档元数据  │  │   API 接口   │  │ • RAGAS 评估集成       │
│ • 用户/权限   │  │ • 负载均衡   │  │ • 成本/延迟监控        │
│ • 会话历史    │  │ • 故障切换   │  │                       │
│ • 集合管理    │  │ • 成本追踪   │  │                       │
└──────────────┘  └──────────────┘  └──────────────────────┘
   已有 ✅          替换 OneAPI         新增
```

---

## 三、核心模块设计

### 3.1 文档管理服务

```
API 端点设计：

POST   /api/v1/documents/upload        上传文档（触发解析+索引）
GET    /api/v1/documents                列出文档
GET    /api/v1/documents/{id}           获取文档详情
DELETE /api/v1/documents/{id}           删除文档（同时删除 chunks + 向量）
PUT    /api/v1/documents/{id}           更新文档（重新解析+索引）
GET    /api/v1/documents/{id}/status    获取文档处理状态

POST   /api/v1/collections             创建集合
GET    /api/v1/collections              列出集合
POST   /api/v1/collections/{id}/documents  添加文档到集合
DELETE /api/v1/collections/{id}         删除集合
```

**处理流程：**
```
上传文档
   ↓
Docling 解析 (PDF/Word/HTML → 结构化文本)
   ↓
LlamaIndex 分块 (RecursiveCharacterTextSplitter, 512 tokens, 10% overlap)
   ↓
OpenAI Embedding (text-embedding-3-small)
   ↓
存入 pgvector (向量 + 元数据 + 文档ID + 集合ID)
   ↓
状态更新为 "完成"
```

### 3.2 检索 + 生成服务（RAG 核心）

```
API 端点设计：

POST   /api/v1/search                  纯检索（返回相关文档块）
POST   /api/v1/chat                    RAG 对话（检索 + LLM 生成）
POST   /api/v1/chat/stream             RAG 对话（SSE 流式）
```

**RAG 管道流程：**
```
用户 Query
   ↓
[可选] Query 改写 (LLM Rewrite)
   ↓
混合检索：
  ├─ Dense: pgvector 向量搜索 → Top-20
  ├─ Sparse: BM25Retriever 关键词搜索 → Top-20
  └─ RRF 合并 → Top-20
   ↓
Reranker 精排 → Top-5
   ↓
Prompt 构建（系统提示 + 检索上下文 + 用户问题 + 对话历史）
   ↓
LLM 生成（通过 LiteLLM 调用）
   ↓
返回回答 + 引用来源
```

### 3.3 对话管理

```
API 端点设计：

POST   /api/v1/conversations                   创建对话
GET    /api/v1/conversations                    列出对话
GET    /api/v1/conversations/{id}               获取对话详情（含历史）
DELETE /api/v1/conversations/{id}               删除对话
POST   /api/v1/conversations/{id}/messages      发送消息（触发 RAG）
```

**对话历史存储在 PostgreSQL 中**，每次 RAG 请求时取最近 N 轮对话作为上下文。

### 3.4 用户认证 + 权限

```
API 端点设计：

POST   /api/v1/auth/register            注册
POST   /api/v1/auth/login               登录 (返回 JWT)
GET    /api/v1/users/me                  当前用户信息
PUT    /api/v1/users/me                  更新用户信息
```

**权限模型：**
```
用户 → 属于 → 集合 (Collection)
文档 → 属于 → 集合
检索时 → 只搜索用户有权限的集合中的文档
```

---

## 四、数据库 Schema 设计

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',  -- admin / user
    created_at TIMESTAMP DEFAULT NOW()
);

-- 集合表 (对应 R2R 的 Collection)
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 用户-集合权限
CREATE TABLE user_collections (
    user_id UUID REFERENCES users(id),
    collection_id UUID REFERENCES collections(id),
    permission VARCHAR(50) DEFAULT 'read',  -- read / write / admin
    PRIMARY KEY (user_id, collection_id)
);

-- 文档表
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID REFERENCES collections(id),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    status VARCHAR(50) DEFAULT 'pending',  -- pending / processing / completed / failed
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 文档块表 (带向量)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    collection_id UUID REFERENCES collections(id),
    content TEXT NOT NULL,
    chunk_index INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),  -- text-embedding-3-small 维度
    created_at TIMESTAMP DEFAULT NOW()
);

-- 向量索引
CREATE INDEX chunks_embedding_idx ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- 对话表
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 消息表
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- user / assistant
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',  -- 引用溯源
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 五、技术栈清单 + 版本

| 组件 | 库/工具 | 用途 |
|------|--------|------|
| **Web 框架** | FastAPI | REST API 服务 |
| **RAG 引擎** | LlamaIndex (llama-index-core) | 分块、索引、检索、生成 |
| **文档解析** | Docling | PDF/Word/HTML → 结构化文本 |
| **Embedding** | OpenAI text-embedding-3-small | 文本 → 向量 |
| **向量数据库** | pgvector (PostgreSQL 扩展) | 向量存储 + 搜索 |
| **BM25 检索** | llama-index-retrievers-bm25 | 关键词检索 |
| **Reranker** | Cohere Rerank v3 (API) | 精排 |
| **LLM Proxy** | LiteLLM | 统一 LLM 接口（替换 OneAPI） |
| **认证** | python-jose + passlib | JWT 认证 |
| **ORM** | SQLAlchemy + asyncpg | PostgreSQL 异步访问 |
| **任务队列** | Celery + Redis 或 FastAPI BackgroundTasks | 异步文档处理 |
| **可观测性** | Langfuse | 全链路追踪 |
| **评估** | RAGAS | 离线质量评估 |
| **部署** | Docker + Docker Compose | 容器化 |

**Python 依赖清单：**
```
fastapi
uvicorn
llama-index-core
llama-index-vector-stores-postgres
llama-index-retrievers-bm25
llama-index-embeddings-openai
llama-index-llms-litellm
docling
litellm
langfuse
ragas
sqlalchemy[asyncio]
asyncpg
python-jose[cryptography]
passlib[bcrypt]
python-multipart
celery          # 或用 FastAPI BackgroundTasks
redis           # 如果用 Celery
```

---

## 六、项目结构

```
rag-service/
├── docker-compose.yml              # PostgreSQL + Redis + LiteLLM + Langfuse + App
├── Dockerfile
├── requirements.txt
├── .env                            # API keys, DB 连接
│
├── app/
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置管理
│   ├── database.py                 # 数据库连接 + Session
│   │
│   ├── api/                        # API 路由
│   │   ├── auth.py                 # 认证端点
│   │   ├── documents.py            # 文档管理端点
│   │   ├── collections.py          # 集合管理端点
│   │   ├── chat.py                 # RAG 对话端点
│   │   ├── search.py               # 检索端点
│   │   └── conversations.py        # 对话管理端点
│   │
│   ├── models/                     # SQLAlchemy 模型
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── collection.py
│   │   ├── conversation.py
│   │   └── message.py
│   │
│   ├── schemas/                    # Pydantic 请求/响应模型
│   │   ├── auth.py
│   │   ├── document.py
│   │   ├── chat.py
│   │   └── search.py
│   │
│   ├── services/                   # 业务逻辑
│   │   ├── auth_service.py         # 认证逻辑
│   │   ├── document_service.py     # 文档处理 (解析+分块+索引)
│   │   ├── rag_service.py          # RAG 核心 (检索+生成)
│   │   ├── search_service.py       # 检索逻辑
│   │   └── conversation_service.py # 对话管理
│   │
│   ├── core/                       # 核心模块
│   │   ├── rag_pipeline.py         # LlamaIndex RAG 管道配置
│   │   ├── embeddings.py           # Embedding 配置
│   │   ├── retriever.py            # 混合检索器 (Dense + BM25 + RRF)
│   │   ├── reranker.py             # Reranker 配置
│   │   └── llm.py                  # LLM 配置 (通过 LiteLLM)
│   │
│   └── utils/
│       ├── security.py             # JWT 工具
│       └── langfuse_callback.py    # Langfuse 集成
│
├── scripts/
│   ├── init_db.py                  # 初始化数据库
│   └── evaluate.py                 # RAGAS 评估脚本
│
└── tests/
    ├── test_documents.py
    ├── test_search.py
    ├── test_chat.py
    └── test_auth.py
```

---

## 七、Docker Compose 部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  # 主应用
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
      - litellm
    volumes:
      - ./uploads:/app/uploads

  # 数据库 (你们已有，可复用)
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: rag_service
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  # 任务队列
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # LLM 代理 (替换 OneAPI)
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml"]

  # 可观测性
  langfuse:
    image: langfuse/langfuse:2
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres:5432/langfuse
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: ${LANGFUSE_SECRET}

volumes:
  pgdata:
```

---

## 八、分阶段实施计划

### Phase 1：基础骨架（第 1-2 周）

```
[ ] 搭建 FastAPI 项目结构
[ ] 配置 PostgreSQL + pgvector 表结构
[ ] 实现文档上传 + Docling 解析 + LlamaIndex 分块 + Embedding + 存储
[ ] 实现基础向量检索（纯 Dense，先不做混合）
[ ] 实现基础 RAG 对话（检索 + LLM 生成）
[ ] Docker Compose 本地跑通

交付物：能上传文档、能问答的最简版本
```

### Phase 2：检索增强（第 3-4 周）

```
[ ] 加入 BM25Retriever（混合检索）
[ ] 加入 RRF 融合
[ ] 加入 Cohere Reranker 精排
[ ] 实现 SSE 流式响应
[ ] 实现引用溯源（回答标注来源文档+段落）
[ ] 用 RAGAS 对比 Phase 1 vs Phase 2 效果

交付物：检索质量达到生产级标准
```

### Phase 3：服务完善（第 5-6 周）

```
[ ] 实现用户认证（JWT + RBAC）
[ ] 实现 Collection 集合管理 + 权限隔离
[ ] 实现对话管理（多轮会话、历史记录）
[ ] 部署 LiteLLM 替换 OneAPI
[ ] 部署 Langfuse，接入全链路 Trace
[ ] 异步文档处理（Celery/BackgroundTasks）
[ ] 文档状态管理（上传中/处理中/完成/失败）

交付物：功能完整的 RAG 服务
```

### Phase 4：迁移切换（第 7-8 周）

```
[ ] 将现有 R2R 中的文档数据迁移到新系统
[ ] 前端/客户端切换 API 端点
[ ] 灰度发布：新旧系统并行运行
[ ] 监控对比：新系统 vs R2R 的效果/延迟/稳定性
[ ] 完全切换，下线 R2R + Open Assistant API

交付物：完成迁移，旧系统退役
```

### Phase 5：持续优化（后续）

```
[ ] Query 改写 (HyDE / Sub-question)
[ ] 自适应检索（判断是否需要检索）
[ ] 增量索引优化
[ ] GraphRAG（如果有多跳推理需求）
[ ] RAGAS 自动化评估 CI 管线
[ ] Embedding 缓存
```

---

## 九、R2R 功能覆盖检查表

| R2R 功能 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---------|:-------:|:-------:|:-------:|:-------:|
| 文档摄取（多格式） | ✅ | | | |
| 文本分块 | ✅ | | | |
| 向量存储检索 | ✅ | | | |
| RAG 问答 | ✅ | | | |
| BM25 关键词检索 | | ✅ | | |
| 混合检索 (RRF) | | ✅ | | |
| 重排序 | | ✅ | | |
| 流式响应 | | ✅ | | |
| 引用溯源 | | ✅ | | |
| 用户认证 | | | ✅ | |
| 集合管理+权限 | | | ✅ | |
| 对话管理 | | | ✅ | |
| LLM 多模型 | | | ✅ | |
| 可观测性/Dashboard | | | ✅ | |
| 数据迁移 | | | | ✅ |
| GraphRAG | | | | 后续 |
| Agentic RAG | | | | 后续 |
| Deep Research | | | | 后续 |

---

## 十、风险和注意事项

| 风险 | 影响 | 应对 |
|------|------|------|
| OpenAI Assistants API 8 月关闭 | 🔴 高 | Phase 1-3 必须在 7 月前完成 |
| 新系统检索质量不如 R2R | 🟡 中 | Phase 2 用 RAGAS 量化对比，持续调优 |
| LiteLLM 与 OneAPI 配置差异 | 🟢 低 | 两者都是 OpenAI 兼容 proxy，迁移简单 |
| 文档迁移数据丢失 | 🟡 中 | 写迁移脚本，先在测试环境验证 |
| 团队对 LlamaIndex 不熟悉 | 🟡 中 | Phase 1 安排 1-2 天框架学习 |
