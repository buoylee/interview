# Python Testing Engineering Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a senior/architect-level `python-testing/` tutorial track with twelve chapters, interview cards, and a runnable order/payment service lab that demonstrates fast, integration, contract, async, stateful, E2E, and suite-governance testing.

**Architecture:** Keep one cumulative modular-monolith lab under `python-testing/lab/`. Grow it from a pure order domain through async application ports, FastAPI, real Postgres, an HTTP payment adapter, an outbox worker, and a legacy refund capstone; each chapter owns the tests and failure scenario introduced at that boundary. Preserve `python/12-testing.md` as a concise bridge and use cross-links instead of repeating the repository's database, concurrency, performance, and consistency tutorials.

**Tech Stack:** CPython 3.11–3.14, pytest 9, pytest-asyncio, FastAPI, HTTPX, SQLAlchemy 2.x async, psycopg 3, Alembic, Testcontainers for Postgres, Hypothesis, pytest-xdist, pytest-cov/coverage.py, mutmut, Nox with the uv backend, and uv lockfiles.

## Global Constraints

- Work only in the isolated worktree on branch `codex/python-testing-tutorial`.
- Tutorial prose is Simplified Chinese to match the repository; identifiers, commands, and exact error text stay in English.
- Python minimum is 3.11; the fast CI matrix is exactly 3.11, 3.12, 3.13, and 3.14.
- `uv run pytest` must run the fast layer without Docker. Only `integration` and `e2e` sessions may require Docker.
- Database integration and E2E tests use real Postgres through Testcontainers; never substitute SQLite for Postgres semantics.
- Keep one cumulative lab. Only pytest-mechanism demonstrations that do not fit the order service go under `lab/scenarios/`.
- Use pytest as the runner. `unittest` and `doctest` appear only in the bridge/selection material and interoperability examples.
- Configure `--strict-markers`, `--strict-config`, `xfail_strict = true`, and `asyncio_mode = "strict"` in `pyproject.toml`.
- Do not hide flaky tests with automatic reruns, arbitrary sleeps, blanket warning suppression, or non-strict `xfail`.
- Every production bug introduced by a task must first have a reproducing test and must retain a regression test after the fix.
- Every formal tutorial code block must be copied from a runnable lab file; pseudocode must be labeled `pseudocode`.
- Version-sensitive claims must cite the official references listed in the design spec; do not use secondary tutorials as authority for pytest, pytest-asyncio, Hypothesis, Testcontainers, xdist, mutmut, or Nox behavior.
- Do not add Kafka, Redis, Kubernetes, browser UI testing, load testing, penetration testing, or a second service.
- Each chapter uses this fixed section order: 核心问题 → 直觉模型 → 机制深入 → 设计取舍 → 贯穿 lab → 故障工单 → Java/Go 对照 → 验收与面试卡.
- Keep the working tree clean after each task and commit only that task's files.

## File and Responsibility Map

### Track documentation

- `python-testing/README.md`: learning path, command tiers, progress map, and cross-track links.
- `python-testing/00-testing-strategy.md` through `11-ci-legacy-and-capstone.md`: one bounded chapter each, following the fixed eight-section template.
- `python-testing/99-interview-cards/README.md`: quick-answer index by chapter.
- `python-testing/99-interview-cards/q-*.md`: deep architecture/mechanism/diagnosis answers.
- `python/12-testing.md`: 10–15 minute pytest/unittest/doctest selection and syntax bridge.
- `python/README.md`: points chapter 12 readers to the new track.

### Lab production code

- `python-testing/lab/src/order_service/domain/order.py`: Money, OrderStatus, Order, and domain transition errors.
- `python-testing/lab/src/order_service/application/messages.py`: commands, payment results, and outbox messages.
- `python-testing/lab/src/order_service/application/create_order.py`: idempotent order creation plus outbox enqueue.
- `python-testing/lab/src/order_service/application/process_payment.py`: payment state transitions around an external HTTP call.
- `python-testing/lab/src/order_service/application/refund_order.py`: capstone refund orchestration.
- `python-testing/lab/src/order_service/ports/uow.py`: repository, outbox, and async unit-of-work protocols.
- `python-testing/lab/src/order_service/ports/payment.py`: charge/refund gateway protocol and uncertainty errors.
- `python-testing/lab/src/order_service/ports/system.py`: Clock and IdGenerator protocols.
- `python-testing/lab/src/order_service/adapters/memory.py`: deterministic handwritten fakes for fast tests.
- `python-testing/lab/src/order_service/adapters/sqlalchemy.py`: SQLAlchemy tables, mappings, repositories, and UoW.
- `python-testing/lab/src/order_service/adapters/payment_http.py`: HTTPX payment provider adapter.
- `python-testing/lab/src/order_service/adapters/outbox.py`: concurrent-safe outbox worker.
- `python-testing/lab/src/order_service/api/dependencies.py`: FastAPI dependency providers and override seams.
- `python-testing/lab/src/order_service/api/schemas.py`: request/response contracts.
- `python-testing/lab/src/order_service/api/app.py`: application factory and routes.

### Lab tests and operations

- `python-testing/lab/tests/unit/`: pure domain tests.
- `python-testing/lab/tests/component/`: application, fake adapter, and in-process API tests.
- `python-testing/lab/tests/integration/`: Postgres, migration, transaction, locking, and outbox tests.
- `python-testing/lab/tests/contract/`: fake provider and payment/OpenAPI contract tests.
- `python-testing/lab/tests/e2e/`: complete API → DB → worker → fake provider flows.
- `python-testing/lab/tests/property/`: Hypothesis example-based properties and state machines.
- `python-testing/lab/scenarios/`: explicit, excluded-by-default failure reproductions.
- `python-testing/lab/migrations/`: Alembic environment and revisions.
- `python-testing/lab/noxfile.py`: local/CI sessions and Python-version matrix.
- `python-testing/lab/pyproject.toml`: package metadata, locked dependency bounds, pytest, coverage, and mutmut configuration.
- `python-testing/lab/README.md`: exact setup, command tiers, expected evidence, and troubleshooting.

---

### Task 1: Bootstrap the Track, Package, and Bridge

**Files:**
- Create: `python-testing/README.md`
- Create: `python-testing/lab/README.md`
- Create: `python-testing/lab/pyproject.toml`
- Create: `python-testing/lab/src/order_service/__init__.py`
- Create: `python-testing/lab/tests/unit/test_package_smoke.py`
- Create: `python-testing/lab/tests/unit/test_pytest_basics.py`
- Modify: `python/12-testing.md`
- Modify: `python/README.md`

**Interfaces:**
- Consumes: the approved design spec at `docs/superpowers/specs/2026-07-15-python-testing-track-design.md`.
- Produces: installable package `order-service-testing-lab`, `order_service.__version__ == "0.1.0"`, pytest marker names `integration`, `contract`, `e2e`, `property`, and `docker`, and the canonical bridge link `../python-testing/README.md`.

- [ ] **Step 1: Write the package smoke test before the package exists**

```python
# python-testing/lab/tests/unit/test_package_smoke.py
from order_service import __version__


def test_package_has_pinned_tutorial_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test and verify the red state**

Run: `cd python-testing/lab && uv run pytest tests/unit/test_package_smoke.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'order_service'`.

- [ ] **Step 3: Add the package and exact project configuration**

```toml
# python-testing/lab/pyproject.toml
[project]
name = "order-service-testing-lab"
version = "0.1.0"
description = "Runnable order/payment lab for the Python testing engineering track"
requires-python = ">=3.11"
dependencies = [
    "alembic>=1.14,<2",
    "fastapi>=0.115,<1",
    "httpx>=0.28,<1",
    "psycopg[binary]>=3.2,<4",
    "sqlalchemy[asyncio]>=2.0,<3",
]

