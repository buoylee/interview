# Pydantic 数据契约教程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一套架构师级 Pydantic v2／pydantic-settings 数据契约教程，以及无需数据库、broker、网络或 API key 即可运行的订单／支付契约 lab。

**Architecture:** 教程以服务信任边界和数据生命周期为主线，lab 是所有核心示例的单一可执行事实来源。代码将 HTTP／Webhook／MQ／Settings 边界模型与应用命令、领域对象、输出视图显式分离；每个行为先以 pytest 锁定，再写最小实现，最后由章节引用经过测试的接口。

**Tech Stack:** CPython 3.11+、Pydantic v2、pydantic-settings v2、pytest、uv；FastAPI 仅作为独立 integration dependency group 中的末章 adapter 示例。

**Spec:** `docs/superpowers/specs/2026-07-15-pydantic-contracts-tutorial-design.md`

## Global Constraints

- CPython 基线为 `>=3.11`；Pydantic 只写 v2 主线，v1 仅在第 13 章给迁移地图。
- 核心依赖精确声明为 `pydantic>=2,<3`、`pydantic-settings>=2,<3`；开发测试组只有 pytest，FastAPI 位于独立 integration group。
- 标准验证命令是从 `python-pydantic/lab/` 执行 `uv sync` 与 `uv run pytest`；`uv.lock` 必须提交。
- 不引入 SQLAlchemy、Kafka／RocketMQ SDK、Pydantic AI、Hypothesis、Docker、数据库、网络服务或 API key。
- validator／serializer 必须确定、无 I/O；签名校验、错误分类、DTO 映射和领域决策放在明确的 adapter／应用／领域函数中。
- 不允许把 `model_dump()` 结果直接展开进应用命令、领域对象或持久化参数；所有跨层转换显式列出字段。
- HTTP 输入默认 `extra='forbid'`；事件 consumer 是否忽略新增字段由版本兼容策略显式决定；金额、数量、ID 和状态不得依赖宽松隐式转换。
- 文档使用简体中文，保留正式英文术语与 API 名称；每章遵循“事故／面试开场 → 心智模型 → 可运行示例 → 机制 → 连续案例 → 失败模式 → 架构边界 → pytest → Java/Go 对照 → 速查 → 面试卡”。
- Pydantic AI 不安装、不运行；第 13 章只说明 Pydantic model 可作为 LLM structured output 契约。
- 只提交源码、测试、文档、`uv.lock`、`.env.example` 和人工审查过的 schema golden；虚拟环境、依赖目录、缓存、coverage、真实 `.env`、secret 和 benchmark 临时输出全部忽略。
- 事实依据以实现时的 Pydantic latest stable 官方文档和本项目 `uv.lock` 解析版本为准；版本敏感行为必须在文中标注并由测试固定。

## File Responsibility Map

| 路径 | 单一职责 |
|---|---|
| `python-pydantic/README.md` | 教程定位、环境、学习路线、章节导航和 lab 入口 |
| `python-pydantic/00-*.md`—`13-*.md` | 按数据生命周期拆分的 14 个教学章节 |
| `python-pydantic/99-interview-cards.md` | 30 秒回答、深挖、误区、生产案例和故障速查 |
| `python/25-runtime-data-contracts-bridge.md` | Python 主线到深度专题的桥接，不复制教程正文 |
| `python-pydantic/lab/src/order_contracts/value_objects.py` | 可复用 ID、货币、金额等稳定边界值对象 |
| `python-pydantic/lab/src/order_contracts/inbound/` | HTTP 与 Webhook 入站协议模型 |
| `python-pydantic/lab/src/order_contracts/application/commands.py` | 不依赖 Pydantic 的应用命令 dataclass |
| `python-pydantic/lab/src/order_contracts/domain/order.py` | 订单领域对象和业务不变量 |
| `python-pydantic/lab/src/order_contracts/outbound/views.py` | 客户／内部输出白名单模型 |
| `python-pydantic/lab/src/order_contracts/events/` | 事件 envelope、版本化 payload 和 TypeAdapter |
| `python-pydantic/lab/src/order_contracts/config.py` | Settings 模型、source 定制、缓存和测试隔离接口 |
| `python-pydantic/lab/src/order_contracts/errors.py` | 稳定错误 DTO 和 MQ 失败分类 |
| `python-pydantic/lab/src/order_contracts/adapters.py` | 边界解析、签名校验、显式 mapper／projection |
| `python-pydantic/lab/src/order_contracts/advanced_types.py` | 直接 CoreSchema hook 的隔离高级示例 |
| `python-pydantic/lab/src/order_contracts/performance.py` | 无硬阈值的验证路径计时观察 |
| `python-pydantic/lab/scripts/export_schemas.py` | 确定性生成三份 JSON Schema golden |
| `python-pydantic/lab/examples/` | 可直接运行且被 pytest 调用的四个边界示例 |
| `python-pydantic/lab/tests/` | 行为、契约、安全、配置、schema、示例和性能观察测试 |

---

### Task 1: 建立可安装 lab 骨架与仓库忽略规则

**Files:**
- Modify: `.gitignore`
- Create: `python-pydantic/lab/pyproject.toml`
- Create: `python-pydantic/lab/README.md`
- Create: `python-pydantic/lab/.env.example`
- Create: `python-pydantic/lab/tests/test_package_smoke.py`
- Create: `python-pydantic/lab/src/order_contracts/__init__.py`
- Create: `python-pydantic/lab/src/order_contracts/inbound/__init__.py`
- Create: `python-pydantic/lab/src/order_contracts/application/__init__.py`
- Create: `python-pydantic/lab/src/order_contracts/domain/__init__.py`
- Create: `python-pydantic/lab/src/order_contracts/outbound/__init__.py`
- Create: `python-pydantic/lab/src/order_contracts/events/__init__.py`

**Interfaces:**
- Produces: 可由 `uv` 安装的 `order_contracts` src-layout package；后续所有测试从此包导入。
- Produces: `order_contracts.__version__ == '0.1.0'`。

- [ ] **Step 1: 声明项目、构建配置、依赖组和 pytest 配置**

创建 `python-pydantic/lab/pyproject.toml`：

```toml
[project]
name = "order-contracts-lab"
version = "0.1.0"
description = "Runnable Pydantic v2 data-contract examples for an order service"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2,<3",
  "pydantic-settings>=2,<3",
]

[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[dependency-groups]
dev = ["pytest>=8,<10"]
integrations = ["fastapi>=0.115,<1"]

[tool.uv]
default-groups = ["dev", "integrations"]

[tool.hatch.build.targets.wheel]
packages = ["src/order_contracts"]

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
```

- [ ] **Step 2: 先写失败的 package smoke test**

创建 `python-pydantic/lab/tests/test_package_smoke.py`：

```python
import order_contracts


def test_package_has_version() -> None:
    assert order_contracts.__version__ == "0.1.0"
```

- [ ] **Step 3: 同步依赖但暂不安装项目，并确认测试按预期失败**

Run: `cd python-pydantic/lab && uv sync --no-install-project && uv run --no-sync pytest tests/test_package_smoke.py -v`

Expected: 依赖同步成功但尚未安装项目；pytest collection 以 `ModuleNotFoundError: No module named 'order_contracts'` 失败。`uv sync` 同时生成 `python-pydantic/lab/uv.lock`。

- [ ] **Step 4: 创建最小 package 和职责目录**

`python-pydantic/lab/src/order_contracts/__init__.py`：

```python
"""Boundary contracts for the runnable order-service tutorial."""

__version__ = "0.1.0"
```

其余五个 `__init__.py` 分别写入以下单行内容：

```python
# inbound/__init__.py
"""Inbound HTTP and webhook contracts."""

# application/__init__.py
"""Application commands produced from validated boundary data."""

# domain/__init__.py
"""Framework-independent order domain objects."""

# outbound/__init__.py
"""Explicit outbound response views."""

# events/__init__.py
"""Versioned event contracts and parsing adapters."""
```

- [ ] **Step 5: 添加安全样例配置和最小运行说明**

创建 `python-pydantic/lab/.env.example`，只使用明显的非生产占位值：

```dotenv
ORDER_ENVIRONMENT=development
ORDER_LOG_LEVEL=INFO
ORDER_ALLOWED_CURRENCIES=USD,EUR
ORDER_PAYMENT__BASE_URL=https://payments.example.test
ORDER_PAYMENT__WEBHOOK_SECRET=replace-with-local-demo-secret
ORDER_PAYMENT__TIMEOUT_SECONDS=3
```

创建 `python-pydantic/lab/README.md`：

````markdown
# Order Contracts Lab

本 lab 是 `python-pydantic/` 教程的可执行事实来源，使用 CPython 3.11+、Pydantic v2、pydantic-settings v2 与 pytest。

```bash
uv sync
uv run pytest
```

它不连接数据库、消息 broker、支付平台或 LLM，也不需要 API key。`.env.example` 只有可公开的本地占位值；真实 `.env` 不得提交。
````

- [ ] **Step 6: 只补根 `.gitignore` 缺失项**

保留现有规则，在 Python 缓存区附近补入以下尚未存在的行；`!.env.example` 必须位于 `.env.*` 之后：

```gitignore
.venv/
.pytest_cache/
.mypy_cache/
.pyright/
.ruff_cache/
.coverage
htmlcov/
.env
.env.*
!.env.example
build/
dist/
*.egg-info/
```

- [ ] **Step 7: 验证 package、锁文件和忽略行为**

Run: `cd python-pydantic/lab && uv sync && uv run --no-sync pytest tests/test_package_smoke.py -v`

Expected: `uv sync` 使用 Hatchling 构建并安装 `order-contracts-lab`；pytest 输出 `1 passed`。

Run: `cd python-pydantic/lab && uv run --no-sync python -I -c 'import order_contracts; assert order_contracts.__version__ == "0.1.0"; print(order_contracts.__version__)'`

Expected: 隔离模式 Python 仍可从已安装环境导入 package，并输出 `0.1.0`。

Run: `git check-ignore python-pydantic/lab/.venv python-pydantic/lab/.env python-pydantic/lab/.pytest_cache python-pydantic/lab/.env.example`

Expected: 前三个路径被列出；`.env.example` 不在输出中。再执行 `git status --short`，确认 `uv.lock`、`.env.example` 可跟踪，`.venv/` 不出现。

- [ ] **Step 8: Commit**

```bash
git add .gitignore python-pydantic/lab
git commit -m "build(pydantic): scaffold runnable contracts lab"
```

---

### Task 2: 值对象与 CreateOrder HTTP 入站契约

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/value_objects.py`
- Create: `python-pydantic/lab/src/order_contracts/inbound/create_order.py`
- Create: `python-pydantic/lab/tests/test_value_objects.py`
- Create: `python-pydantic/lab/tests/test_create_order.py`

**Interfaces:**
- Produces: `OrderId`、`CustomerId`、`CurrencyCode`、`Sku`、`Money`。
- Produces: `CreateOrderItem`、`CreateOrderRequest`。
- Policy: ID／quantity 严格；currency 允许字符串规范化为大写；Money 仅接受 `Decimal` 或十进制字符串并拒绝其他原始输入类型；请求 items 验证后存储为不可变 tuple。

- [ ] **Step 1: 写值对象失败测试**

创建 `tests/test_value_objects.py`：

```python
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from order_contracts.value_objects import CurrencyCode, Money, OrderId


def test_currency_is_normalized_to_uppercase() -> None:
    adapter = TypeAdapter(CurrencyCode)
    assert adapter.validate_python("usd") == "USD"


def test_order_id_rejects_non_string_input() -> None:
    adapter = TypeAdapter(OrderId)
    with pytest.raises(ValidationError) as caught:
        adapter.validate_python(123)
    assert caught.value.errors()[0]["type"] == "string_type"


def test_money_accepts_decimal_string_and_serializes_as_string() -> None:
    money = Money.model_validate({"amount": "12.30", "currency": "usd"})
    assert money.amount == Decimal("12.30")
    assert money.model_dump(mode="json") == {"amount": "12.30", "currency": "USD"}


def test_money_rejects_binary_float() -> None:
    with pytest.raises(ValidationError) as caught:
        Money.model_validate({"amount": 12.30, "currency": "USD"})
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("amount",)


def test_money_rejects_integer_input() -> None:
    with pytest.raises(ValidationError) as caught:
        Money.model_validate({"amount": 12, "currency": "USD"})
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("amount",)
```

- [ ] **Step 2: 运行并确认缺少模块**

Run: `cd python-pydantic/lab && uv run pytest tests/test_value_objects.py -v`

Expected: collection 以 `ModuleNotFoundError: No module named 'order_contracts.value_objects'` 失败。

- [ ] **Step 3: 实现稳定值对象**

创建 `src/order_contracts/value_objects.py`：

```python
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    field_serializer,
)


def _validate_money_input(value: Any) -> Any:
    if not isinstance(value, (Decimal, str)):
        raise ValueError("money amount must be a Decimal or decimal string")
    return value


