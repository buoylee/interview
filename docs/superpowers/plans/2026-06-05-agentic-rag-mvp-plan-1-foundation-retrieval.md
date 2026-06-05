# Agentic RAG MVP — Plan 1:地基 + RAG 检索通路 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起项目骨架,实现「文档入库 → 混合检索(向量+全文+RRF+rerank)→ `retrieve_kb` 工具」这条可独立运行、可测试的 RAG 数据通路。

**Architecture:** 一个 Python 包 `mvp_agentic_rag`(src 布局)。Postgres(pgvector)单库存 chunk(向量 + 全文 tsvector)。检索层手写 dense(pgvector ANN)+ sparse(Postgres 全文)两路,用 RRF 融合,再过可插拔 reranker。所有 IO 组件(embeddings、db)依赖注入,测试用确定性假 embedding,跑得 hermetic、不联网。

**Tech Stack:** Python 3.12、uv(包管理)、psycopg3 + psycopg_pool + pgvector、langchain-openai(embeddings)、langchain-text-splitters、langchain-core(tool、FakeEmbedding)、pydantic-settings、pytest + pytest-asyncio + testcontainers[postgres]、Docker Compose。

---

## 上位文档

- 设计 spec:`docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`
- 本计划只覆盖 spec 第 5.2(检索层)、5.7(配置)、以及 5.1 里的 `retrieve_kb` 工具 + 入库通路。Agent 图 / API / 可观测 / eval 在 Plan 2-4。

## 前置条件

- 本机有 Docker(跑 Postgres + testcontainers)。
- 本机有 `uv`(`curl -LsSf https://astral.sh/uv/install.sh | sh`)。
- 一个 OpenAI 兼容 embedding 端点 + key(**仅生产入库时需要**;测试用假 embedding,不需要联网)。

## 文件结构(本计划产出)

```
ai/langchain/mvp-agentic-rag/
├─ pyproject.toml                       项目元数据 + 依赖 + pytest 配置
├─ .gitignore
├─ .env.example                         配置样例
├─ Makefile                             db-init / ingest / test / up 等
├─ docker-compose.yml                   postgres(pgvector)
├─ README.md                            quickstart
├─ sample_docs/                         入库演示语料(几篇 .md)
├─ src/mvp_agentic_rag/
│  ├─ __init__.py
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ config.py                      pydantic-settings 配置
│  │  ├─ llm.py                         embeddings 工厂(OpenAI 兼容)
│  │  └─ db.py                          连接池 + schema 初始化 + 查询助手
│  ├─ ingest/
│  │  ├─ __init__.py
│  │  ├─ loader.py                      读 .md/.txt 目录
│  │  ├─ splitter.py                    RecursiveCharacterTextSplitter 封装
│  │  ├─ pipeline.py                    load→split→embed→upsert(幂等)
│  │  └─ cli.py                         python -m mvp_agentic_rag.ingest.cli
│  ├─ retrieval/
│  │  ├─ __init__.py
│  │  ├─ types.py                       RetrievedChunk 数据类
│  │  ├─ dense.py                       pgvector ANN
│  │  ├─ sparse.py                      Postgres 全文
│  │  ├─ fusion.py                      RRF
│  │  ├─ rerank.py                      Reranker 接口 + Identity 默认
│  │  └─ hybrid.py                      组合 dense+sparse+RRF+rerank
│  └─ agent/
│     ├─ __init__.py
│     └─ tools.py                       make_retrieve_kb_tool(retriever)
└─ tests/
   ├─ conftest.py                       testcontainers postgres fixture + 假 embedding
   ├─ test_config.py
   ├─ test_splitter.py
   ├─ test_fusion.py
   ├─ test_rerank.py
   ├─ test_db.py
   ├─ test_ingest.py
   ├─ test_dense.py
   ├─ test_sparse.py
   ├─ test_hybrid.py
   └─ test_tools.py
```

> 约定:下文所有命令都在项目根目录 `ai/langchain/mvp-agentic-rag/` 执行(除非另注)。所有 `uv run` 会自动用项目虚拟环境。

---

### Task 1: 项目骨架与基础设施

**Files:**
- Create: `ai/langchain/mvp-agentic-rag/pyproject.toml`
- Create: `ai/langchain/mvp-agentic-rag/.gitignore`
- Create: `ai/langchain/mvp-agentic-rag/.env.example`
- Create: `ai/langchain/mvp-agentic-rag/docker-compose.yml`
- Create: `ai/langchain/mvp-agentic-rag/Makefile`
- Create: `ai/langchain/mvp-agentic-rag/README.md`
- Create: `ai/langchain/mvp-agentic-rag/src/mvp_agentic_rag/__init__.py`

- [ ] **Step 1: 创建 `pyproject.toml`**