[project.optional-dependencies]
dev = [
    "hypothesis>=6.156,<7",
    "mutmut>=3,<4",
    "nox>=2026.4,<2027",
    "pytest>=9,<10",
    "pytest-asyncio>=1.4,<2",
    "pytest-cov>=7,<8",
    "pytest-xdist>=3.8,<4",
    "testcontainers[postgres]>=4,<5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/order_service"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-config", "--strict-markers"]
asyncio_mode = "strict"
xfail_strict = true
markers = [
    "integration: requires a real infrastructure adapter",
    "contract: verifies a versioned HTTP or API contract",
    "e2e: exercises the complete application boundary",
    "property: generated or stateful property test",
    "docker: requires a Docker daemon",
]
filterwarnings = [
    "error::RuntimeWarning:order_service.*",
]

[tool.coverage.run]
branch = true
source = ["order_service"]

[tool.coverage.report]
show_missing = true
skip_covered = true

[tool.mutmut]
source_paths = ["src/order_service/domain"]
pytest_add_cli_args_test_selection = ["tests/unit", "tests/property"]
```

```python
# python-testing/lab/src/order_service/__init__.py
__version__ = "0.1.0"
```

Run: `cd python-testing/lab && uv lock && uv sync --extra dev`

Expected: `uv.lock` is created and the editable package plus dev tools install without resolution errors.

- [ ] **Step 4: Verify the green state and the default Docker-free contract**

Run: `cd python-testing/lab && uv run pytest -q`

Expected: `1 passed`; Docker is not contacted.

- [ ] **Step 5: Create the track README and condense the existing chapter into a bridge**

`python-testing/README.md` must include: audience, prerequisite links, the 00–11 chapter table, fast/integration/e2e command tiers, the fixed chapter template, a progress table initially marking only bootstrap complete, and links to `python-data/`, `python-concurrency/`, `performance-tuning-roadmap/`, `financial-consistency/`, `golang/testing/`, and `fastapi-ops/`.

Rewrite `python/12-testing.md` to contain exactly these top-level sections: `为什么 pytest 是默认选择`, `pytest 十分钟上手`, `unittest 与 doctest 什么时候仍然合理`, `下一步：Python 测试工程 track`, `Java/Go 对照框`, and `章末面试卡`. Keep one runnable assert example, one fixture example, and one parametrize example; move all advanced promises to the new track link. Put the three basics in `python-testing/lab/tests/unit/test_pytest_basics.py`, and copy its full contents verbatim into the bridge's single formal Python block.

Run: `cd python-testing/lab && uv run pytest tests/unit/test_pytest_basics.py -q`

Expected: `5 passed` from the dedicated bridge-basics file.

Run: `cd python-testing/lab && uv run pytest -q`

Expected: `6 passed` for the complete Task 1 suite after the bridge source is added.

Update the chapter-12 row and relationship section in `python/README.md` so they point to `../python-testing/README.md` for depth.

- [ ] **Step 6: Verify navigation and marker registration**

Run: `rg -n "python-testing|pytest|unittest|doctest" python/12-testing.md python/README.md python-testing/README.md`

Expected: all three files contain the track link and framework-selection language.

Run: `cd python-testing/lab && uv run pytest --markers | rg "integration|contract|e2e|property|docker"`

Expected: all five custom markers are listed with no unknown-marker warning.

- [ ] **Step 7: Commit bootstrap and bridge**

```bash
git add python-testing python/12-testing.md python/README.md
git commit -m "docs(python): bootstrap testing track"
```

### Task 2: Write the Testing Strategy and Risk Model Chapter

**Files:**
- Create: `python-testing/00-testing-strategy.md`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: test boundary names and command tiers established in Task 1.
- Produces: canonical definitions of `unit`, `component`, `integration`, `contract`, `e2e`, and `property/stateful`, plus the order-service risk matrix reused by later chapters.

- [ ] **Step 1: Write the chapter using the fixed eight-section template**

The chapter must include all of the following concrete content:

- a table separating business risk, failure example, cheapest trustworthy oracle, and required boundary;
- the order-service risks `金额/币种`, `非法状态转移`, `幂等键重复`, `数据库约束与事务`, `支付 HTTP 相容性`, `timeout 后结果未知`, `重复投递`, and `API 向后相容`;
- a decision model using feedback speed, fidelity, isolation, diagnosability, and maintenance cost;
- why test pyramid/diamond/honeycomb are heuristics rather than ratios;
- false-positive, false-negative, and environment-fidelity examples;
- a failure ticket where a mocked repository gives confidence while a Postgres unique constraint is missing;
- Java JUnit/Spring slice and Go package/integration comparisons;
- interview answers for `单元测试的 unit 到底是什么`, `为什么不能只看 coverage`, and `如何选择 E2E 数量`.

- [ ] **Step 2: Verify required anchors and links**

Run:

```bash
rg -n "反馈速度|失真|oracle|unit|component|integration|contract|e2e|property|幂等|timeout|coverage|python-data" python-testing/00-testing-strategy.md
```

Expected: every term appears in an explanatory section, not only in the table of contents.

- [ ] **Step 3: Update the progress map and commit**

Mark chapter 00 complete in `python-testing/README.md`.

```bash
git add python-testing/00-testing-strategy.md python-testing/README.md
git commit -m "docs(testing): define risk-based strategy"
```

### Task 3: Explain pytest's Execution Model with Runnable Failure Scenarios

**Files:**
- Create: `python-testing/01-pytest-execution-model.md`
- Create: `python-testing/lab/scenarios/collection/test_assertion_report.py`
- Create: `python-testing/lab/scenarios/collection/helpers.py`
- Create: `python-testing/lab/scenarios/collection/conftest.py`
- Create: `python-testing/lab/scenarios/collection/README.md`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: pytest configuration and the excluded-by-default `lab/scenarios/` convention from Task 1.
- Produces: exact mental model `Session → Package/Module/Class → Function`, node-ID syntax, collection/import diagnostics, and an assertion-rewriting scenario that later fixture/plugin chapters reference.

- [ ] **Step 1: Add an intentionally failing assertion scenario outside default testpaths**

```python
# python-testing/lab/scenarios/collection/helpers.py
from decimal import Decimal


def assert_total(got: Decimal, expected: Decimal) -> None:
    assert got == expected
```

```python
# python-testing/lab/scenarios/collection/conftest.py
import pytest

pytest.register_assert_rewrite("helpers")
```

```python
# python-testing/lab/scenarios/collection/test_assertion_report.py
from decimal import Decimal

from helpers import assert_total


def test_assert_rewrite_shows_both_operands() -> None:
    assert_total(Decimal("9.99"), Decimal("10.00"))
```

- [ ] **Step 2: Run collection and the failure separately**

Run: `cd python-testing/lab && uv run pytest --collect-only scenarios/collection -q`

Expected: exactly one node ID ending in `test_assertion_report.py::test_assert_rewrite_shows_both_operands`.

Run: `cd python-testing/lab && uv run pytest scenarios/collection/test_assertion_report.py -q`

Expected: FAIL and show both `Decimal('9.99')` and `Decimal('10.00')` inside the helper assertion report.

Run: `cd python-testing/lab && uv run pytest -q`

Expected: PASS; the intentionally failing scenario is not collected by default.

- [ ] **Step 3: Write the chapter and scenario README**

Cover: rootdir/config discovery, testpaths, collectors and node IDs, collection versus execution, import modes and `sys.modules`, assertion import hook and rewritten `.pyc`, conftest/plugin loading, marker registration, hook ordering at a conceptual level, `--collect-only`, `-k`, `-m`, `--setup-show`, traceback verbosity, and why plugin auto-loading can change behavior. The failure ticket is `本地单测能 import，CI collection 失败`; diagnose rootdir, editable install, duplicate module names, and import mode without adding `sys.path` hacks.

`scenarios/collection/README.md` must list the two commands above, explain why the failure is intentional, and state that the directory is excluded from default `testpaths`.

- [ ] **Step 4: Verify chapter claims against the runnable scenario**

Run: `rg -n "Session|Package|Module|Function|node ID|assert rewriting|import hook|rootdir|sys.modules|--collect-only|conftest|hook" python-testing/01-pytest-execution-model.md`

Expected: all mechanism anchors exist.

- [ ] **Step 5: Update progress and commit**

```bash
git add python-testing/01-pytest-execution-model.md python-testing/README.md python-testing/lab/scenarios/collection
git commit -m "docs(testing): explain pytest execution"
```

### Task 4: Build the Order Domain Test-First

**Files:**
- Create: `python-testing/02-test-design-and-tdd.md`
- Create: `python-testing/lab/src/order_service/domain/__init__.py`
- Create: `python-testing/lab/src/order_service/domain/order.py`
- Create: `python-testing/lab/tests/unit/test_order.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: only Python stdlib types; no framework or I/O dependency.
- Produces: `Money`, `OrderStatus`, `Order`, `InvalidAmount`, `InvalidCurrency`, `InvalidOrderTransition`, the keyword-only `Order.create` factory, exact package `__all__`, and idempotent `mark_paid` behavior used by later tasks.
- `Money.amount` accepts `Decimal` only. `Money(1.0, "USD")` raises `InvalidAmount` with a stable Decimal-specific diagnostic; production never coerces float.

- [ ] **Step 1: Reset production and enforce two-stage proof**

Delete existing Task 4 production and package exports, then reduce the focused test file. For every absent module, exception, class, enum, method, or package export:

1. write and run one narrow symbol/API test;
2. add only the minimal symbol or callable signature;
3. rerun that symbol/API test GREEN;
4. only then add a separate behavior test, run it until the public API executes and fails on an assertion, `DID NOT RAISE`, or the expected behavior/policy exception such as `TypeError`/`AttributeError`;
5. add only the minimal guard/mutation and rerun GREEN.

A collection/import/attribute failure proves only missing public surface. It must never be reported as evidence for a guard or mutation behind that surface.

- [ ] **Step 2: Introduce public symbols independently**

Use these separate RED→GREEN symbol/API cycles:

1. `test_order_module_exposes_money_type`: missing module/`Money` → add only `class Money`.
2. `test_order_module_exposes_invalid_amount_type`: missing exception → add only the `ValueError` subtype.
3. `test_order_module_exposes_invalid_currency_type`: missing exception → add only the `ValueError` subtype.
4. `test_order_module_exposes_order_status_type`: missing enum → add only an empty plain `Enum`.
5. `test_order_module_exposes_order_type`: missing aggregate → add only `class Order`.
6. `test_order_type_exposes_create_factory`: missing factory → add a callable, permissive classmethod that returns `None`.
7. `test_order_module_exposes_invalid_order_transition_type`: missing exception → add only the `RuntimeError` subtype.
8. `test_order_type_exposes_start_payment_method`: missing method → add a no-op signature.
9. `test_order_type_exposes_mark_payment_failed_method`: missing method → add a no-op signature.
10. `test_order_type_exposes_mark_paid_method`: missing method → add a no-op signature.
11. `test_domain_package_exposes_public_order_symbols`: missing package attributes → add only the six imports, without `__all__`.

Each corresponding behavior must remain unimplemented until its later behavioral RED.

- [ ] **Step 3: Build `Money` with executable behavioral REDs**

After the relevant symbols are green:

1. `test_money_accepts_positive_decimal`: `Money() takes no arguments` → add only mutable, non-slotted dataclass fields.
2. `test_money_is_immutable`: assignment reports `DID NOT RAISE FrozenInstanceError` → add only `frozen=True`.
3. `test_money_uses_slots_without_instance_dict`: the frozen instance still has `__dict__` → add only `slots=True`.
4. `test_money_rejects_float_amount`: `DID NOT RAISE InvalidAmount` → add only the Decimal type guard and stable diagnostic.
5. `test_money_rejects_non_positive_amount` for zero, negative integer, and negative fraction: three `DID NOT RAISE` failures → add only the positive guard.
6. `test_money_normalizes_valid_currency`: lowercase assertion failure → add uppercase normalization.
7. `test_money_rejects_invalid_currency_code` for blank, short, non-alpha, and long values: four `DID NOT RAISE` failures → add only the documented three-letter alphabetic guard.

Do not add arithmetic, rounding, float conversion, currency conversion, or a currency allowlist.

- [ ] **Step 4: Specify exact enum policy after the enum symbol exists**

Run `test_order_status_has_exact_public_members_and_values` against the empty enum and observe `[]` versus the four expected pairs. Then add exactly:

- `PENDING_PAYMENT = "pending_payment"`
- `PAYMENT_IN_PROGRESS = "payment_in_progress"`
- `PAYMENT_FAILED = "payment_failed"`
- `PAID = "paid"`

Keep the enum as a plain `Enum` for that member-policy GREEN. Then run `test_order_status_interoperates_with_strings` and observe `isinstance(OrderStatus.PAID, str)` fail. Switch only the enum base/import to `StrEnum`, and rerun both the interoperability and exact-member tests GREEN.

- [ ] **Step 5: Build `Order.create` through separate signature and behavior cycles**

After `Order` and callable `create` are green:

1. `test_order_create_rejects_positional_invocation`: permissive factory reports `DID NOT RAISE TypeError` → add only the keyword-only `*`.
2. `test_order_create_requires_each_named_field`: optional arguments produce four `DID NOT RAISE TypeError` failures → make all four keyword-only arguments required while still returning `None`.
3. `test_order_create_preserves_required_fields_at_version_one`: required factory returns `None` → add only aggregate fields/defaults and successful construction.
4. `test_order_create_rejects_blank_idempotency_key`: empty and whitespace keys execute and report `DID NOT RAISE` → add the blank-key guard.
5. `test_order_create_rejects_naive_timestamp`: naive time executes and reports `DID NOT RAISE` → add the timezone-aware guard.

Use deterministic `ORDER_ID`, UTC `NOW`, and `Decimal` totals.

- [ ] **Step 6: Build each successful transition after its method symbol**

1. With no-op `start_payment`, run `test_start_payment_retries_failed_order_and_increments_version`; observe unchanged failed state, then implement only failed→in-progress.
2. Run `test_start_payment_moves_pending_order_and_increments_version`; observe unchanged pending state, then extend the legal mutation to pending.
3. With no-op `mark_payment_failed`, run `test_mark_payment_failed_moves_in_progress_order_and_increments_version`; observe unchanged in-progress state, then add only the successful failed transition.
4. With no-op `mark_paid`, run `test_mark_paid_moves_in_progress_order_and_records_reference`; observe unchanged state, then add only paid status/reference/version mutation.

Every success test asserts status, payment reference, and exact version.

- [ ] **Step 7: Build replay and provider-reference guards behavior-first**

1. `test_mark_paid_same_reference_replay_preserves_paid_state`: observe version 4, then add only the same-reference early return.
2. `test_mark_paid_rejects_different_reference_and_preserves_paid_state`: observe `DID NOT RAISE InvalidOrderTransition`, then add only the mismatched paid replay rejection.
3. `test_mark_paid_rejects_blank_provider_reference_without_mutation`: observe `DID NOT RAISE ValueError`, then add only the blank-reference guard.

Same-reference and different-reference cases remain distinct. Both assert stored status/reference/version.

- [ ] **Step 8: Add the exhaustive illegal-transition matrix before legality guards**

Parameterize `test_illegal_transition_matrix_preserves_order_state` with exactly these illegal source→target rows:

- `start_payment`: `PAYMENT_IN_PROGRESS → PAYMENT_IN_PROGRESS`, `PAID → PAYMENT_IN_PROGRESS`;
- `mark_payment_failed`: `PENDING_PAYMENT → PAYMENT_FAILED`, `PAYMENT_FAILED → PAYMENT_FAILED`, `PAID → PAYMENT_FAILED`;
- `mark_paid`: `PENDING_PAYMENT → PAID`, `PAYMENT_FAILED → PAID`.

Before guards, run the matrix and require all seven rows to execute their method and fail with `DID NOT RAISE InvalidOrderTransition`. Then add the three legality guards and shared source→target diagnostic. Each row must assert the diagnostic and preservation of status, payment reference, and version. Rerun all seven GREEN.

- [ ] **Step 9: Separate package symbols from exact export policy**

After the six package attributes are green, add `test_domain_package_all_is_exact_public_order_api`. Observe that `__all__` is absent, then add exactly:

```text
InvalidAmount
InvalidCurrency
InvalidOrderTransition
Money
Order
OrderStatus
```

Do not use explicit imports alone as proof of exact `__all__`.

- [ ] **Step 10: Write the chapter around the executed proof chain**

Use the fixed eight-section structure. Cover behavior versus implementation, Arrange-Act-Assert/Given-When-Then, one failure reason, executable-policy names, equivalence classes/boundaries, exception-message brittleness, deterministic time/IDs, coverage versus assertion quality, mutation testing, Classical versus London TDD, and the private-call-order failure ticket.

Every formal Python block must be byte-for-byte identical to the complete runnable `order.py` or `test_order.py`. The failure ticket must name the runnable regression `test_mark_paid_moves_in_progress_order_and_records_reference`.

- [ ] **Step 11: Run exact final verification and amend Task 4**

From `python-testing/lab/`:

```bash
uv run pytest tests/unit/test_order.py -q
uv run pytest tests/unit -q
uv run pytest -q
```

From the worktree root:

```bash
python3 -c 'import re; from pathlib import Path; chapter=Path("python-testing/02-test-design-and-tdd.md").read_text(); blocks=re.findall(r"```python\n(.*?)```", chapter, re.S); sources=[Path(p).read_text() for p in ["python-testing/lab/src/order_service/domain/order.py", "python-testing/lab/tests/unit/test_order.py"]]; assert blocks == sources'
python3 -c 'import re; from pathlib import Path; f=Path("python-testing/02-test-design-and-tdd.md"); targets=re.findall(r"\[[^]]+\]\(([^)]+)\)", f.read_text()); local=[t for t in targets if not t.startswith(("http://", "https://", "#"))]; missing=[t for t in local if not (f.parent / t.split("#",1)[0]).exists()]; assert not missing, missing'
rg -n '^## ' python-testing/02-test-design-and-tdd.md
rg -n "behavior|Arrange|Given|失败理由|测试名|等价类|边界|异常|确定性|coverage|mutation|London|Classical|私有|调用顺序" python-testing/02-test-design-and-tdd.md
git diff --check
git diff -- .superpowers/sdd/progress.md
```

Do not encode a permanent cumulative suite count in the plan or README. Stage only the Task 4 files and this Task 4 plan section, then amend the existing Task 4 commit with `git commit --amend --no-edit`.

### Task 5: Build Fixture Graphs and Test-Data Factories

**Files:**
- Create: `python-testing/03-fixtures-and-parametrization.md`
- Create: `python-testing/lab/tests/__init__.py`
- Create: `python-testing/lab/tests/factories.py`
- Create: `python-testing/lab/tests/conftest.py`
- Create: `python-testing/lab/tests/unit/test_order_factory.py`
- Create: `python-testing/lab/scenarios/fixture-leak/conftest.py`
- Create: `python-testing/lab/scenarios/fixture-leak/test_leak.py`
- Create: `python-testing/lab/scenarios/fixture-leak/README.md`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: `Order.create`, `Money`, and deterministic constants from Task 4.
- Produces: typed `OrderFactory = Callable[..., Order]`, function-scoped `order_factory`, and the repository-wide rule that mutable domain objects are never returned from session/module-scoped fixtures.

- [ ] **Step 1: Write a failing freshness test for the factory fixture**

```python
# python-testing/lab/tests/unit/test_order_factory.py
from tests.factories import OrderFactory


def test_order_factory_returns_fresh_objects(order_factory: OrderFactory) -> None:
    first = order_factory()
    second = order_factory()
    first.start_payment()
    assert second.status.value == "pending_payment"
```

Run: `cd python-testing/lab && uv run pytest tests/unit/test_order_factory.py -q`

Expected: FAIL during collection because `tests.factories` and `order_factory` do not exist.

- [ ] **Step 2: Add a typed factory and function-scoped fixture**

```python
# python-testing/lab/tests/factories.py
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias
from uuid import UUID

from order_service.domain.order import Money, Order

OrderFactory: TypeAlias = Callable[..., Order]


def make_order(
    *,
    order_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
    idempotency_key: str = "create-001",
    amount: Decimal = Decimal("10.00"),
    currency: str = "USD",
    created_at: datetime = datetime(2026, 7, 15, tzinfo=UTC),
) -> Order:
    return Order.create(
        order_id=order_id,
        idempotency_key=idempotency_key,
        total=Money(amount, currency),
        created_at=created_at,
    )
```

```python
# python-testing/lab/tests/conftest.py
import pytest

from tests.factories import OrderFactory, make_order


@pytest.fixture
def order_factory() -> OrderFactory:
    return make_order
```

Run: `cd python-testing/lab && uv run pytest tests/unit/test_order_factory.py -q`

Expected: `1 passed`.

- [ ] **Step 3: Add a deterministic state-leak reproduction excluded from defaults**

```python
# python-testing/lab/scenarios/fixture-leak/conftest.py
import pytest

from tests.factories import make_order


@pytest.fixture(scope="module")
def shared_order():
    return make_order()
```

```python
# python-testing/lab/scenarios/fixture-leak/test_leak.py
def test_a_mutates_shared_order(shared_order) -> None:
    shared_order.start_payment()


def test_b_expected_fresh_order(shared_order) -> None:
    assert shared_order.status.value == "pending_payment"
```

Run: `cd python-testing/lab && uv run pytest scenarios/fixture-leak -q`

Expected: first test passes and second test fails because the module-scoped mutable object leaked state.

- [ ] **Step 4: Write the chapter and failure-scenario README**

Cover: fixture dependency DAG, request-time lookup by name, cache per scope, scope mismatch, yield/finalizer LIFO teardown, teardown after setup failure, factory fixture versus object fixture, indirect parametrization, `request.param`, readable IDs, conftest visibility, plugin fixtures, autouse risk, and why session scope is an ownership decision rather than a speed switch. The failure ticket starts from the scenario above and fixes it by returning a factory or using function scope.

- [ ] **Step 5: Verify fast tests remain isolated and commit**

Run: `cd python-testing/lab && uv run pytest tests/unit -q --setup-show`

Expected: all unit tests pass; `order_factory` is set up and torn down per test.

```bash
git add python-testing/03-fixtures-and-parametrization.md python-testing/README.md python-testing/lab/tests python-testing/lab/scenarios/fixture-leak
git commit -m "docs(testing): teach fixture ownership"
```

### Task 6: Add Application Ports, Handwritten Fakes, and Idempotent Creation

**Files:**
- Create: `python-testing/04-test-doubles-and-seams.md`
- Create: `python-testing/lab/src/order_service/application/__init__.py`
- Create: `python-testing/lab/src/order_service/application/messages.py`
- Create: `python-testing/lab/src/order_service/application/create_order.py`
- Create: `python-testing/lab/src/order_service/ports/__init__.py`
- Create: `python-testing/lab/src/order_service/ports/uow.py`
- Create: `python-testing/lab/src/order_service/ports/system.py`
- Create: `python-testing/lab/src/order_service/adapters/__init__.py`
- Create: `python-testing/lab/src/order_service/adapters/memory.py`
- Create: `python-testing/lab/tests/component/test_create_order.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: `Order`, `Money`, `OrderFactory`, and async pytest strict mode.
- Produces: `CreateOrderCommand`, `OutboxMessage`, `CreateOrder.execute`, `OrderRepository`, `OutboxRepository`, `UnitOfWork`, `Clock`, `IdGenerator`, `MemoryUnitOfWork`, `FrozenClock`, and `SequenceIdGenerator`. Later SQL and HTTP tasks implement these protocols without changing their signatures.

- [ ] **Step 1: Write component tests for idempotency and atomic outbox intent**

```python
# python-testing/lab/tests/component/test_create_order.py
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from order_service.adapters.memory import FrozenClock, MemoryStore, MemoryUnitOfWork, SequenceIdGenerator
from order_service.application.create_order import CreateOrder
from order_service.application.messages import CreateOrderCommand


@pytest.mark.asyncio
async def test_create_order_writes_order_and_payment_request_once() -> None:
    store = MemoryStore()
    use_case = CreateOrder(
        uow_factory=lambda: MemoryUnitOfWork(store),
        ids=SequenceIdGenerator(
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ),
        clock=FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )
    command = CreateOrderCommand("create-001", Decimal("10.00"), "USD")

    first = await use_case.execute(command)
    second = await use_case.execute(command)

    assert second.id == first.id
    assert len(store.orders) == 1
    assert len(store.outbox) == 1
    assert store.commits == 2
    assert store.outbox[0].topic == "payment_requested"
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_create_order.py -q`

Expected: FAIL during collection because application and memory adapter modules do not exist.

- [ ] **Step 2: Define commands, messages, and stable protocols**

```python
# python-testing/lab/src/order_service/application/messages.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    idempotency_key: str
    amount: Decimal
    currency: str


@dataclass(slots=True)
class OutboxMessage:
    id: UUID
    topic: str
    aggregate_id: UUID
    payload: dict[str, str]
    occurred_at: datetime
    attempts: int = 0
    available_at: datetime | None = None
    claimed_at: datetime | None = None
    done: bool = False
```

```python
# python-testing/lab/src/order_service/ports/uow.py
from collections.abc import Callable
from typing import Protocol, TypeAlias
from uuid import UUID

from order_service.application.messages import OutboxMessage
from order_service.domain.order import Order


class OrderRepository(Protocol):
    async def get(self, order_id: UUID) -> Order | None: ...
    async def get_by_idempotency_key(self, key: str) -> Order | None: ...
    async def add(self, order: Order) -> None: ...
    async def save(self, order: Order) -> None: ...


class OutboxRepository(Protocol):
    async def add(self, message: OutboxMessage) -> None: ...
    async def claim_batch(self, *, limit: int, now) -> list[OutboxMessage]: ...
    async def mark_done(self, message_id: UUID) -> None: ...
    async def mark_failed(self, message_id: UUID, *, available_at) -> None: ...


class UnitOfWork(Protocol):
    orders: OrderRepository
    outbox: OutboxRepository
    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]
