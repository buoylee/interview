# SQLAlchemy Hands-on M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver chapters 00–06 as a runnable, evidence-backed SQLAlchemy 2.0 Core tutorial using the first production slice of the multi-tenant order/inventory case.

**Architecture:** `sqlalchemy-handson/lab` is one Python package with a stable Engine factory, Core `MetaData`, business-focused Core query modules, real PostgreSQL integration tests, and one deterministic scenario per chapter. Each scenario writes a structured Markdown evidence file; chapter prose links to the scenario, its tests, and official primary sources.

**Tech Stack:** Python 3.14 runtime with Python 3.11-compatible syntax, SQLAlchemy 2.0.51, psycopg 3, PostgreSQL 18.4, uv, pytest, pytest-timeout, Ruff, mypy, Docker Compose.

## Global Constraints

- Work only in `/Users/buoy/Development/gitrepo/interview/.worktrees/sqlalchemy-handson` on branch `codex/sqlalchemy-handson`.
- Write tutorial prose in Traditional Chinese; keep API names, error text, SQL, and necessary technical terms in English.
- Use SQLAlchemy 2.0 public APIs in application code; any private attribute used by a scenario must be labelled `Implementation note` and pinned to 2.0.51.
- Use PostgreSQL 18.4 for all database behavior; do not substitute SQLite for integration tests.
- Keep the executable path synchronous in M1. ORM, AsyncSession, Alembic, FastAPI, idempotency, outbox, and multi-tenant RLS belong to separate milestone plans.
- The application transaction owner is the application-service entry point. Lower-level Core functions may execute statements but never call `commit()`.
- Use exact SQLAlchemy `2.0.51`; let `uv.lock` pin transitive and development dependencies.
- Every chapter follows: production question → prediction → failing/naive behavior → mechanism → corrected behavior → evidence → decision → interview drill.
- Label explanations as `Public contract`, `Mental model`, or `Implementation note` where stability matters.
- Do not claim universal timing ratios. Prefer query count, event order, transaction state, constraint behavior, pool state, and plan shape.
- Run a red-green test cycle for each behavior and commit after every task.

## Scope Split

This plan implements M1 only:

- `00-overview`
- `01-engine-execution`
- `02-schema-types`
- `03-expression-compiler`
- `04-core-dml-results`
- `05-connection-transactions`
- `06-pooling-capacity`

M2, M3, and M4 require separate implementation plans. Their stable inputs from M1 are:

- `order_service.db.settings.DatabaseSettings`
- `order_service.db.engine.build_engine`
- `order_service.db.schema.metadata` and the eight named `Table` objects
- `order_service.core.catalog` record types and Core functions
- the evidence document format in `scenarios._evidence`
- the Docker Compose service name `postgres` and database URL environment variable `SQLALCHEMY_DATABASE_URL`

## Planned File Map

```text
sqlalchemy-handson/
├── README.md                              # learning map and M1 run path
├── 00-overview/README.md                  # positioning, architecture, decisions
├── 01-engine-execution/README.md          # Engine → Pool → Dialect → DBAPI
├── 02-schema-types/README.md               # MetaData, constraints, types
├── 03-expression-compiler/README.md        # expressions, binds, cache keys
├── 04-core-dml-results/README.md           # DML, RETURNING, upsert, Result
├── 05-connection-transactions/README.md    # autobegin and transaction state
├── 06-pooling-capacity/README.md           # QueuePool and capacity budgets
└── lab/
    ├── .gitignore
    ├── .python-version
    ├── Makefile
    ├── README.md
    ├── compose.yaml
    ├── pyproject.toml
    ├── uv.lock
    ├── evidence/
    │   ├── environment.md
    │   ├── ch01-engine-execution.md
    │   ├── ch02-schema-types.md
    │   ├── ch03-expression-compiler.md
    │   ├── ch04-core-dml-results.md
    │   ├── ch05-connection-transactions.md
    │   └── ch06-pooling-capacity.md
    ├── scenarios/
    │   ├── __init__.py
    │   ├── _evidence.py
    │   ├── environment.py
    │   ├── ch01_engine_execution.py
    │   ├── ch02_schema_types.py
    │   ├── ch03_expression_compiler.py
    │   ├── ch04_core_dml_results.py
    │   ├── ch05_connection_transactions.py
    │   └── ch06_pooling_capacity.py
    ├── src/order_service/
    │   ├── __init__.py
    │   ├── application/
    │   │   ├── __init__.py
    │   │   └── catalog_service.py
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── catalog.py
    │   └── db/
    │       ├── __init__.py
    │       ├── engine.py
    │       ├── schema.py
    │       ├── settings.py
    │       └── statements.py
    └── tests/
        ├── conftest.py
        ├── integration/
        │   ├── test_catalog.py
        │   ├── test_engine.py
        │   ├── test_engine_execution_scenario.py
        │   ├── test_pooling.py
        │   ├── test_schema.py
        │   ├── test_statement_cache.py
        │   └── test_transactions.py
        └── unit/
            ├── test_evidence.py
            ├── test_evidence_manifest.py
            ├── test_package_contract.py
            ├── test_pool_budget.py
            ├── test_schema_contract.py
            ├── test_settings.py
            └── test_statements.py
```

---

### Task 1: Create the M1 package, toolchain, and chapter 00

**Files:**

- Create: `sqlalchemy-handson/lab/.gitignore`
- Create: `sqlalchemy-handson/lab/.python-version`
- Create: `sqlalchemy-handson/lab/pyproject.toml`
- Create: `sqlalchemy-handson/lab/uv.lock` via `uv sync`
- Create: `sqlalchemy-handson/lab/Makefile`
- Create: `sqlalchemy-handson/lab/README.md`
- Create: `sqlalchemy-handson/lab/src/order_service/__init__.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_package_contract.py`
- Create: `sqlalchemy-handson/README.md`
- Create: `sqlalchemy-handson/00-overview/README.md`

**Interfaces:**

- Produces: importable package `order_service` with `__version__ == "0.1.0"`.
- Produces: `make sync`, `make unit`, `make lint`, `make typecheck`, and `make verify` entry points.
- Produces: M1 navigation contract used by all later chapter documents.

- [ ] **Step 1: Add the project metadata and a failing package-contract test**

Create `.python-version` containing exactly:

```text
3.14
```

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sqlalchemy-handson-lab"
version = "0.1.0"
description = "Evidence-backed PostgreSQL lab for the SQLAlchemy hands-on tutorial"
requires-python = ">=3.11,<3.15"
dependencies = [
    "sqlalchemy==2.0.51",
    "psycopg[binary]>=3.3,<3.4",
]

[dependency-groups]
dev = [
    "mypy>=1.15,<2",
    "pytest>=9,<10",
    "pytest-timeout>=2.3,<3",
    "ruff>=0.12,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/order_service"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]
markers = [
    "integration: requires the PostgreSQL 18 Compose service",
]
timeout = 10

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["order_service"]
```

Create `tests/unit/test_package_contract.py`:

```python
import sqlalchemy

import order_service


def test_package_and_sqlalchemy_versions_are_pinned() -> None:
    assert order_service.__version__ == "0.1.0"
    assert sqlalchemy.__version__ == "2.0.51"
```

- [ ] **Step 2: Sync dependencies and confirm the test fails for the missing package**

Run from `sqlalchemy-handson/lab`:

```bash
uv sync --no-install-project
uv run --no-sync pytest tests/unit/test_package_contract.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'order_service'`.

- [ ] **Step 3: Add the minimal package and developer commands**

Create `src/order_service/__init__.py`:

```python
"""Runnable case study for the SQLAlchemy hands-on tutorial."""

__version__ = "0.1.0"
```

Create `.gitignore`:

```gitignore
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
```

Create `Makefile`:

```make
.PHONY: sync unit integration lint typecheck verify db-up db-down

sync:
	uv sync

unit:
	uv run pytest tests/unit -q

integration:
	uv run pytest -m integration -q

lint:
	uv run ruff check src tests scenarios

typecheck:
	uv run mypy src tests scenarios

verify: lint typecheck unit integration

db-up:
	docker compose up -d --wait

db-down:
	docker compose down -v
```

- [ ] **Step 4: Write the M1 navigation and chapter 00 documents**

Write `sqlalchemy-handson/README.md` with these exact top-level sections and content contracts:

```markdown
# SQLAlchemy Hands-on：從正確使用到架構決策

## 這不是 API 翻譯
說明正確使用、機制解釋、架構決策三個目標，並連回 `../python-data/`。

## 執行基線
列出 Python 3.14、SQLAlchemy 2.0.51、PostgreSQL 18.4、psycopg 3、uv。

## 四卷地圖
列出 00–24；M1 的 00–06 使用可點擊連結，M2–M4 標示為後續里程碑範圍而非已完成內容。

## 每章怎麼讀
列出 production question、prediction、mechanism、evidence、decision、interview drill。

## 五分鐘啟動 M1 Lab
只放可執行命令：`cd lab`、`make sync`、`make db-up`、`make verify`。

## 與既有教程的邊界
說明 `python-data/` 是選型導讀，本目錄是 SQLAlchemy 深水教程。
```

Write `00-overview/README.md` with:

- the request → application service → Connection → Engine → Pool → Dialect → psycopg → PostgreSQL path;
- the Core/ORM and sync/async decision boundaries without teaching ORM or async APIs yet;
- the multi-tenant product/inventory/order case model;
- the `Public contract` / `Mental model` / `Implementation note` stability labels;
- a “讀完 M1 能做什麼” checklist limited to chapters 00–06;
- links to `../lab/README.md` and chapter 01.

Write `lab/README.md` with the same four commands as the root tutorial README, the local URL `postgresql+psycopg://sqlalchemy:sqlalchemy@localhost:55432/sqlalchemy_handson`, and a warning that the credentials are local-only Compose defaults.

- [ ] **Step 5: Run the package checks and confirm green**

Run:

```bash
uv run pytest tests/unit/test_package_contract.py -q
uv run ruff check src tests
uv run mypy src tests
```