```toml
[project]
name = "mvp-agentic-rag"
version = "0.1.0"
description = "企业知识库 Agentic RAG 助手(LangGraph 生产级 MVP)"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "psycopg[binary,pool]>=3.2",
    "pgvector>=0.3.6",
    "langchain-core>=0.3",
    "langchain-openai>=0.2",
    "langchain-text-splitters>=0.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "testcontainers[postgres]>=4.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mvp_agentic_rag"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 3: 创建 `.env.example`**

```bash
# ---- Embedding(OpenAI 兼容)----
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-replace-me
EMBEDDING_MODEL=text-embedding-3-small
EMBED_DIM=1536

# ---- Postgres ----
DATABASE_URL=postgresql://rag:rag@localhost:5433/rag

# ---- 检索旋钮 ----
TOP_K_DENSE=20
TOP_K_SPARSE=20
RRF_K=60
RERANK_TOP_N=5
CHUNK_SIZE=800
CHUNK_OVERLAP=120
FTS_CONFIG=simple
```

- [ ] **Step 4: 创建 `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: rag
      POSTGRES_DB: rag
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag -d rag"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  pgdata:
```

- [ ] **Step 5: 创建 `Makefile`**

```makefile
.PHONY: install up down db-init ingest test

install:
	uv sync --extra dev

up:
	docker compose up -d postgres

down:
	docker compose down

db-init:
	uv run python -m mvp_agentic_rag.core.db

ingest:
	uv run python -m mvp_agentic_rag.ingest.cli sample_docs

test:
	uv run pytest -v
```

- [ ] **Step 6: 创建 `README.md`**

```markdown
# 企业知识库 Agentic RAG 助手(MVP)

LangGraph 生产级 Agentic RAG 参考项目。详见
`../../../docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`。

## Plan 1 已实现:RAG 检索通路

\`\`\`bash
make install          # uv 装依赖
make up               # 起 postgres(pgvector)
cp .env.example .env  # 填入你的 embedding 端点 + key
make db-init          # 建表
make ingest           # 把 sample_docs 入库
make test             # 跑测试(hermetic,不联网)
\`\`\`
```

- [ ] **Step 7: 创建空包文件 `src/mvp_agentic_rag/__init__.py`**

```python
"""企业知识库 Agentic RAG 助手。"""
```

- [ ] **Step 8: 安装依赖并验证骨架**

Run: `cd ai/langchain/mvp-agentic-rag && uv sync --extra dev`
Expected: 成功创建 `.venv` 并装好依赖,无报错。

- [ ] **Step 9: 验证 Postgres 能起来**

Run: `docker compose up -d postgres && docker compose ps`
Expected: postgres 服务状态 `running`/`healthy`。然后 `docker compose down` 关掉(测试用 testcontainers 自带容器)。

- [ ] **Step 10: Commit**

```bash
git add ai/langchain/mvp-agentic-rag/
git commit -m "mvp-agentic-rag: Plan1 Task1 项目骨架与基础设施"
```

---

### Task 2: 配置(pydantic-settings)

**Files:**
- Create: `src/mvp_agentic_rag/core/__init__.py`
- Create: `src/mvp_agentic_rag/core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试 `tests/test_config.py`**

```python
from mvp_agentic_rag.core.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://x/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("EMBEDDING_MODEL", "m")
    monkeypatch.setenv("EMBED_DIM", "8")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    s = Settings()

    assert s.embedding_base_url == "http://x/v1"
    assert s.embed_dim == 8
    assert s.top_k_dense == 20  # 默认值
    assert s.rrf_k == 60