```

Use `datetime` for both untyped `now`/`available_at` parameters in the actual file; the abbreviated signatures above must be expanded to `datetime` imports so type checking remains explicit.

```python
# python-testing/lab/src/order_service/ports/system.py
from datetime import datetime
from typing import Protocol
from uuid import UUID


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new(self) -> UUID: ...
```

- [ ] **Step 3: Implement deterministic memory fakes and the use case**

Implement `memory.py` with these complete ownership rules:

```python
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from order_service.application.messages import OutboxMessage
from order_service.domain.order import Order


@dataclass
class MemoryStore:
    orders: dict[UUID, Order] = field(default_factory=dict)
    outbox: list[OutboxMessage] = field(default_factory=list)
    commits: int = 0


class MemoryOrderRepository:
    def __init__(self, orders: dict[UUID, Order]) -> None:
        self._orders = orders

    async def get(self, order_id: UUID) -> Order | None:
        return self._orders.get(order_id)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        return next((order for order in self._orders.values() if order.idempotency_key == key), None)

    async def add(self, order: Order) -> None:
        self._orders[order.id] = order

    async def save(self, order: Order) -> None:
        self._orders[order.id] = order


class MemoryOutboxRepository:
    def __init__(self, messages: list[OutboxMessage]) -> None:
        self._messages = messages

    async def add(self, message: OutboxMessage) -> None:
        self._messages.append(message)

    async def claim_batch(self, *, limit: int, now: datetime) -> list[OutboxMessage]:
        claimed: list[OutboxMessage] = []
        for message in self._messages:
            due = message.available_at is None or message.available_at <= now
            lease_available = (
                message.claimed_at is None
                or message.claimed_at <= now - timedelta(seconds=30)
            )
            if not message.done and lease_available and due:
                message.claimed_at = now
                claimed.append(message)
                if len(claimed) == limit:
                    break
        return claimed

    async def mark_done(self, message_id: UUID) -> None:
        message = next(item for item in self._messages if item.id == message_id)
        message.done = True
        message.claimed_at = None

    async def mark_failed(self, message_id: UUID, *, available_at: datetime) -> None:
        message = next(item for item in self._messages if item.id == message_id)
        message.attempts += 1
        message.available_at = available_at
        message.claimed_at = None


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def __aenter__(self) -> "MemoryUnitOfWork":
        self._orders = deepcopy(self._store.orders)
        self._outbox = deepcopy(self._store.outbox)
        self.orders = MemoryOrderRepository(self._orders)
        self.outbox = MemoryOutboxRepository(self._outbox)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self._store.orders = deepcopy(self._orders)
        self._store.outbox = deepcopy(self._outbox)
        self._store.commits += 1


@dataclass(frozen=True)
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class SequenceIdGenerator:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)

    def new(self) -> UUID:
        try:
            return next(self._values)
        except StopIteration as exc:
            raise RuntimeError("no IDs remaining") from exc
```

```python
# python-testing/lab/src/order_service/application/create_order.py
from order_service.application.messages import CreateOrderCommand, OutboxMessage
from order_service.domain.order import Money, Order
from order_service.ports.system import Clock, IdGenerator
from order_service.ports.uow import UnitOfWorkFactory