def _normalize_currency(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().upper()
    return value


OrderId = Annotated[StrictStr, Field(pattern=r"^ord_[0-9a-f]{12}$")]
CustomerId = Annotated[StrictStr, Field(pattern=r"^cus_[0-9a-f]{12}$")]
CurrencyCode = Annotated[
    StrictStr,
    BeforeValidator(_normalize_currency),
    Field(pattern=r"^[A-Z]{3}$"),
]
Sku = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"),
]
MoneyAmount = Annotated[
    Decimal,
    BeforeValidator(_validate_money_input),
    Field(gt=Decimal("0"), max_digits=12, decimal_places=2),
]


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: MoneyAmount
    currency: CurrencyCode

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")
```

- [ ] **Step 4: 验证值对象测试转绿**

Run: `cd python-pydantic/lab && uv run pytest tests/test_value_objects.py -v`

Expected: `5 passed`。

- [ ] **Step 5: 写 CreateOrder 失败测试**

创建 `tests/test_create_order.py`：

```python
from copy import deepcopy

import pytest
from pydantic import ValidationError

from order_contracts.inbound.create_order import CreateOrderRequest


def valid_payload() -> dict[str, object]:
    return {
        "customer_id": "cus_0123456789ab",
        "idempotency_key": "checkout-2026-0001",
        "items": [
            {
                "sku": "SKU-RED-1",
                "quantity": 2,
                "unit_price": {"amount": "12.30", "currency": "usd"},
            }
        ],
    }


def test_create_order_normalizes_nested_currency() -> None:
    request = CreateOrderRequest.model_validate(valid_payload())
    assert request.items[0].unit_price.currency == "USD"


def test_quantity_does_not_coerce_string() -> None:
    payload = deepcopy(valid_payload())
    payload["items"][0]["quantity"] = "2"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "int_type"
    assert error["loc"] == ("items", 0, "quantity")


def test_http_contract_forbids_unknown_fields() -> None:
    payload = valid_payload()
    payload["is_admin"] = True
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_duplicate_sku_is_rejected() -> None:
    payload = valid_payload()
    first = deepcopy(payload["items"][0])  # type: ignore[index]
    payload["items"] = [first, deepcopy(first)]
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "value_error"


def test_validated_items_are_immutable() -> None:
    request = CreateOrderRequest.model_validate(valid_payload())
    with pytest.raises(TypeError):
        request.items[0] = request.items[0]  # type: ignore[index]
    assert isinstance(request.items, tuple)
```

- [ ] **Step 6: 运行并确认 CreateOrder 模型尚不存在**

Run: `cd python-pydantic/lab && uv run pytest tests/test_create_order.py -v`

Expected: collection 以缺少 `order_contracts.inbound.create_order` 失败。

- [ ] **Step 7: 实现严格 HTTP 入站模型**

创建 `src/order_contracts/inbound/create_order.py`：

```python
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, StringConstraints, model_validator

from order_contracts.value_objects import CustomerId, Money, Sku


IdempotencyKey = Annotated[
    StrictStr,
    StringConstraints(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"),
]
Quantity = Annotated[StrictInt, Field(ge=1, le=100)]


class CreateOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: Sku
    quantity: Quantity
    unit_price: Money


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: CustomerId
    idempotency_key: IdempotencyKey
    items: Annotated[tuple[CreateOrderItem, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def reject_duplicate_skus(self) -> Self:
        skus = [item.sku for item in self.items]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate sku is not allowed")
        return self
```

- [ ] **Step 8: 跑该任务全部测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_value_objects.py tests/test_create_order.py -v`

Expected: `10 passed`。

- [ ] **Step 9: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/value_objects.py python-pydantic/lab/src/order_contracts/inbound/create_order.py python-pydantic/lab/tests/test_value_objects.py python-pydantic/lab/tests/test_create_order.py
git commit -m "feat(pydantic): add strict order input contracts"
```

---

### Task 3: Payment Webhook 可辨识联合契约

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/inbound/payment_webhook.py`
- Create: `python-pydantic/lab/tests/test_webhook.py`

**Interfaces:**
- Consumes: `OrderId`、`Money`。
- Produces: `PaymentSucceeded`、`PaymentFailed`、`PaymentPayload`、`PaymentWebhookEnvelope`。
- Policy: `event_type` 为 discriminator；时间必须带时区；模型只验证 payload，不验证签名。

- [ ] **Step 1: 写 discriminator 与时区失败测试**

创建 `tests/test_webhook.py`：

```python
from copy import deepcopy

import pytest
from pydantic import ValidationError

from order_contracts.inbound.payment_webhook import PaymentSucceeded, PaymentWebhookEnvelope


def succeeded_payload() -> dict[str, object]:
    return {
        "event_id": "evt_0123456789ab",
        "schema_version": 1,
        "payload": {
            "event_type": "payment.succeeded",
            "provider_reference": "pay_demo_001",
            "order_id": "ord_0123456789ab",
            "paid_amount": {"amount": "24.60", "currency": "USD"},
            "occurred_at": "2026-07-15T12:30:00Z",
        },
    }


def test_discriminator_selects_succeeded_payload() -> None:
    envelope = PaymentWebhookEnvelope.model_validate(succeeded_payload())
    assert isinstance(envelope.payload, PaymentSucceeded)


def test_unknown_event_type_has_stable_union_error() -> None:
    payload = succeeded_payload()
    payload["payload"]["event_type"] = "payment.refunded"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "union_tag_invalid"
    assert error["loc"] == ("payload",)


def test_naive_datetime_is_rejected() -> None:
    payload = deepcopy(succeeded_payload())
    payload["payload"]["occurred_at"] = "2026-07-15T12:30:00"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "timezone_aware"


def test_failed_payload_requires_failure_code() -> None:
    payload = succeeded_payload()
    payload["payload"] = {
        "event_type": "payment.failed",
        "provider_reference": "pay_demo_002",
        "order_id": "ord_0123456789ab",
        "occurred_at": "2026-07-15T12:30:00Z",
    }
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "missing"
```

- [ ] **Step 2: 运行并确认模型缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_webhook.py -v`

Expected: collection 以缺少 `order_contracts.inbound.payment_webhook` 失败。

- [ ] **Step 3: 实现 Webhook payload union**

创建 `src/order_contracts/inbound/payment_webhook.py`：

```python
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, StringConstraints

from order_contracts.value_objects import Money, OrderId


EventId = Annotated[StrictStr, Field(pattern=r"^evt_[0-9a-f]{12}$")]
ProviderReference = Annotated[
    StrictStr,
    StringConstraints(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"),
]
FailureCode = Annotated[
    StrictStr,
    StringConstraints(min_length=3, max_length=40, pattern=r"^[A-Z0-9_]+$"),
]


class PaymentSucceeded(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["payment.succeeded"]
    provider_reference: ProviderReference
    order_id: OrderId
    paid_amount: Money
    occurred_at: AwareDatetime


class PaymentFailed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["payment.failed"]
    provider_reference: ProviderReference
    order_id: OrderId
    failure_code: FailureCode
    occurred_at: AwareDatetime


PaymentPayload = Annotated[PaymentSucceeded | PaymentFailed, Field(discriminator="event_type")]


class PaymentWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: EventId
    schema_version: Literal[1]
    payload: PaymentPayload
```

- [ ] **Step 4: 验证全部 Webhook 行为**

Run: `cd python-pydantic/lab && uv run pytest tests/test_webhook.py -v`

Expected: `4 passed`。

- [ ] **Step 5: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/inbound/payment_webhook.py python-pydantic/lab/tests/test_webhook.py
git commit -m "feat(pydantic): add discriminated payment webhook"
```

---

### Task 4: 显式映射到应用命令与领域订单

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/application/commands.py`
- Create: `python-pydantic/lab/src/order_contracts/domain/order.py`
- Create: `python-pydantic/lab/src/order_contracts/adapters.py`
- Create: `python-pydantic/lab/tests/test_adapters.py`
- Create: `python-pydantic/lab/tests/test_domain_order.py`

**Interfaces:**
- Consumes: `CreateOrderRequest`。
- Produces: `CreateOrderLine`、`CreateOrderCommand`、`OrderStatus`、`OrderLine`、`Order`。
- Produces: `to_create_order_command(request: CreateOrderRequest) -> CreateOrderCommand`。
- Policy: command／domain 层不继承 Pydantic；混合币种是领域不变量，不塞进入站 validator。

- [ ] **Step 1: 写 mapper 和领域失败测试**

创建 `tests/test_adapters.py`：

```python
from decimal import Decimal

from order_contracts.adapters import to_create_order_command
from order_contracts.inbound.create_order import CreateOrderRequest


def test_mapper_lists_fields_explicitly() -> None:
    request = CreateOrderRequest.model_validate(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "USD"},
                }
            ],
        }
    )
    command = to_create_order_command(request)
    assert command.customer_id == "cus_0123456789ab"
    assert command.lines[0].unit_amount == Decimal("12.30")
    assert command.lines[0].currency == "USD"
```

创建 `tests/test_domain_order.py`：

```python
from decimal import Decimal

import pytest

from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order, OrderStatus


def test_order_calculates_total_from_command() -> None:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    order = Order.create("ord_0123456789ab", command)
    assert order.total_amount == Decimal("24.60")
    assert order.currency == "USD"
    assert order.status is OrderStatus.PENDING_PAYMENT


def test_mixed_currency_is_a_domain_error() -> None:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(
            CreateOrderLine("SKU-RED-1", 1, Decimal("12.30"), "USD"),
            CreateOrderLine("SKU-BLUE-1", 1, Decimal("10.00"), "EUR"),
        ),
    )
    with pytest.raises(ValueError, match="single currency"):
        Order.create("ord_0123456789ab", command)
```

- [ ] **Step 2: 运行并确认应用／领域模块缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_adapters.py tests/test_domain_order.py -v`

Expected: collection 因缺少 `application.commands`、`domain.order` 或 `adapters` 失败。

- [ ] **Step 3: 实现不依赖 Pydantic 的命令 dataclass**

创建 `src/order_contracts/application/commands.py`：

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateOrderLine:
    sku: str
    quantity: int
    unit_amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    customer_id: str
    idempotency_key: str
    lines: tuple[CreateOrderLine, ...]
```

- [ ] **Step 4: 实现领域订单及业务不变量**

创建 `src/order_contracts/domain/order.py`：

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from order_contracts.application.commands import CreateOrderCommand


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"


@dataclass(frozen=True, slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_amount: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_amount * self.quantity


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    customer_id: str
    lines: tuple[OrderLine, ...]
    currency: str
    status: OrderStatus
    internal_note: str | None = None

    @classmethod
    def create(cls, order_id: str, command: CreateOrderCommand) -> "Order":
        currencies = {line.currency for line in command.lines}
        if len(currencies) != 1:
            raise ValueError("an order must use a single currency")
        lines = tuple(
            OrderLine(
                sku=line.sku,
                quantity=line.quantity,
                unit_amount=line.unit_amount,
            )
            for line in command.lines
        )
        return cls(
            order_id=order_id,
            customer_id=command.customer_id,
            lines=lines,
            currency=next(iter(currencies)),
            status=OrderStatus.PENDING_PAYMENT,
        )

    @property
    def total_amount(self) -> Decimal:
        return sum((line.subtotal for line in self.lines), start=Decimal("0"))
```

- [ ] **Step 5: 实现逐字段 mapper**

创建 `src/order_contracts/adapters.py`：

```python
from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.inbound.create_order import CreateOrderRequest


def to_create_order_command(request: CreateOrderRequest) -> CreateOrderCommand:
    return CreateOrderCommand(
        customer_id=request.customer_id,
        idempotency_key=request.idempotency_key,
        lines=tuple(
            CreateOrderLine(
                sku=item.sku,
                quantity=item.quantity,
                unit_amount=item.unit_price.amount,
                currency=item.unit_price.currency,
            )
            for item in request.items
        ),
    )
```

- [ ] **Step 6: 验证 mapper 与领域测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_adapters.py tests/test_domain_order.py -v`

Expected: `3 passed`。

- [ ] **Step 7: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/application/commands.py python-pydantic/lab/src/order_contracts/domain/order.py python-pydantic/lab/src/order_contracts/adapters.py python-pydantic/lab/tests/test_adapters.py python-pydantic/lab/tests/test_domain_order.py
git commit -m "feat(pydantic): separate boundary DTOs from domain"
```

---

### Task 5: 输出白名单与序列化泄漏防御

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/outbound/views.py`
- Modify: `python-pydantic/lab/src/order_contracts/adapters.py`
- Create: `python-pydantic/lab/tests/test_serialization.py`

**Interfaces:**
- Consumes: `Order`、`Money`。
- Produces: `CustomerOrderView`、`InternalOrderView`、`CustomerOrderEnvelope`。
- Produces: `project_customer_order(order: Order) -> CustomerOrderView`、`project_internal_order(order: Order, provider_reference: str | None) -> InternalOrderView`。
- Policy: 客户输出只由白名单模型决定；默认按字段注解序列化，测试证明打开 `serialize_as_any` 会暴露子类字段。

- [ ] **Step 1: 写输出投影和泄漏失败测试**

创建 `tests/test_serialization.py`：

```python
from decimal import Decimal