def test_settings_overrides_knobs(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TOP_K_DENSE", "3")

    s = Settings()

    assert s.top_k_dense == 3
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL —`ModuleNotFoundError: No module named 'mvp_agentic_rag.core.config'`。

- [ ] **Step 3: 创建 `src/mvp_agentic_rag/core/__init__.py`(空文件)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Embedding(OpenAI 兼容)
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embed_dim: int = 1536

    # Postgres
    database_url: str = "postgresql://rag:rag@localhost:5433/rag"

    # 检索旋钮
    top_k_dense: int = 20
    top_k_sparse: int = 20
    rrf_k: int = 60
    rerank_top_n: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 120
    fts_config: str = "simple"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/core/ tests/test_config.py
git commit -m "mvp-agentic-rag: Plan1 Task2 配置 Settings"
```

---

### Task 3: Embedding 工厂

**Files:**
- Create: `src/mvp_agentic_rag/core/llm.py`
- Test: `tests/test_config.py`(追加用例,复用文件)

> embeddings 用 OpenAI 兼容客户端;不联网时无法真正调用,所以测试只验证「按 config 正确构造」。生产由该工厂返回真实客户端;检索/入库模块通过依赖注入接收 embeddings,测试注入假 embedding(见 conftest)。

- [ ] **Step 1: 写失败测试(追加到 `tests/test_config.py` 末尾)**

```python
def test_get_embeddings_uses_config(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://x/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "my-embed")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings
    from mvp_agentic_rag.core.llm import get_embeddings

    emb = get_embeddings(Settings())

    assert emb.model == "my-embed"
    assert str(emb.openai_api_base) == "http://x/v1"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_config.py::test_get_embeddings_uses_config -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.core.llm'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/core/llm.py`**

```python
from langchain_openai import OpenAIEmbeddings

from mvp_agentic_rag.core.config import Settings, get_settings


def get_embeddings(settings: Settings | None = None) -> OpenAIEmbeddings:
    s = settings or get_settings()
    return OpenAIEmbeddings(
        model=s.embedding_model,
        base_url=s.embedding_base_url,
        api_key=s.embedding_api_key,
        dimensions=s.embed_dim,
    )
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS(3 passed)。

> 注:`OpenAIEmbeddings` 把 `base_url` 存为 `openai_api_base`。若该版本属性名不同,按红灯提示调整断言/字段(执行期 TDD 自纠)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/core/llm.py tests/test_config.py
git commit -m "mvp-agentic-rag: Plan1 Task3 embedding 工厂"
```

---

### Task 4: 测试基建(conftest:假 embedding + Postgres 容器)

**Files:**
- Create: `tests/conftest.py`

> 这是后续所有集成测试的地基:一个会话级 Postgres(pgvector)容器 + 一个确定性假 embedding。假 embedding 让「同一文本 → 同一向量」,于是「用某 chunk 原文查询 → 该 chunk 距离 0 → 排第一」可被确定性断言,无需联网、无需语义模型。

- [ ] **Step 1: 写 `tests/conftest.py`**

```python
import psycopg
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from testcontainers.postgres import PostgresContainer

EMBED_DIM = 64  # 测试用小维度,加速


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(
        "pgvector/pgvector:pg16",
        username="rag",
        password="rag",
        dbname="rag",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def conninfo(pg_container):
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql://rag:rag@{host}:{port}/rag"


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=EMBED_DIM)


@pytest.fixture
def clean_db(conninfo):
    """每个测试前重建 schema,保证隔离。"""
    from mvp_agentic_rag.core.db import Database

    db = Database(conninfo, embed_dim=EMBED_DIM)
    with db.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS kb_chunks")
        conn.commit()
    db.init_schema()
    yield db
    db.close()
```

- [ ] **Step 2: 验证 conftest 至少能被 pytest 收集(此刻无测试用例)**

Run: `uv run pytest tests/ -q`
Expected: 已通过的 config 测试仍 PASS;conftest 暂不被直接执行(它定义 fixture)。`Database` 尚未实现,但只要没有测试用到 `clean_db`,收集不会失败。

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "mvp-agentic-rag: Plan1 Task4 测试基建(假 embedding + pg 容器)"
```

---

### Task 5: 数据库层(连接池 + schema + 查询助手)

**Files:**
- Create: `src/mvp_agentic_rag/core/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 写失败测试 `tests/test_db.py`**

```python
def test_init_schema_creates_table(clean_db):
    with clean_db.connect() as conn:
        row = conn.execute(
            "SELECT to_regclass('public.kb_chunks')"
        ).fetchone()
    assert row[0] == "kb_chunks"


def test_vector_extension_enabled(clean_db):
    with clean_db.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
    assert row is not None
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.core.db'`(首次会拉取 pgvector 镜像,稍慢)。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/core/db.py`**

```python
import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from mvp_agentic_rag.core.config import get_settings


class Database:
    def __init__(self, conninfo: str, embed_dim: int):
        self.conninfo = conninfo
        self.embed_dim = embed_dim
        self.pool = ConnectionPool(
            conninfo,
            min_size=1,
            max_size=5,
            configure=self._configure,
            open=True,
        )

    @staticmethod
    def _configure(conn: psycopg.Connection) -> None:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        register_vector(conn)

    def connect(self):
        return self.pool.connection()

    def init_schema(self) -> None:
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id           BIGSERIAL PRIMARY KEY,
            doc_id       TEXT NOT NULL,
            chunk_idx    INT  NOT NULL,
            content      TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            metadata     JSONB NOT NULL DEFAULT '{{}}',
            embedding    vector({self.embed_dim}) NOT NULL,
            tsv          tsvector GENERATED ALWAYS AS
                         (to_tsvector('simple', content)) STORED
        );
        CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx
            ON kb_chunks USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS kb_chunks_tsv_idx
            ON kb_chunks USING GIN (tsv);
        """
        with self.connect() as conn:
            conn.execute(ddl)
            conn.commit()

    def close(self) -> None:
        self.pool.close()


def to_vector_literal(vec) -> str:
    """把向量序列化成 pgvector 文本字面量 '[1.0,2.0,...]',配 %s::vector 使用。
    用字面量 + 显式 cast,避开不同版本 pgvector 适配器对 list 支持的差异。"""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def get_database() -> Database:
    s = get_settings()
    return Database(s.database_url, s.embed_dim)


if __name__ == "__main__":
    db = get_database()
    db.init_schema()
    print("schema initialized")
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/core/db.py tests/test_db.py
git commit -m "mvp-agentic-rag: Plan1 Task5 数据库层(池+schema)"
```

---

### Task 6: 文本分块

**Files:**
- Create: `src/mvp_agentic_rag/ingest/__init__.py`
- Create: `src/mvp_agentic_rag/ingest/splitter.py`
- Test: `tests/test_splitter.py`

- [ ] **Step 1: 写失败测试 `tests/test_splitter.py`**

```python
from mvp_agentic_rag.ingest.splitter import split_text


def test_split_produces_overlapping_chunks():
    text = "abcdefghij" * 30  # 300 字符
    chunks = split_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) >= 3
    assert all(len(c) <= 100 for c in chunks)


def test_split_short_text_single_chunk():
    chunks = split_text("hello", chunk_size=100, chunk_overlap=20)
    assert chunks == ["hello"]
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_splitter.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.ingest.splitter'`。

- [ ] **Step 3: 创建 `src/mvp_agentic_rag/ingest/__init__.py`(空文件)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/ingest/splitter.py`**

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_splitter.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/ingest/__init__.py src/mvp_agentic_rag/ingest/splitter.py tests/test_splitter.py
git commit -m "mvp-agentic-rag: Plan1 Task6 文本分块"
```

---

### Task 7: 文档加载器

**Files:**
- Create: `src/mvp_agentic_rag/ingest/loader.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: 写失败测试 `tests/test_ingest.py`**

```python
from mvp_agentic_rag.ingest.loader import load_documents


def test_load_documents_reads_md_and_txt(tmp_path):
    (tmp_path / "a.md").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bravo content", encoding="utf-8")
    (tmp_path / "ignore.png").write_bytes(b"\x89PNG")

    docs = load_documents(str(tmp_path))

    by_id = {d["doc_id"]: d["text"] for d in docs}
    assert by_id == {"a.md": "alpha content", "b.txt": "bravo content"}
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.ingest.loader'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/ingest/loader.py`**

```python
from pathlib import Path

SUPPORTED = {".md", ".txt"}


def load_documents(directory: str) -> list[dict]:
    """读目录下 .md/.txt,返回 [{doc_id, text}]。doc_id = 相对文件名。"""
    base = Path(directory)
    docs: list[dict] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            docs.append(
                {
                    "doc_id": str(path.relative_to(base)),
                    "text": path.read_text(encoding="utf-8"),
                }
            )
    return docs
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS(1 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/ingest/loader.py tests/test_ingest.py
git commit -m "mvp-agentic-rag: Plan1 Task7 文档加载器"
```

---

### Task 8: 入库流水线(embed + upsert + 幂等)

**Files:**
- Create: `src/mvp_agentic_rag/ingest/pipeline.py`
- Test: `tests/test_ingest.py`(追加用例)

- [ ] **Step 1: 写失败测试(追加到 `tests/test_ingest.py`)**

```python
def test_ingest_inserts_chunks(clean_db, fake_embeddings, tmp_path):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    (tmp_path / "doc.md").write_text("hello world. " * 50, encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=100, chunk_overlap=20
    )

    n = pipe.ingest_directory(str(tmp_path))

    assert n > 0
    with clean_db.connect() as conn:
        count = conn.execute("SELECT count(*) FROM kb_chunks").fetchone()[0]
    assert count == n


def test_ingest_is_idempotent(clean_db, fake_embeddings, tmp_path):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    (tmp_path / "doc.md").write_text("hello world. " * 50, encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=100, chunk_overlap=20
    )

    first = pipe.ingest_directory(str(tmp_path))
    pipe.ingest_directory(str(tmp_path))  # 再来一次

    with clean_db.connect() as conn:
        count = conn.execute("SELECT count(*) FROM kb_chunks").fetchone()[0]
    assert count == first  # 没有重复插入
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.ingest.pipeline'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/ingest/pipeline.py`**

```python
import hashlib

from psycopg.types.json import Jsonb

from mvp_agentic_rag.core.db import Database, to_vector_literal
from mvp_agentic_rag.ingest.loader import load_documents
from mvp_agentic_rag.ingest.splitter import split_text


class IngestionPipeline:
    def __init__(self, db: Database, embeddings, chunk_size: int, chunk_overlap: int):
        self.db = db
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_directory(self, directory: str) -> int:
        docs = load_documents(directory)
        rows: list[tuple] = []
        for doc in docs:
            chunks = split_text(doc["text"], self.chunk_size, self.chunk_overlap)
            if not chunks:
                continue
            vectors = self.embeddings.embed_documents(chunks)
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                content_hash = hashlib.sha256(
                    f"{doc['doc_id']}::{idx}::{chunk}".encode()
                ).hexdigest()
                rows.append(
                    (
                        doc["doc_id"],
                        idx,
                        chunk,
                        content_hash,
                        Jsonb({"doc_id": doc["doc_id"], "chunk_idx": idx}),
                        to_vector_literal(vec),
                    )
                )

        inserted = 0
        with self.db.connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO kb_chunks
                            (doc_id, chunk_idx, content, content_hash, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s::vector)
                        ON CONFLICT (content_hash) DO NOTHING
                        """,
                        row,
                    )
                    inserted += cur.rowcount
            conn.commit()
        return inserted