class CreateOrder:
    def __init__(self, uow_factory: UnitOfWorkFactory, ids: IdGenerator, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._ids = ids
        self._clock = clock

    async def execute(self, command: CreateOrderCommand) -> Order:
        async with self._uow_factory() as uow:
            existing = await uow.orders.get_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                await uow.commit()
                return existing
            now = self._clock.now()
            order = Order.create(
                order_id=self._ids.new(),
                idempotency_key=command.idempotency_key,
                total=Money(command.amount, command.currency),
                created_at=now,
            )
            await uow.orders.add(order)
            await uow.outbox.add(
                OutboxMessage(
                    id=self._ids.new(),
                    topic="payment_requested",
                    aggregate_id=order.id,
                    payload={"order_id": str(order.id)},
                    occurred_at=now,
                    available_at=now,
                )
            )
            await uow.commit()
            return order
```

- [ ] **Step 4: Verify component behavior and make fake rollback observable**

Run: `cd python-testing/lab && uv run pytest tests/component/test_create_order.py -q`

Expected: `1 passed`.

Add the exact rollback-fidelity test:

```python
@pytest.mark.asyncio
async def test_create_order_does_not_publish_partial_state_when_message_id_fails() -> None:
    store = MemoryStore()
    use_case = CreateOrder(
        lambda: MemoryUnitOfWork(store),
        SequenceIdGenerator(UUID("00000000-0000-0000-0000-000000000001")),
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )
    with pytest.raises(RuntimeError, match="no IDs remaining"):
        await use_case.execute(CreateOrderCommand("create-001", Decimal("10.00"), "USD"))
    assert store.orders == {}
    assert store.outbox == []
    assert store.commits == 0
```

Run the component file and expect two passing tests; this prevents the fake from lying about transaction atomicity.

- [ ] **Step 5: Write the chapter**

Cover the Meszaros taxonomy (dummy/stub/spy/mock/fake), state versus interaction verification, consumer-defined ports, constructor/dependency injection, `Mock(spec_set=...)`, `create_autospec`, `side_effect`, patch-at-lookup-site, async mocks, time/random/UUID seams, fake fidelity contracts, and why mocking SQLAlchemy query chains tests the mock. The failure ticket patches the definition site and accidentally performs a real payment call; show the import binding that explains it.

- [ ] **Step 6: Run fast tests and commit**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component -q`

Expected: all tests pass without Docker.

```bash
git add python-testing/04-test-doubles-and-seams.md python-testing/README.md python-testing/lab/src/order_service/application python-testing/lab/src/order_service/ports python-testing/lab/src/order_service/adapters python-testing/lab/tests/component
git commit -m "feat(testing-lab): add testable order use case"
```

### Task 7: Add FastAPI Component Tests without a Network Process

**Files:**
- Create: `python-testing/05-component-and-api-tests.md`
- Create: `python-testing/lab/src/order_service/api/__init__.py`
- Create: `python-testing/lab/src/order_service/api/dependencies.py`
- Create: `python-testing/lab/src/order_service/api/schemas.py`
- Create: `python-testing/lab/src/order_service/api/app.py`
- Create: `python-testing/lab/tests/component/test_api.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: `CreateOrder.execute` and FastAPI dependency overrides.
- Produces: `create_app() -> FastAPI`, dependency provider `get_create_order() -> CreateOrder`, and POST `/orders` contract with `Idempotency-Key`, decimal amount, currency, ID, status, and version.

- [ ] **Step 1: Write the failing in-process API test**

```python
# python-testing/lab/tests/component/test_api.py
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from order_service.adapters.memory import FrozenClock, MemoryStore, MemoryUnitOfWork, SequenceIdGenerator
from order_service.api.app import create_app
from order_service.api.dependencies import get_create_order
from order_service.application.create_order import CreateOrder


@pytest.mark.asyncio
async def test_create_order_returns_public_contract() -> None:
    store = MemoryStore()
    use_case = CreateOrder(
        lambda: MemoryUnitOfWork(store),
        SequenceIdGenerator(
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ),
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )
    app = create_app()
    app.dependency_overrides[get_create_order] = lambda: use_case
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/orders",
                headers={"Idempotency-Key": "create-001"},
                json={"amount": "10.00", "currency": "usd"},
            )
    assert response.status_code == 201
    assert response.json() == {
        "id": "00000000-0000-0000-0000-000000000001",
        "status": "pending_payment",
        "amount": "10.00",
        "currency": "USD",
        "version": 1,
    }
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_api.py -q`

Expected: FAIL during collection because `order_service.api` does not exist.

- [ ] **Step 2: Add schemas, dependency seam, lifespan, and route**

```python
# python-testing/lab/src/order_service/api/dependencies.py
from order_service.application.create_order import CreateOrder


def get_create_order() -> CreateOrder:
    raise RuntimeError("CreateOrder dependency is not configured")
```

`CreateOrderRequest` uses `Decimal` amount with `gt=0` and a three-letter currency pattern. `OrderResponse` uses UUID, status string, Decimal amount, uppercase currency, and integer version. Configure JSON output so Decimal remains a string.

```python
# python-testing/lab/src/order_service/api/app.py
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, status

from order_service.api.dependencies import get_create_order
from order_service.api.schemas import CreateOrderRequest, OrderResponse
from order_service.application.create_order import CreateOrder
from order_service.application.messages import CreateOrderCommand


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ready = True
        yield
        app.state.ready = False

    app = FastAPI(title="Order Service Testing Lab", version="1.0.0", lifespan=lifespan)

    @app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
    async def create_order(
        body: CreateOrderRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        use_case: Annotated[CreateOrder, Depends(get_create_order)],
    ) -> OrderResponse:
        order = await use_case.execute(
            CreateOrderCommand(idempotency_key, body.amount, body.currency)
        )
        return OrderResponse.from_domain(order)

    return app
```

- [ ] **Step 3: Verify success, validation, lifespan, and override cleanup**

Run: `cd python-testing/lab && uv run pytest tests/component/test_api.py -q`

Expected: the public-contract test passes.

Refactor setup into an `app` fixture that yields the configured app and calls `app.dependency_overrides.clear()` after yield. Add an async client fixture that owns `app.router.lifespan_context(app)` and `httpx.AsyncClient`. Then add these exact behaviors:

```python
import pytest_asyncio


@pytest.fixture
def use_case() -> CreateOrder:
    store = MemoryStore()
    return CreateOrder(
        lambda: MemoryUnitOfWork(store),
        SequenceIdGenerator(
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ),
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )


@pytest.fixture
def app(use_case: CreateOrder):
    application = create_app()
    application.dependency_overrides[get_create_order] = lambda: use_case
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
            yield value