Expected: `1 passed`; Ruff exits 0; mypy prints `Success: no issues found`.

- [ ] **Step 6: Commit the skeleton**

```bash
git add sqlalchemy-handson
git commit -m "feat(sqlalchemy): scaffold M1 tutorial lab"
```

---

### Task 2: Add PostgreSQL 18, settings, and the Engine factory

**Files:**

- Create: `sqlalchemy-handson/lab/compose.yaml`
- Create: `sqlalchemy-handson/lab/src/order_service/db/__init__.py`
- Create: `sqlalchemy-handson/lab/src/order_service/db/settings.py`
- Create: `sqlalchemy-handson/lab/src/order_service/db/engine.py`
- Create: `sqlalchemy-handson/lab/tests/conftest.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_settings.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_engine.py`

**Interfaces:**

- Produces: `DatabaseSettings.from_env() -> DatabaseSettings`.
- Produces: `DatabaseSettings.safe_url -> str`, always hiding the password.
- Produces: `build_engine(settings: DatabaseSettings, **overrides: Any) -> Engine`.
- Produces: session-scoped pytest fixture `engine() -> Iterator[Engine]`.

- [ ] **Step 1: Write failing configuration and Engine tests**

Create `tests/unit/test_settings.py`:

```python
from order_service.db.settings import DatabaseSettings


def test_settings_use_local_compose_url_and_hide_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URL", raising=False)

    settings = DatabaseSettings.from_env()

    assert settings.url.drivername == "postgresql+psycopg"
    assert settings.url.port == 55432
    assert settings.url.database == "sqlalchemy_handson"
    assert "sqlalchemy:***@" in settings.safe_url
    assert "sqlalchemy:sqlalchemy@" not in settings.safe_url
```

Add `import pytest` above the `DatabaseSettings` import.

Create `tests/integration/test_engine.py`:

```python
import pytest
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration


def test_engine_connects_to_the_expected_postgresql(engine: Engine) -> None:
    with engine.connect() as connection:
        database, version_num = connection.execute(
            text("SELECT current_database(), current_setting('server_version_num')")
        ).one()

    assert database == "sqlalchemy_handson"
    assert int(version_num) == 180004
```

- [ ] **Step 2: Run the unit test and confirm the missing-module failure**

Run:

```bash
uv run pytest tests/unit/test_settings.py -q
```

Expected: collection fails because `order_service.db.settings` does not exist.

- [ ] **Step 3: Implement settings and Engine construction**

Create `src/order_service/db/__init__.py`:

```python
"""Database configuration, schema, and runtime factories."""
```

Create `src/order_service/db/settings.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Self

from sqlalchemy import URL, make_url

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://sqlalchemy:sqlalchemy@localhost:55432/sqlalchemy_handson"
)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: URL

    @classmethod
    def from_env(cls) -> Self:
        raw_url = os.environ.get("SQLALCHEMY_DATABASE_URL", DEFAULT_DATABASE_URL)
        return cls(url=make_url(raw_url))

    @property
    def safe_url(self) -> str:
        return self.url.render_as_string(hide_password=True)
```

Create `src/order_service/db/engine.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine

from order_service.db.settings import DatabaseSettings


def build_engine(settings: DatabaseSettings, **overrides: Any) -> Engine:
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 1.0,
        "pool_recycle": 1_800,
    }
    options.update(overrides)
    return create_engine(settings.url, **options)
```

Create `tests/conftest.py`:

```python
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    value = build_engine(DatabaseSettings.from_env())
    try:
        yield value
    finally:
        value.dispose()
```

- [ ] **Step 4: Add the pinned PostgreSQL Compose service**

Create `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:18.4
    environment:
      POSTGRES_USER: sqlalchemy
      POSTGRES_PASSWORD: sqlalchemy
      POSTGRES_DB: sqlalchemy_handson
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sqlalchemy -d sqlalchemy_handson"]
      interval: 1s
      timeout: 3s
      retries: 30
```

- [ ] **Step 5: Start PostgreSQL and run both test layers**

Run:

```bash
docker compose up -d --wait
uv run pytest tests/unit/test_settings.py tests/integration/test_engine.py -q
```

Expected: Compose reports `postgres` healthy; pytest reports `2 passed`.

- [ ] **Step 6: Run static checks and commit**

```bash
uv run ruff check src tests
uv run mypy src tests
git add sqlalchemy-handson/lab
git commit -m "feat(sqlalchemy): add PostgreSQL Engine runtime"
```

Expected: Ruff exits 0; mypy reports no issues; commit contains no generated database files or secrets.

---

### Task 3: Establish the evidence contract and chapter 01 execution path

**Files:**

- Create: `sqlalchemy-handson/lab/scenarios/__init__.py`
- Create: `sqlalchemy-handson/lab/scenarios/_evidence.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch01_engine_execution.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_evidence.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_engine_execution_scenario.py`
- Create: `sqlalchemy-handson/lab/evidence/ch01-engine-execution.md`
- Create: `sqlalchemy-handson/01-engine-execution/README.md`

**Interfaces:**

- Produces: immutable `Evidence` document with exactly seven required sections:
  Hypothesis, Setup, Command, Observation, Explanation, Decision, Caveat.
- Enforces: every evidence document contains exactly one reproducible command.
- Produces: `write_evidence(path: Path, evidence: Evidence) -> None`.
- Produces: `ch01_engine_execution.run(engine: Engine) -> Evidence`.

- [ ] **Step 1: Write failing evidence-format and event-order tests**

Create `tests/unit/test_evidence.py`:

```python
from pathlib import Path

from scenarios._evidence import Evidence, write_evidence


def test_evidence_writer_emits_every_required_section(tmp_path: Path) -> None:
    target = tmp_path / "evidence.md"
    evidence = Evidence(
        title="Example",
        hypothesis=("one prediction",),
        setup=("one setup fact",),
        command="uv run python -m scenarios.example",
        observation=("one observation",),
        explanation=("one explanation",),
        decision=("one decision",),
        caveat=("one caveat",),
    )

    write_evidence(target, evidence)

    rendered = target.read_text(encoding="utf-8")
    for heading in (
        "## Hypothesis",
        "## Setup",
        "## Command",
        "## Observation",
        "## Explanation",
        "## Decision",
        "## Caveat",
    ):
        assert heading in rendered
```

Create `tests/integration/test_engine_execution_scenario.py`:

```python
import pytest
from sqlalchemy import Engine

from scenarios.ch01_engine_execution import run

pytestmark = pytest.mark.integration


def test_execute_path_observes_checkout_before_cursor_execution(engine: Engine) -> None:
    evidence = run(engine)
    observations = "\n".join(evidence.observation)

    assert "event_order=checkout->before_cursor_execute" in observations
    assert "checkout_during_connect=True" in observations
    assert "sql_not_executed_at_checkout=True" in observations
    assert "naive_distinct_pools=True" in observations
    assert "corrected_reused_pool=True" in observations
    assert "result=42" in observations
    assert "dialect=postgresql" in observations
    assert "driver=psycopg" in observations
```

- [ ] **Step 2: Run the tests and confirm both missing-module failures**

Run:

```bash
uv run pytest tests/unit/test_evidence.py tests/integration/test_engine_execution_scenario.py -q
```

Expected: collection fails because `scenarios._evidence` and `scenarios.ch01_engine_execution` do not exist.

- [ ] **Step 3: Implement the reusable evidence writer**

Create an empty `scenarios/__init__.py`, then create `scenarios/_evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Evidence:
    title: str
    hypothesis: tuple[str, ...]
    setup: tuple[str, ...]
    command: str
    observation: tuple[str, ...]
    explanation: tuple[str, ...]
    decision: tuple[str, ...]
    caveat: tuple[str, ...]

    def render(self) -> str:
        sections = [f"# {self.title}", ""]
        for heading, values in (
            ("Hypothesis", self.hypothesis),
            ("Setup", self.setup),
            ("Command", (self.command,)),
            ("Observation", self.observation),
            ("Explanation", self.explanation),
            ("Decision", self.decision),
            ("Caveat", self.caveat),
        ):
            sections.extend((f"## {heading}", ""))
            sections.extend(f"- {value}" for value in values)
            sections.append("")
        return "\n".join(sections)


def write_evidence(path: Path, evidence: Evidence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(evidence.render(), encoding="utf-8")
```

- [ ] **Step 4: Implement the Engine execution-path scenario**

Create `scenarios/ch01_engine_execution.py`:

Before installing event listeners, the scenario must execute two temporary Engine-per-operation
queries, assert their Pool objects differ, and dispose both Engines in `finally`. It must then execute
two work units through the passed process-scoped Engine and assert that both use the same Pool.

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    naive_engines = (create_engine(engine.url), create_engine(engine.url))
    try:
        for naive_engine in naive_engines:
            with naive_engine.connect() as connection:
                assert connection.scalar(text("SELECT 1")) == 1
        naive_distinct_pools = naive_engines[0].pool is not naive_engines[1].pool
    finally:
        for naive_engine in naive_engines:
            naive_engine.dispose()

    corrected_pool_ids: set[int] = set()
    for _ in range(2):
        corrected_pool_ids.add(id(engine.pool))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    corrected_reused_pool = len(corrected_pool_ids) == 1

    event_order: list[str] = []
    statements: list[str] = []

    def on_checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
        del dbapi_connection, connection_record, connection_proxy
        event_order.append("checkout")

    def before_cursor_execute(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        del connection, cursor, parameters, context, executemany
        event_order.append("before_cursor_execute")
        statements.append(statement)

    event.listen(engine.pool, "checkout", on_checkout)
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        with engine.connect() as connection:
            checkout_during_connect = event_order == ["checkout"]
            sql_not_executed_at_checkout = not statements
            result = connection.scalar(text("SELECT :value"), {"value": 42})
    finally:
        event.remove(engine.pool, "checkout", on_checkout)
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    return Evidence(
        title="Chapter 01 — Engine execution path",
        hypothesis=(
            "create_engine() configures an Engine without checking out a connection.",
            "Entering engine.connect() checks out a DBAPI connection before SQL execution.",
        ),
        setup=(
            f"dialect={engine.dialect.name}",
            f"driver={engine.dialect.driver}",
            f"pool={type(engine.pool).__name__}",
        ),
        command="uv run python -m scenarios.ch01_engine_execution",
        observation=(
            f"naive_distinct_pools={naive_distinct_pools}",
            f"corrected_reused_pool={corrected_reused_pool}",
            f"checkout_during_connect={checkout_during_connect}",
            f"sql_not_executed_at_checkout={sql_not_executed_at_checkout}",
            f"event_order={'->'.join(event_order)}",
            f"statement={statements[0]}",
            f"result={result}",
            f"dialect={engine.dialect.name}",
            f"driver={engine.dialect.driver}",
        ),
        explanation=(
            "Engine coordinates a Pool and Dialect; the Dialect adapts SQLAlchemy constructs to psycopg.",
            "Bound values travel through the DBAPI parameter channel rather than string concatenation.",
        ),
        decision=(
            "Create one process-scoped Engine per database role, not one Engine per request.",
        ),
        caveat=(
            "Event hooks observe public execution events; they do not expose every internal call frame.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch01-engine-execution.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests and capture real evidence**

Run:

```bash
uv run pytest tests/unit/test_evidence.py tests/integration/test_engine_execution_scenario.py -q
uv run python -m scenarios.ch01_engine_execution
```

Expected: focused tests pass; evidence contains all seven required sections, proves checkout already occurred inside `engine.connect()` before SQL execution, preserves `event_order=checkout->before_cursor_execute`, and records executable `naive_distinct_pools=True` / `corrected_reused_pool=True` lifecycle observations.

- [ ] **Step 6: Write chapter 01 from the verified scenario**

Write `01-engine-execution/README.md` with these headings:

```markdown
# 01 · Engine 解剖：一次 execute 的完整旅程
## 生產問題：Engine 應該活多久？
## 先預測，再執行
## Public contract：Engine、Connection、Pool、Dialect
## Mental model：SQL Expression 到 psycopg cursor
## Implementation note：2.0.51 的執行路徑地圖
## 參數綁定不是字串插值
## 事故模式：每請求建立 Engine
## 架構決策表
## 面試追問
```

The chapter must:

- link to `../lab/scenarios/ch01_engine_execution.py`, its integration test, and `../lab/evidence/ch01-engine-execution.md`;
- explain that `create_engine()` is lazy and that Engine is process-scoped;
- distinguish Engine, physical DBAPI connection, SQLAlchemy Connection, and checked-out pool resource;
- cite <https://docs.sqlalchemy.org/en/20/core/engines.html> and <https://docs.sqlalchemy.org/en/20/core/engines_connections.html>;
- include three interview drills: Engine lifetime, Dialect responsibility, and why bound parameters do not require manual quoting.

- [ ] **Step 7: Run static checks and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "docs(sqlalchemy): trace the Engine execution path"
```

Expected: Ruff and mypy exit 0; the commit includes actual captured evidence, not a hand-written sample.

---

### Task 4: Define the multi-tenant Core schema and chapter 02

**Files:**

- Create: `sqlalchemy-handson/lab/src/order_service/db/schema.py`
- Modify: `sqlalchemy-handson/lab/tests/conftest.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_schema_contract.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_schema.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch02_schema_types.py`
- Create: `sqlalchemy-handson/lab/evidence/ch02-schema-types.md`
- Create: `sqlalchemy-handson/02-schema-types/README.md`

**Interfaces:**

- Produces: `metadata: MetaData` with naming conventions.
- Produces: `Money`, a cache-safe `TypeDecorator[Decimal]` that rejects floats and stores scale 2.
- Produces exactly eight tables: `tenants`, `products`, `inventories`, `orders`, `order_lines`, `inventory_reservations`, `idempotency_records`, `outbox_events`.
- Produces: function-scoped `recreated_schema` fixture for database-behavior tests.
- Produces: `ch02_schema_types.run(engine: Engine) -> Evidence`.
- Enforces with PostgreSQL behavior tests: cross-tenant composite references fail for
  inventories, order_lines, and inventory_reservations; each assertion reads the expected
  constraint name from `IntegrityError.orig` / psycopg diagnostics and explicitly rolls back
  before reusing the Connection.

- [ ] **Step 1: Write failing schema contract tests**

Create `tests/unit/test_schema_contract.py`:

```python
from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from order_service.db.schema import Money, metadata


def test_schema_has_stable_tables_and_constraint_names() -> None:
    assert set(metadata.tables) == {
        "tenants",
        "products",
        "inventories",
        "orders",
        "order_lines",
        "inventory_reservations",
        "idempotency_records",
        "outbox_events",
    }
    product_names = {constraint.name for constraint in metadata.tables["products"].constraints}
    assert "pk_products" in product_names
    assert "uq_products_tenant_id_sku" in product_names


def test_money_quantizes_decimal_and_rejects_float() -> None:
    money = Money()
    dialect = postgresql.dialect()

    assert money.process_bind_param(Decimal("12.345"), dialect) == Decimal("12.34")
    with pytest.raises(TypeError, match="Decimal"):
        money.process_bind_param(12.34, dialect)  # type: ignore[arg-type]
    assert Money.cache_ok is True
```

Create `tests/integration/test_schema.py`:

```python
import pytest
from sqlalchemy import Engine, inspect

from order_service.db.schema import metadata
from scenarios.ch02_schema_types import run

pytestmark = pytest.mark.integration


def test_metadata_round_trips_through_postgresql(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == set(metadata.tables)
    product_types = {
        column["name"]: column["type"].__class__.__name__
        for column in inspector.get_columns("products")
    }
    assert product_types["attributes"] == "JSONB"


def test_schema_scenario_records_named_constraints(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "table_count=8" in observations
    assert "uq_products_tenant_id_sku" in observations
    assert "ix_outbox_events_claimable" in observations
    assert "naive_cross_tenant_rejected=True" in observations
    assert "corrected_tenant_scoped_reference=True" in observations
```

Also seed two tenants, products, and orders, then attempt invalid cross-tenant INSERTs into
inventories, order_lines, and inventory_reservations. Each attempt must assert its named composite
foreign key, call `rollback()`, and prove the Connection is reusable. The test must fail if any
relevant composite FK is removed or weakened.

- [ ] **Step 2: Run the tests and confirm the missing schema failure**

Run:

```bash
uv run pytest tests/unit/test_schema_contract.py tests/integration/test_schema.py -q
```

Expected: collection fails because `order_service.db.schema` does not exist.

- [ ] **Step 3: Implement the complete Core schema**

Create `src/order_service/db/schema.py`:

```python
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
CENT = Decimal("0.01")


class Money(TypeDecorator[Decimal]):
    impl = Numeric(12, 2)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Decimal | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise TypeError("Money values must be Decimal")
        return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


tenants = Table(
    "tenants",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

products = Table(
    "products",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("sku", String(64), nullable=False),
    Column("name", String(200), nullable=False),
    Column("unit_price", Money(), nullable=False),
    Column("attributes", JSONB, nullable=False, server_default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "sku"),
    CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
)

inventories = Table(
    "inventories",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("product_id", Uuid(as_uuid=True), primary_key=True),
    Column("available", Integer, nullable=False, server_default="0"),
    Column("reserved", Integer, nullable=False, server_default="0"),
    Column("version", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    CheckConstraint("available >= 0", name="available_nonnegative"),
    CheckConstraint("reserved >= 0", name="reserved_nonnegative"),
    CheckConstraint("reserved <= available", name="reserved_not_above_available"),
    CheckConstraint("version > 0", name="version_positive"),
)

orders = Table(
    "orders",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("status", String(24), nullable=False),
    Column("total", Money(), nullable=False),
    Column("idempotency_key", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "idempotency_key"),
    CheckConstraint(
        "status IN ('pending', 'confirmed', 'cancelled')",
        name="known_status",
    ),
    CheckConstraint("total >= 0", name="total_nonnegative"),
)

order_lines = Table(
    "order_lines",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("order_id", Uuid(as_uuid=True), primary_key=True),
    Column("line_number", Integer, primary_key=True),
    Column("product_id", Uuid(as_uuid=True), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Money(), nullable=False),
    ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"]),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    CheckConstraint("line_number > 0", name="line_number_positive"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
)

inventory_reservations = Table(
    "inventory_reservations",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("order_id", Uuid(as_uuid=True), nullable=False),
    Column("product_id", Uuid(as_uuid=True), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", String(24), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"]),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    UniqueConstraint("tenant_id", "order_id", "product_id"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    CheckConstraint("status IN ('held', 'released', 'consumed')", name="known_status"),
)

idempotency_records = Table(
    "idempotency_records",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("key", String(120), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("resource_type", String(64), nullable=False),
    Column("resource_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
)

outbox_events = Table(
    "outbox_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("aggregate_type", String(64), nullable=False),
    Column("aggregate_id", Uuid(as_uuid=True), nullable=False),
    Column("event_type", String(120), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", String(24), nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("locked_by", String(120)),
    Column("locked_at", DateTime(timezone=True)),
    Column("published_at", DateTime(timezone=True)),
    Column("last_error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("status IN ('pending', 'publishing', 'published')", name="known_status"),
    CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
)

Index(
    "ix_outbox_events_claimable",
    outbox_events.c.available_at,
    postgresql_where=outbox_events.c.status == "pending",
)
```

- [ ] **Step 4: Add the schema-reset fixture**

Append to `tests/conftest.py`:

```python
from order_service.db.schema import metadata


@pytest.fixture
def recreated_schema(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
    try:
        yield
    finally:
        with engine.begin() as connection:
            metadata.drop_all(connection)
```

Keep all imports at the top of the file after Ruff sorting; do not duplicate the existing `Iterator`, `pytest`, or `Engine` imports.

- [ ] **Step 5: Implement the schema-introspection scenario**

Create `scenarios/ch02_schema_types.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import Engine, inspect

from order_service.db.engine import build_engine
from order_service.db.schema import metadata
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
    # Seed fixed parent IDs, execute a cross-tenant inventory INSERT, catch IntegrityError,
    # assert its named composite FK, and rollback. Then execute the matching tenant-scoped
    # INSERT successfully. Record deterministic naive_... and corrected_... observations.
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    unique_names = sorted(
        constraint["name"]
        for constraint in inspector.get_unique_constraints("products")
        if constraint["name"] is not None
    )
    index_names = sorted(
        index["name"]
        for index in inspector.get_indexes("outbox_events")
        if index["name"] is not None
    )
    return Evidence(
        title="Chapter 02 — Schema and types",
        hypothesis=(
            "MetaData naming conventions produce deterministic PostgreSQL constraint names.",
            "The PostgreSQL dialect preserves JSONB and partial-index intent.",
        ),
        setup=("PostgreSQL 18.4", "SQLAlchemy MetaData.create_all() for the M1 lab"),
        command="uv run python -m scenarios.ch02_schema_types",
        observation=(
            f"table_count={len(table_names)}",
            f"tables={','.join(table_names)}",
            f"product_unique_constraints={','.join(unique_names)}",
            f"outbox_indexes={','.join(index_names)}",
        ),
        explanation=(
            "Named constraints become stable handles for migrations and IntegrityError translation.",
            "TypeDecorator.cache_ok=True lets the Money type participate in statement caching.",
        ),
        decision=(
            "Name every business-relevant constraint and use Decimal-backed numeric storage for money.",
        ),
        caveat=(
            "create_all() is a lab bootstrap mechanism; Alembic owns production schema evolution in M3.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("evidence/ch02-schema-types.md"))
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests and capture evidence**

```bash
uv run pytest tests/unit/test_schema_contract.py tests/integration/test_schema.py -q
uv run python -m scenarios.ch02_schema_types
```

Expected: `4 passed`; evidence reports eight tables, `uq_products_tenant_id_sku`, and `ix_outbox_events_claimable`.

- [ ] **Step 7: Write chapter 02**

Write `02-schema-types/README.md` with:

```markdown
# 02 · Schema 與型別系統：讓約束成為架構的一部分
## 生產問題：哪些 invariant 必須下沉到資料庫？
## 先預測，再執行
## Public contract：MetaData、Table、Column、constraint
## 命名慣例與可操作的 IntegrityError
## Python 型別、SQLAlchemy 型別、PostgreSQL 型別
## Money TypeDecorator 與 cache_ok
## UUID、timezone、JSONB、Enum 的取捨
## 多租戶 composite constraint
## create_all 只屬於 Lab
## 面試追問
```

The chapter must link the schema source, both tests, scenario, and evidence. Cite <https://docs.sqlalchemy.org/en/20/core/metadata.html>, <https://docs.sqlalchemy.org/en/20/core/type_basics.html>, <https://docs.sqlalchemy.org/en/20/core/custom_types.html>, and <https://docs.sqlalchemy.org/en/20/dialects/postgresql.html>. Explain why floats are rejected for money, why JSONB is a PostgreSQL decision, and why constraint names are part of the error-handling contract.

- [ ] **Step 8: Verify and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "docs(sqlalchemy): build the typed Core schema"
```

---

### Task 5: Demonstrate expressions, bound parameters, and compilation caching

**Files:**

- Create: `sqlalchemy-handson/lab/src/order_service/db/statements.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_statements.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_statement_cache.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch03_expression_compiler.py`
- Create: `sqlalchemy-handson/lab/evidence/ch03-expression-compiler.md`
- Create: `sqlalchemy-handson/03-expression-compiler/README.md`

**Interfaces:**

- Produces: `product_by_sku_statement() -> Select[Any]` with explicit `tenant_id` and `sku` bind parameters.
- Produces: `ch03_expression_compiler.run(engine: Engine) -> Evidence`.

- [ ] **Step 1: Write failing statement-structure tests**

Create `tests/unit/test_statements.py`:

```python
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from order_service.db.statements import product_by_sku_statement


def test_product_lookup_keeps_hostile_value_out_of_sql_text() -> None:
    tenant_id = uuid4()
    hostile_sku = "x'; DROP TABLE products; --"
    statement = product_by_sku_statement().params(tenant_id=tenant_id, sku=hostile_sku)
    compiled = statement.compile(dialect=postgresql.dialect())

    assert hostile_sku not in str(compiled)
    assert compiled.params["tenant_id"] == tenant_id
    assert compiled.params["sku"] == hostile_sku


def test_structurally_equal_lookups_compile_to_the_same_sql() -> None:
    dialect = postgresql.dialect()
    first = product_by_sku_statement().compile(dialect=dialect)
    second = product_by_sku_statement().compile(dialect=dialect)

    assert str(first) == str(second)
```

Create `tests/integration/test_statement_cache.py`:

```python
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from order_service.db.schema import products, tenants
from order_service.db.statements import product_by_sku_statement
from scenarios.ch03_expression_compiler import run

pytestmark = pytest.mark.integration


def test_equivalent_executions_share_one_compiled_cache_entry(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    product_id = uuid4()
    cache: dict[Any, Any] = {}
    with engine.begin() as connection:
        connection.execute(tenants.insert().values(id=tenant_id, name="Cache Tenant"))
        connection.execute(
            products.insert().values(
                id=product_id,
                tenant_id=tenant_id,
                sku="CACHE-1",
                name="Cached Product",
                unit_price=Decimal("10.00"),
                attributes={},
            )
        )
        cached_connection = connection.execution_options(compiled_cache=cache)
        statement = product_by_sku_statement()
        cached_connection.execute(statement, {"tenant_id": tenant_id, "sku": "CACHE-1"}).one()
        cached_connection.execute(statement, {"tenant_id": tenant_id, "sku": "CACHE-1"}).one()

    assert len(cache) == 1


def test_compiler_scenario_reports_cache_reuse(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "compiled_cache_entries=1" in observations
    assert "naive_hostile_value_present_in_sql=True" in observations
    assert "corrected_hostile_value_present_in_sql=False" in observations
```

- [ ] **Step 2: Run tests and confirm the missing statement module**

```bash
uv run pytest tests/unit/test_statements.py tests/integration/test_statement_cache.py -q
```

Expected: collection fails because `order_service.db.statements` does not exist.

- [ ] **Step 3: Implement the reusable statement**

Create `src/order_service/db/statements.py`:

```python
from typing import Any

from sqlalchemy import Select, bindparam, select

from order_service.db.schema import products


def product_by_sku_statement() -> Select[Any]:
    return select(
        products.c.id,
        products.c.tenant_id,
        products.c.sku,
        products.c.name,
        products.c.unit_price,
        products.c.attributes,
    ).where(
        products.c.tenant_id == bindparam("tenant_id"),
        products.c.sku == bindparam("sku"),
    )
```

- [ ] **Step 4: Implement the compiler/cache scenario**

Create `scenarios/ch03_expression_compiler.py`:

```python
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.dialects import postgresql

from order_service.db.engine import build_engine
from order_service.db.schema import metadata, products, tenants
from order_service.db.settings import DatabaseSettings
from order_service.db.statements import product_by_sku_statement
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    tenant_id = uuid4()
    product_id = uuid4()
    hostile_sku = "x'; DROP TABLE products; --"
    naive_sql = f"SELECT * FROM products WHERE sku = '{hostile_sku}'"
    statement = product_by_sku_statement()
    compiled = statement.params(tenant_id=tenant_id, sku=hostile_sku).compile(
        dialect=postgresql.dialect()
    )
    cache: dict[Any, Any] = {}
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(tenants.insert().values(id=tenant_id, name="Compiler Tenant"))
        connection.execute(
            products.insert().values(
                id=product_id,
                tenant_id=tenant_id,
                sku="COMPILER-1",
                name="Compiler Product",
                unit_price=Decimal("10.00"),
                attributes={},
            )
        )
        cached_connection = connection.execution_options(compiled_cache=cache)
        for _ in range(2):
            cached_connection.execute(
                statement,
                {"tenant_id": tenant_id, "sku": "COMPILER-1"},
            ).one()

    return Evidence(
        title="Chapter 03 — Expression compiler and cache",
        hypothesis=(
            "Changing bound values does not change the structural SQL shape.",
            "Two equivalent executions reuse one explicit compiled-cache entry.",
        ),
        setup=("PostgreSQL dialect compiler", "Connection-level compiled_cache dictionary"),
        command="uv run python -m scenarios.ch03_expression_compiler",
        observation=(
            f"naive_sql={naive_sql}",
            f"naive_hostile_value_present_in_sql={hostile_sku in naive_sql}",
            f"compiled_sql={compiled}",
            f"hostile_value_present_in_sql={hostile_sku in str(compiled)}",
            f"corrected_hostile_value_present_in_sql={hostile_sku in str(compiled)}",
            f"bound_sku={compiled.params['sku']}",
            f"compiled_cache_entries={len(cache)}",
        ),
        explanation=(
            "ClauseElement structure and bound values travel separately into compilation and execution.",
            "Cache keys describe statement structure; uncacheable custom types disable reuse conservatively.",
        ),
        decision=(
            "Compose SQL with SQLAlchemy expressions and bind parameters; never concatenate request values.",
        ),
        caveat=(
            "The explicit dictionary exposes cache cardinality for the lab; production Engines manage their own cache.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch03-expression-compiler.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests and capture evidence**

```bash
uv run pytest tests/unit/test_statements.py tests/integration/test_statement_cache.py -q
uv run python -m scenarios.ch03_expression_compiler
```

Expected: tests pass; compile-only naive SQL visibly embeds the hostile value but is never
executed, corrected bound-parameter SQL keeps it out of SQL text, and the explicit cache has one entry.

- [ ] **Step 6: Write chapter 03**

Write `03-expression-compiler/README.md` with:

```markdown
# 03 · SQL Expression 與 compiler：SQL 是結構，不是字串
## 生產問題：為什麼參數化同時影響安全與效能？
## 先預測，再執行
## Public contract：generative expression、bindparam、compile
## Mental model：ClauseElement tree → cache key → SQLCompiler
## compiled.params 與 DBAPI parameter channel
## statement cache 的命中與失效
## TypeDecorator.cache_ok 與自訂 construct
## 方言編譯與 literal_binds 的診斷邊界
## 面試追問
```

The chapter must cite <https://docs.sqlalchemy.org/en/20/core/expression_api.html>, <https://docs.sqlalchemy.org/en/20/core/compiler.html>, <https://docs.sqlalchemy.org/en/20/errors.html>, and <https://docs.sqlalchemy.org/en/20/faq/performance.html>. It must identify `_generate_cache_key()` as private if shown in an Implementation note and keep it out of production modules.

- [ ] **Step 7: Verify and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "docs(sqlalchemy): explain expressions and cache keys"
```

---

### Task 6: Build the Core catalog slice and chapter 04

**Files:**

- Create: `sqlalchemy-handson/lab/src/order_service/core/__init__.py`
- Create: `sqlalchemy-handson/lab/src/order_service/core/catalog.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_catalog.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch04_core_dml_results.py`
- Create: `sqlalchemy-handson/lab/evidence/ch04-core-dml-results.md`
- Create: `sqlalchemy-handson/04-core-dml-results/README.md`

**Interfaces:**

- Produces: `ProductRecord` and `InventoryRecord` immutable return types.
- Produces: `create_tenant(connection, *, tenant_id, name) -> None`.
- Produces: explicit idempotent `ensure_tenant(connection, *, tenant_id, name) -> None` for
  repeatable tenant provisioning; `create_tenant` retains strict INSERT semantics.
- Produces: `upsert_product(...) -> ProductRecord` using PostgreSQL `ON CONFLICT ... RETURNING`.
- Produces: `replenish_inventory(...) -> InventoryRecord` using an atomic upsert.
- Produces: `inventory_report(connection, *, tenant_id) -> list[InventoryRecord]` using a CTE and window aggregate.

- [ ] **Step 1: Write failing Core catalog tests**

Create `tests/integration/test_catalog.py`:

```python
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from order_service.core.catalog import (
    create_tenant,
    inventory_report,
    replenish_inventory,
    upsert_product,
)

pytestmark = pytest.mark.integration


def test_product_upsert_returns_existing_identity_and_updated_values(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    original_id = uuid4()
    with engine.begin() as connection:
        create_tenant(connection, tenant_id=tenant_id, name="Core Tenant")
        first = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=original_id,
            sku="CORE-1",
            name="Original",
            unit_price=Decimal("10.00"),
            attributes={"color": "black"},
        )
        second = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=uuid4(),
            sku="CORE-1",
            name="Updated",
            unit_price=Decimal("12.50"),
            attributes={"color": "blue"},
        )

    assert first.id == original_id
    assert second.id == original_id
    assert second.name == "Updated"
    assert second.unit_price == Decimal("12.50")


def test_inventory_upsert_and_report_are_tenant_scoped(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    product_id = uuid4()
    with engine.begin() as connection:
        create_tenant(connection, tenant_id=tenant_id, name="Stock Tenant")
        upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            sku="STOCK-1",
            name="Stock Product",
            unit_price=Decimal("5.00"),
            attributes={},
        )
        first = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=3,
        )
        second = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=5,
        )
        report = inventory_report(connection, tenant_id=tenant_id)

    assert first.available == 3
    assert second.available == 8
    assert second.version == 2
    assert report[0].tenant_stock_value == Decimal("40.00")
```

- [ ] **Step 2: Run tests and confirm the missing Core module**

```bash
uv run pytest tests/integration/test_catalog.py -q
```

Expected: collection fails because `order_service.core.catalog` does not exist.

- [ ] **Step 3: Implement the business-focused Core functions**

Create `src/order_service/core/__init__.py` with the docstring `"""Business-focused SQLAlchemy Core operations."""`.

Create `src/order_service/core/catalog.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from order_service.db.schema import inventories, products, tenants


@dataclass(frozen=True, slots=True)
class ProductRecord:
    id: UUID
    tenant_id: UUID
    sku: str
    name: str
    unit_price: Decimal
    attributes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    tenant_id: UUID
    product_id: UUID
    sku: str
    available: int
    reserved: int
    version: int
    tenant_stock_value: Decimal


def create_tenant(connection: Connection, *, tenant_id: UUID, name: str) -> None:
    connection.execute(tenants.insert().values(id=tenant_id, name=name))


def ensure_tenant(connection: Connection, *, tenant_id: UUID, name: str) -> None:
    statement = (
        pg_insert(tenants)
        .values(id=tenant_id, name=name)
        .on_conflict_do_nothing(index_elements=[tenants.c.id])
    )
    connection.execute(statement)


def upsert_product(
    connection: Connection,
    *,
    tenant_id: UUID,
    product_id: UUID,
    sku: str,
    name: str,
    unit_price: Decimal,
    attributes: Mapping[str, Any],
) -> ProductRecord:
    insert_statement = pg_insert(products).values(
        id=product_id,
        tenant_id=tenant_id,
        sku=sku,
        name=name,
        unit_price=unit_price,
        attributes=dict(attributes),
    )
    statement = insert_statement.on_conflict_do_update(
        constraint="uq_products_tenant_id_sku",
        set_={
            "name": insert_statement.excluded.name,
            "unit_price": insert_statement.excluded.unit_price,
            "attributes": insert_statement.excluded.attributes,
        },
    ).returning(
        products.c.id,
        products.c.tenant_id,
        products.c.sku,
        products.c.name,
        products.c.unit_price,
        products.c.attributes,
    )
    row = connection.execute(statement).mappings().one()
    return ProductRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        sku=row["sku"],
        name=row["name"],
        unit_price=row["unit_price"],
        attributes=row["attributes"],
    )


def replenish_inventory(
    connection: Connection,
    *,
    tenant_id: UUID,
    product_id: UUID,
    quantity: int,
) -> InventoryRecord:
    insert_statement = pg_insert(inventories).values(
        tenant_id=tenant_id,
        product_id=product_id,
        available=quantity,
        reserved=0,
        version=1,
    )
    statement = insert_statement.on_conflict_do_update(
        index_elements=[inventories.c.tenant_id, inventories.c.product_id],
        set_={
            "available": inventories.c.available + insert_statement.excluded.available,
            "version": inventories.c.version + 1,
        },
    ).returning(
        inventories.c.tenant_id,
        inventories.c.product_id,
        inventories.c.available,
        inventories.c.reserved,
        inventories.c.version,
    )
    stock = connection.execute(statement).mappings().one()
    product = connection.execute(
        select(products.c.sku, products.c.unit_price).where(
            products.c.tenant_id == tenant_id,
            products.c.id == product_id,
        )
    ).mappings().one()
    return InventoryRecord(
        **stock,
        sku=product["sku"],
        tenant_stock_value=(stock["available"] - stock["reserved"])
        * product["unit_price"],
    )


def inventory_report(connection: Connection, *, tenant_id: UUID) -> list[InventoryRecord]:
    stock = (
        select(
            inventories.c.tenant_id,
            inventories.c.product_id,
            products.c.sku,
            inventories.c.available,
            inventories.c.reserved,
            inventories.c.version,
            (
                (inventories.c.available - inventories.c.reserved) * products.c.unit_price
            ).label("stock_value"),
        )
        .join(
            products,
            (products.c.tenant_id == inventories.c.tenant_id)
            & (products.c.id == inventories.c.product_id),
        )
        .cte("stock")
    )
    statement = (
        select(
            stock.c.tenant_id,
            stock.c.product_id,
            stock.c.sku,
            stock.c.available,
            stock.c.reserved,
            stock.c.version,
            func.sum(stock.c.stock_value)
            .over(partition_by=stock.c.tenant_id)
            .label("tenant_stock_value"),
        )
        .where(stock.c.tenant_id == tenant_id)
        .order_by(stock.c.sku)
    )
    return [
        InventoryRecord(
            tenant_id=row["tenant_id"],
            product_id=row["product_id"],
            sku=row["sku"],
            available=row["available"],
            reserved=row["reserved"],
            version=row["version"],
            tenant_stock_value=row["tenant_stock_value"],
        )
        for row in connection.execute(statement).mappings()
    ]
```

- [ ] **Step 4: Add a scenario covering executemany, upsert, RETURNING, and Result**

Create `scenarios/ch04_core_dml_results.py`:

```python
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, select

from order_service.core.catalog import (
    inventory_report,
    replenish_inventory,
    upsert_product,
)
from order_service.db.engine import build_engine
from order_service.db.schema import metadata, products, tenants
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    product_id = uuid4()
    other_product_id = uuid4()
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
        executemany_result = connection.execute(
            tenants.insert(),
            [
                {"id": tenant_id, "name": "Core Tenant"},
                {"id": other_tenant_id, "name": "Other Tenant"},
            ],
        )
        original = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            sku="CORE-1",
            name="Original",
            unit_price=Decimal("10.00"),
            attributes={"color": "black"},
        )
        updated = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=uuid4(),
            sku="CORE-1",
            name="Updated",
            unit_price=Decimal("12.50"),
            attributes={"color": "blue"},
        )
        replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=3,
        )
        stock = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=5,
        )
        report = inventory_report(connection, tenant_id=tenant_id)
        upsert_product(
            connection,
            tenant_id=other_tenant_id,
            product_id=other_product_id,
            sku="CORE-1",
            name="Other Tenant Product",
            unit_price=Decimal("99.00"),
            attributes={},
        )
        naive_matches = connection.scalars(
            select(products.c.tenant_id).where(products.c.sku == "CORE-1")
        ).all()
        corrected_matches = connection.scalars(
            select(products.c.tenant_id).where(
                products.c.tenant_id == tenant_id,
                products.c.sku == "CORE-1",
            )
        ).all()

    return Evidence(
        title="Chapter 04 — Core DML and Result",
        hypothesis=(
            "executemany sends one statement shape with multiple parameter sets.",
            "ON CONFLICT updates the existing tenant/SKU row and RETURNING exposes its identity.",
        ),
        setup=("Two tenants", "One product upserted twice", "Inventory replenished 3 + 5"),
        command="uv run python -m scenarios.ch04_core_dml_results",
        observation=(
            f"executemany_tenant_rows={executemany_result.rowcount}",
            f"upsert_preserved_product_id={original.id == updated.id == product_id}",
            f"returned_product_name={updated.name}",
            f"inventory_available={stock.available}",
            f"inventory_version={stock.version}",
            f"tenant_stock_value={report[0].tenant_stock_value:.2f}",
            f"naive_unscoped_matches={len(naive_matches)}",
            f"naive_cross_tenant_ambiguous={len(set(naive_matches)) > 1}",
            f"corrected_tenant_matches={len(corrected_matches)}",
            f"corrected_tenant_isolated={corrected_matches == [tenant_id]}",
        ),
        explanation=(
            "PostgreSQL RETURNING removes a follow-up lookup for server-visible results.",
            "Result.mappings() makes the selected row shape explicit before conversion to a record type.",
        ),
        decision=(
            "Use Core for explicit set-oriented DML and reports whose SQL shape is the primary abstraction.",
        ),
        caveat=(
            "ON CONFLICT and JSONB are PostgreSQL dialect capabilities; portability requires a deliberate fallback.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch04-core-dml-results.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Test the implementation and evidence scenario**

Add this test to `tests/integration/test_catalog.py`:

```python
from scenarios.ch04_core_dml_results import run


def test_core_dml_scenario_records_expected_result_shapes(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "executemany_tenant_rows=2" in observations
    assert "upsert_preserved_product_id=True" in observations
    assert "inventory_available=8" in observations
    assert "naive_unscoped_matches=2" in observations
    assert "naive_cross_tenant_ambiguous=True" in observations
    assert "corrected_tenant_matches=1" in observations
    assert "corrected_tenant_isolated=True" in observations
```

Run:

```bash
uv run pytest tests/integration/test_catalog.py -q
uv run python -m scenarios.ch04_core_dml_results
```

Expected: tests pass; evidence retains the DML/result observations and adds deterministic
naive unscoped ambiguity plus corrected tenant-scoped isolation observations.

- [ ] **Step 6: Write chapter 04**

Write `04-core-dml-results/README.md` with:

```markdown
# 04 · Core 查詢、DML 與 Result：控制 SQL，也控制回傳形狀
## 生產問題：何時 Core 比 ORM 更直接？
## 先預測，再執行
## SELECT、JOIN、subquery、CTE、window function
## INSERT／UPDATE／DELETE 與 executemany
## PostgreSQL RETURNING 與 ON CONFLICT
## Result、Row、mappings、scalars、one 的語義
## 批量不是逐列迴圈
## 方言能力與可攜性成本
## 面試追問
```

Link every production function, test, scenario, and evidence file. Cite <https://docs.sqlalchemy.org/en/20/core/dml.html>, <https://docs.sqlalchemy.org/en/20/core/selectable.html>, <https://docs.sqlalchemy.org/en/20/core/connections.html>, and <https://docs.sqlalchemy.org/en/20/dialects/postgresql.html>. Explicitly state that Core and ORM share the same Engine and expression system; Core is not a lower-quality fallback.

- [ ] **Step 7: Verify and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "feat(sqlalchemy): add the Core catalog slice"
```

---

### Task 7: Make transaction ownership executable and write chapter 05

**Files:**

- Create: `sqlalchemy-handson/lab/src/order_service/application/__init__.py`
- Create: `sqlalchemy-handson/lab/src/order_service/application/catalog_service.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_transactions.py`
- Modify: `sqlalchemy-handson/lab/tests/unit/test_package_contract.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch05_connection_transactions.py`
- Create: `sqlalchemy-handson/lab/evidence/ch05-connection-transactions.md`
- Create: `sqlalchemy-handson/05-connection-transactions/README.md`

**Interfaces:**

- Produces: `RegisterStockCommand`, the transaction input DTO.
- Produces: `register_product_with_stock(engine: Engine, command: RegisterStockCommand) -> InventoryRecord`.
- Enforces: repeated service calls can provision multiple products for one tenant, and a repeated
  tenant/SKU request replenishes inventory through the canonical `ProductRecord.id` returned by upsert.
- Enforces: the application-service entry point owns `with engine.begin()`; Core functions remain commit-free.
- Produces: `ch05_connection_transactions.run(engine: Engine) -> Evidence`.

- [ ] **Step 1: Write failing commit and rollback tests**

Create `tests/integration/test_transactions.py`:

```python
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select

from order_service.application import catalog_service
from order_service.application.catalog_service import RegisterStockCommand
from order_service.db.schema import inventories, products, tenants

pytestmark = pytest.mark.integration


def command() -> RegisterStockCommand:
    return RegisterStockCommand(
        tenant_id=uuid4(),
        tenant_name="Transaction Tenant",
        product_id=uuid4(),
        sku="TX-1",
        product_name="Transaction Product",
        unit_price=Decimal("20.00"),
        attributes={},
        quantity=4,
    )


def test_application_service_commits_the_complete_operation(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    value = command()

    result = catalog_service.register_product_with_stock(engine, value)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(products)) == 1
        assert connection.scalar(select(func.count()).select_from(inventories)) == 1
    assert result.available == 4


def test_application_service_rolls_back_every_prior_write(
    engine: Engine,
    recreated_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del recreated_schema
    value = command()

    def fail_after_product(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("failure injection after product upsert")

    monkeypatch.setattr(catalog_service, "replenish_inventory", fail_after_product)

    with pytest.raises(RuntimeError, match="failure injection"):
        catalog_service.register_product_with_stock(engine, value)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(tenants)) == 0
        assert connection.scalar(select(func.count()).select_from(products)) == 0
```

Add real PostgreSQL regressions for two products under one tenant and for replaying the same
tenant/SKU with a different requested product ID. The latter must assert one canonical product row,
one canonical inventory row, and accumulated inventory on the original ID. Retain the rollback and
lower-layer transaction-ownership tests.

Append this architecture guard to `tests/unit/test_package_contract.py` and add `from pathlib import Path` at the top:

```python
def test_lower_layers_never_commit_their_callers_transaction() -> None:
    package_root = Path(__file__).parents[2] / "src" / "order_service"
    offenders = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*.py")
        if ".commit(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
```

- [ ] **Step 2: Run the tests and confirm the missing application module**

```bash
uv run pytest tests/integration/test_transactions.py -q
```

Expected: collection fails because `order_service.application.catalog_service` does not exist.

- [ ] **Step 3: Implement the transaction-owning application service**

Create `src/order_service/application/__init__.py`:

```python
"""Transaction-owning application services."""
```

Create `src/order_service/application/catalog_service.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine

from order_service.core.catalog import (
    InventoryRecord,
    ensure_tenant,
    replenish_inventory,
    upsert_product,
)


@dataclass(frozen=True, slots=True)
class RegisterStockCommand:
    tenant_id: UUID
    tenant_name: str
    product_id: UUID
    sku: str
    product_name: str
    unit_price: Decimal
    attributes: Mapping[str, Any]
    quantity: int


def register_product_with_stock(
    engine: Engine,
    command: RegisterStockCommand,
) -> InventoryRecord:
    if command.quantity <= 0:
        raise ValueError("quantity must be positive")
    with engine.begin() as connection:
        ensure_tenant(
            connection,
            tenant_id=command.tenant_id,
            name=command.tenant_name,
        )
        product = upsert_product(
            connection,
            tenant_id=command.tenant_id,
            product_id=command.product_id,
            sku=command.sku,
            name=command.product_name,
            unit_price=command.unit_price,
            attributes=command.attributes,
        )
        return replenish_inventory(
            connection,
            tenant_id=command.tenant_id,
            product_id=product.id,
            quantity=command.quantity,
        )
```

- [ ] **Step 4: Implement a deterministic transaction-state scenario**

The scenario must also execute a naive failed root transaction: catch `IntegrityError`, prove the
next statement is rejected, call public `rollback()`, and prove the same Connection is reusable.
Record deterministic `naive_failed_transaction_rejected=True` and
`corrected_connection_reusable=True` observations while retaining the original state observations.

Create `scenarios/ch05_connection_transactions.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError

from order_service.db.engine import build_engine
from order_service.db.schema import metadata, tenants
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)

    with engine.connect() as connection:
        before_execute = connection.in_transaction()
        connection.scalar(text("SELECT 1"))
        after_execute = connection.in_transaction()
        connection.rollback()

    rollback_tenant_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                tenants.insert().values(id=rollback_tenant_id, name="Rollback Tenant")
            )
            raise RuntimeError("failure injection")
    except RuntimeError:
        pass
    with engine.connect() as connection:
        rolled_back_count = connection.scalar(
            select(func.count()).select_from(tenants).where(tenants.c.id == rollback_tenant_id)
        )

    savepoint_tenant_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            tenants.insert().values(id=savepoint_tenant_id, name="Savepoint Tenant")
        )
        try:
            with connection.begin_nested():
                connection.execute(
                    tenants.insert().values(id=savepoint_tenant_id, name="Duplicate Tenant")
                )
        except IntegrityError:
            pass
    with engine.connect() as connection:
        committed_count = connection.scalar(
            select(func.count()).select_from(tenants).where(tenants.c.id == savepoint_tenant_id)
        )

    return Evidence(
        title="Chapter 05 — Connection transaction state",
        hypothesis=(
            "The first execute triggers autobegin on a fresh Connection.",
            "Engine.begin() rolls back on exception, while a savepoint can roll back one failed unit.",
        ),
        setup=("Fresh PostgreSQL schema", "One exception block", "One nested transaction"),
        command="uv run python -m scenarios.ch05_connection_transactions",
        observation=(
            f"in_transaction_before_execute={before_execute}",
            f"in_transaction_after_execute={after_execute}",
            f"exception_block_rolled_back={rolled_back_count == 0}",
            f"savepoint_preserved_outer={committed_count == 1}",
        ),
        explanation=(
            "BEGIN (implicit) is SQLAlchemy/DBAPI transaction state, not necessarily a literal BEGIN sent at that instant.",
            "The outer transaction owns atomicity; begin_nested() only scopes a savepoint within it.",
        ),
        decision=(
            "Place the transaction boundary at the application-service operation and keep lower layers commit-free.",
        ),
        caveat=(
            "A savepoint does not isolate external side effects and does not shorten the outer transaction lifetime.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch05-connection-transactions.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Add and run the scenario test**

Append to `tests/integration/test_transactions.py`:

```python
from scenarios.ch05_connection_transactions import run


def test_transaction_scenario_records_autobegin_and_savepoint(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "in_transaction_before_execute=False" in observations
    assert "in_transaction_after_execute=True" in observations
    assert "exception_block_rolled_back=True" in observations
    assert "savepoint_preserved_outer=True" in observations
    assert "naive_failed_transaction_rejected=True" in observations
    assert "corrected_connection_reusable=True" in observations
```

Run:

```bash
uv run pytest tests/integration/test_transactions.py -q
uv run python -m scenarios.ch05_connection_transactions
```

Expected: `3 passed`; evidence contains all four exact observation keys.

- [ ] **Step 6: Write chapter 05**

Write `05-connection-transactions/README.md` with:

```markdown
# 05 · Connection 與交易狀態機：沒有「不在交易裡」的寫入
## 生產問題：commit 到底應該由誰呼叫？
## 先預測，再執行
## Public contract：autobegin、commit-as-you-go、begin-once
## Connection、Transaction、NestedTransaction 的狀態
## DBAPI implicit transaction 與 DBAPI AUTOCOMMIT
## savepoint 是局部回滾，不是獨立交易
## 失敗後先 rollback，再重用資源
## 交易所有權：application service 擁有邊界
## 事故模式：長交易與交易內外部 I/O
## 面試追問
```

The chapter must link the application service, its failure-injection test, scenario, and evidence. Cite <https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html> and <https://docs.sqlalchemy.org/en/20/core/engines_connections.html>. Include one explicit anti-example where a lower-level function calls `commit()` and explain how it destroys caller atomicity.

- [ ] **Step 7: Verify and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "feat(sqlalchemy): enforce transaction ownership"
```

---

### Task 8: Reproduce pool exhaustion and write chapter 06

**Files:**

- Create: `sqlalchemy-handson/lab/src/order_service/db/pool_budget.py`
- Create: `sqlalchemy-handson/lab/tests/unit/test_pool_budget.py`
- Create: `sqlalchemy-handson/lab/tests/integration/test_pooling.py`
- Create: `sqlalchemy-handson/lab/scenarios/ch06_pooling_capacity.py`
- Create: `sqlalchemy-handson/lab/evidence/ch06-pooling-capacity.md`
- Create: `sqlalchemy-handson/06-pooling-capacity/README.md`
- Modify: `sqlalchemy-handson/lab/pyproject.toml`
- Modify: `sqlalchemy-handson/lab/uv.lock`

**Interfaces:**

- Produces: `PoolBudget(instances, workers, pool_size, max_overflow)`.
- Produces: `PoolBudget.connection_ceiling -> int` and `assert_fits(database_budget: int) -> None`.
- Produces: `observe_pool_exhaustion(settings: DatabaseSettings) -> PoolExhaustionObservation`.
- Produces: `ch06_pooling_capacity.run(settings: DatabaseSettings) -> Evidence`.

- [ ] **Step 1: Write failing pool-budget and exhaustion tests**

Create `tests/unit/test_pool_budget.py`:

```python
import pytest

from order_service.db.pool_budget import PoolBudget


def test_pool_budget_counts_every_process_and_overflow_slot() -> None:
    budget = PoolBudget(instances=3, workers=4, pool_size=5, max_overflow=2)

    assert budget.connection_ceiling == 84
    budget.assert_fits(database_budget=100)
    with pytest.raises(ValueError, match="84 exceeds database budget 80"):
        budget.assert_fits(database_budget=80)
    with pytest.raises(ValueError, match="pool_size must be positive"):
        PoolBudget(instances=1, workers=1, pool_size=0, max_overflow=0)
```

Create `tests/integration/test_pooling.py`:

```python
import pytest

from order_service.db.settings import DatabaseSettings
from scenarios.ch06_pooling_capacity import observe_pool_exhaustion, run

pytestmark = pytest.mark.integration


def test_third_checkout_times_out_when_two_slots_are_held() -> None:
    observed = observe_pool_exhaustion(DatabaseSettings.from_env())

    assert 0.15 <= observed.waited_seconds < 0.8
    assert "QueuePool limit of size 2 overflow 0 reached" in observed.error_message
    assert observed.checked_out_at_timeout == 2


def test_pool_scenario_records_capacity_and_timeout() -> None:
    observations = "\n".join(run(DatabaseSettings.from_env()).observation)
    assert "configured_hard_limit=2" in observations
    assert "checked_out_at_timeout=2" in observations
    assert "timeout_class=sqlalchemy.exc.TimeoutError" in observations
    assert "naive_checkout_timed_out=True" in observations
    assert "corrected_pool_recovered=True" in observations
    assert "timeout_within_expected_bound=True" in observations
    assert "waited_seconds=" not in observations
```

- [ ] **Step 2: Run tests and confirm missing modules**

```bash
uv run pytest tests/unit/test_pool_budget.py tests/integration/test_pooling.py -q
```

Expected: collection fails because `order_service.db.pool_budget` and the chapter 06 scenario do not exist.

- [ ] **Step 3: Implement the process-wide connection budget model**

Create `src/order_service/db/pool_budget.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoolBudget:
    instances: int
    workers: int
    pool_size: int
    max_overflow: int

    def __post_init__(self) -> None:
        if (
            self.instances <= 0
            or self.workers <= 0
            or self.pool_size <= 0
            or self.max_overflow < 0
        ):
            raise ValueError(
                "instances, workers, and pool_size must be positive; "
                "max_overflow cannot be negative"
            )

    @property
    def connection_ceiling(self) -> int:
        return self.instances * self.workers * (self.pool_size + self.max_overflow)

    def assert_fits(self, database_budget: int) -> None:
        if self.connection_ceiling > database_budget:
            raise ValueError(
                f"{self.connection_ceiling} exceeds database budget {database_budget}"
            )
```

- [ ] **Step 4: Implement deterministic pool saturation**

Create `scenarios/ch06_pooling_capacity.py`:

```python
from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sqlalchemy import event, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.pool import QueuePool

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


@dataclass(frozen=True, slots=True)
class PoolExhaustionObservation:
    waited_seconds: float
    error_message: str
    checked_out_at_timeout: int
    event_names: tuple[str, ...]
    checked_out_after_recovery: int


def observe_pool_exhaustion(settings: DatabaseSettings) -> PoolExhaustionObservation:
    engine = build_engine(
        settings,
        pool_size=2,
        max_overflow=0,
        pool_timeout=0.2,
        pool_pre_ping=False,
    )
    both_checked_out = threading.Barrier(3)
    release = threading.Event()
    holder_errors: list[Exception] = []
    pool = cast(QueuePool, engine.pool)
    event_names: list[str] = []
    event_lock = threading.Lock()

    def record_event(name: str) -> None:
        with event_lock:
            event_names.append(name)

    event.listen(pool, "checkout", lambda *_args: record_event("checkout"))
    event.listen(pool, "reset", lambda *_args: record_event("reset"))
    event.listen(pool, "checkin", lambda *_args: record_event("checkin"))

    def hold_connection() -> None:
        try:
            with engine.connect() as connection:
                connection.scalar(text("SELECT 1"))
                both_checked_out.wait(timeout=2)
                if not release.wait(timeout=2):
                    raise TimeoutError("holder release timed out")
        except Exception as error:
            holder_errors.append(error)

    threads = [threading.Thread(target=hold_connection) for _ in range(2)]
    timeout_result: tuple[float, str, int] | None = None
    try:
        try:
            for thread in threads:
                thread.start()
            both_checked_out.wait(timeout=2)
            started = time.perf_counter()
            try:
                third_connection = engine.connect()
            except SQLAlchemyTimeoutError as error:
                waited = time.perf_counter() - started
                record_event("timeout")
                timeout_result = (waited, str(error), pool.checkedout())
            else:
                third_connection.close()
                raise AssertionError("third checkout unexpectedly succeeded")
        finally:
            record_event("release")
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(timeout=2)
                    if thread.is_alive():
                        holder_errors.append(TimeoutError("connection holder did not stop"))
        if holder_errors:
            raise ExceptionGroup("connection holders failed", holder_errors)
        if timeout_result is None:
            raise AssertionError("pool exhaustion observation was not captured")

        with engine.connect() as connection:
            connection.scalar(text("SELECT 1"))

        waited, error_message, checked_out_at_timeout = timeout_result
        return PoolExhaustionObservation(
            waited_seconds=waited,
            error_message=error_message,
            checked_out_at_timeout=checked_out_at_timeout,
            event_names=tuple(event_names),
            checked_out_after_recovery=pool.checkedout(),
        )
    finally:
        engine.dispose()


def run(settings: DatabaseSettings) -> Evidence:
    observed = observe_pool_exhaustion(settings)
    return Evidence(
        title="Chapter 06 — Pooling and capacity",
        hypothesis=(
            "pool_size=2 and max_overflow=0 allow exactly two simultaneous checkouts.",
            "A third checkout waits pool_timeout before SQLAlchemy raises TimeoutError.",
        ),
        setup=("pool_size=2", "max_overflow=0", "pool_timeout=0.2 seconds"),
        command="uv run python -m scenarios.ch06_pooling_capacity",
        observation=(
            "configured_hard_limit=2",
            f"checked_out_at_timeout={observed.checked_out_at_timeout}",
            "timeout_class=sqlalchemy.exc.TimeoutError",
            "naive_checkout_timed_out=True",
            f"corrected_pool_recovered={observed.checked_out_after_recovery == 0}",
            f"timeout_within_expected_bound={0.15 <= observed.waited_seconds < 0.8}",
            f"error_message={observed.error_message}",
        ),
        explanation=(
            "QueuePool limits concurrent checked-out connections, not request concurrency.",
            "The process-wide ceiling multiplies pool limits by workers and service instances.",
        ),
        decision=(
            "Budget database connections across all processes before changing pool_size.",
        ),
        caveat=(
            "The timeout duration is an invariant window; scheduler-level milliseconds vary by host.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch06-pooling-capacity.md"),
    )
    args = parser.parse_args()
    write_evidence(args.evidence, run(DatabaseSettings.from_env()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests repeatedly and capture evidence**

```bash
uv run pytest tests/unit/test_pool_budget.py tests/integration/test_pooling.py -q
uv run pytest tests/integration/test_pooling.py -q --count=5
uv run python -m scenarios.ch06_pooling_capacity
```

Before using `--count=5`, add this exact entry to `[dependency-groups].dev` in `pyproject.toml`, then run `uv sync` so `uv.lock` records it:

```toml
"pytest-repeat>=0.9,<1",
```

Expected: unit and integration tests pass; all five repeated executions pass; the test retains the
bounded timing assertion, while committed evidence records `timeout_within_expected_bound=True`
instead of a wall-clock millisecond value and proves recovery after saturation.

- [ ] **Step 6: Write chapter 06**

Write `06-pooling-capacity/README.md` with:

```markdown
# 06 · 連線池與容量治理：Pool 是並發閘門，不是加速按鈕
## 生產問題：pool timeout 是池太小，還是連線拿太久？
## 先預測，再執行
## Public contract：QueuePool checkout、checkin、reset、invalidate
## pool_size、max_overflow、pool_timeout、pool_recycle、pre_ping
## 全服務連線預算：instance × worker × process pool
## Little's Law 只提供估算，不提供魔法數字
## PgBouncer 與應用池的雙層關係
## fork safety、DB restart、disconnect handling
## 排查順序與觀測指標
## 面試追問
```

The chapter must link the deterministic saturation test and evidence, cite <https://docs.sqlalchemy.org/en/20/core/pooling.html> and <https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic>, and explicitly distinguish pool saturation, database max-connections exhaustion, slow transactions, and leaked Connections.

- [ ] **Step 7: Verify and commit**

```bash
uv run ruff check src tests scenarios
uv run mypy src tests scenarios
git add sqlalchemy-handson
git commit -m "docs(sqlalchemy): reproduce QueuePool saturation"
```

---

### Task 9: Capture the environment, wire cross-links, and close M1

**Files:**

- Create: `sqlalchemy-handson/lab/scenarios/environment.py`
- Create: `sqlalchemy-handson/lab/evidence/environment.md`
- Create: `sqlalchemy-handson/lab/tests/unit/test_evidence_manifest.py`
- Modify: `sqlalchemy-handson/lab/Makefile`
- Modify: `sqlalchemy-handson/lab/README.md`
- Modify: `sqlalchemy-handson/README.md`
- Modify: `python-data/README.md`
- Modify: `python/23-data-access-bridge.md`

**Interfaces:**

- Produces: `make evidence`, which regenerates all seven committed evidence documents.
- Produces: `make verify`, which runs Ruff, mypy, unit tests, and PostgreSQL integration tests.
- Produces: bidirectional navigation from `python/23` → `python-data/` → `sqlalchemy-handson/`.

- [ ] **Step 1: Write a failing evidence-manifest test**

Create `tests/unit/test_evidence_manifest.py`:

```python
from pathlib import Path

EXPECTED_EVIDENCE = {
    "environment.md",
    "ch01-engine-execution.md",
    "ch02-schema-types.md",
    "ch03-expression-compiler.md",
    "ch04-core-dml-results.md",
    "ch05-connection-transactions.md",
    "ch06-pooling-capacity.md",
}
REQUIRED_HEADINGS = {
    "## Hypothesis",
    "## Setup",
    "## Command",
    "## Observation",
    "## Explanation",
    "## Decision",
    "## Caveat",
}


def test_committed_evidence_manifest_is_complete() -> None:
    evidence_dir = Path(__file__).parents[2] / "evidence"
    assert {path.name for path in evidence_dir.glob("*.md")} == EXPECTED_EVIDENCE
    for path in evidence_dir.glob("*.md"):
        rendered = path.read_text(encoding="utf-8")
        assert REQUIRED_HEADINGS <= set(rendered.splitlines())
        command_section = rendered.split("## Command\n\n", maxsplit=1)[1].split(
            "\n## Observation", maxsplit=1
        )[0]
        command_lines = [
            line for line in command_section.splitlines() if line.startswith("- ")
        ]
        assert len(command_lines) == 1
```

- [ ] **Step 2: Run the manifest test and confirm environment evidence is missing**

```bash
uv run pytest tests/unit/test_evidence_manifest.py -q
```

Expected: FAIL because `environment.md` is absent.

- [ ] **Step 3: Implement environment capture without secrets**

Create `scenarios/environment.py`:

```python
from __future__ import annotations

import platform
import sys
from pathlib import Path

import psycopg
import sqlalchemy
from sqlalchemy import text

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def main() -> None:
    settings = DatabaseSettings.from_env()
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            postgres_version = connection.scalar(text("SHOW server_version"))
        evidence = Evidence(
            title="M1 environment manifest",
            hypothesis=("The committed evidence identifies every behavior-affecting runtime version.",),
            setup=(f"database_url={settings.safe_url}",),
            command="uv run python -m scenarios.environment",
            observation=(
                f"python={platform.python_version()}",
                f"implementation={sys.implementation.name}",
                f"sqlalchemy={sqlalchemy.__version__}",
                f"psycopg={psycopg.__version__}",
                f"postgresql={postgres_version}",
                f"platform={platform.machine()}-{platform.system()}",
            ),
            explanation=(
                "Version and platform context separate reproducible behavior from host-specific timing.",
            ),
            decision=("Regenerate this manifest whenever the lockfile or database image changes.",),
            caveat=("The rendered database URL hides the password and contains no production secret.",),
        )
        write_evidence(Path("evidence/environment.md"), evidence)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add the reproducible evidence target**

Add this target to `Makefile` and add `evidence` to `.PHONY`:

```make
evidence:
	uv run python -m scenarios.environment
	uv run python -m scenarios.ch01_engine_execution
	uv run python -m scenarios.ch02_schema_types
	uv run python -m scenarios.ch03_expression_compiler
	uv run python -m scenarios.ch04_core_dml_results
	uv run python -m scenarios.ch05_connection_transactions
	uv run python -m scenarios.ch06_pooling_capacity
```

Run:

```bash
make evidence
uv run pytest tests/unit/test_evidence_manifest.py -q
```

Expected: seven evidence files exist and the manifest test passes.

- [ ] **Step 5: Finish tutorial navigation and cross-track boundaries**

Update `sqlalchemy-handson/README.md` so chapters 00–06 link to existing files and show status `M1 complete`. Keep 07–24 described as subsequent milestone scope without dead links.

Update `lab/README.md` with:

- `make db-up`, `make evidence`, `make verify`, `make db-down`;
- the exact purpose of each scenario and evidence file;
- a warning that `make evidence` recreates the lab schema and must never target a shared database;
- a troubleshooting table for Docker unavailable, port 55432 occupied, PostgreSQL unhealthy, and stale lockfile.

Add a “SQLAlchemy 專題深水區” paragraph near the top of `python-data/README.md` that links to `../sqlalchemy-handson/` and states that `python-data/` remains the shorter architecture/selection track.

Add one row below the existing `python-data/` table in `python/23-data-access-bridge.md`:

```markdown
| SQLAlchemy 2.0 深水教程（Core／ORM／一致性／事故實驗） | [`../sqlalchemy-handson/`](../sqlalchemy-handson/) |
```

- [ ] **Step 6: Run the complete M1 acceptance suite**

Run from `sqlalchemy-handson/lab`:

```bash
uv sync --locked
docker compose up -d --wait
make evidence
make verify
```

Expected:

- Ruff exits 0.
- mypy prints `Success: no issues found`.
- all unit and integration tests pass with zero deselected failures.
- all seven evidence files are regenerated.
- `environment.md` reports Python 3.14.x, SQLAlchemy 2.0.51, psycopg 3.3.x, and PostgreSQL 18.4.

Run from the repository worktree root:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits 0; status lists only intended M1 tutorial and cross-link changes.

- [ ] **Step 7: Commit the completed milestone**

```bash
git add sqlalchemy-handson python-data/README.md python/23-data-access-bridge.md
git commit -m "docs(sqlalchemy): complete the Core runtime milestone"
```

Do not stop the PostgreSQL service before tests and evidence are reviewed. After review, `make db-down` is safe because all evidence is committed text.

## M1 Completion Gate

M1 is complete only when all conditions are true:

- Chapters 00–06 exist and follow the approved chapter contract.
- Every chapter 01–06 links to a runnable scenario, at least one behavior test, and committed evidence.
- The Core catalog slice persists tenant-scoped products and inventory through caller-owned Connections.
- The application service proves all-or-nothing transaction ownership with a failure-injection test.
- Pool saturation is deterministic across five repeated runs.
- No application module calls `Connection.commit()`.
- `uv sync --locked`, `make evidence`, and `make verify` all exit 0 against PostgreSQL 18.4.
- `git diff --check` exits 0 and the worktree contains no unrelated user changes.