```

> 要点:向量用 `to_vector_literal(vec)` + `%s::vector` 写入(避开适配器差异);JSONB 用 psycopg3 的 `Jsonb(...)` 适配器(text 不会隐式转 jsonb,必须用适配器或 `::jsonb`)。

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/ingest/pipeline.py tests/test_ingest.py
git commit -m "mvp-agentic-rag: Plan1 Task8 入库流水线(幂等 upsert)"
```

---

### Task 9: 检索结果类型 + 稠密检索(pgvector ANN)

**Files:**
- Create: `src/mvp_agentic_rag/retrieval/__init__.py`
- Create: `src/mvp_agentic_rag/retrieval/types.py`
- Create: `src/mvp_agentic_rag/retrieval/dense.py`
- Test: `tests/test_dense.py`

- [ ] **Step 1: 写失败测试 `tests/test_dense.py`**

```python
import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    import tempfile, pathlib

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("the quick brown fox", encoding="utf-8")
    (d / "y.md").write_text("a totally different sentence", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db, fake_embeddings


def test_dense_exact_text_ranks_first(seeded):
    from mvp_agentic_rag.retrieval.dense import DenseRetriever

    db, emb = seeded
    retriever = DenseRetriever(db=db, embeddings=emb)

    results = retriever.search("the quick brown fox", top_k=2)

    assert len(results) >= 1
    assert results[0].content == "the quick brown fox"
    assert results[0].score >= results[-1].score  # 分数降序
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_dense.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.retrieval.dense'`。