@pytest.mark.asyncio
async def test_missing_idempotency_header_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post("/orders", json={"amount": "10.00", "currency": "USD"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_zero_amount_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/orders",
        headers={"Idempotency-Key": "create-001"},
        json={"amount": "0", "currency": "USD"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_same_order(client: httpx.AsyncClient) -> None:
    request = {
        "headers": {"Idempotency-Key": "create-001"},
        "json": {"amount": "10.00", "currency": "usd"},
    }
    first = await client.post("/orders", **request)
    second = await client.post("/orders", **request)
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_lifespan_marks_application_ready(app, client: httpx.AsyncClient) -> None:
    assert app.state.ready is True
```

Together with the original public-contract test, expect five passing tests. Run the same file a second time and expect the same five passes; do not introduce a repeat plugin only for this check.

- [ ] **Step 4: Write the chapter**

Cover component boundaries, ASGITransport versus a real network process, TestClient versus AsyncClient, lifespan ownership, dependency override cleanup, request validation, error-handler contracts, structured log assertions with `caplog`, snapshot/golden trade-offs, OpenAPI as a contract artifact, and why route tests must not mock the function being verified. The failure ticket is a dependency override that leaks into the next test.

- [ ] **Step 5: Run fast tests and commit**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component -q`

Expected: all tests pass and no Docker process starts.

```bash
git add python-testing/05-component-and-api-tests.md python-testing/README.md python-testing/lab/src/order_service/api python-testing/lab/tests/component/test_api.py
git commit -m "feat(testing-lab): add API component boundary"
```

### Task 8: Add Real Postgres, Migrations, and Async Unit of Work

**Files:**
- Create: `python-testing/06-database-integration.md`
- Create: `python-testing/lab/alembic.ini`
- Create: `python-testing/lab/migrations/env.py`
- Create: `python-testing/lab/migrations/script.py.mako`
- Create: `python-testing/lab/migrations/versions/0001_orders_and_outbox.py`
- Create: `python-testing/lab/src/order_service/adapters/sqlalchemy.py`
- Create: `python-testing/lab/tests/integration/conftest.py`
- Create: `python-testing/lab/tests/integration/test_migrations.py`
- Create: `python-testing/lab/tests/integration/test_sqlalchemy_uow.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: final repository/UoW protocols and Order/OutboxMessage mappings from Tasks 4 and 6.
- Produces: `orders` and `outbox_messages` tables, `SQLAlchemyUnitOfWork`, `ConcurrentOrderUpdate`, session factory fixture, and marker contract `integration + docker`.

- [ ] **Step 1: Write a failing committed-visibility integration test**

```python
# python-testing/lab/tests/integration/test_sqlalchemy_uow.py
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from order_service.adapters.sqlalchemy import SQLAlchemyUnitOfWork
from order_service.domain.order import Money, Order

pytestmark = [pytest.mark.integration, pytest.mark.docker]


@pytest.mark.asyncio
async def test_committed_order_is_visible_to_a_new_uow(session_factory) -> None:
    order = Order.create(
        order_id=UUID("00000000-0000-0000-0000-000000000001"),
        idempotency_key="create-001",
        total=Money(Decimal("10.00"), "USD"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        loaded = await uow.orders.get(order.id)
    assert loaded == order
```

Run: `cd python-testing/lab && uv run pytest tests/integration/test_sqlalchemy_uow.py -q`

Expected: FAIL during collection because the SQLAlchemy adapter and fixture do not exist. If Docker is unavailable, record that prerequisite separately; do not change the expected red reason.

- [ ] **Step 2: Create the exact schema migration**

The `orders` table has: UUID `id` primary key, unique non-null `idempotency_key`, numeric(18,2) `amount`, char(3) `currency`, non-null `status`, timezone-aware `created_at`, nullable `payment_reference`, and integer `version`.

The `outbox_messages` table has: UUID `id` primary key, non-null `topic`, UUID `aggregate_id`, JSONB `payload`, timezone-aware `occurred_at`, integer `attempts` default 0, timezone-aware nullable `available_at` and `claimed_at`, and boolean `done` default false. Add an index on `(done, available_at, claimed_at)`.

`upgrade()` creates both tables and index. `downgrade()` drops the index, outbox table, then orders table. `migrations/env.py` reads the URL from Alembic config and runs synchronous psycopg migrations; application data access remains async.

- [ ] **Step 3: Implement explicit domain/table mapping and optimistic save**

`SQLAlchemyOrderRepository.add` executes an insert. `get` and `get_by_idempotency_key` map rows to `Order`. `save` performs an update with `WHERE id = :id AND version = :expected`, where `expected = order.version - 1`; if `rowcount != 1`, raise `ConcurrentOrderUpdate(order.id)`.

`SQLAlchemyOutboxRepository` implements all four protocol methods. `claim_batch` uses a transaction-scoped `SELECT ... FOR UPDATE SKIP LOCKED`, filters due messages whose claim is absent or older than the fixed 30-second lease, updates `claimed_at`, and returns mapped messages. This lease rule must match `MemoryOutboxRepository` so a crashed/cancelled worker cannot strand a message forever.

`SQLAlchemyUnitOfWork` creates one AsyncSession on enter, exposes both repositories, rolls back on any uncommitted exit, closes on exit, and commits only when explicitly requested.

- [ ] **Step 4: Add session-scoped container and real-commit cleanup fixtures**

`postgres_url` uses `PostgresContainer("postgres:16-alpine", driver=None)` at session scope. Convert `postgresql://` to `postgresql+psycopg://` for `create_async_engine`; keep `postgresql+psycopg://` usable by Alembic's synchronous engine.

Before the session, run `alembic upgrade head`. After every integration test, execute `TRUNCATE TABLE outbox_messages, orders CASCADE`; do not wrap tests in a hidden outer rollback because this track must test real commit visibility.

- [ ] **Step 5: Verify migrations, uniqueness, rollback, and optimistic conflict**

Add these exact tests (use complete imports and unique UUID constants in the actual files):

```python
# test_migrations.py
@pytest.mark.asyncio
async def test_upgrade_creates_orders_and_outbox(alembic_config, async_engine) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    async with async_engine.connect() as connection:
        tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
    assert {"orders", "outbox_messages"} <= tables
```

```python
# test_sqlalchemy_uow.py
@pytest.mark.asyncio
async def test_duplicate_idempotency_key_uses_real_postgres_constraint(session_factory) -> None:
    first = make_order(order_id=UUID(int=1), idempotency_key="same-key")
    second = make_order(order_id=UUID(int=2), idempotency_key="same-key")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(first)
        await uow.commit()
    with pytest.raises(IntegrityError):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.add(second)
            await uow.commit()


@pytest.mark.asyncio
async def test_exit_without_commit_rolls_back(session_factory) -> None:
    order = make_order(order_id=UUID(int=3))
    with pytest.raises(RuntimeError, match="abort"):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.add(order)
            raise RuntimeError("abort")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.orders.get(order.id) is None


@pytest.mark.asyncio
async def test_stale_save_raises_concurrent_update(session_factory) -> None:
    order = make_order(order_id=UUID(int=4))
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as first_uow:
        first = await first_uow.orders.get(order.id)
    async with SQLAlchemyUnitOfWork(session_factory) as second_uow:
        second = await second_uow.orders.get(order.id)
    assert first is not None and second is not None
    first.start_payment()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.save(first)
        await uow.commit()
    second.start_payment()
    with pytest.raises(ConcurrentOrderUpdate):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.save(second)
            await uow.commit()
```

Keep the committed-visibility test from Step 1 as the fifth behavior.

Run: `cd python-testing/lab && uv run pytest tests/integration -q`

Expected: all five behaviors pass against Postgres 16.

- [ ] **Step 6: Prove the default suite remains Docker-free**

Stop Docker or unset its socket for this one command if convenient.

Run: `cd python-testing/lab && uv run pytest -q`

Expected: fast tests pass; integration tests are not in the default `testpaths` selection only if default addopts excludes `docker`. Update `addopts` to include `-m not docker` so `uv run pytest` always honors this contract.

- [ ] **Step 7: Write the chapter and commit**

Cover real database fidelity, transaction ownership, rollback-fixture blind spots, nested transaction/savepoint alternatives, Testcontainers lifecycle, schema/migration tests, unique/check constraints, isolation/locks, optimistic conflict, query-count assertions, N+1 regression, cleanup under failure, container diagnostics, and why SQLite is not a Postgres substitute. Link deep mechanisms to `python-data/`.

```bash
git add python-testing/06-database-integration.md python-testing/README.md python-testing/lab/alembic.ini python-testing/lab/migrations python-testing/lab/src/order_service/adapters/sqlalchemy.py python-testing/lab/tests/integration python-testing/lab/pyproject.toml
git commit -m "feat(testing-lab): add Postgres integration"
```

### Task 9: Add the Payment HTTP Adapter and Contract Tests

**Files:**
- Create: `python-testing/07-http-and-contract-testing.md`
- Create: `python-testing/lab/src/order_service/ports/payment.py`
- Create: `python-testing/lab/src/order_service/application/process_payment.py`
- Create: `python-testing/lab/src/order_service/adapters/payment_http.py`
- Create: `python-testing/lab/tests/contract/fake_provider.py`
- Create: `python-testing/lab/tests/contract/test_payment_contract.py`
- Create: `python-testing/lab/tests/component/test_process_payment.py`
- Modify: `python-testing/lab/src/order_service/adapters/memory.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: `Order.start_payment`, `mark_paid`, `mark_payment_failed`, `UnitOfWorkFactory`, and HTTPX.
- Produces: `PaymentGateway.charge`, `PaymentGateway.refund`, `PaymentResult`, `PaymentDeclined`, `PaymentUncertain`, `HTTPPaymentGateway`, and `ProcessPayment.execute(order_id)`. Task 10 invokes this use case from the worker; Task 15 uses the same gateway refund signature.

- [ ] **Step 1: Write the component test for an uncertain outcome**

```python
# python-testing/lab/tests/component/test_process_payment.py
from uuid import UUID

import pytest

from order_service.adapters.memory import MemoryStore, MemoryUnitOfWork, StubPaymentGateway
from order_service.application.process_payment import ProcessPayment
from order_service.ports.payment import PaymentUncertain
from tests.factories import make_order


@pytest.mark.asyncio
async def test_timeout_leaves_order_in_progress_for_reconciliation() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentUncertain("provider timeout"))
    use_case = ProcessPayment(lambda: MemoryUnitOfWork(store), gateway)

    with pytest.raises(PaymentUncertain, match="provider timeout"):
        await use_case.execute(order.id)

    assert store.orders[order.id].status.value == "payment_in_progress"
    assert store.commits == 1
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_process_payment.py -q`

Expected: FAIL during collection because payment ports and use case do not exist.

- [ ] **Step 2: Define the gateway result and uncertainty contract**

```python
# python-testing/lab/src/order_service/ports/payment.py
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from order_service.domain.order import Money


class PaymentDeclined(RuntimeError):
    pass


class PaymentUncertain(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PaymentResult:
    reference: str


class PaymentGateway(Protocol):
    async def charge(
        self,
        *,
        order_id: UUID,
        total: Money,
        idempotency_key: str,
    ) -> PaymentResult: ...

    async def refund(
        self,
        *,
        payment_reference: str,
        total: Money,
        idempotency_key: str,
    ) -> PaymentResult: ...
```

- [ ] **Step 3: Implement the two-transaction payment use case**

```python
# python-testing/lab/src/order_service/application/process_payment.py
from uuid import UUID

from order_service.domain.order import InvalidOrderTransition, Order, OrderStatus
from order_service.ports.payment import PaymentDeclined, PaymentGateway, PaymentUncertain
from order_service.ports.uow import UnitOfWorkFactory


class OrderNotFound(LookupError):
    pass


class ProcessPayment:
    def __init__(self, uow_factory: UnitOfWorkFactory, gateway: PaymentGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
            if order.status is OrderStatus.PAID:
                return order
            if order.status in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}:
                order.start_payment()
                await uow.orders.save(order)
                await uow.commit()
            elif order.status is not OrderStatus.PAYMENT_IN_PROGRESS:
                raise InvalidOrderTransition(
                    f"cannot process payment from {order.status.name}"
                )

        try:
            result = await self._gateway.charge(
                order_id=order.id,
                total=order.total,
                idempotency_key=f"charge:{order.id}",
            )
        except PaymentDeclined:
            async with self._uow_factory() as uow:
                failed = await uow.orders.get(order_id)
                if failed is None:
                    raise OrderNotFound(str(order_id))
                failed.mark_payment_failed()
                await uow.orders.save(failed)
                await uow.commit()
                return failed
        except PaymentUncertain:
            raise

        async with self._uow_factory() as uow:
            paid = await uow.orders.get(order_id)
            if paid is None:
                raise OrderNotFound(str(order_id))
            paid.mark_paid(result.reference)
            await uow.orders.save(paid)
            await uow.commit()
            return paid
```

`StubPaymentGateway` records charge/refund calls and either raises its configured error or returns `PaymentResult`. Ensure the memory UoW copy-on-enter keeps the first committed transition visible after the exception.

- [ ] **Step 4: Verify approved, declined, timeout, and already-paid behavior**

Add the approved, declined, and already-paid tests below alongside the timeout test from Step 1. Use full imports in the actual file.

```python
@pytest.mark.asyncio
async def test_approved_payment_commits_provider_reference() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("pay-001"))
    paid = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)
    assert paid.status is OrderStatus.PAID
    assert paid.payment_reference == "pay-001"
    assert store.commits == 2


@pytest.mark.asyncio
async def test_declined_payment_commits_failed_state() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentDeclined("insufficient_funds"))
    failed = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)
    assert failed.status is OrderStatus.PAYMENT_FAILED
    assert store.commits == 2


@pytest.mark.asyncio
async def test_already_paid_replay_does_not_call_gateway() -> None:
    order = make_order()
    order.start_payment()
    order.mark_paid("pay-existing")
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("must-not-be-used"))
    replayed = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)
    assert replayed.payment_reference == "pay-existing"
    assert gateway.charge_calls == []
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_process_payment.py -q`

Expected: four tests pass. The timeout test proves only one commit; approved/declined prove two commits.

- [ ] **Step 5: Write the HTTP adapter contract against a controllable ASGI provider**

The fake provider exposes POST `/charges`. It validates `Idempotency-Key`, UUID order ID, string decimal amount, and uppercase currency. It returns:

- 200 `{"status":"approved","reference":"pay-001"}` for normal input;
- 402 `{"status":"declined","reason":"insufficient_funds"}` for key `decline`;
- an invalid response body for key `malformed`.

`HTTPPaymentGateway.charge` maps 200 to `PaymentResult`, 402 to `PaymentDeclined`, malformed/5xx to a provider-protocol error, and `httpx.TimeoutException` to `PaymentUncertain`. `refund` uses POST `/refunds` with the same idempotency header and is initially covered only by its interface contract; Task 15 exercises it end to end.

Run: `cd python-testing/lab && uv run pytest tests/contract/test_payment_contract.py -q`

Expected: approved, declined, malformed, and timeout mapping tests pass using ASGITransport/MockTransport, without Docker or a real payment network.

- [ ] **Step 6: Write the chapter**

Cover transport fake versus monkeypatched method, request/response schema ownership, consumer-driven contract limits, provider verification, timeout taxonomy, retry eligibility, idempotency headers, malformed/partial responses, unknown outcomes, OpenAPI compatibility, schema diffing, secret redaction, and why a 200-only mock is weak evidence. The failure ticket is `timeout 后自动重试导致重复扣款` and ends with an idempotency-key assertion.

- [ ] **Step 7: Run fast tests and commit**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component tests/contract -q`

Expected: all fast and contract tests pass without Docker.

```bash
git add python-testing/07-http-and-contract-testing.md python-testing/README.md python-testing/lab/src/order_service/ports/payment.py python-testing/lab/src/order_service/application/process_payment.py python-testing/lab/src/order_service/adapters/memory.py python-testing/lab/src/order_service/adapters/payment_http.py python-testing/lab/tests/component/test_process_payment.py python-testing/lab/tests/contract
git commit -m "feat(testing-lab): add payment contracts"
```

### Task 10: Add Async Outbox Processing and Concurrency Tests

**Files:**
- Create: `python-testing/08-async-concurrency-background.md`
- Create: `python-testing/lab/src/order_service/adapters/outbox.py`
- Create: `python-testing/lab/tests/component/test_payment_worker.py`
- Create: `python-testing/lab/tests/integration/test_outbox.py`
- Create: `python-testing/lab/tests/e2e/test_order_flow.py`
- Modify: `python-testing/lab/src/order_service/adapters/memory.py`
- Modify: `python-testing/lab/tests/integration/conftest.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: `OutboxRepository.claim_batch/mark_done/mark_failed`, `ProcessPayment.execute`, `Clock`, and SQLAlchemy `SKIP LOCKED` implementation.
- Produces: `PaymentWorker.run_once(limit=10) -> int`, mutable test-only `ManualClock`, a 30-second claim lease, deterministic exponential backoff `min(2 ** attempts, 60)` seconds, concurrent claim guarantees, and the first complete order-to-paid E2E proof.

- [ ] **Step 1: Write the failing worker success test**

```python
# python-testing/lab/tests/component/test_payment_worker.py
import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from order_service.adapters.memory import FrozenClock, MemoryStore, MemoryUnitOfWork
from order_service.adapters.outbox import PaymentWorker
from order_service.application.messages import OutboxMessage


def make_outbox_message(*, available_at: datetime) -> OutboxMessage:
    order_id = UUID("00000000-0000-0000-0000-000000000001")
    return OutboxMessage(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        topic="payment_requested",
        aggregate_id=order_id,
        payload={"order_id": str(order_id)},
        occurred_at=available_at,
        available_at=available_at,
    )