from order_contracts.adapters import project_customer_order, project_internal_order
from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order
from order_contracts.outbound.views import CustomerOrderEnvelope


def make_order() -> Order:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    return Order.create("ord_0123456789ab", command)


def test_customer_projection_is_an_explicit_whitelist() -> None:
    view = project_customer_order(make_order())
    dumped = view.model_dump(mode="json")
    assert dumped == {
        "order_id": "ord_0123456789ab",
        "status": "pending_payment",
        "total": {"amount": "24.60", "currency": "USD"},
        "item_count": 1,
    }


def test_base_annotation_hides_internal_subclass_fields_by_default() -> None:
    internal = project_internal_order(make_order(), provider_reference="pay_demo_001")
    envelope = CustomerOrderEnvelope(order=internal)
    safe = envelope.model_dump(mode="json")
    assert "customer_id" not in safe["order"]
    assert "provider_reference" not in safe["order"]


def test_serialize_as_any_demonstrates_the_leak_risk() -> None:
    internal = project_internal_order(make_order(), provider_reference="pay_demo_001")
    envelope = CustomerOrderEnvelope(order=internal)
    unsafe = envelope.model_dump(mode="json", serialize_as_any=True)
    assert unsafe["order"]["customer_id"] == "cus_0123456789ab"
    assert unsafe["order"]["provider_reference"] == "pay_demo_001"
```

- [ ] **Step 2: 运行并确认输出模块／函数缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_serialization.py -v`

Expected: collection 因缺少 `outbound.views` 或 projection 函数失败。

- [ ] **Step 3: 实现客户与内部输出模型**

创建 `src/order_contracts/outbound/views.py`：

```python
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from order_contracts.domain.order import OrderStatus
from order_contracts.value_objects import CustomerId, Money, OrderId


class CustomerOrderView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: OrderId
    status: OrderStatus
    total: Money
    item_count: StrictInt


class InternalOrderView(CustomerOrderView):
    customer_id: CustomerId
    provider_reference: StrictStr | None
    internal_note: StrictStr | None


class CustomerOrderEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: CustomerOrderView
```

- [ ] **Step 4: 在 adapters 中追加显式 projection**

在 `src/order_contracts/adapters.py` 增加 imports：

```python
from order_contracts.domain.order import Order
from order_contracts.outbound.views import CustomerOrderView, InternalOrderView
from order_contracts.value_objects import Money
```

并追加：

```python
def project_customer_order(order: Order) -> CustomerOrderView:
    return CustomerOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
    )


def project_internal_order(
    order: Order,
    provider_reference: str | None,
) -> InternalOrderView:
    return InternalOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
        customer_id=order.customer_id,
        provider_reference=provider_reference,
        internal_note=order.internal_note,
    )
```

- [ ] **Step 5: 验证安全与危险两条序列化路径**

Run: `cd python-pydantic/lab && uv run pytest tests/test_serialization.py -v`

Expected: `3 passed`；默认输出无内部字段，显式 `serialize_as_any=True` 测试展示风险。

- [ ] **Step 6: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/outbound/views.py python-pydantic/lab/src/order_contracts/adapters.py python-pydantic/lab/tests/test_serialization.py
git commit -m "feat(pydantic): add safe outbound projections"
```

---

### Task 6: 版本化 OrderCreated 事件与 TypeAdapter

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/events/v1.py`
- Create: `python-pydantic/lab/src/order_contracts/events/v2.py`
- Create: `python-pydantic/lab/src/order_contracts/events/envelope.py`
- Modify: `python-pydantic/lab/src/order_contracts/events/__init__.py`
- Modify: `python-pydantic/lab/src/order_contracts/adapters.py`
- Create: `python-pydantic/lab/tests/test_event_compatibility.py`

**Interfaces:**
- Produces: `OrderCreatedV1`、`OrderCreatedV2`。
- Produces: `EventEnvelope[T]`、`OrderCreatedEnvelopeV1`、`OrderCreatedEnvelopeV2`、`OrderCreatedMessage`。
- Produces: `parse_order_created(raw: bytes) -> OrderCreatedMessage`。
- Produces: `project_order_created_v2(order: Order, event_id: str, occurred_at: datetime) -> OrderCreatedEnvelopeV2`。
- Policy: V1 payload 对新增字段使用 `extra='ignore'` 以展示向前读取；V2 producer 使用 `extra='forbid'`；envelope 用 `schema_version` discriminator 明确选择版本。

- [ ] **Step 1: 写事件解析与兼容性失败测试**

创建 `tests/test_event_compatibility.py`：

```python
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from order_contracts.adapters import project_order_created_v2
from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order
from order_contracts.events.envelope import (
    OrderCreatedEnvelopeV2,
    parse_order_created,
)
from order_contracts.events.v1 import OrderCreatedV1


def v2_message() -> dict[str, object]:
    return {
        "event_id": "msg_0123456789ab",
        "event_type": "order.created",
        "schema_version": 2,
        "occurred_at": "2026-07-15T12:30:00Z",
        "payload": {
            "order_id": "ord_0123456789ab",
            "customer_id": "cus_0123456789ab",
            "total": {"amount": "24.60", "currency": "USD"},
            "item_count": 1,
        },
    }


def test_type_adapter_selects_v2_envelope() -> None:
    parsed = parse_order_created(json.dumps(v2_message()).encode())
    assert isinstance(parsed, OrderCreatedEnvelopeV2)
    assert parsed.payload.item_count == 1


def test_v1_payload_reader_ignores_additive_v2_field() -> None:
    payload = v2_message()["payload"]
    parsed = OrderCreatedV1.model_validate(payload)
    assert parsed.order_id == "ord_0123456789ab"
    assert "item_count" not in parsed.model_dump()


def test_unknown_schema_version_is_incompatible() -> None:
    message = v2_message()
    message["schema_version"] = 3
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    assert caught.value.errors()[0]["type"] == "union_tag_invalid"


def test_v2_producer_rejects_unknown_payload_field() -> None:
    message = v2_message()
    message["payload"]["internal_note"] = "must not escape"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_domain_order_is_explicitly_projected_to_v2_event() -> None:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    order = Order.create("ord_0123456789ab", command)
    event = project_order_created_v2(
        order,
        event_id="msg_0123456789ab",
        occurred_at=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
    )
    assert event.payload.order_id == order.order_id
    assert event.payload.total.amount == Decimal("24.60")
    assert event.payload.item_count == 1
```

- [ ] **Step 2: 运行并确认事件模块缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_event_compatibility.py -v`

Expected: collection 因缺少 `events.envelope`／`events.v1` 失败。

- [ ] **Step 3: 实现 V1／V2 payload**

`src/order_contracts/events/v1.py`：

```python
from pydantic import BaseModel, ConfigDict

from order_contracts.value_objects import CustomerId, Money, OrderId


class OrderCreatedV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    order_id: OrderId
    customer_id: CustomerId
    total: Money
```

`src/order_contracts/events/v2.py`：

```python
from typing import Annotated

from pydantic import ConfigDict, Field, StrictInt

from order_contracts.events.v1 import OrderCreatedV1


class OrderCreatedV2(OrderCreatedV1):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_count: Annotated[StrictInt, Field(ge=1, le=100)]
```

- [ ] **Step 4: 实现 generic envelope 与版本 adapter**

创建 `src/order_contracts/events/envelope.py`：

```python
from typing import Annotated, Generic, Literal, TypeAlias, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter

from order_contracts.events.v1 import OrderCreatedV1
from order_contracts.events.v2 import OrderCreatedV2


PayloadT = TypeVar("PayloadT")
MessageId = Annotated[StrictStr, Field(pattern=r"^msg_[0-9a-f]{12}$")]