- [ ] **Step 3: 创建 `src/mvp_agentic_rag/retrieval/__init__.py`(空文件)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/retrieval/types.py`**

```python
from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    id: int
    doc_id: str
    chunk_idx: int
    content: str
    metadata: dict
    score: float = 0.0
```

- [ ] **Step 5: 写实现 `src/mvp_agentic_rag/retrieval/dense.py`**

```python
from mvp_agentic_rag.core.db import Database, to_vector_literal
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class DenseRetriever:
    def __init__(self, db: Database, embeddings):
        self.db = db
        self.embeddings = embeddings

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        vec = to_vector_literal(self.embeddings.embed_query(query))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, doc_id, chunk_idx, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM kb_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec, vec, top_k),
            ).fetchall()
        return [
            RetrievedChunk(
                id=r[0], doc_id=r[1], chunk_idx=r[2],
                content=r[3], metadata=r[4], score=float(r[5]),
            )
            for r in rows
        ]
```

- [ ] **Step 6: 运行测试,确认通过**

Run: `uv run pytest tests/test_dense.py -v`
Expected: PASS(1 passed)。

- [ ] **Step 7: Commit**

```bash
git add src/mvp_agentic_rag/retrieval/__init__.py src/mvp_agentic_rag/retrieval/types.py src/mvp_agentic_rag/retrieval/dense.py tests/test_dense.py
git commit -m "mvp-agentic-rag: Plan1 Task9 稠密检索(pgvector ANN)"
```

---

### Task 10: 稀疏检索(Postgres 全文)

**Files:**
- Create: `src/mvp_agentic_rag/retrieval/sparse.py`
- Test: `tests/test_sparse.py`

> 注:`to_tsvector('simple', ...)` 对英文/代码分词良好,对中文不分词。中文语料需 `pg_jieba`/`zhparser`(README 注明)。本计划用 `simple`,演示语料以英文为主。

- [ ] **Step 1: 写失败测试 `tests/test_sparse.py`**

```python
import pathlib
import tempfile