@pytest.mark.asyncio
async def test_worker_marks_successful_message_done() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    processed: list[UUID] = []

    async def process(order_id: UUID) -> None:
        processed.append(order_id)

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, FrozenClock(now))
    assert await worker.run_once(limit=10) == 1
    assert processed == [message.aggregate_id]
    assert store.outbox[0].done is True
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_payment_worker.py -q`

Expected: FAIL because `order_service.adapters.outbox` does not exist.

- [ ] **Step 2: Implement worker ownership, cleanup, and retry scheduling**

Add this test-only clock to `adapters/memory.py` so time advances without sleeping:

```python
@dataclass
class ManualClock:
    value: datetime

    def now(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)
```

Update the test import to `from order_service.adapters.memory import FrozenClock, ManualClock, MemoryStore, MemoryUnitOfWork` before adding the cancellation and retry cases below.

```python
# python-testing/lab/src/order_service/adapters/outbox.py
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from order_service.ports.system import Clock
from order_service.ports.uow import UnitOfWorkFactory


class PaymentWorker:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        process_payment: Callable[[UUID], Awaitable[object]],
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._process_payment = process_payment
        self._clock = clock

    async def run_once(self, *, limit: int = 10) -> int:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            messages = await uow.outbox.claim_batch(limit=limit, now=now)
            await uow.commit()

        for message in messages:
            try:
                await self._process_payment(message.aggregate_id)
            except Exception:
                delay = min(2 ** (message.attempts + 1), 60)
                async with self._uow_factory() as uow:
                    await uow.outbox.mark_failed(
                        message.id,
                        available_at=self._clock.now() + timedelta(seconds=delay),
                    )
                    await uow.commit()
            else:
                async with self._uow_factory() as uow:
                    await uow.outbox.mark_done(message.id)
                    await uow.commit()
        return len(messages)
```

Do not catch `BaseException`; cancellation must propagate after repository/UoW cleanup. Add this exact cancellation test:

```python
@pytest.mark.asyncio
async def test_worker_propagates_cancellation_without_leaking_its_task() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    clock = ManualClock(now)
    started = asyncio.Event()
    never = asyncio.Event()

    async def process(order_id: UUID) -> None:
        started.set()
        await never.wait()

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, clock)
    task = asyncio.create_task(worker.run_once())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    assert store.outbox[0].claimed_at == now

    recovered: list[UUID] = []
    clock.advance(seconds=31)

    async def recover(order_id: UUID) -> None:
        recovered.append(order_id)

    recovery_worker = PaymentWorker(lambda: MemoryUnitOfWork(store), recover, clock)
    assert await recovery_worker.run_once() == 1
    assert recovered == [message.aggregate_id]
    assert store.outbox[0].done is True
```

- [ ] **Step 3: Verify retry without sleeping**

Add this retry test using `ManualClock`; no test may call `asyncio.sleep` for timing:

```python
@pytest.mark.asyncio
async def test_failed_message_retries_only_after_backoff() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    clock = ManualClock(now)
    outcomes = iter([RuntimeError("temporary"), None])

    async def process(order_id: UUID) -> None:
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, clock)
    assert await worker.run_once() == 1
    assert store.outbox[0].attempts == 1
    assert await worker.run_once() == 0
    clock.advance(seconds=2)
    assert await worker.run_once() == 1
    assert store.outbox[0].done is True
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_payment_worker.py -q`

Expected: success, retry, and cancellation-cleanup tests pass.

- [ ] **Step 4: Prove two Postgres workers do not claim the same message**

Create two due outbox messages in Postgres. Use `asyncio.gather` to call `claim_batch(limit=1)` in two independent UoWs, each committing its claim. Assert the returned message IDs are distinct and both rows have non-null `claimed_at`. Do not coordinate with sleeps; use an `asyncio.Event` barrier before both claim calls.

Run: `cd python-testing/lab && uv run pytest tests/integration/test_outbox.py -q`

Expected: the concurrent claim test passes repeatedly and under `-n 2` when each test uses unique UUIDs.

- [ ] **Step 5: Add the first E2E order-to-paid flow**

Build the app with a `CreateOrder` override backed by `SQLAlchemyUnitOfWork`; POST an order through ASGITransport; run one `PaymentWorker` with `ProcessPayment` and the fake HTTP provider; load through a fresh SQL UoW and assert `PAID`, provider reference `pay-001`, and outbox row `done=true`.

Mark the file `e2e + docker`. Use unique IDs from a per-test generator and truncate tables in teardown.

Run: `cd python-testing/lab && uv run pytest tests/e2e/test_order_flow.py -q`

Expected: one complete flow passes against Postgres 16 without contacting an external payment system.

- [ ] **Step 6: Write the chapter**

Cover coroutine/test ownership, pytest-asyncio strict versus auto mode, collector/loop scopes, async fixture teardown, leaked tasks, cancellation, deadlines versus sleeps, event/barrier coordination, deterministic clocks, async mock limits, worker at-least-once delivery, duplicate execution, `SKIP LOCKED`, xdist versus asyncio concurrency, and why async tests still run sequentially unless a separate mechanism parallelizes them. Link deep runtime material to `python-concurrency/`.

- [ ] **Step 7: Verify tier contracts and commit**

Run: `cd python-testing/lab && uv run pytest -q`

Expected: fast suite passes and excludes Docker markers.

Run: `cd python-testing/lab && uv run pytest tests/integration tests/e2e -q`

Expected: all Docker-backed tests pass.

```bash
git add python-testing/08-async-concurrency-background.md python-testing/README.md python-testing/lab/src/order_service/adapters/outbox.py python-testing/lab/tests/component/test_payment_worker.py python-testing/lab/tests/integration python-testing/lab/tests/e2e
git commit -m "feat(testing-lab): add async outbox tests"
```

### Task 11: Add Hypothesis Properties and a Stateful Order Model

**Files:**
- Create: `python-testing/09-property-and-stateful-testing.md`
- Create: `python-testing/lab/tests/property/conftest.py`
- Create: `python-testing/lab/tests/property/test_order_properties.py`
- Create: `python-testing/lab/tests/property/test_order_state_machine.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: pure `Money` and `Order` transitions; no Docker or external adapters.
- Produces: reusable Decimal/currency strategies, deterministic CI Hypothesis profile, and a RuleBasedStateMachine that checks reference-model agreement after every transition.

- [ ] **Step 1: Write a property that exposes an untested currency-normalization boundary**

```python
# python-testing/lab/tests/property/test_order_properties.py
from decimal import Decimal

import hypothesis.strategies as st
import pytest
from hypothesis import given

from order_service.domain.order import Money

pytestmark = pytest.mark.property


@given(
    amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
    currency=st.sampled_from(["usd", "Usd", "USD", "eur", "EUR"]),
)
def test_money_normalizes_valid_currency(amount: Decimal, currency: str) -> None:
    money = Money(amount, currency)
    assert money.amount == amount
    assert money.currency == currency.upper()
```

Run: `cd python-testing/lab && uv run pytest tests/property/test_order_properties.py -q`

Expected: PASS against the current domain; then temporarily change `.upper()` to `.lower()` and verify Hypothesis reports a minimal counterexample. Restore production code before continuing.

- [ ] **Step 2: Add CI and development profiles**

Register `ci` with `max_examples=100`, `deadline=None`, and `print_blob=True`; register `dev` with `max_examples=25`. Load `ci` when `CI` is present, otherwise `dev`. Do not globally suppress health checks. Document the example database path and how to replay a printed blob.

- [ ] **Step 3: Define a state machine with explicit model agreement**

```python
# core of python-testing/lab/tests/property/test_order_state_machine.py
class OrderMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.order = make_order()
        self.model_status = OrderStatus.PENDING_PAYMENT

    @precondition(lambda self: self.model_status in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED})
    @rule()
    def start_payment(self) -> None:
        self.order.start_payment()
        self.model_status = OrderStatus.PAYMENT_IN_PROGRESS

    @precondition(lambda self: self.model_status is OrderStatus.PAYMENT_IN_PROGRESS)
    @rule(reference=st.text(min_size=1).filter(lambda value: bool(value.strip())))
    def approve(self, reference: str) -> None:
        self.order.mark_paid(reference)
        self.model_status = OrderStatus.PAID

    @precondition(lambda self: self.model_status is OrderStatus.PAYMENT_IN_PROGRESS)
    @rule()
    def decline(self) -> None:
        self.order.mark_payment_failed()
        self.model_status = OrderStatus.PAYMENT_FAILED

    @invariant()
    def implementation_matches_model(self) -> None:
        assert self.order.status is self.model_status
        assert (self.order.payment_reference is not None) == (self.model_status is OrderStatus.PAID)


TestOrderMachine = OrderMachine.TestCase
```

Use full imports in the actual file and attach the `property` marker to the generated test class.

- [ ] **Step 4: Verify generation, shrinking evidence, and fast-tier placement**

Run: `cd python-testing/lab && uv run pytest tests/property -q --hypothesis-show-statistics`

Expected: property and state-machine tests pass; statistics show generated examples and rule execution.

Introduce a temporary defect that allows `mark_payment_failed` from `PAID`; run the state machine and capture the short failing sequence in the chapter. Restore the code and rerun green.

- [ ] **Step 5: Write the chapter**

Cover examples versus properties, strategy composition, filtering/assume cost, shrinking, example database, seeds/blobs, deadlines and health checks, reference models, metamorphic relations, stateful rules/bundles/preconditions/invariants, state explosion, when not to use stateful tests, and how generated tests complement rather than replace named business examples. The failure ticket is a four-step sequence that example tests missed and shrinking reduces.

- [ ] **Step 6: Run the complete Docker-free suite and commit**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component tests/contract tests/property -q`

Expected: all Docker-free tests pass.

```bash
git add python-testing/09-property-and-stateful-testing.md python-testing/README.md python-testing/lab/tests/property
git commit -m "test(testing-lab): add stateful properties"
```

### Task 12: Govern Flakiness, Parallelism, Coverage, and Mutation Quality

**Files:**
- Create: `python-testing/10-suite-reliability-and-scale.md`
- Create: `python-testing/lab/scenarios/order-dependency/state.py`
- Create: `python-testing/lab/scenarios/order-dependency/test_seed.py`
- Create: `python-testing/lab/scenarios/order-dependency/test_expect_seed.py`
- Create: `python-testing/lab/scenarios/order-dependency/README.md`
- Create: `python-testing/lab/scenarios/mutation/fee.py`
- Create: `python-testing/lab/scenarios/mutation/test_fee.py`
- Create: `python-testing/lab/scenarios/mutation/README.md`
- Create: `python-testing/lab/tests/unit/test_time_contract.py`
- Modify: `python-testing/lab/pyproject.toml`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: all fast test directories, marker contract, xdist, coverage, and mutmut.
- Produces: parallel-safe fast suite, deterministic order-dependency reproduction, one concrete coverage-without-assertion mutation example, duration-budget evidence, and quarantine policy.

- [ ] **Step 1: Add the deterministic order-dependency scenario**

```python
# python-testing/lab/scenarios/order-dependency/state.py
seen: list[str] = []
```

```python
# python-testing/lab/scenarios/order-dependency/test_seed.py
from state import seen


def test_seed() -> None:
    seen.append("seed")
```

```python
# python-testing/lab/scenarios/order-dependency/test_expect_seed.py
from state import seen


def test_expect_seed() -> None:
    assert seen == ["seed"]
```

Run in declared order: `cd python-testing/lab && uv run pytest scenarios/order-dependency/test_seed.py scenarios/order-dependency/test_expect_seed.py -q`

Expected: PASS.

Run reversed: `cd python-testing/lab && uv run pytest scenarios/order-dependency/test_expect_seed.py scenarios/order-dependency/test_seed.py -q`

Expected: first test FAILS with `assert [] == ['seed']`.

- [ ] **Step 2: Add a controlled mutation example that has 100% line coverage but no oracle**

```python
# python-testing/lab/scenarios/mutation/fee.py
from decimal import Decimal


def fee(amount: Decimal) -> Decimal:
    return amount * Decimal("0.02")
```

```python
# initial python-testing/lab/scenarios/mutation/test_fee.py
from decimal import Decimal

from fee import fee


def test_fee_executes() -> None:
    fee(Decimal("100.00"))