class EventEnvelope(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: MessageId
    event_type: StrictStr
    schema_version: StrictInt
    occurred_at: AwareDatetime
    payload: PayloadT


class OrderCreatedEnvelopeV1(EventEnvelope[OrderCreatedV1]):
    event_type: Literal["order.created"]
    schema_version: Literal[1]


class OrderCreatedEnvelopeV2(EventEnvelope[OrderCreatedV2]):
    event_type: Literal["order.created"]
    schema_version: Literal[2]


OrderCreatedMessage: TypeAlias = Annotated[
    OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2,
    Field(discriminator="schema_version"),
]
ORDER_CREATED_ADAPTER = TypeAdapter(OrderCreatedMessage)


def parse_order_created(raw: bytes) -> OrderCreatedMessage:
    return ORDER_CREATED_ADAPTER.validate_json(raw)
```

更新 `src/order_contracts/events/__init__.py`，仅公开稳定入口：

```python
"""Versioned event contracts and parsing adapters."""

from order_contracts.events.envelope import OrderCreatedMessage, parse_order_created

__all__ = ["OrderCreatedMessage", "parse_order_created"]
```

- [ ] **Step 5: 在 adapter 中追加领域到事件的显式 projection**

在 `src/order_contracts/adapters.py` 增加 imports：

```python
from datetime import datetime

from order_contracts.events.envelope import OrderCreatedEnvelopeV2
from order_contracts.events.v2 import OrderCreatedV2
```

并追加：

```python
def project_order_created_v2(
    order: Order,
    event_id: str,
    occurred_at: datetime,
) -> OrderCreatedEnvelopeV2:
    return OrderCreatedEnvelopeV2(
        event_id=event_id,
        event_type="order.created",
        schema_version=2,
        occurred_at=occurred_at,
        payload=OrderCreatedV2(
            order_id=order.order_id,
            customer_id=order.customer_id,
            total=Money(amount=order.total_amount, currency=order.currency),
            item_count=len(order.lines),
        ),
    )
```

- [ ] **Step 6: 跑事件兼容与 projection 测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_event_compatibility.py -v`

Expected: `5 passed`。

- [ ] **Step 7: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/events python-pydantic/lab/src/order_contracts/adapters.py python-pydantic/lab/tests/test_event_compatibility.py
git commit -m "feat(pydantic): version order-created event contracts"
```

---

### Task 7: 稳定错误契约、Webhook 签名边界与 MQ 失败分类

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/errors.py`
- Modify: `python-pydantic/lab/src/order_contracts/adapters.py`
- Create: `python-pydantic/lab/tests/test_errors.py`
- Modify: `python-pydantic/lab/tests/test_webhook.py`

**Interfaces:**
- Produces: `ErrorDetail`、`ErrorResponse`、`to_error_response(error: ValidationError) -> ErrorResponse`。
- Produces: `MessageFailureKind`、`classify_consume_failure(error: Exception) -> MessageFailureKind`。
- Produces: `parse_create_order(raw: bytes) -> CreateOrderRequest`、`parse_payment_webhook(raw: bytes, signature: str, secret: SecretStr) -> PaymentWebhookEnvelope`。
- Policy: Webhook 先验签再解析；错误输出只有 machine type 和 loc；ValidationError 不等于可重试政策。

- [ ] **Step 1: 写错误清洗与分类失败测试**

创建 `tests/test_errors.py`：

```python
import json

import pytest
from pydantic import ValidationError

from order_contracts.errors import (
    MessageFailureKind,
    classify_consume_failure,
    to_error_response,
)
from order_contracts.events.envelope import parse_order_created
from order_contracts.inbound.create_order import CreateOrderRequest


def test_error_response_exposes_type_and_loc_but_not_input() -> None:
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(
            {
                "customer_id": "top-secret-customer-value",
                "idempotency_key": "checkout-2026-0001",
                "items": [],
            }
        )
    response = to_error_response(caught.value)
    dumped = response.model_dump_json()
    assert response.details[0].reason in {"string_pattern_mismatch", "too_short"}
    assert "top-secret-customer-value" not in dumped


def test_unknown_event_version_is_incompatible_not_transient() -> None:
    raw = json.dumps(
        {
            "event_id": "msg_0123456789ab",
            "event_type": "order.created",
            "schema_version": 9,
            "occurred_at": "2026-07-15T12:30:00Z",
            "payload": {},
        }
    ).encode()
    with pytest.raises(ValidationError) as caught:
        parse_order_created(raw)
    assert classify_consume_failure(caught.value) is MessageFailureKind.INCOMPATIBLE


def test_field_validation_is_permanent_and_timeout_is_transient() -> None:
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate({})
    assert classify_consume_failure(caught.value) is MessageFailureKind.PERMANENT
    assert classify_consume_failure(TimeoutError("broker unavailable")) is MessageFailureKind.TRANSIENT
```

- [ ] **Step 2: 写签名先于 payload parsing 的失败测试**

向 `tests/test_webhook.py` 追加：

```python
import hashlib
import hmac
import json

from pydantic import SecretStr

from order_contracts.adapters import InvalidWebhookSignature, parse_payment_webhook


def test_webhook_rejects_signature_before_parsing_payload() -> None:
    with pytest.raises(InvalidWebhookSignature):
        parse_payment_webhook(
            b"not-json",
            signature="bad-signature",
            secret=SecretStr("demo-secret"),
        )


def test_valid_signature_then_parses_payload() -> None:
    raw = json.dumps(succeeded_payload(), separators=(",", ":")).encode()
    signature = hmac.new(b"demo-secret", raw, hashlib.sha256).hexdigest()
    parsed = parse_payment_webhook(raw, signature, SecretStr("demo-secret"))
    assert parsed.event_id == "evt_0123456789ab"
```

- [ ] **Step 3: 运行并确认错误／签名接口缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_errors.py tests/test_webhook.py -v`

Expected: collection 因缺少 `errors.py` 或 adapter API 失败。

- [ ] **Step 4: 实现稳定且不含原始 input 的错误 DTO**

创建 `src/order_contracts/errors.py`：

```python
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str
    path: list[str | int]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal["invalid_request"] = "invalid_request"
    details: list[ErrorDetail]


def to_error_response(error: ValidationError) -> ErrorResponse:
    return ErrorResponse(
        details=[
            ErrorDetail(
                reason=item["type"],
                path=list(item["loc"]),
            )
            for item in error.errors(include_url=False)
        ]
    )


class MessageFailureKind(StrEnum):
    INCOMPATIBLE = "incompatible"
    PERMANENT = "permanent"
    TRANSIENT = "transient"


def classify_consume_failure(error: Exception) -> MessageFailureKind:
    if not isinstance(error, ValidationError):
        return MessageFailureKind.TRANSIENT
    error_types = {item["type"] for item in error.errors(include_url=False)}
    incompatible_types = {"union_tag_invalid", "union_tag_not_found", "literal_error"}
    if error_types & incompatible_types:
        return MessageFailureKind.INCOMPATIBLE
    return MessageFailureKind.PERMANENT
```

- [ ] **Step 5: 在 adapter 中实现边界解析与 HMAC 验签**

在 `src/order_contracts/adapters.py` 增加 imports：

```python
import hashlib
import hmac

from pydantic import SecretStr

from order_contracts.inbound.payment_webhook import PaymentWebhookEnvelope
```

并追加：

```python
class InvalidWebhookSignature(ValueError):
    """Raised before payload parsing when the provider signature is invalid."""


def parse_create_order(raw: bytes) -> CreateOrderRequest:
    return CreateOrderRequest.model_validate_json(raw)


def parse_payment_webhook(
    raw: bytes,
    signature: str,
    secret: SecretStr,
) -> PaymentWebhookEnvelope:
    expected = hmac.new(
        secret.get_secret_value().encode(),
        raw,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidWebhookSignature("invalid webhook signature")
    return PaymentWebhookEnvelope.model_validate_json(raw)
```

- [ ] **Step 6: 验证错误、安全与失败分类**

Run: `cd python-pydantic/lab && uv run pytest tests/test_errors.py tests/test_webhook.py -v`

Expected: `9 passed`；输出 JSON 不出现敏感 input；坏签名在坏 JSON 之前失败。

- [ ] **Step 7: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/errors.py python-pydantic/lab/src/order_contracts/adapters.py python-pydantic/lab/tests/test_errors.py python-pydantic/lab/tests/test_webhook.py
git commit -m "feat(pydantic): add safe boundary error policies"
```

---

### Task 8: 生产级 pydantic-settings 来源、缓存与隔离

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/config.py`
- Create: `python-pydantic/lab/tests/test_settings.py`

**Interfaces:**
- Produces: `PaymentProviderSettings`、`AppSettings`。
- Produces: `load_settings(env_file: Path | None = None, secrets_dir: Path | None = None) -> AppSettings`。
- Produces: `get_settings() -> AppSettings`、`clear_settings_cache() -> None`。
- Policy: default 不读 `.env`；显式 source 顺序为 init > env > dotenv > file secrets > defaults；逗号分隔 currency 是受测 custom env source；没有 import-time singleton。

- [ ] **Step 1: 写 Settings 来源和隔离失败测试**

创建 `tests/test_settings.py`：

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_settings import BaseSettings

from order_contracts.config import clear_settings_cache, get_settings, load_settings


ENV_KEYS = (
    "ORDER_ENVIRONMENT",
    "ORDER_LOG_LEVEL",
    "ORDER_ALLOWED_CURRENCIES",
    "ORDER_PAYMENT__BASE_URL",
    "ORDER_PAYMENT__WEBHOOK_SECRET",
    "ORDER_PAYMENT__TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_order_environment(monkeypatch) -> Iterator[None]:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()


def set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("ORDER_PAYMENT__BASE_URL", "https://env.example.test")
    monkeypatch.setenv("ORDER_PAYMENT__WEBHOOK_SECRET", "env-secret")


def test_env_overrides_explicit_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv = tmp_path / "settings.env"
    dotenv.write_text(
        "ORDER_PAYMENT__BASE_URL=https://dotenv.example.test\n"
        "ORDER_PAYMENT__WEBHOOK_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )
    set_required_env(monkeypatch)
    settings = load_settings(env_file=dotenv)
    assert str(settings.payment.base_url) == "https://env.example.test/"
    assert settings.payment.webhook_secret.get_secret_value() == "env-secret"


def test_custom_env_source_parses_currency_csv(monkeypatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("ORDER_ALLOWED_CURRENCIES", "usd, eur")
    settings = load_settings()
    assert settings.allowed_currencies == ("USD", "EUR")


def test_default_loader_does_not_read_ambient_dotenv(monkeypatch, tmp_path: Path) -> None:
    set_required_env(monkeypatch)
    (tmp_path / ".env").write_text("ORDER_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    assert settings.log_level == "INFO"


def test_file_secret_source_can_be_explicit(monkeypatch, tmp_path: Path) -> None:
    class SecretOnlySettings(BaseSettings):
        api_key: SecretStr

    monkeypatch.delenv("API_KEY", raising=False)
    (tmp_path / "api_key").write_text("file-secret", encoding="utf-8")
    settings = SecretOnlySettings(_secrets_dir=tmp_path)
    assert settings.api_key.get_secret_value() == "file-secret"
    assert "file-secret" not in repr(settings)


def test_cache_is_explicit_and_clearable(monkeypatch) -> None:
    set_required_env(monkeypatch)
    clear_settings_cache()
    first = get_settings()
    second = get_settings()
    assert first is second
    clear_settings_cache()
    assert get_settings() is not first
    clear_settings_cache()
```

- [ ] **Step 2: 运行并确认 config 模块缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_settings.py -v`

Expected: collection 以缺少 `order_contracts.config` 失败。

- [ ] **Step 3: 实现嵌套 Settings 和 custom env source**

创建 `src/order_contracts/config.py`：

```python
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from order_contracts.value_objects import CurrencyCode


class PaymentProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: AnyHttpUrl
    webhook_secret: SecretStr
    timeout_seconds: Annotated[int, Field(gt=0, le=30)] = 3


class CommaSeparatedEnvSource(EnvSettingsSource):
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "allowed_currencies" and isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        env_nested_delimiter="__",
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_currencies: tuple[CurrencyCode, ...] = ("USD",)
    payment: PaymentProviderSettings

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            CommaSeparatedEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


def load_settings(
    *,
    env_file: Path | None = None,
    secrets_dir: Path | None = None,
) -> AppSettings:
    return AppSettings(_env_file=env_file, _secrets_dir=secrets_dir)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
```

- [ ] **Step 4: 跑 Settings 全部测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_settings.py -v`

Expected: `5 passed`；测试不读取仓库或开发者真实 `.env`。

- [ ] **Step 5: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/config.py python-pydantic/lab/tests/test_settings.py
git commit -m "feat(pydantic): govern production settings sources"
```

---

### Task 9: JSON Schema golden 生成与契约差异门槛

**Files:**
- Create: `python-pydantic/lab/scripts/export_schemas.py`
- Create: `python-pydantic/lab/tests/test_json_schema.py`
- Create: `python-pydantic/lab/schemas/create-order.schema.json`
- Create: `python-pydantic/lab/schemas/order-created-v1.schema.json`
- Create: `python-pydantic/lab/schemas/order-created-v2.schema.json`

**Interfaces:**
- Consumes: `CreateOrderRequest`、`OrderCreatedEnvelopeV1`、`OrderCreatedEnvelopeV2`。
- Produces: 三个使用 UTF-8、两空格缩进、key 排序、末尾换行的确定性 schema 文件。
- Policy: golden 是人工审查契约变化的 diff，不代替兼容性测试。

- [ ] **Step 1: 写 golden 缺失时失败的测试**

创建 `tests/test_json_schema.py`：

```python
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from order_contracts.events.envelope import OrderCreatedEnvelopeV1, OrderCreatedEnvelopeV2
from order_contracts.inbound.create_order import CreateOrderRequest


SCHEMA_DIR = Path(__file__).parents[1] / "schemas"
MODELS: dict[str, type[BaseModel]] = {
    "create-order.schema.json": CreateOrderRequest,
    "order-created-v1.schema.json": OrderCreatedEnvelopeV1,
    "order-created-v2.schema.json": OrderCreatedEnvelopeV2,
}


@pytest.mark.parametrize(("filename", "model"), MODELS.items())
def test_json_schema_matches_reviewed_golden(filename: str, model: type[BaseModel]) -> None:
    expected = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    assert model.model_json_schema(mode="validation") == expected
```

- [ ] **Step 2: 运行并确认 golden 不存在**

Run: `cd python-pydantic/lab && uv run pytest tests/test_json_schema.py -v`

Expected: 三个 case 都以 `FileNotFoundError` 失败。

- [ ] **Step 3: 创建确定性 schema exporter**

创建 `scripts/export_schemas.py`：

```python
import json
from pathlib import Path

from pydantic import BaseModel

from order_contracts.events.envelope import OrderCreatedEnvelopeV1, OrderCreatedEnvelopeV2
from order_contracts.inbound.create_order import CreateOrderRequest


ROOT = Path(__file__).parents[1]
SCHEMA_DIR = ROOT / "schemas"
MODELS: dict[str, type[BaseModel]] = {
    "create-order.schema.json": CreateOrderRequest,
    "order-created-v1.schema.json": OrderCreatedEnvelopeV1,
    "order-created-v2.schema.json": OrderCreatedEnvelopeV2,
}


def render_schema(model: type[BaseModel]) -> str:
    schema = model.model_json_schema(mode="validation")
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, model in MODELS.items():
        (SCHEMA_DIR / filename).write_text(render_schema(model), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 生成并审查三份 schema**

Run: `cd python-pydantic/lab && uv run python scripts/export_schemas.py`

Expected: `schemas/` 下生成三份非空 JSON；人工检查 required、`additionalProperties`、ID pattern、amount 约束、event version literal 与 nested `$defs` 符合模型政策。

- [ ] **Step 5: 验证 golden 与重复生成稳定**

Run: `cd python-pydantic/lab && uv run pytest tests/test_json_schema.py -v`

Expected: `3 passed`。

Run: `cd python-pydantic/lab && uv run python scripts/export_schemas.py && git diff --exit-code -- schemas`

Expected: exit code 0，重复生成没有 diff。

- [ ] **Step 6: Commit**

```bash
git add python-pydantic/lab/scripts/export_schemas.py python-pydantic/lab/tests/test_json_schema.py python-pydantic/lab/schemas
git commit -m "test(pydantic): lock reviewed JSON schemas"
```

---

### Task 10: 隔离 CoreSchema 高级扩展与性能观察

**Files:**
- Create: `python-pydantic/lab/src/order_contracts/advanced_types.py`
- Create: `python-pydantic/lab/src/order_contracts/performance.py`
- Create: `python-pydantic/lab/tests/test_advanced_types.py`
- Create: `python-pydantic/lab/tests/test_performance_observations.py`

**Interfaces:**
- Produces: `ProviderReference` 直接 CoreSchema／JSON Schema hook 示例。
- Produces: `ValidationTiming`、`compare_json_validation(raw: bytes, iterations: int = 1000) -> ValidationTiming`。
- Policy: 高层 `Annotated` 仍是默认方案；benchmark 只返回观察值，不断言某条路径必须快多少。

- [ ] **Step 1: 写高级类型和性能失败测试**

创建 `tests/test_advanced_types.py`：

```python
import pytest
from pydantic import TypeAdapter, ValidationError

from order_contracts.advanced_types import ProviderReference


def test_core_schema_type_normalizes_and_returns_subclass() -> None:
    adapter = TypeAdapter(ProviderReference)
    value = adapter.validate_python("  pay_ABC12345  ")
    assert value == "pay_ABC12345"
    assert isinstance(value, ProviderReference)


def test_core_schema_type_has_matching_json_schema() -> None:
    schema = TypeAdapter(ProviderReference).json_schema()
    assert schema["type"] == "string"
    assert schema["pattern"] == r"^pay_[A-Za-z0-9_-]{8,64}$"


def test_core_schema_type_rejects_invalid_reference() -> None:
    with pytest.raises(ValidationError) as caught:
        TypeAdapter(ProviderReference).validate_python("wrong")
    assert caught.value.errors()[0]["type"] == "value_error"
```

创建 `tests/test_performance_observations.py`：

```python
import json

from order_contracts.performance import compare_json_validation


def test_performance_observation_has_no_machine_specific_threshold() -> None:
    raw = json.dumps(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "USD"},
                }
            ],
        }
    ).encode()
    observation = compare_json_validation(raw, iterations=10)
    assert observation.iterations == 10
    assert observation.direct_json_seconds > 0
    assert observation.loads_then_validate_seconds > 0
```

- [ ] **Step 2: 运行并确认高级模块缺失**

Run: `cd python-pydantic/lab && uv run pytest tests/test_advanced_types.py tests/test_performance_observations.py -v`

Expected: collection 因缺少 `advanced_types`／`performance` 失败。

- [ ] **Step 3: 实现版本敏感 CoreSchema hook**

创建 `src/order_contracts/advanced_types.py`：

```python
import re
from typing import Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


PROVIDER_REFERENCE_PATTERN = r"^pay_[A-Za-z0-9_-]{8,64}$"


class ProviderReference(str):
    @classmethod
    def validate(cls, value: str) -> "ProviderReference":
        normalized = value.strip()
        if re.fullmatch(PROVIDER_REFERENCE_PATTERN, normalized) is None:
            raise ValueError("invalid provider reference")
        return cls(normalized)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler.resolve_ref_schema(handler(schema))
        json_schema.update(type="string", pattern=PROVIDER_REFERENCE_PATTERN)
        return json_schema
```

- [ ] **Step 4: 实现无硬阈值计时观察**

创建 `src/order_contracts/performance.py`：

```python
import json
from dataclasses import dataclass
from timeit import timeit

from order_contracts.inbound.create_order import CreateOrderRequest


@dataclass(frozen=True, slots=True)
class ValidationTiming:
    iterations: int
    direct_json_seconds: float
    loads_then_validate_seconds: float


def compare_json_validation(raw: bytes, iterations: int = 1000) -> ValidationTiming:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    direct = timeit(
        lambda: CreateOrderRequest.model_validate_json(raw),
        number=iterations,
    )
    staged = timeit(
        lambda: CreateOrderRequest.model_validate(json.loads(raw)),
        number=iterations,
    )
    return ValidationTiming(
        iterations=iterations,
        direct_json_seconds=direct,
        loads_then_validate_seconds=staged,
    )
```

- [ ] **Step 5: 验证扩展和观察代码**

Run: `cd python-pydantic/lab && uv run pytest tests/test_advanced_types.py tests/test_performance_observations.py -v -s`

Expected: `4 passed`；没有“direct 必须比 staged 快”的断言。

- [ ] **Step 6: Commit**

```bash
git add python-pydantic/lab/src/order_contracts/advanced_types.py python-pydantic/lab/src/order_contracts/performance.py python-pydantic/lab/tests/test_advanced_types.py python-pydantic/lab/tests/test_performance_observations.py
git commit -m "feat(pydantic): isolate core-schema and timing examples"
```

---

### Task 11: 四个可执行示例与 FastAPI 薄 adapter

**Files:**
- Create: `python-pydantic/lab/examples/__init__.py`
- Create: `python-pydantic/lab/examples/validate_http_payload.py`
- Create: `python-pydantic/lab/examples/consume_event.py`
- Create: `python-pydantic/lab/examples/load_settings.py`
- Create: `python-pydantic/lab/examples/fastapi_adapter.py`
- Create: `python-pydantic/lab/tests/test_examples.py`
- Create: `python-pydantic/lab/tests/test_integrations.py`

**Interfaces:**
- Consumes: 任务 2—10 的公开入口。
- Produces: 四个 `main()`／endpoint，可导入执行且不需要网络、server、真实 secret 或当前工作目录。
- Policy: `load_settings` 只输出掩码；FastAPI 只演示 request／response adapter，不启动 Uvicorn。

- [ ] **Step 1: 先写示例契约测试**

创建 `tests/test_examples.py`：

```python
from examples.consume_event import main as consume_event
from examples.fastapi_adapter import app, create_order
from examples.load_settings import main as load_settings
from examples.validate_http_payload import main as validate_http_payload
from order_contracts.inbound.create_order import CreateOrderRequest


def test_http_example_executes() -> None:
    assert validate_http_payload() == {
        "customer_id": "cus_0123456789ab",
        "line_count": 1,
    }


def test_event_example_executes() -> None:
    assert consume_event() == {
        "version": 2,
        "order_id": "ord_0123456789ab",
    }


def test_settings_example_never_returns_raw_secret() -> None:
    result = load_settings()
    assert result["environment"] == "development"
    assert result["webhook_secret"] == "**********"
    assert "replace-with-local-demo-secret" not in str(result)


def test_fastapi_adapter_registers_route_and_function_is_callable() -> None:
    assert any(route.path == "/orders" for route in app.routes)
    request = CreateOrderRequest.model_validate(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "USD"},
                }
            ],
        }
    )
    assert create_order(request).order_id == "ord_0123456789ab"
```

创建 `tests/test_integrations.py`，把第 13 章的 ORM attribute adapter 变成受测事实：

```python
from pydantic import BaseModel, ConfigDict


class OrderRow:
    def __init__(self, order_id: str, status: str) -> None:
        self.order_id = order_id
        self.status = status


class OrderAttributeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    status: str


def test_from_attributes_only_projects_object_attributes() -> None:
    row = OrderRow("ord_0123456789ab", "pending_payment")
    view = OrderAttributeView.model_validate(row)
    assert view.model_dump() == {
        "order_id": "ord_0123456789ab",
        "status": "pending_payment",
    }
```

- [ ] **Step 2: 运行并确认 examples 尚不存在**

Run: `cd python-pydantic/lab && uv run pytest tests/test_examples.py -v`

Expected: collection 以缺少 `examples` modules 失败。

- [ ] **Step 3: 实现 HTTP 与 MQ 示例**

`examples/__init__.py`：

```python
"""Executable examples imported by the test suite."""
```

`examples/validate_http_payload.py`：

```python
import json

from order_contracts.adapters import parse_create_order, to_create_order_command


RAW_REQUEST = json.dumps(
    {
        "customer_id": "cus_0123456789ab",
        "idempotency_key": "checkout-2026-0001",
        "items": [
            {
                "sku": "SKU-RED-1",
                "quantity": 2,
                "unit_price": {"amount": "12.30", "currency": "USD"},
            }
        ],
    }
).encode()


def main() -> dict[str, str | int]:
    request = parse_create_order(RAW_REQUEST)
    command = to_create_order_command(request)
    return {"customer_id": command.customer_id, "line_count": len(command.lines)}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
```

`examples/consume_event.py`：

```python
import json

from order_contracts.events.envelope import parse_order_created


RAW_EVENT = json.dumps(
    {
        "event_id": "msg_0123456789ab",
        "event_type": "order.created",
        "schema_version": 2,
        "occurred_at": "2026-07-15T12:30:00Z",
        "payload": {
            "order_id": "ord_0123456789ab",
            "customer_id": "cus_0123456789ab",
            "total": {"amount": "24.60", "currency": "USD"},
            "item_count": 1,
        },
    }
).encode()


def main() -> dict[str, str | int]:
    event = parse_order_created(RAW_EVENT)
    return {"version": event.schema_version, "order_id": event.payload.order_id}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
```

- [ ] **Step 4: 实现显式 dotenv 与 FastAPI 示例**

`examples/load_settings.py`：

```python
import json
import os
from pathlib import Path
from unittest.mock import patch

from order_contracts.config import load_settings


EXAMPLE_ENV = Path(__file__).parents[1] / ".env.example"


def main() -> dict[str, str]:
    with patch.dict(os.environ, {}, clear=True):
        settings = load_settings(env_file=EXAMPLE_ENV)
    return {
        "environment": settings.environment,
        "payment_base_url": str(settings.payment.base_url),
        "webhook_secret": str(settings.payment.webhook_secret),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
```

`examples/fastapi_adapter.py`：

```python
from fastapi import FastAPI

from order_contracts.adapters import project_customer_order, to_create_order_command
from order_contracts.domain.order import Order
from order_contracts.inbound.create_order import CreateOrderRequest
from order_contracts.outbound.views import CustomerOrderView


app = FastAPI(title="Order contract adapter")


@app.post("/orders", response_model=CustomerOrderView)
def create_order(payload: CreateOrderRequest) -> CustomerOrderView:
    command = to_create_order_command(payload)
    order = Order.create("ord_0123456789ab", command)
    return project_customer_order(order)
```

- [ ] **Step 5: 验证 examples 由 pytest 与 CLI 两种方式执行**

Run: `cd python-pydantic/lab && uv run pytest tests/test_examples.py tests/test_integrations.py -v`

Expected: `5 passed`。

Run: `cd python-pydantic/lab && uv run python examples/validate_http_payload.py && uv run python examples/consume_event.py && uv run python examples/load_settings.py`

Expected: 三个命令退出码 0；输出不含 `replace-with-local-demo-secret`。

- [ ] **Step 6: Commit**

```bash
git add python-pydantic/lab/examples python-pydantic/lab/tests/test_examples.py python-pydantic/lab/tests/test_integrations.py
git commit -m "feat(pydantic): add executable boundary examples"
```

---

## Chapter Definition of Done

下面每个章节任务都继承这些完成条件：

1. 开头给一个具体生产事故或高级面试追问，随后用一句话给出心智模型。
2. 至少一个代码块直接导入 lab 的真实公开接口；若为独立机制片段，必须在章节内给完整 imports、输入和预期输出。
3. 明确写出机制／底层原理、订单／支付案例、错误实现、架构边界和相应 pytest 文件。
4. 包含 Java／Go 对照表、API／决策速查表，以及至少 4 张“30 秒回答 → 深挖 → 常见误区 → 生产例子”面试卡。
5. 每章结尾列出“继续阅读”相对链接，至少指向前后章、对应 lab 文件或测试；不复制其他 track 的完整内容。
6. 所有代码引用以 `python-pydantic/` 为基准使用相对路径；所有技术断言与锁定版本及 Pydantic 官方 latest stable 文档核对。
7. 文档提交前执行对应 pytest、`git diff --check` 和章节链接存在性检查。

---

### Task 12: 第 00 章——数据契约与信任边界

**Files:**
- Create: `python-pydantic/00-data-contracts-and-trust-boundaries.md`

**Interfaces:**
- Consumes: `CreateOrderRequest`、`CreateOrderCommand`、`Order`、`CustomerOrderView` 的分层事实。
- Produces: 全教程统一术语：parse、validate、normalize、authorize、act、project、serialize。

- [ ] **Step 1: 跑分层案例基线**

Run: `cd python-pydantic/lab && uv run pytest tests/test_create_order.py tests/test_adapters.py tests/test_domain_order.py tests/test_serialization.py -v`

Expected: 全部通过。

- [ ] **Step 2: 创建章节并按精确教学顺序展开**

章节必须包含这些标题和结论：

- `## 事故开场：模型构造成功，为什么订单仍然不能下？`：用“库存已售罄但 DTO 合法”区分契约有效与业务允许。
- `## 一句话心智：Pydantic 守边界，不替领域做决定`。
- `## 从 raw bytes 到领域行为的完整流水线`：画出 bytes → schema → parse/coerce → local invariants → command → domain → view/event → JSON。
- `## 五类信任边界`：HTTP、Webhook、MQ、Settings、内部命令逐行比较来源、coercion、unknown-field、失败政策。
- `## 类型注解、静态检查、运行时验证、业务规则不是一件事`：连接 `python/09-typing.md`，明确 mypy／Pyright 不在本项目安装。
- `## 订单案例：一个模型贯穿所有层会怎样`：展示 mass assignment、权限字段、版本耦合和 ORM 泄漏。
- `## 决策表：规则应该放在哪一层`：结构／局部不变量 → Pydantic；外部状态／状态迁移 → application/domain；签名／重试／ack → adapter。
- `## 对应 pytest`：解释 `test_adapters.py` 与 `test_domain_order.py` 为什么分开失败。
- Java／Go 对照必须覆盖 Bean Validation／Jackson DTO、Go struct tags／显式 validator 和 Python runtime annotation consumer。

- [ ] **Step 3: 验证术语与链接**

Run: `rg -n 'parse|validate|normalize|authorize|act|project|serialize|test_domain_order' python-pydantic/00-data-contracts-and-trust-boundaries.md`

Expected: 每个统一术语和测试文件至少出现一次；相对链接均能从该文件所在目录解析。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/00-data-contracts-and-trust-boundaries.md
git commit -m "docs(pydantic): teach contracts and trust boundaries"
```

---

### Task 13: 第 01 章——Pydantic v2 验证引擎

**Files:**
- Create: `python-pydantic/01-pydantic-v2-validation-engine.md`

**Interfaces:**
- Consumes: `CreateOrderRequest.model_validate()`、`model_validate_json()` 和 `ORDER_CREATED_ADAPTER`。
- Produces: annotation → CoreSchema → SchemaValidator／SchemaSerializer 的机制心智图。

- [ ] **Step 1: 运行两条验证入口**

Run: `cd python-pydantic/lab && uv run pytest tests/test_create_order.py tests/test_event_compatibility.py -v`

Expected: 全部通过。

- [ ] **Step 2: 创建章节并覆盖四层机制**

章节必须包含：

- `## 事故开场：每条消息都重建 TypeAdapter，CPU 为什么突然升高？`。
- `## 一句话心智：Python 构建 CoreSchema，pydantic-core 执行验证与序列化`。
- `## 类定义阶段发生什么`：解析 annotation、合并 `Annotated` metadata、生成 CoreSchema、创建并缓存 validator／serializer。
- `## 调用阶段发生什么`：Python mode、JSON mode、`model_validate_strings()` 的输入路径差异。
- `## 四个入口的契约`：`__init__`、`model_validate()`、`model_validate_json()`、`TypeAdapter.validate_json()` 的适用表。
- `## model_construct() 是可信数据逃生舱`：完整演示它可以绕过 quantity／duplicate SKU 校验；明确不要用于外部边界和不要假设永远更快。
- `## 错误树如何形成`：CoreSchema 节点积累 `type`、`loc`、input、ctx；错误显示与服务错误 DTO 分离。
- `## schema/adapter 复用与缓存`：模块级 `ORDER_CREATED_ADAPTER` 的理由，禁止请求内重复创建。
- `## 版本敏感边界`：`__pydantic_core_schema__` 只用于观察，直接 CoreSchema hook 推迟到第 11 章。
- Java／Go 对照必须覆盖 Jackson＋Bean Validation pipeline、Go 显式 decode＋validate 与 Rust core 的定位。

- [ ] **Step 3: 事实核对与术语检查**

对照 Pydantic 官方 Architecture、Models、TypeAdapter、Performance 文档，确认没有把 CoreSchema 称为 JSON Schema，也没有承诺固定内部 dict 形状。

Run: `rg -n 'CoreSchema|SchemaValidator|SchemaSerializer|model_construct|ORDER_CREATED_ADAPTER' python-pydantic/01-pydantic-v2-validation-engine.md`

Expected: 五个关键机制均出现。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/01-pydantic-v2-validation-engine.md
git commit -m "docs(pydantic): explain the v2 validation engine"
```

---

### Task 14: 第 02 章——字段语义、类型与 coercion

**Files:**
- Create: `python-pydantic/02-field-semantics-types-and-coercion.md`

**Interfaces:**
- Consumes: `OrderId`、`CurrencyCode`、`Money`、`CreateOrderItem` 和 `test_value_objects.py`。
- Produces: HTTP／Webhook／MQ／Settings 的逐字段 coercion policy 表。

- [ ] **Step 1: 跑 coercion 决策测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_value_objects.py tests/test_create_order.py -v`

Expected: ID／quantity／float 拒绝与 currency 规范化测试全部通过。

- [ ] **Step 2: 创建章节并覆盖字段的独立维度**

章节必须包含：

- required、optional、nullable、default、default_factory 的 2×2 示例，明确 `str | None` 不自动代表有默认。
- `StrictInt` 拒绝 `"2"`、`CurrencyCode` 接受 `" usd "`、Money 拒绝 float 的三列政策矩阵：输入表示、理由、错误 type。
- Python mode 与 JSON mode 的 strict 差异，以及为什么 Settings 的字符串环境值可以采用不同策略。
- `Annotated`、`Field`、`StringConstraints`、alias、validation_alias、serialization_alias 的职责与优先级。
- Decimal 的十进制字符串路径、binary float 风险、JSON 输出字符串政策；不能写成“Decimal 天然解决所有货币问题”。
- bool／int 子类关系、日期／时区、UUID／Enum／Literal 的常见反直觉转换。
- `extra='forbid'` 与协议向前兼容的取舍，指出 MQ V1 在第 08 章有不同策略。
- Java／Go 对照覆盖 Jackson coercion、BigDecimal、Go `json.Number`／自定义 unmarshaler。

- [ ] **Step 3: 检查政策矩阵与可执行引用**

Run: `rg -n 'required|nullable|StrictInt|Decimal|binary float|validation_alias|test_value_objects' python-pydantic/02-field-semantics-types-and-coercion.md`

Expected: 每个主题有命中，且代码中的模型／错误 type 与 pytest 一致。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/02-field-semantics-types-and-coercion.md
git commit -m "docs(pydantic): define field and coercion policies"
```

---

### Task 15: 第 03 章——验证管线与规范化

**Files:**
- Create: `python-pydantic/03-validation-pipeline-and-normalization.md`

**Interfaces:**
- Consumes: `Money` 的 `BeforeValidator`、`CreateOrderRequest.reject_duplicate_skus()`。
- Produces: before／plain／wrap／after 与 field／model validator 选择表。

- [ ] **Step 1: 跑 validator 案例**

Run: `cd python-pydantic/lab && uv run pytest tests/test_value_objects.py tests/test_create_order.py -v`

Expected: 全部通过。

- [ ] **Step 2: 创建章节并精确解释执行顺序**

章节必须包含：

- `BeforeValidator(_reject_binary_float)` 与 `model_validator(mode='after')` 的完整代码和错误路径。
- Annotated pattern 顺序：before／wrap 从右向左，after 从左向右；decorator 会转换成 metadata 并追加，遵循同一规则。
- plain validator 会终止内部验证的危险示例；wrap validator 何时可观察／截断／重抛。
- field validator 的 `ValidationInfo.data` 只含已经按字段定义顺序验证的字段；model validator 的 `data` 为 `None`。
- `model_validate(..., context=...)` 可以传纯上下文，但 direct `Model(...)` 不能直接传 validation context；本教程不为此覆写 `__init__`。
- default 默认不验证，何时使用 `validate_default`；禁止用 mutable／invalid default 偷渡。
- 纯规范化白名单：trim、case、timezone canonicalization；禁止项：DB lookup、库存、签名、HTTP、sleep、日志完整 input。
- 在 union 的 before validator 中不要先原地 mutate 再抛错，因为值可能流向其他分支。
- Java／Go 对照覆盖 Bean Validation group/class-level constraint 与 Go 显式 normalization function。

- [ ] **Step 3: 对照官方 validator ordering 核验**

Run: `rg -n '右向左|左向右|ValidationInfo|validate_default|context|原地' python-pydantic/03-validation-pipeline-and-normalization.md`

Expected: 顺序、default、context 和 union mutation 风险均出现；与官方 Validators 文档一致。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/03-validation-pipeline-and-normalization.md
git commit -m "docs(pydantic): teach validation ordering and purity"
```

---

### Task 16: 第 04 章——组合、多态与批量数据

**Files:**
- Create: `python-pydantic/04-composition-polymorphism-and-batches.md`

**Interfaces:**
- Consumes: `PaymentPayload` discriminator、`EventEnvelope[T]`、`ORDER_CREATED_ADAPTER`。
- Produces: nested model、RootModel、generic model、discriminated union、TypeAdapter 的选型树。

- [ ] **Step 1: 跑 union／generic／adapter 测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_webhook.py tests/test_event_compatibility.py -v`

Expected: union tag 和 event version 测试全部通过。

- [ ] **Step 2: 创建章节并对比四种组合工具**

章节必须包含：

- 支付成功／失败 union 的 `event_type` discriminator，与未标记 union 逐分支试错的错误噪声／性能对比。
- `EventEnvelope[PayloadT]` generic 的 schema 复用与版本子类；禁止在 generic 中隐藏版本语义。
- `RootModel[list[OrderCreatedMessage]]` 的完整批量示例，以及普通 field model 更适合需要 batch metadata 的情况。
- `TypeAdapter(list[PaymentPayload])`／现有 `ORDER_CREATED_ADAPTER`：适合 BaseModel 之外的 union、list、TypedDict；adapter 应复用。
- 递归模型和 `model_rebuild()` 的使用条件，不为订单案例强加递归结构。
- 大批次的内存、错误聚合和延迟风险；给出“消息逐条／有界 chunk 验证”，不声称 Pydantic 自动流式解析。
- 多版本输入统一映射到应用命令，不让领域层成为 `V1 | V2` union。
- Java／Go 对照覆盖 Jackson `@JsonTypeInfo`、Java 泛型擦除、Go tagged union 手工 switch。

- [ ] **Step 3: 验证 API 名称与失败模式**

Run: `rg -n 'RootModel|TypeAdapter|discriminator|model_rebuild|有界|ORDER_CREATED_ADAPTER' python-pydantic/04-composition-polymorphism-and-batches.md`

Expected: 六个关键点均出现，示例 tag 与 lab 的 `event_type`／`schema_version` 一致。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/04-composition-polymorphism-and-batches.md
git commit -m "docs(pydantic): cover composition and polymorphism"
```

---

### Task 17: 第 05 章——模型行为与生命周期

**Files:**
- Create: `python-pydantic/05-model-behavior-and-lifecycle.md`

**Interfaces:**
- Consumes: lab 模型统一的 `ConfigDict(extra=..., frozen=True)`。
- Produces: extra、frozen、validate_assignment、revalidation、copy、private／computed、dynamic model 的生命周期决策表。

- [ ] **Step 1: 运行模型配置基线**

Run: `cd python-pydantic/lab && uv run pytest tests/test_create_order.py tests/test_serialization.py tests/test_event_compatibility.py -v`

Expected: HTTP forbid、事件 V1 ignore、frozen 模型构造均通过。

- [ ] **Step 2: 创建章节并解释“看似不可变”的边界**

章节必须包含：

- `extra='forbid'/'ignore'/'allow'` 对 HTTP producer、事件 consumer 和 Settings 的不同政策表。
- `frozen=True` 只阻止属性重新赋值，不会深冻结任意 mutable child；本 lab 使用 tuple／frozen nested model 降低风险。
- `validate_assignment` 只覆盖赋值路径；嵌套对象 mutation、`model_copy(update=...)` 和 `model_construct()` 不应被误认为完整重验。
- revalidation of instances 的风险模型：可信模型实例、子类实例、跨边界复用。
- `model_copy(deep=False/True)` 的引用差异，并强调 update 数据是否重验需要显式测试。
- private attribute 不属于普通字段契约；computed field 会进入序列化／schema 的条件和泄漏风险。
- `create_model()` 用于真正动态 schema 的最小完整例子，列出可发现性、IDE／静态分析和版本治理成本。
- “不可变 DTO ≠ 不可变聚合根”，连接普通领域 dataclass。
- Java／Go 对照覆盖 Java record、Lombok immutable、Go value copy／slice alias。

- [ ] **Step 3: 检查所有生命周期逃生舱都写出风险**

Run: `rg -n 'extra=|frozen|validate_assignment|revalidation|model_copy|private|computed|create_model|model_construct' python-pydantic/05-model-behavior-and-lifecycle.md`

Expected: 每个关键词至少出现一次，没有把任何单一配置描述成深不可变保证。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/05-model-behavior-and-lifecycle.md
git commit -m "docs(pydantic): explain model lifecycle policies"
```

---

### Task 18: 第 06 章——契约分层与领域边界

**Files:**
- Create: `python-pydantic/06-contract-layering-and-domain-boundaries.md`

**Interfaces:**
- Consumes: `CreateOrderRequest -> CreateOrderCommand -> Order -> CustomerOrderView` 的完整映射。
- Produces: boundary／application／domain／outbound／event 模型拆分准则。

- [ ] **Step 1: 跑完整同步订单流**

Run: `cd python-pydantic/lab && uv run pytest tests/test_adapters.py tests/test_domain_order.py tests/test_serialization.py -v`

Expected: mapper、领域和 projection 全部通过。

- [ ] **Step 2: 创建章节并逐字段解剖映射理由**

章节必须包含：

- 同一笔订单的五张表：HTTP request、application command、domain Order、customer view、OrderCreated event，各自 owner、信任、版本、权限和失败含义。
- `to_create_order_command()` 的完整代码，解释为什么逐字段重复是安全边界而非“样板浪费”。
- 反例 `Order(**request.model_dump())`／`repository.update(**payload.model_dump())`，逐项说明 mass assignment、字段漂移和 persistence coupling。
- 混合币种在 `Order.create()` 拒绝，用于证明跨行业务规则属于领域层；入站 empty／quantity 则属于协议局部不变量。
- 值对象共享只基于相同语义；同形 `status: str`、`id: str` 不自动复用。
- Pydantic model、stdlib dataclass、普通 class、TypedDict 的层级选择矩阵。
- ORM `from_attributes` 延后到第 13 章，明确它不能替代 repository／session boundary。
- Java／Go 对照覆盖 Controller DTO → command → aggregate → response DTO，以及 Go 手写 mapper 的可审计性。

- [ ] **Step 3: 检查禁止模式只作为反例出现**

Run: `rg -n 'to_create_order_command|mass assignment|model_dump|single currency|TypedDict|from_attributes' python-pydantic/06-contract-layering-and-domain-boundaries.md`

Expected: 关键点均出现；所有 `**model_dump()` 代码块明确标为错误实现且不进入 lab。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/06-contract-layering-and-domain-boundaries.md
git commit -m "docs(pydantic): separate contracts from domain models"
```

---

### Task 19: 第 07 章——序列化与数据泄漏防御

**Files:**
- Create: `python-pydantic/07-serialization-and-data-leak-defense.md`

**Interfaces:**
- Consumes: `CustomerOrderView`、`InternalOrderView`、`CustomerOrderEnvelope`、Money amount serializer。
- Produces: 入站验证 schema 与出站白名单 schema 分离的安全政策。

- [ ] **Step 1: 跑出站安全测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_serialization.py tests/test_errors.py tests/test_settings.py -v`

Expected: 默认子类字段隐藏、错误不含 input、SecretStr 掩码测试全部通过。

- [ ] **Step 2: 创建章节并覆盖所有出站通道**

章节必须包含：

- `model_dump()` Python mode 与 `model_dump(mode='json')`／`model_dump_json()` JSON mode 的类型差异。
- include、exclude、exclude_unset、exclude_defaults、exclude_none 的语义表；明确临时 exclude 不是权限模型。
- Money `field_serializer` 的完整代码，以及 field serializer、model serializer、plain／wrap、serialization context 的选择边界。
- Pydantic v2 默认按字段注解类型序列化 model-like subclass；用 `CustomerOrderEnvelope` 证明内部字段默认不输出。
- `serialize_as_any=True` 会恢复运行时子类字段并可能泄漏；只在契约明确要求多态输出时局部启用并测试。
- `SecretStr` 只控制 repr／默认展示，不加密、不清内存，主动 `get_secret_value()` 后仍需调用方负责。
- response、event、log、error 各自需要不同白名单；禁止复用 `InternalOrderView` 后靠 exclude 拼权限。
- Java／Go 对照覆盖 Jackson `@JsonView`／DTO、Go `json:"-"` 和显式 response struct。

- [ ] **Step 3: 对照官方 subclass serialization 行为**

Run: `rg -n 'exclude_unset|field_serializer|model_serializer|serialize_as_any|SecretStr|CustomerOrderEnvelope' python-pydantic/07-serialization-and-data-leak-defense.md`

Expected: 六个重点均出现；示例输出与 `test_serialization.py` 一致。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/07-serialization-and-data-leak-defense.md
git commit -m "docs(pydantic): defend outbound serialization"
```

---

### Task 20: 第 08 章——JSON Schema 与契约演进

**Files:**
- Create: `python-pydantic/08-json-schema-and-contract-evolution.md`

**Interfaces:**
- Consumes: 三份 schema golden、V1／V2 event、兼容性测试。
- Produces: producer／consumer compatibility 与 breaking-change 审查清单。

- [ ] **Step 1: 重生 schema 并跑兼容性测试**

Run: `cd python-pydantic/lab && uv run python scripts/export_schemas.py && uv run pytest tests/test_json_schema.py tests/test_event_compatibility.py -v`

Expected: `8 passed`，schema regeneration 无预期外变化。

- [ ] **Step 2: 创建章节并区分 schema 与兼容性**

章节必须包含：

- CoreSchema 与 JSON Schema 的职责差异；`model_json_schema(mode='validation'/'serialization')` 可能输出不同契约。
- title、description、examples、`$defs`／`$ref`、`json_schema_extra` 的用途；禁止把描述性 metadata 当运行时验证。
- `export_schemas.py` 与 golden test 完整工作流：生成 → diff → 人工判断 → 提交；禁止无条件更新快照。
- `OrderCreatedV1` 使用 `extra='ignore'` 读取加法字段，V2 producer `extra='forbid'`，解释两者并不矛盾。
- producer compatibility、consumer compatibility、双读／双写迁移、envelope version 的矩阵。
- breaking changes：required field、新 enum value、字段重命名、类型／单位／时区语义改变、unknown-field 政策改变。
- “schema diff 没变但语义已变”与“schema diff 变了但 consumer 仍兼容”各给一个订单例子。
- Java／Go 对照覆盖 OpenAPI／Avro／Protobuf compatibility 与 JSON struct schema 边界。

- [ ] **Step 3: 验证版本术语和 golden 链接**

Run: `rg -n 'CoreSchema|validation.*serialization|producer compatibility|consumer compatibility|breaking|export_schemas|golden' python-pydantic/08-json-schema-and-contract-evolution.md`

Expected: 机制、兼容性和审查流程均出现；三份 schema 相对链接有效。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/08-json-schema-and-contract-evolution.md
git commit -m "docs(pydantic): govern schema evolution"
```

---

### Task 21: 第 09 章——错误契约与可观测性

**Files:**
- Create: `python-pydantic/09-error-contracts-and-observability.md`

**Interfaces:**
- Consumes: `ErrorResponse`、`MessageFailureKind`、`InvalidWebhookSignature`。
- Produces: HTTP／Webhook／MQ／Settings／内部命令五类失败政策。

- [ ] **Step 1: 跑错误与边界测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_errors.py tests/test_webhook.py tests/test_settings.py -v`

Expected: 全部通过。

- [ ] **Step 2: 创建章节并把 ValidationError 与服务政策分离**

章节必须包含：

- `ValidationError.errors()` 中 type、loc、msg、input、ctx、url 的含义与稳定性；测试只锁 `type`／`loc`，不锁整句 msg。
- `to_error_response()` 的完整清洗代码，说明“没有序列化 input”比对日志字符串做 redact 更可靠。
- `ValueError`、`AssertionError`、`PydanticCustomError` 的 validator 选择；指出 `assert` 会被 Python `-O` 跳过。
- HTTP：契约错误 → 稳定 4xx；领域冲突另有业务 code；未处理异常 → 5xx。
- Webhook：原始 bytes 验签先于 parsing，签名错误与 payload 错误不得混在同一 validator。
- MQ：unknown version/tag → incompatible；字段值无效 → permanent；broker／DB timeout → transient；只有 permanent 进入 DLQ 是示例政策，不宣称由 Pydantic 自动决定。
- Settings：启动 fail fast；内部 command 无效视为 producer bug。
- observability：error type／boundary／model version 可做低基数维度；完整 loc、input、客户 ID 不做 metric label；trace／log 不记录 secret。
- Java／Go 对照覆盖 `MethodArgumentNotValidException`、Go error wrapping 与 broker nack/retry policy。

- [ ] **Step 3: 检查安全与可观测性结论**

Run: `rg -n 'type|loc|msg|input|PydanticCustomError|DLQ|低基数|InvalidWebhookSignature' python-pydantic/09-error-contracts-and-observability.md`

Expected: 每个关键点均出现；没有示例回显完整 payload 或 secret。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/09-error-contracts-and-observability.md
git commit -m "docs(pydantic): design safe observable errors"
```

---

### Task 22: 第 10 章——使用 pytest 进行契约测试

**Files:**
- Create: `python-pydantic/10-contract-testing-with-pytest.md`

**Interfaces:**
- Consumes: lab 全部 test categories。
- Produces: 行为、错误、序列化、schema、兼容性、Settings、example、性能八类测试策略。

- [ ] **Step 1: 跑完整 lab 测试并记录测试类别**

Run: `cd python-pydantic/lab && uv run pytest -v`

Expected: 所有既有测试通过；按文件记录行为类型，不抄机器耗时作为教程承诺。

- [ ] **Step 2: 创建章节并用真实 tests 教 test design**

章节必须包含：

- `pytest.mark.parametrize` 表格化 coercion policy 的完整示例，cases 明确 input、expected／error type、loc。
- 正例不能替代反例：unknown field、string quantity、float money、naive datetime、bad discriminator。
- 错误断言 `type`／`loc`，说明 msg、url 和 input 不适合作为长期公开契约。
- round-trip 只在 canonical serialization 对称时成立；currency uppercasing、alias、Decimal string 说明 raw input 不会原样返回。
- output leak 测试采用“敏感字段不存在”，不是仅比对一个 happy-path dict。
- schema golden 与 V1／V2 semantic compatibility 是两层测试，均不可省略。
- Settings 使用 `monkeypatch`／`tmp_path`，显式清 cache，禁止读取 ambient `.env`。
- examples 由 pytest import 并执行，防止 Markdown 与脚本腐化。
- 性能 test 只检查 observation 可产生、数值为正，不写硬耗时／倍率门槛。
- property-based testing 的适用范围和价值，但明确本 lab 不加 Hypothesis dependency。
- Java／Go 对照覆盖 JUnit parameterized／Spring contract tests、Go table-driven tests／golden files。

- [ ] **Step 3: 建立章节到 test 文件映射表**

映射表必须逐行列出 `test_package_smoke.py`、`test_value_objects.py`、`test_create_order.py`、`test_webhook.py`、`test_adapters.py`、`test_domain_order.py`、`test_serialization.py`、`test_event_compatibility.py`、`test_errors.py`、`test_settings.py`、`test_json_schema.py`、`test_advanced_types.py`、`test_performance_observations.py`、`test_examples.py`、`test_integrations.py`，并说明每个文件防哪类回归。

Run: `rg -c 'test_[a-z_]+\.py' python-pydantic/10-contract-testing-with-pytest.md`

Expected: 输出计数至少为 15。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/10-contract-testing-with-pytest.md
git commit -m "docs(pydantic): teach contract testing with pytest"
```

---

### Task 23: 第 11 章——自定义类型、CoreSchema 与性能

**Files:**
- Create: `python-pydantic/11-custom-types-core-schema-and-performance.md`

**Interfaces:**
- Consumes: `ProviderReference`、`compare_json_validation()`、`CurrencyCode`。
- Produces: 扩展层级与优化决策树。

- [ ] **Step 1: 跑高级扩展与计时测试**

Run: `cd python-pydantic/lab && uv run pytest tests/test_advanced_types.py tests/test_performance_observations.py -v -s`

Expected: 全部通过，无机器相关 threshold。

- [ ] **Step 2: 创建章节并按“最低成本优先”展开**

章节必须包含：

- 扩展顺序：标准类型／`Annotated`＋Field／functional validator → field／model validator → `ValidateAs`／自定义类型 → `GetPydanticSchema`／`__get_pydantic_core_schema__`。
- `CurrencyCode` 高层实现与 `ProviderReference` 直接 hook 对照，说明后者同时承担 validation、serialization、JSON Schema 三份责任。
- CoreSchema hook 的 middleware 心智：source_type、handler、返回 schema；明确该 API 比高层构造更版本敏感。
- `__get_pydantic_json_schema__` 与 CoreSchema 不自动等价，pattern 必须同步测试。
- schema／TypeAdapter 重用；禁止在 hot loop 内重复构建。
- `model_validate_json(raw)` 与 `json.loads(raw) + model_validate()` 的数据路径；只能报告当前锁定版本、输入形状、机器条件下的观察。
- `model_construct()` 不是通用优化：会绕过所有验证，且 v2 简单模型上不保证更快。
- profiler-first：先确认验证占 CPU／allocation，再调整 schema、批大小或 adapter 复用；不为微基准牺牲边界清晰度。
- Java／Go 对照覆盖 Jackson module／custom deserializer、Go `UnmarshalJSON` 与生成代码。

- [ ] **Step 3: 核对直接 hook 的警告和测试责任**

Run: `rg -n 'Annotated|ValidateAs|GetPydanticSchema|__get_pydantic_core_schema__|__get_pydantic_json_schema__|model_construct|profile' python-pydantic/11-custom-types-core-schema-and-performance.md`

Expected: 每层扩展、两类 schema hook 和 profiler-first 都出现。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/11-custom-types-core-schema-and-performance.md
git commit -m "docs(pydantic): bound core-schema and performance work"
```

---

### Task 24: 第 12 章——生产级 pydantic-settings

**Files:**
- Create: `python-pydantic/12-pydantic-settings-in-production.md`

**Interfaces:**
- Consumes: `AppSettings`、`PaymentProviderSettings`、custom env source、cache functions、Settings tests。
- Produces: 来源优先级、secret、缓存、多 worker、更新语义和测试隔离的完整配置政策。

- [ ] **Step 1: 跑配置测试与安全示例**

Run: `cd python-pydantic/lab && uv run pytest tests/test_settings.py tests/test_examples.py::test_settings_example_never_returns_raw_secret -v`

Expected: `6 passed`。

- [ ] **Step 2: 创建章节并从启动故障切入**

章节必须包含：

- 事故：worker 启动后第一个支付请求才发现 secret 缺失；结论是 Settings 在 composition root 启动 fail fast。
- `BaseSettings` 是配置边界模型，不是业务 DTO 基类；对比 `os.environ` 手写解析的分散错误。
- 默认优先级完整写为：CLI arguments（仅启用 `cli_parse_args` 时）> init kwargs > environment > dotenv > file secrets > defaults。
- 本 lab 自定义后为 init > `CommaSeparatedEnvSource` > dotenv > file secrets > defaults；首项优先级最高。
- `env_prefix`、`env_nested_delimiter`、alias／validation_alias、case sensitivity、nested model 和复杂 JSON／CSV 值解析。
- nested default partial update 的行为和版本敏感配置；不依赖隐式 partial merge 处理关键 secret。
- dotenv 路径相对 cwd 的陷阱；`load_settings(env_file=...)` 显式路径和 `env_file=None` 防 ambient 读取。
- file secrets 只是从文件读取明文值，不是加密；`SecretStr` 只掩码；debug settings sources 可能打印 secret，只在可信环境短期开启。
- custom source 的完整 `prepare_field_value()`；定制来源必须保留清楚的优先级和测试。
- `get_settings()`／`clear_settings_cache()`：缓存位于 composition root，可清理；禁止 module import 时直接 `settings = AppSettings()`。
- 多 worker 各进程独立加载 snapshot；环境／secret 文件改变不会自动同步已有对象，更新需要明确 reload／restart 政策。
- 测试隔离逐项解释 `monkeypatch`、`tmp_path`、cache clear 和不读真实 `.env`。
- Java／Go 对照覆盖 Spring ConfigData／`@ConfigurationProperties`、Viper／envconfig 与进程 snapshot。

- [ ] **Step 3: 对照当前官方 Settings 文档核验优先级**

Run: `rg -n 'CLI|init|environment|dotenv|file secrets|defaults|settings_customise_sources|多 worker|clear_settings_cache|ambient' python-pydantic/12-pydantic-settings-in-production.md`

Expected: 默认和本 lab 两套顺序都明确，无互相矛盾；secret debug 风险有醒目标注。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/12-pydantic-settings-in-production.md
git commit -m "docs(pydantic): govern settings in production"
```

---

### Task 25: 第 13 章——集成矩阵与 v1 迁移

**Files:**
- Create: `python-pydantic/13-integrations-and-v1-migration.md`

**Interfaces:**
- Consumes: FastAPI example、event parser／failure classifier、普通 domain object、全部 v2 APIs。
- Produces: FastAPI／MQ／ORM／LLM structured output 的薄集成边界，以及集中式 v1 → v2 迁移地图。

- [ ] **Step 1: 跑四类集成证据**

Run: `cd python-pydantic/lab && uv run pytest tests/test_examples.py tests/test_integrations.py tests/test_event_compatibility.py tests/test_errors.py -v`

Expected: FastAPI route、event bytes、失败分类和安全输出全部通过。

- [ ] **Step 2: 创建章节并限制每个集成的职责**

章节必须包含：

- FastAPI：完整 `@app.post(..., response_model=CustomerOrderView)` 示例；request validation、application mapping、response whitelist 三步分开；不讲 auth、deployment、Uvicorn。
- Kafka／RocketMQ：client 只负责拿到 bytes／metadata／ack；`parse_order_created()` 负责契约；`classify_consume_failure()` 负责示例政策；不安装任何 broker SDK。
- ORM：引用 `tests/test_integrations.py` 的普通 Python row object，完整演示 `ConfigDict(from_attributes=True)`；说明它只读取属性，不处理 lazy-load、session、transaction、N+1 或 repository。
- LLM structured output：用 `CreateOrderRequest.model_json_schema()`／`model_validate()` 说明 schema 与验证可复用；模型输出仍是不可信外部输入；不出现 `pydantic_ai` import、provider、agent、tool calling 或 API key。
- v1 → v2 表必须至少包含：`parse_obj` → `model_validate`、`parse_raw` → `model_validate_json`、`dict` → `model_dump`、`json` → `model_dump_json`、`schema` → `model_json_schema`、`copy` → `model_copy`、`construct` → `model_construct`。
- validator migration：`@validator`／`@root_validator` → field／model validators；签名、ordering、default 和 TypeError 行为必须回归测试。
- config migration：inner `Config` → `ConfigDict`；`orm_mode` → `from_attributes`；`__root__` → `RootModel`；generic 不再需要 `GenericModel`。
- serialization migration：V2 默认按字段注解隐藏 model subclass 新字段，与 V1 recursive dump 行为不同；审计 `serialize_as_any`。
- 迁移流程：锁版本 → 建 coercion／error／serialization golden → 机械 API 替换 → 行为审计 → framework integration test → 分阶段上线。
- Java／Go 对照只总结 adapter ownership，不扩成框架教程。

- [ ] **Step 3: 验证范围没有滑向外部框架**

Run: `rg -n 'FastAPI|Kafka|RocketMQ|from_attributes|structured output|parse_obj|model_validate|root_validator|RootModel|serialize_as_any' python-pydantic/13-integrations-and-v1-migration.md`

Expected: 集成和迁移项齐全。

Run: `rg -n 'from pydantic_ai|import pydantic_ai|confluent_kafka|aiokafka|rocketmq\.client|sqlalchemy' python-pydantic/13-integrations-and-v1-migration.md`

Expected: 无输出。

- [ ] **Step 4: Commit**

```bash
git add python-pydantic/13-integrations-and-v1-migration.md
git commit -m "docs(pydantic): add integrations and v2 migration map"
```

---

### Task 26: 教程 README、面试卡、Python 桥接章与全仓导航

**Files:**
- Create: `python-pydantic/README.md`
- Create: `python-pydantic/99-interview-cards.md`
- Create: `python/25-runtime-data-contracts-bridge.md`
- Modify: `python/README.md`
- Modify: `README.md`
- Modify: `python/09-typing.md`
- Modify: `python/14-stdlib-and-ecosystem.md`
- Modify: `python/20-production-skeleton.md`
- Modify: `python-pydantic/lab/README.md`

**Interfaces:**
- Consumes: 完成的 00—13 章节与 lab。
- Produces: 从仓库首页、Python 主线、typing／ecosystem／production skeleton 到深度专题的单向导航，以及面试复习入口。

- [ ] **Step 1: 创建专题 README**

`python-pydantic/README.md` 必须包含：

- 定位：“服务边界的数据契约与运行时验证引擎”，不是 FastAPI 附件。
- CPython 3.11+／Pydantic v2 环境，`cd lab && uv sync && uv run pytest`。
- 三种读法：线性 00→13、按事故／边界跳读、面试前 99 卡。
- 四阶段路线：00—04 inbound trust；05—06 architecture；07—08 outbound／evolution；09—13 errors／tests／internals／settings／integrations。
- 00—13 和 99 的完整表格，每行包含相对链接与一句话产出。
- “lab 是可执行事实来源”的目录图及四个 example 命令。
- 明确 out-of-scope：FastAPI 运维、SQLAlchemy、MQ client、Pydantic AI runtime、静态类型工具。
- 官方参考链接：Pydantic latest concepts／internals／migration 与 pydantic-settings latest docs。

- [ ] **Step 2: 创建架构师面试卡与故障速查**

`python-pydantic/99-interview-cards.md` 至少包含以下 20 题，每题都有“30 秒回答／深挖／误区／生产例子”：

1. Pydantic 与类型注解／mypy 的关系。
2. v2 CoreSchema／pydantic-core pipeline。
3. strict 为什么不能全局一刀切。
4. required／optional／nullable 区别。
5. validator ordering。
6. field vs model validator。
7. 为什么 validator 禁止 I/O。
8. TypeAdapter 何时优于 BaseModel。
9. discriminated union 的价值。
10. DTO／command／domain／view 为什么拆分。
11. `model_construct()` 风险。
12. `extra` policy 如何按边界选。
13. 子类序列化如何泄漏。
14. JSON Schema golden 是否证明兼容。
15. event V1／V2 如何演进。
16. ValidationError 如何变成稳定 API error。
17. MQ invalid message 是否应该 retry／DLQ。
18. pydantic-settings 来源优先级和缓存。
19. CoreSchema hook 何时值得用。
20. Pydantic 性能如何测、如何优化。

故障速查按症状列出：意外 coercion、unknown field、validator latency、内部字段泄漏、event version 不兼容、错误日志泄密、worker 配置不一致、ambient `.env` 污染、schema golden 漂移、adapter 热路径重建。

- [ ] **Step 3: 创建 Python 第 25 桥接章**

`python/25-runtime-data-contracts-bridge.md` 只写以下内容：

- 静态类型、runtime validation、serialization、JSON Schema、domain rule 的一页定位图。
- 选择决策：dataclass／TypedDict／Pydantic／普通 domain class 各适合什么。
- 一个 20 行以内 `CreateOrderRequest` 入站示例，随后链接 `../python-pydantic/`；不复制深度机制。
- 指向 `09-typing.md`、`12-testing.md`、`20-production-skeleton.md`、`23-data-access-bridge.md`、`../fastapi-ops/` 的职责边界。
- Java／Go 对照与 4 张桥接面试卡。

- [ ] **Step 4: 更新导航与散落 Pydantic 指针**

执行精确内容变更：

- 根 `README.md` 的 Python 主线描述改为“26 章 + 面试卡”，并在 `python-data/` 后加入 `python-pydantic/`：“Pydantic v2 数据契约与配置治理（含可跑 lab）”。
- `python/README.md` 的线性路线改为 `00 → 25`；目录表在 24 后加入 25；“与仓库其他目录的关系”新增数据契约深度指针。
- `python/09-typing.md` 在“运行时校验靠库”处链接 `../python-pydantic/00-data-contracts-and-trust-boundaries.md`，并保持“注解本身不强制”结论。
- `python/14-stdlib-and-ecosystem.md` 的 pydantic 生态表项链接 `../python-pydantic/`，MQ 客户端内容不扩写。
- `python/20-production-skeleton.md` 在 pydantic-settings 样例后加醒目说明：该 import-time `settings = Settings()` 只是最小示意，生产来源优先级、显式缓存、测试隔离和多 worker 语义见第 12 章。
- `python-pydantic/lab/README.md` 补充目录图、四个 example 命令、schema regeneration 命令、`.env.example`／真实 `.env` 政策和测试文件地图。

- [ ] **Step 5: 验证章节／导航完整性**

Run: `rg --files python-pydantic | rg '/(00|01|02|03|04|05|06|07|08|09|10|11|12|13|99)-[^/]+\.md$' | wc -l`

Expected: 输出 `15`。

Run: `rg -n 'python-pydantic|25-runtime-data-contracts-bridge|00 → 25|26 章' README.md python/README.md python/09-typing.md python/14-stdlib-and-ecosystem.md python/20-production-skeleton.md`

Expected: 首页、主线和三个散落入口均有正确指针。

- [ ] **Step 6: 跑完整测试并提交导航层**

Run: `cd python-pydantic/lab && uv run pytest -q`

Expected: 全部通过。

```bash
git add README.md python/README.md python/09-typing.md python/14-stdlib-and-ecosystem.md python/20-production-skeleton.md python/25-runtime-data-contracts-bridge.md python-pydantic
git commit -m "docs(pydantic): publish tutorial navigation and interview cards"
```

---

### Task 27: 全量质量、安全与仓库卫生验收

**Files:**
- Verify only: 本计划涉及的所有文件；任何失败返回其所属任务修正并重新提交。

**Interfaces:**
- Consumes: 全部实现提交。
- Produces: 可复现、无 secret、无依赖产物、schema 稳定、文档导航完整的干净分支。

- [ ] **Step 1: 从锁文件同步并跑完整测试**

Run: `cd python-pydantic/lab && uv lock --check && uv sync --locked && uv run pytest -ra`

Expected: lock 无需更新，sync 成功，全部 tests 通过且无 collection warning。

- [ ] **Step 2: 直接执行四个 example**

Run: `cd python-pydantic/lab && uv run python examples/validate_http_payload.py && uv run python examples/consume_event.py && uv run python examples/load_settings.py && uv run python -c "from examples.fastapi_adapter import app; assert any(route.path == '/orders' for route in app.routes)"`

Expected: 四个入口退出码 0；输出没有真实 secret。

- [ ] **Step 3: 重生 schema 并证明没有漂移**

Run: `cd python-pydantic/lab && uv run python scripts/export_schemas.py && git diff --exit-code -- schemas`

Expected: exit code 0。

- [ ] **Step 4: 检查禁止依赖和秘密模式**

Run: `rg -n 'sqlalchemy|confluent_kafka|aiokafka|rocketmq\.client|from pydantic_ai|import pydantic_ai' python-pydantic/lab/src python-pydantic/lab/tests python-pydantic/lab/examples python-pydantic/lab/pyproject.toml`

Expected: 无输出。

Run: `rg -n 'sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|postgres(ql)?://[^[:space:]]+:[^@[:space:]]+@' python-pydantic`

Expected: 无输出。

- [ ] **Step 5: 检查 Git 忽略和未跟踪内容**

Run: `git status --short --ignored`

Expected: `.venv/`、pytest cache 等只以 ignored 形式出现；没有真实 `.env`、coverage、build、dist、egg-info、benchmark 输出或 vendor dependency 成为可跟踪文件；`uv.lock`、`.env.example`、三份 schema 已跟踪。

- [ ] **Step 6: 检查文档结构、链接和禁止占位符**

Run: `rg -n 'TBD|TODO|FIXME|待定|待补|占位' python-pydantic python/25-runtime-data-contracts-bridge.md`

Expected: 无输出。

Run: `rg -L 'Java/Go 对照' python-pydantic/{00,01,02,03,04,05,06,07,08,09,10,11,12,13}-*.md`

Expected: 无输出。

逐个点击 `python-pydantic/README.md`、各章“继续阅读”、`python/25-runtime-data-contracts-bridge.md` 和根导航中的相对链接；所有本地目标存在，外部官方链接可访问。

- [ ] **Step 7: 最终 diff 与 clean status**

Run: `git diff --check && git status --short --branch && git log --oneline --decorate -30`

Expected: `git diff --check` 无输出；分支为 `codex/pydantic-contracts-tutorial`；工作树 clean；历史包含每个独立可审查任务的 commit。