import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("kubernetes autoscaling guide", encoding="utf-8")
    (d / "y.md").write_text("postgres replication tuning", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db


def test_sparse_keyword_match(seeded):
    from mvp_agentic_rag.retrieval.sparse import SparseRetriever

    retriever = SparseRetriever(db=seeded, fts_config="simple")
    results = retriever.search("kubernetes", top_k=5)

    assert len(results) == 1
    assert "kubernetes" in results[0].content
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_sparse.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.retrieval.sparse'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/retrieval/sparse.py`**

```python
from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class SparseRetriever:
    def __init__(self, db: Database, fts_config: str = "simple"):
        self.db = db
        self.fts_config = fts_config

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, doc_id, chunk_idx, content, metadata,
                       ts_rank(tsv, plainto_tsquery(%s, %s)) AS score
                FROM kb_chunks
                WHERE tsv @@ plainto_tsquery(%s, %s)
                ORDER BY score DESC
                LIMIT %s
                """,
                (self.fts_config, query, self.fts_config, query, top_k),
            ).fetchall()
        return [
            RetrievedChunk(
                id=r[0], doc_id=r[1], chunk_idx=r[2],
                content=r[3], metadata=r[4], score=float(r[5]),
            )
            for r in rows
        ]
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_sparse.py -v`
Expected: PASS(1 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/retrieval/sparse.py tests/test_sparse.py
git commit -m "mvp-agentic-rag: Plan1 Task10 稀疏检索(全文)"
```

---

### Task 11: RRF 融合

**Files:**
- Create: `src/mvp_agentic_rag/retrieval/fusion.py`
- Test: `tests/test_fusion.py`

- [ ] **Step 1: 写失败测试 `tests/test_fusion.py`**

```python
from mvp_agentic_rag.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_rewards_items_high_in_multiple_lists():
    dense = ["a", "b", "c"]
    sparse = ["b", "a", "d"]

    fused = reciprocal_rank_fusion([dense, sparse], k=60)
    order = [item for item, _ in fused]

    # a 和 b 都在两路靠前,应排在只出现一次的 c/d 之前
    assert set(order[:2]) == {"a", "b"}
    assert order[0] == "a" or order[0] == "b"


def test_rrf_single_list_preserves_order():
    fused = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    assert [item for item, _ in fused] == ["x", "y", "z"]
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_fusion.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.retrieval.fusion'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/retrieval/fusion.py`**

```python
from collections.abc import Hashable


def reciprocal_rank_fusion(
    rankings: list[list[Hashable]], k: int = 60
) -> list[tuple[Hashable, float]]:
    """对多路排名做 RRF 融合,返回按融合分降序的 (item, score)。"""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_fusion.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/retrieval/fusion.py tests/test_fusion.py
git commit -m "mvp-agentic-rag: Plan1 Task11 RRF 融合"
```

---

### Task 12: Reranker 接口 + Identity 默认

**Files:**
- Create: `src/mvp_agentic_rag/retrieval/rerank.py`
- Test: `tests/test_rerank.py`

> 默认 `IdentityReranker` 不改变顺序(测试/轻量运行用)。生产可换 cross-encoder(bge-reranker)——作为可选实现 + `[rerank]` 依赖组,留待后续任务/扩展接入,不阻塞 Plan 1。

- [ ] **Step 1: 写失败测试 `tests/test_rerank.py`**

```python
from mvp_agentic_rag.retrieval.rerank import IdentityReranker
from mvp_agentic_rag.retrieval.types import RetrievedChunk


def _chunk(i, content):
    return RetrievedChunk(id=i, doc_id="d", chunk_idx=i, content=content, metadata={})


def test_identity_reranker_keeps_order_and_truncates():
    chunks = [_chunk(i, f"c{i}") for i in range(5)]
    reranker = IdentityReranker()

    out = reranker.rerank("q", chunks, top_n=3)

    assert [c.content for c in out] == ["c0", "c1", "c2"]
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_rerank.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.retrieval.rerank'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/retrieval/rerank.py`**

```python
from typing import Protocol

from mvp_agentic_rag.retrieval.types import RetrievedChunk


class Reranker(Protocol):
    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]: ...


class IdentityReranker:
    """不改变顺序,只截断到 top_n。默认实现。"""

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]:
        return chunks[:top_n]
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_rerank.py -v`
Expected: PASS(1 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/retrieval/rerank.py tests/test_rerank.py
git commit -m "mvp-agentic-rag: Plan1 Task12 reranker 接口+identity"
```

---

### Task 13: 混合检索器(组合 dense+sparse+RRF+rerank)

**Files:**
- Create: `src/mvp_agentic_rag/retrieval/hybrid.py`
- Test: `tests/test_hybrid.py`

- [ ] **Step 1: 写失败测试 `tests/test_hybrid.py`**

```python
import pathlib
import tempfile

import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("kubernetes autoscaling best practices", encoding="utf-8")
    (d / "y.md").write_text("postgres index tuning notes", encoding="utf-8")
    (d / "z.md").write_text("redis caching strategies", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db, fake_embeddings


def test_hybrid_returns_relevant_chunk(seeded):
    from mvp_agentic_rag.retrieval.dense import DenseRetriever
    from mvp_agentic_rag.retrieval.sparse import SparseRetriever
    from mvp_agentic_rag.retrieval.rerank import IdentityReranker
    from mvp_agentic_rag.retrieval.hybrid import HybridRetriever

    db, emb = seeded
    retriever = HybridRetriever(
        dense=DenseRetriever(db=db, embeddings=emb),
        sparse=SparseRetriever(db=db, fts_config="simple"),
        reranker=IdentityReranker(),
        db=db,
        top_k_dense=10,
        top_k_sparse=10,
        rrf_k=60,
        rerank_top_n=3,
    )

    results = retriever.retrieve("kubernetes autoscaling")

    assert len(results) >= 1
    assert any("kubernetes" in c.content for c in results)
    assert len(results) <= 3
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_hybrid.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.retrieval.hybrid'`。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/retrieval/hybrid.py`**

```python
from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.retrieval.dense import DenseRetriever
from mvp_agentic_rag.retrieval.fusion import reciprocal_rank_fusion
from mvp_agentic_rag.retrieval.rerank import Reranker
from mvp_agentic_rag.retrieval.sparse import SparseRetriever
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class HybridRetriever:
    def __init__(
        self,
        dense: DenseRetriever,
        sparse: SparseRetriever,
        reranker: Reranker,
        db: Database,
        top_k_dense: int,
        top_k_sparse: int,
        rrf_k: int,
        rerank_top_n: int,
    ):
        self.dense = dense
        self.sparse = sparse
        self.reranker = reranker
        self.db = db
        self.top_k_dense = top_k_dense
        self.top_k_sparse = top_k_sparse
        self.rrf_k = rrf_k
        self.rerank_top_n = rerank_top_n

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        dense_hits = self.dense.search(query, self.top_k_dense)
        sparse_hits = self.sparse.search(query, self.top_k_sparse)

        by_id: dict[int, RetrievedChunk] = {}
        for hit in [*dense_hits, *sparse_hits]:
            by_id.setdefault(hit.id, hit)

        fused = reciprocal_rank_fusion(
            [[h.id for h in dense_hits], [h.id for h in sparse_hits]],
            k=self.rrf_k,
        )
        # 取融合后候选(rerank 前多给一些),再交给 reranker 截断
        candidate_ids = [item_id for item_id, _ in fused]
        candidates = [by_id[i] for i in candidate_ids if i in by_id]

        return self.reranker.rerank(query, candidates, self.rerank_top_n)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_hybrid.py -v`
Expected: PASS(1 passed)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/retrieval/hybrid.py tests/test_hybrid.py
git commit -m "mvp-agentic-rag: Plan1 Task13 混合检索器"
```

---

### Task 14: `retrieve_kb` 工具

**Files:**
- Create: `src/mvp_agentic_rag/agent/__init__.py`
- Create: `src/mvp_agentic_rag/agent/tools.py`
- Test: `tests/test_tools.py`

> 工具返回「带来源标注的文本」给 LLM 用。检索器通过工厂注入,测试用 stub 检索器,不碰 DB。

- [ ] **Step 1: 写失败测试 `tests/test_tools.py`**

```python
from mvp_agentic_rag.agent.tools import make_retrieve_kb_tool
from mvp_agentic_rag.retrieval.types import RetrievedChunk


class StubRetriever:
    def retrieve(self, query: str):
        return [
            RetrievedChunk(
                id=1, doc_id="guide.md", chunk_idx=0,
                content="autoscaling uses HPA", metadata={},
            )
        ]


def test_retrieve_kb_tool_formats_with_citation():
    tool = make_retrieve_kb_tool(StubRetriever())

    out = tool.invoke({"query": "autoscaling"})

    assert "autoscaling uses HPA" in out
    assert "guide.md" in out  # 引用来源


def test_retrieve_kb_tool_has_name_and_description():
    tool = make_retrieve_kb_tool(StubRetriever())
    assert tool.name == "retrieve_kb"
    assert tool.description
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL —`No module named 'mvp_agentic_rag.agent.tools'`。

- [ ] **Step 3: 创建 `src/mvp_agentic_rag/agent/__init__.py`(空文件)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/agent/tools.py`**

```python
from langchain_core.tools import StructuredTool

from mvp_agentic_rag.retrieval.types import RetrievedChunk


def _format(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "未在知识库中找到相关内容。"
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[{i}] (来源: {c.doc_id}#chunk{c.chunk_idx})\n{c.content}")
    return "\n\n".join(lines)


def make_retrieve_kb_tool(retriever) -> StructuredTool:
    def retrieve_kb(query: str) -> str:
        """搜索企业知识库,返回最相关的若干片段(含来源标注)。
        当用户的问题需要依据内部文档/知识库回答时调用。"""
        return _format(retriever.retrieve(query))

    return StructuredTool.from_function(
        func=retrieve_kb,
        name="retrieve_kb",
        description=(
            "搜索企业知识库,返回最相关片段(含来源标注)。"
            "当问题需要依据内部文档回答时调用。"
        ),
    )
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/agent/__init__.py src/mvp_agentic_rag/agent/tools.py tests/test_tools.py
git commit -m "mvp-agentic-rag: Plan1 Task14 retrieve_kb 工具"
```

---

### Task 15: 入库 CLI + 端到端冒烟

**Files:**
- Create: `src/mvp_agentic_rag/ingest/cli.py`
- Create: `ai/langchain/mvp-agentic-rag/sample_docs/kubernetes.md`
- Create: `ai/langchain/mvp-agentic-rag/sample_docs/postgres.md`
- Create: `src/mvp_agentic_rag/retrieval/factory.py`(组装生产用检索器)

> 这一步把各组件用生产配置(真实 embedding + 本地 docker postgres)串起来,提供 `make ingest` 和一个手动查询冒烟。**需要 `.env` 里填真实 embedding 端点 + key**。

- [ ] **Step 1: 写检索器工厂 `src/mvp_agentic_rag/retrieval/factory.py`**

```python
from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.core.llm import get_embeddings
from mvp_agentic_rag.retrieval.dense import DenseRetriever
from mvp_agentic_rag.retrieval.hybrid import HybridRetriever
from mvp_agentic_rag.retrieval.rerank import IdentityReranker
from mvp_agentic_rag.retrieval.sparse import SparseRetriever


def build_hybrid_retriever(
    db: Database, settings: Settings | None = None
) -> HybridRetriever:
    s = settings or get_settings()
    embeddings = get_embeddings(s)
    return HybridRetriever(
        dense=DenseRetriever(db=db, embeddings=embeddings),
        sparse=SparseRetriever(db=db, fts_config=s.fts_config),
        reranker=IdentityReranker(),
        db=db,
        top_k_dense=s.top_k_dense,
        top_k_sparse=s.top_k_sparse,
        rrf_k=s.rrf_k,
        rerank_top_n=s.rerank_top_n,
    )
```

- [ ] **Step 2: 写入库 CLI `src/mvp_agentic_rag/ingest/cli.py`**

```python
import sys

from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.core.llm import get_embeddings
from mvp_agentic_rag.ingest.pipeline import IngestionPipeline


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python -m mvp_agentic_rag.ingest.cli <目录>")
        return 1
    directory = argv[0]
    s = get_settings()
    db = get_database()
    db.init_schema()
    pipe = IngestionPipeline(
        db=db,
        embeddings=get_embeddings(s),
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
    )
    n = pipe.ingest_directory(directory)
    print(f"已入库 {n} 个新片段(来自 {directory})")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 3: 写演示语料 `sample_docs/kubernetes.md`**

```markdown
# Kubernetes Autoscaling

Horizontal Pod Autoscaler (HPA) scales the number of pods based on CPU,
memory, or custom metrics. The Cluster Autoscaler adds or removes nodes
when pods cannot be scheduled. For latency-sensitive workloads, prefer
custom metrics over CPU to react earlier.
```

- [ ] **Step 4: 写演示语料 `sample_docs/postgres.md`**

```markdown
# Postgres Index Tuning

Use HNSW indexes for approximate nearest neighbor search on pgvector
columns. For full-text search, a GIN index on a tsvector column gives
fast keyword lookup. Combine both for hybrid retrieval.
```

- [ ] **Step 5: 端到端冒烟(需 docker postgres + `.env` 真实 embedding)**

```bash
cp .env.example .env     # 编辑 .env,填入真实 EMBEDDING_BASE_URL / EMBEDDING_API_KEY
make up                  # 起 postgres
make db-init             # 建表
make ingest              # 入库 sample_docs
```
Expected: 打印 `已入库 N 个新片段`(N>0)。再跑一次 `make ingest`,Expected: `已入库 0 个新片段`(幂等)。

- [ ] **Step 6: 手动查询冒烟(可选,验证检索)**

Run:
```bash
uv run python -c "
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.retrieval.factory import build_hybrid_retriever
db = get_database(); db.init_schema()
r = build_hybrid_retriever(db)
for c in r.retrieve('how does autoscaling work'):
    print(c.score, c.doc_id, c.content[:60])
db.close()
"
```
Expected: 打印出 kubernetes.md 的相关片段在前。

- [ ] **Step 7: 跑全量测试确认无回归**

Run: `uv run pytest -v`
Expected: 全部 PASS(config/db/splitter/ingest/dense/sparse/fusion/rerank/hybrid/tools)。

- [ ] **Step 8: Commit**

```bash
git add src/mvp_agentic_rag/ingest/cli.py src/mvp_agentic_rag/retrieval/factory.py ai/langchain/mvp-agentic-rag/sample_docs/
git commit -m "mvp-agentic-rag: Plan1 Task15 入库 CLI + 检索器工厂 + 演示语料"
```

---

## 完成定义(Plan 1)

- `make install && make up && make db-init && make ingest` 能把 `sample_docs` 入库,重复 ingest 幂等(0 新增)。
- `make test` 全绿,且**不联网**(testcontainers 起 pgvector,embedding 用确定性假实现)。
- 手动查询冒烟能对自然语言问题返回相关片段(dense + sparse 经 RRF + rerank)。
- 交付物:可独立运行的 RAG 检索通路 + `retrieve_kb` 工具,供 Plan 2 的 Agent 图直接消费。

## 自审记录(对照 spec)

- spec §5.2 检索层:dense(Task9)+ sparse(Task10)+ RRF(Task11)+ 可插拔 rerank(Task12)+ 组合(Task13)+ pgvector 表 schema(Task5)✅
- spec §5.7 配置:Settings + LLM/embedding 工厂(Task2/3)✅
- spec §5.1 `retrieve_kb` 工具(Task14)✅
- 幂等去重 content_hash(Task5 schema + Task8 ON CONFLICT)✅
- 类型一致性:`RetrievedChunk`(types.py)贯穿 dense/sparse/hybrid/rerank/tool ✅
- 暂不覆盖(留 Plan 2-4):Agent 图、API、可观测、eval、cross-encoder rerank 实现、中文 FTS(已注明)。
```