```

Run coverage on this scenario and show `fee.py` at 100%. Temporarily replace multiplication with addition (`return amount + Decimal("0.02")`) and rerun the weak test; it still passes, proving the missing oracle. Restore production code, replace the weak test body with `assert fee(Decimal("100.00")) == Decimal("2.0000")`, apply the same temporary mutation, and verify the strengthened test fails with differing values. Restore production code and preserve both before/after output excerpts in the scenario README; commit only the correct implementation and strong test. The formal mutmut exercise still runs against `order_service.domain.order` in Step 5.

- [ ] **Step 3: Add an explicit timezone regression before domain mutation runs**

```python
# python-testing/lab/tests/unit/test_time_contract.py
from datetime import datetime

import pytest

from tests.factories import make_order


def test_order_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_order(created_at=datetime(2026, 7, 15))
```

Run: `cd python-testing/lab && uv run pytest tests/unit/test_time_contract.py -q`

Expected: PASS and protect the branch before running mutmut on `domain/`.

- [ ] **Step 4: Prove fast tests pass under xdist and capture slowest nodes**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component tests/contract tests/property -n 2 -q --durations=10`

Expected: all tests pass in two worker processes; no fixed-port, shared-file, event-loop, or UUID collision appears.

If a test fails only under xdist, fix ownership in the test/fixture rather than adding `-n 0` or an automatic retry. Add the exact failure and fix to the chapter failure ticket.

- [ ] **Step 5: Run coverage and selective domain mutation**

Run: `cd python-testing/lab && uv run pytest tests/unit tests/component tests/contract tests/property --cov=order_service --cov-branch --cov-report=term-missing`

Expected: branch report is generated; record uncovered lines as risk questions, not a pass/fail percentage target.

Run: `cd python-testing/lab && uv run mutmut run "order_service.domain.order*"`

Expected: mutmut completes on the pure domain subset. Inspect every survivor; add a named test for any non-equivalent survivor and document equivalent mutants explicitly instead of gaming the score.

- [ ] **Step 6: Write the chapter and policies**

Cover flaky taxonomy (product race, test race, environment, clock/random, external dependency, resource exhaustion), order dependence, global state, ports/temp paths/UUID ownership, xdist worker model and fixture duplication, async versus worker parallelism, duration budgets, test selection, coverage branches, mutation score limits, quarantine owner/expiry, no-rerun policy, warning policy, failure artifacts, and test-suite observability. The failure ticket starts with the reversed-order scenario and ends with factory/function ownership.

- [ ] **Step 7: Verify defaults, update progress, and commit**

Run: `cd python-testing/lab && uv run pytest -q`

Expected: default fast suite passes; scenario failures remain excluded.

```bash
git add python-testing/10-suite-reliability-and-scale.md python-testing/README.md python-testing/lab/scenarios python-testing/lab/tests/unit/test_time_contract.py python-testing/lab/pyproject.toml
git commit -m "docs(testing): govern suite reliability"
```

### Task 13: Add Nox Sessions and a Platform-Neutral CI Contract

**Files:**
- Create: `python-testing/lab/noxfile.py`
- Modify: `python-testing/lab/README.md`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: exact test directories and markers from Tasks 1–12.
- Produces: Nox sessions `fast-3.11`, `fast-3.12`, `fast-3.13`, `fast-3.14`, `integration`, `e2e`, `coverage`, and `mutation`; local and CI use the same commands.

- [ ] **Step 1: Write the exact Nox session definitions**

```python
# python-testing/lab/noxfile.py
import nox

FAST_PYTHONS = ["3.11", "3.12", "3.13", "3.14"]


def install_lab(session: nox.Session) -> None:
    session.install("-e", ".[dev]")


@nox.session(name="fast", python=FAST_PYTHONS, venv_backend="uv")
def fast(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "-q",
    )


@nox.session(python="3.14", venv_backend="uv")
def integration(session: nox.Session) -> None:
    install_lab(session)
    session.run("pytest", "tests/integration", "-m", "integration and docker", "-q")


@nox.session(python="3.14", venv_backend="uv")
def e2e(session: nox.Session) -> None:
    install_lab(session)
    session.run("pytest", "tests/e2e", "-m", "e2e and docker", "-q")


@nox.session(python="3.14", venv_backend="uv")
def coverage(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "--cov=order_service",
        "--cov-branch",
        "--cov-report=term-missing",
    )


@nox.session(python="3.14", venv_backend="uv")
def mutation(session: nox.Session) -> None:
    install_lab(session)
    session.run("mutmut", "run", "order_service.domain.order*")
```

- [ ] **Step 2: List sessions and verify names**

Run: `cd python-testing/lab && uv run nox --list`

Expected: four parameterized fast sessions plus integration, e2e, coverage, and mutation.

- [ ] **Step 3: Install the exact interpreter matrix and run fast sessions**

Run: `uv python install 3.11 3.12 3.13 3.14`

Expected: all four interpreters are available to Nox. If network access is sandbox-blocked, request approval for this exact installation command; do not silently reduce the matrix.

Run: `cd python-testing/lab && uv run nox -s "fast-3.11" "fast-3.12" "fast-3.13" "fast-3.14"`

Expected: all four fast sessions pass without Docker.

- [ ] **Step 4: Document the CI job contract and failure artifacts**

`lab/README.md` must state:

- PR fast matrix: Nox `fast` on 3.11–3.14;
- Postgres integration: Nox `integration` on 3.14 with Docker;
- E2E: Nox `e2e` on 3.14 with Docker;
- quality: coverage on PR, mutation on schedule/manual;
- cache keys include OS, Python minor, and `uv.lock` hash;
- artifacts include JUnit XML, coverage, pytest logs, Hypothesis reproduction blob, and container logs on failure;
- local direct `uv run pytest ...` equivalents for every Nox session;
- exact troubleshooting for unavailable Docker, unavailable interpreter, and stale lockfile.

The track README must explain why the plan is platform-neutral and does not maintain complete GitHub Actions/GitLab/Jenkins YAML variants.

- [ ] **Step 5: Verify frozen installation and session parity**

Run: `cd python-testing/lab && uv sync --frozen --extra dev`

Expected: lockfile is current and no dependency resolution occurs.

Run the direct fast pytest command and `uv run nox -s fast-3.14`; expected test counts and outcomes match.

- [ ] **Step 6: Commit the executable CI contract**

```bash
git add python-testing/lab/noxfile.py python-testing/lab/README.md python-testing/README.md python-testing/lab/uv.lock
git commit -m "build(testing-lab): add Nox test matrix"
```

### Task 14: Introduce the Legacy Refund Behavior and Characterization Tests

**Files:**
- Create: `python-testing/lab/src/order_service/application/legacy_refund.py`
- Create: `python-testing/lab/tests/component/test_legacy_refund.py`
- Create: `python-testing/lab/tests/component/test_refund_characterization.py`
- Modify: `python-testing/lab/src/order_service/api/dependencies.py`
- Modify: `python-testing/lab/src/order_service/api/schemas.py`
- Modify: `python-testing/lab/src/order_service/api/app.py`
- Modify: `python-testing/lab/src/order_service/adapters/memory.py`

**Interfaces:**
- Consumes: paid Order, `PaymentGateway.refund`, FastAPI dependency overrides, and strict xfail policy.
- Produces: intentionally flawed `LegacyRefund.execute(order_id, request_id)`, stable HTTP POST `/orders/{order_id}/refunds`, response contract `202 {order_id,status:"accepted"}`, and a strict known-failure regression named `CAPSTONE-REFUND-IDEMPOTENCY`.

- [ ] **Step 1: Write the characterization test for the existing public behavior**

```python
# core of python-testing/lab/tests/component/test_refund_characterization.py
@pytest.mark.asyncio
async def test_refund_endpoint_preserves_accepted_response_shape() -> None:
    app = create_app()
    app.dependency_overrides[get_legacy_refund] = lambda: legacy_refund
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/orders/{PAID_ORDER_ID}/refunds",
                headers={"Idempotency-Key": "caller-attempt-001"},
            )
    assert response.status_code == 202
    assert response.json() == {
        "order_id": str(PAID_ORDER_ID),
        "status": "accepted",
    }
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_refund_characterization.py -q`

Expected: FAIL because the dependency, route, and legacy use case do not exist.

- [ ] **Step 2: Implement the smallest behavior that satisfies the characterization**

```python
# python-testing/lab/src/order_service/application/legacy_refund.py
from uuid import UUID

from order_service.application.process_payment import OrderNotFound
from order_service.ports.payment import PaymentGateway
from order_service.ports.uow import UnitOfWorkFactory


class LegacyRefund:
    def __init__(self, uow_factory: UnitOfWorkFactory, gateway: PaymentGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID, request_id: str) -> None:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
        if order.payment_reference is None:
            raise RuntimeError("order has no captured payment")
        await self._gateway.refund(
            payment_reference=order.payment_reference,
            total=order.total,
            idempotency_key=request_id,
        )
```

Add `get_legacy_refund`, request header parsing, and a 202 response schema without changing the existing POST `/orders` contract.

- [ ] **Step 3: Add the known-failure duplicate-refund test**

```python
# core of python-testing/lab/tests/component/test_legacy_refund.py
@pytest.mark.xfail(strict=True, reason="CAPSTONE-REFUND-IDEMPOTENCY")
@pytest.mark.asyncio
async def test_retry_with_new_request_id_does_not_refund_twice() -> None:
    await legacy_refund.execute(PAID_ORDER_ID, "caller-attempt-001")
    await legacy_refund.execute(PAID_ORDER_ID, "caller-attempt-002")
    assert len(gateway.refund_calls) == 1
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_legacy_refund.py tests/component/test_refund_characterization.py -q`

Expected: characterization passes and the duplicate-refund test reports exactly one strict XFAIL.

- [ ] **Step 4: Record the capstone evidence before fixing it**

In `test_refund_characterization.py`, also lock the missing-order error mapping and the absence of extra response fields. Capture gateway calls to show that caller-generated request IDs become provider idempotency keys and therefore permit a double refund.

Run the full fast suite. Expected: green with one named XFAIL and no XPASS.

- [ ] **Step 5: Commit the intentionally bounded legacy state**

```bash
git add python-testing/lab/src/order_service/application/legacy_refund.py python-testing/lab/src/order_service/api python-testing/lab/src/order_service/adapters/memory.py python-testing/lab/tests/component/test_legacy_refund.py python-testing/lab/tests/component/test_refund_characterization.py
git commit -m "test(testing-lab): characterize legacy refund"
```

### Task 15: Fix Refund Idempotency and Complete the Legacy/CI Capstone Chapter

**Files:**
- Create: `python-testing/11-ci-legacy-and-capstone.md`
- Create: `python-testing/lab/src/order_service/application/refund_order.py`
- Create: `python-testing/lab/migrations/versions/0002_refund_state.py`
- Create: `python-testing/lab/tests/component/test_refund_order.py`
- Create: `python-testing/lab/tests/integration/test_refund_persistence.py`
- Create: `python-testing/lab/tests/e2e/test_refund_flow.py`
- Delete: `python-testing/lab/src/order_service/application/legacy_refund.py`
- Modify: `python-testing/lab/src/order_service/domain/order.py`
- Modify: `python-testing/lab/src/order_service/adapters/sqlalchemy.py`
- Modify: `python-testing/lab/src/order_service/api/dependencies.py`
- Modify: `python-testing/lab/src/order_service/api/app.py`
- Move: `python-testing/lab/tests/component/test_legacy_refund.py` → `python-testing/lab/tests/component/test_refund_idempotency.py`
- Modify: `python-testing/README.md`

**Interfaces:**
- Consumes: characterization response contract, payment refund port, optimistic SQL save, Nox sessions, and evidence policies.
- Produces: `REFUND_IN_PROGRESS`, `REFUNDED`, `Order.start_refund`, `Order.mark_refunded`, `RefundOrder.execute`, deterministic provider key `refund:{order_id}`, persisted refund reference, green former-XFAIL, and the final chapter.

- [ ] **Step 1: Remove xfail and verify the bug is red**

Run `git mv python-testing/lab/tests/component/test_legacy_refund.py python-testing/lab/tests/component/test_refund_idempotency.py`. Delete only the `pytest.mark.xfail` decorator and reason from `test_retry_with_new_request_id_does_not_refund_twice`; leave the test body unchanged.

Run: `cd python-testing/lab && uv run pytest tests/component/test_refund_idempotency.py::test_retry_with_new_request_id_does_not_refund_twice -q`

Expected: FAIL with `assert 2 == 1`.

- [ ] **Step 2: Add refund domain transitions test-first**

Add these exact unit tests to `tests/unit/test_order.py` before changing the domain:

```python
def paid_order() -> Order:
    order = make_order()
    order.start_payment()
    order.mark_paid("pay-001")
    return order


def test_only_paid_order_can_start_refund() -> None:
    with pytest.raises(InvalidOrderTransition, match="PENDING_PAYMENT.*REFUND_IN_PROGRESS"):
        make_order().start_refund()


def test_refund_transitions_and_replay_are_idempotent() -> None:
    order = paid_order()
    order.start_refund()
    assert order.status is OrderStatus.REFUND_IN_PROGRESS
    order.mark_refunded("refund-001")
    completed_version = order.version
    order.mark_refunded("refund-001")
    assert order.status is OrderStatus.REFUNDED
    assert order.refund_reference == "refund-001"
    assert order.version == completed_version
```

Run: `cd python-testing/lab && uv run pytest tests/unit/test_order.py -q`

Expected: FAIL because refund states and methods do not exist.

Extend the domain exactly as follows:

```python
# additions to order.py
class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_IN_PROGRESS = "payment_in_progress"
    PAYMENT_FAILED = "payment_failed"
    PAID = "paid"
    REFUND_IN_PROGRESS = "refund_in_progress"
    REFUNDED = "refunded"


# add field on Order
refund_reference: str | None = None


def start_refund(self) -> None:
    if self.status is OrderStatus.REFUND_IN_PROGRESS:
        return
    if self.status is not OrderStatus.PAID:
        self._reject(OrderStatus.REFUND_IN_PROGRESS)
    self.status = OrderStatus.REFUND_IN_PROGRESS
    self.version += 1


def mark_refunded(self, provider_reference: str) -> None:
    if self.status is OrderStatus.REFUNDED and self.refund_reference == provider_reference:
        return
    if self.status is not OrderStatus.REFUND_IN_PROGRESS:
        self._reject(OrderStatus.REFUNDED)
    if not provider_reference.strip():
        raise ValueError("provider_reference must not be blank")
    self.status = OrderStatus.REFUNDED
    self.refund_reference = provider_reference
    self.version += 1
```

Run the focused unit tests and expect green.

- [ ] **Step 3: Implement deterministic two-transaction refund orchestration**

```python
# python-testing/lab/src/order_service/application/refund_order.py
from uuid import UUID

from order_service.application.process_payment import OrderNotFound
from order_service.domain.order import InvalidOrderTransition, Order, OrderStatus
from order_service.ports.payment import PaymentGateway, PaymentUncertain
from order_service.ports.uow import UnitOfWorkFactory


class RefundOrder:
    def __init__(self, uow_factory: UnitOfWorkFactory, gateway: PaymentGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
            if order.status is OrderStatus.REFUNDED:
                return order
            if order.status is OrderStatus.PAID:
                order.start_refund()
                await uow.orders.save(order)
                await uow.commit()
            elif order.status is not OrderStatus.REFUND_IN_PROGRESS:
                raise InvalidOrderTransition(
                    f"cannot refund order from {order.status.name}"
                )

        if order.payment_reference is None:
            raise RuntimeError("order has no captured payment")
        try:
            result = await self._gateway.refund(
                payment_reference=order.payment_reference,
                total=order.total,
                idempotency_key=f"refund:{order.id}",
            )
        except PaymentUncertain:
            raise

        async with self._uow_factory() as uow:
            refunded = await uow.orders.get(order_id)
            if refunded is None:
                raise OrderNotFound(str(order_id))
            refunded.mark_refunded(result.reference)
            await uow.orders.save(refunded)
            await uow.commit()
            return refunded
```

Replace `get_legacy_refund` with `get_refund_order() -> RefundOrder`, update route/tests to override the new provider, but preserve the 202 status and exact `{"order_id", "status":"accepted"}` response. Ignore the caller request ID for provider idempotency while keeping the header accepted for backward compatibility. Delete `legacy_refund.py` after moving the characterized public contract to `RefundOrder`; no dead legacy implementation remains in the final package.

- [ ] **Step 4: Turn the former XFAIL green and prove uncertainty behavior**

Before implementation, add this component regression to `test_refund_order.py`:

```python
@pytest.mark.asyncio
async def test_refund_timeout_persists_in_progress_for_reconciliation() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentUncertain("refund timeout"))
    use_case = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)
    with pytest.raises(PaymentUncertain, match="refund timeout"):
        await use_case.execute(order.id)
    assert store.orders[order.id].status is OrderStatus.REFUND_IN_PROGRESS
    assert store.commits == 1
```

Run: `cd python-testing/lab && uv run pytest tests/component/test_refund_idempotency.py tests/component/test_refund_order.py tests/component/test_refund_characterization.py -q`

Expected: all tests pass, no xfail remains, replay invokes `gateway.refund` once, both calls use the deterministic `refund:{order_id}` key, and timeout leaves `refund_in_progress` for reconciliation.

- [ ] **Step 5: Persist refund state with a migration and integration tests**

Migration `0002_refund_state.py` adds nullable `refund_reference` to `orders`; status remains a string so no enum migration is needed. Update row/domain mapping and optimistic save.

Integration tests prove REFUND_IN_PROGRESS survives a timeout across UoWs, REFUNDED/reference persist, stale concurrent refund save raises `ConcurrentOrderUpdate`, and downgrade/upgrade preserves the original orders/outbox schema contract.

Run: `cd python-testing/lab && uv run pytest tests/integration/test_refund_persistence.py tests/integration/test_migrations.py -q`

Expected: all tests pass on Postgres 16.

- [ ] **Step 6: Add the backward-compatible E2E refund flow**

Create and pay an order through the existing E2E path, POST refund twice with two caller keys, assert both HTTP responses preserve the characterized 202 shape, load REFUNDED state and provider reference from a fresh UoW, and assert the fake provider saw one effective deterministic refund key.

Run: `cd python-testing/lab && uv run pytest tests/e2e/test_refund_flow.py -q`

Expected: one complete refund flow passes with no duplicate provider refund.

- [ ] **Step 7: Write the final chapter around the actual capstone history**

Cover test matrix and Nox, hermetic CI, cache/artifact contracts, characterization versus approval tests, seam discovery, change amplification, bug-versus-test-versus-environment classification, red reproduction, transaction boundary, unknown external outcome, backward-compatible API response, flaky diagnosis, safe refactor order, and the final evidence ledger. Include the exact pre-fix XFAIL, red `2 == 1`, green component/integration/E2E commands, and interview narrative.

- [ ] **Step 8: Run every tier, update progress, and commit**

Run fast, integration, and E2E Nox sessions. Expected: all pass, no XPASS/XFAIL, and the default suite remains Docker-free.

```bash
git add python-testing/11-ci-legacy-and-capstone.md python-testing/README.md python-testing/lab/src/order_service python-testing/lab/migrations/versions/0002_refund_state.py python-testing/lab/tests
git commit -m "feat(testing-lab): complete refund capstone"
```

### Task 16: Add Interview Cards, Cross-Links, and Final Evidence

**Files:**
- Create: `python-testing/99-interview-cards/README.md`
- Create: `python-testing/99-interview-cards/q-test-strategy.md`
- Create: `python-testing/99-interview-cards/q-fixture-dag.md`
- Create: `python-testing/99-interview-cards/q-mock-vs-fake.md`
- Create: `python-testing/99-interview-cards/q-database-testing.md`
- Create: `python-testing/99-interview-cards/q-async-flaky.md`
- Create: `python-testing/99-interview-cards/q-property-stateful.md`
- Create: `python-testing/99-interview-cards/q-suite-governance.md`
- Modify: `python-testing/README.md`
- Modify: `python/12-testing.md`
- Modify: `python/README.md`

**Interfaces:**
- Consumes: every chapter's mental model, failure ticket, commands, and final lab evidence.
- Produces: one-line/three-minute/deep-dive answers, chapter backlinks, complete navigation, and final verified handoff.

- [ ] **Step 1: Write the quick-answer index**

For each chapter 00–11, include at least four `问 — 一句话答 ｜标签` entries. Every answer links back to the exact chapter heading that supports it. Required tags include `test-boundary`, `oracle`, `collection`, `assert-rewrite`, `fixture-dag`, `scope`, `patch-lookup`, `fake-fidelity`, `transaction-fixture`, `testcontainers`, `contract`, `timeout-unknown`, `event-loop`, `xdist`, `shrinking`, `state-machine`, `flaky`, `mutation`, `characterization`, and `ci-matrix`.

- [ ] **Step 2: Write seven deep cards with a fixed answer structure**

Each deep card contains: question, 30-second answer, mechanism, production example from the lab, trade-off/counterexample, follow-up questions, and links to code/tests/chapters.

Required questions:

1. How do you select test boundaries for a payment workflow?
2. How does pytest build and execute a fixture DAG, including teardown?
3. Mock, stub, fake, spy: which one and why?
4. Why test a data layer against real Postgres, and when is rollback misleading?
5. Why do async tests become flaky, and how do loop/task ownership and xdist differ?
6. When does property/stateful testing find bugs examples miss?
7. How do you govern a 30-minute, flaky test suite without hiding failures?

- [ ] **Step 3: Verify all navigation and bridge links**

Run:

```bash
rg -n "python-testing|99-interview-cards|00-testing-strategy|11-ci-legacy" python/README.md python/12-testing.md python-testing/README.md python-testing/99-interview-cards
```

Expected: main tutorial → bridge → track → chapter/card and card → chapter backlinks are all present.

For every relative link under `python-testing/`, resolve the target from the source file's directory and verify it exists. Fix any broken target before continuing.

- [ ] **Step 4: Run the full evidence matrix from a frozen environment**

Run in order:

```bash
cd python-testing/lab
uv sync --frozen --extra dev
uv run pytest -q
uv run pytest tests/unit tests/component tests/contract tests/property -n 2 -q --durations=10
uv run pytest tests/integration -m "integration and docker" -q
uv run pytest tests/e2e -m "e2e and docker" -q
uv run pytest tests/property -q --hypothesis-show-statistics
uv run pytest tests/unit tests/component tests/contract tests/property --cov=order_service --cov-branch --cov-report=term-missing
uv run nox -s "fast-3.11" "fast-3.12" "fast-3.13" "fast-3.14"
```

Expected: every command exits 0; default command does not need Docker; Docker tiers use Postgres 16; xdist has no collision; Hypothesis reports generated examples; coverage reports branches; all four Nox Python versions pass.

- [ ] **Step 5: Verify documentation scope and forbidden-dependency guards**

Run:

```bash
rg -n "Kafka|Redis|Kubernetes|Playwright|Selenium|SQLite" python-testing
```

Expected: any match appears only in an explicit non-goal, comparison, or warning; no lab dependency/import/config introduces these systems.

Run:

```bash
rg -n "TODO|TBD|FIXME|implement later|以后补|待补" python-testing python/12-testing.md
```

Expected: no matches.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 6: Mark the track complete and commit final documentation**

Update every progress-map row in `python-testing/README.md` to complete and record the verified command matrix without machine-specific timing promises.

```bash
git add python-testing python/12-testing.md python/README.md
git commit -m "docs(testing): complete Python testing track"
```

## Final Implementation Review Checklist

Before claiming the implementation complete:

- [ ] Compare all sixteen task deliverables against every section of `docs/superpowers/specs/2026-07-15-python-testing-track-design.md`.
- [ ] Confirm `git status --short` is empty and review `git log --oneline` for one bounded commit per task.
- [ ] Confirm the default pytest command works with Docker unavailable.
- [ ] Confirm integration and E2E evidence comes from Postgres 16, not a fake or SQLite.
- [ ] Confirm no intentional failure scenario is part of default collection.
- [ ] Confirm strict markers, strict xfail, strict async ownership, and targeted warning policy are active.
- [ ] Confirm every known bug/failure ticket has a retained regression test or an explicitly excluded scenario README.
- [ ] Confirm all formal code blocks correspond to lab files and all pseudocode is labeled.
- [ ] Confirm the 3.11–3.14 Nox matrix and frozen lockfile pass.
- [ ] Confirm no placeholders, broken relative links, whitespace errors, or unrelated repository edits remain.
