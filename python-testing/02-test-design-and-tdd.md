# 好测试与 TDD

## 核心问题

测试通过不等于测试有价值。测试可能绑住实现细节、遗漏真正的业务边界，或在生产逻辑已经变坏时仍然保持绿色。本章用订单领域模型完成一次可复现的 test-first 循环：先写出支付状态和金额不变量的可执行政策，亲眼看到它因能力缺失而失败，再增加使其通过的最小生产实现。

目标不是追求测试数量，而是提高 oracle（判定对错的规则）的质量。一个好测试应在业务行为违反约定时失败，并在内部结构无害重排时继续通过。订单状态、支付引用和版本号是可观察行为；某个私有方法是否先于另一个私有方法调用，通常只是实现细节。

## 直觉模型

### 一个测试只承担一个失败理由

把测试看成一条可执行政策：名称说明政策，Arrange 建立前提，Act 触发一个行为，Assert 观察结果。Given-When-Then 是同一结构的业务语言版本：

| 测试结构 | 业务叙事 | 本章例子 |
|---|---|---|
| Arrange | Given | 一个待支付订单 |
| Act | When | 开始支付并确认支付成功 |
| Assert | Then | 状态为 `PAID`、引用被保存、版本为 3 |

“一个失败理由”不等于“只能写一个 `assert`”。同一次状态转换的状态、引用和版本共同构成一个业务结果，放在同一测试中能防止读者在多个测试间拼接语义。相反，金额校验与支付转换属于不同政策，应拆开命名。

### RED、GREEN、REFACTOR 是证据链

本章的顺序是：

1. 删除既有生产实现。先用 11 个窄测试逐一引入 module、exception、class、enum、method 与 package export；这类 RED 只证明 public surface 缺失，不冒充 guard 的证据。
2. public symbol 变绿后，再执行 23 个行为／export-policy 循环：构造、不可变与 slots、Decimal 与币种规则、enum 值与字符串互操作、keyword-only 与必填参数、创建 guard、合法转换、重放、空 reference、七行非法转换矩阵，以及精确 `__all__`。
3. 每个行为 RED 必须真正调用已存在的 API，并通过 assertion、`DID NOT RAISE`，或预期的 behavior/policy exception（例如 `TypeError`／`AttributeError`）失败。每个 transition case 同时检查 status、payment reference 和 version；拒绝与重放还要证明已有状态未被部分改写。
4. 最后才用已绿的行为测试保护 REFACTOR，把重复的 transition exception 构造收敛到 `_reject`；Task 4 的最终聚焦快照是 `49 passed`，但累计套件数量会随后续任务增长。

RED 的价值在于证明测试确实能感知目标缺失。import／attribute failure 只能证明 symbol 不存在；symbol 已绿后，assertion、`DID NOT RAISE`，或预期的 behavior/policy exception（例如拒绝 positional call 的 `TypeError`、禁止动态属性的 `AttributeError`）都能证明对应行为尚未实现。若测试首次运行就绿，可能是在描述既有行为，也可能根本没有触及目标；必须先解释原因，不能把绿色自动当成 TDD 证据。

## 机制深入

### 值对象把输入不变量收紧在入口

以下是 Task 4 结束时的历史实现快照，作为本章 test-first 演进的伪代码（pseudocode）保留；累积 lab 已在 mutation seam 与退款 capstone 中继续演进，当前 runnable 源码见 [`lab/src/order_service/domain/order.py`](lab/src/order_service/domain/order.py)：

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class InvalidAmount(ValueError):
    pass


class InvalidCurrency(ValueError):
    pass


class InvalidOrderTransition(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidAmount("amount must be a Decimal")
        if self.amount <= 0:
            raise InvalidAmount("amount must be positive")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise InvalidCurrency("currency must be a three-letter code")
        object.__setattr__(self, "currency", self.currency.upper())


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_IN_PROGRESS = "payment_in_progress"
    PAYMENT_FAILED = "payment_failed"
    PAID = "paid"


@dataclass(slots=True)
class Order:
    id: UUID
    idempotency_key: str
    total: Money
    status: OrderStatus
    created_at: datetime
    payment_reference: str | None = None
    version: int = 1

    @classmethod
    def create(
        cls,
        *,
        order_id: UUID,
        idempotency_key: str,
        total: Money,
        created_at: datetime,
    ) -> "Order":
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return cls(
            id=order_id,
            idempotency_key=idempotency_key,
            total=total,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=created_at,
        )

    def start_payment(self) -> None:
        if self.status not in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}:
            self._reject(OrderStatus.PAYMENT_IN_PROGRESS)
        self.status = OrderStatus.PAYMENT_IN_PROGRESS
        self.version += 1

    def mark_paid(self, provider_reference: str) -> None:
        if self.status is OrderStatus.PAID and self.payment_reference == provider_reference:
            return
        if self.status is not OrderStatus.PAYMENT_IN_PROGRESS:
            self._reject(OrderStatus.PAID)
        if not provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        self.status = OrderStatus.PAID
        self.payment_reference = provider_reference
        self.version += 1

    def mark_payment_failed(self) -> None:
        if self.status is not OrderStatus.PAYMENT_IN_PROGRESS:
            self._reject(OrderStatus.PAYMENT_FAILED)
        self.status = OrderStatus.PAYMENT_FAILED
        self.version += 1

    def _reject(self, target: OrderStatus) -> None:
        raise InvalidOrderTransition(f"cannot move {self.status.name} to {target.name}")
```

`Money` 在运行时拒绝非 `Decimal`，`Money(1.0, "USD")` 会得到带 `Decimal` 诊断的 `InvalidAmount`，绝不静默转换 float；它也不暗中增加算术或币种换算。金额边界是 `amount > 0`；零、负整数和负小数属于同一无效分区的不同代表值。币种规则只负责三字母校验与大写规范化，不冒充完整 ISO 币种目录。

订单从版本 1 开始，每次真实状态转换加 1。相同 provider reference 对已经支付的订单重复调用 `mark_paid` 是幂等重放，因此不改状态、不改引用、不增版本；在其他非法状态请求转移则抛出包含源、目标状态的诊断异常。

### 测试名是可搜索的业务政策

以下是与上述 Task 4 快照配套的历史测试伪代码（pseudocode），用于保留逐步 RED→GREEN 的证据顺序；当前 runnable regression suite 见 [`lab/tests/unit/test_order.py`](lab/tests/unit/test_order.py)：

```python
import importlib
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 15, tzinfo=UTC)


def test_order_module_exposes_money_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.Money, type)


def test_money_accepts_positive_decimal() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("10.00"), "USD")

    assert money.amount == Decimal("10.00")
    assert money.currency == "USD"


def test_money_is_immutable() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    money = order_module.Money(Decimal("10.00"), "USD")

    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("11.00")

    assert money.amount == Decimal("10.00")


def test_money_uses_slots_without_instance_dict() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("10.00"), "USD")

    assert not hasattr(money, "__dict__")


def test_order_module_exposes_invalid_amount_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidAmount, ValueError)


def test_money_rejects_float_amount() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidAmount, match="Decimal"):
        order_module.Money(1.0, "USD")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("-0.01")])
def test_money_rejects_non_positive_amount(amount: Decimal) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidAmount, match="positive"):
        order_module.Money(amount, "USD")


def test_money_normalizes_valid_currency() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("1.00"), "usd")

    assert money.currency == "USD"


def test_order_module_exposes_invalid_currency_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidCurrency, ValueError)


@pytest.mark.parametrize("currency", ["", "US", "US1", "USDD"])
def test_money_rejects_invalid_currency_code(currency: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidCurrency, match="three-letter"):
        order_module.Money(Decimal("1.00"), currency)


def test_order_module_exposes_order_status_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.OrderStatus, type)


def test_order_status_has_exact_public_members_and_values() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert [(status.name, status.value) for status in order_module.OrderStatus] == [
        ("PENDING_PAYMENT", "pending_payment"),
        ("PAYMENT_IN_PROGRESS", "payment_in_progress"),
        ("PAYMENT_FAILED", "payment_failed"),
        ("PAID", "paid"),
    ]


def test_order_status_interoperates_with_strings() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    paid = order_module.OrderStatus.PAID

    assert isinstance(paid, str)
    assert paid == "paid"
    assert {"paid": "settled"}[paid] == "settled"


def test_order_module_exposes_order_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.Order, type)


def test_order_type_exposes_create_factory() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.create)


def test_order_create_rejects_positional_invocation() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(TypeError, match="positional"):
        order_module.Order.create(
            ORDER_ID,
            "create-001",
            order_module.Money(Decimal("10.00"), "USD"),
            NOW,
        )


@pytest.mark.parametrize(
    "missing_field", ["order_id", "idempotency_key", "total", "created_at"]
)
def test_order_create_requires_each_named_field(missing_field: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")
    arguments: dict[str, object] = {
        "order_id": ORDER_ID,
        "idempotency_key": "create-001",
        "total": order_module.Money(Decimal("10.00"), "USD"),
        "created_at": NOW,
    }
    del arguments[missing_field]

    with pytest.raises(TypeError, match=missing_field):
        order_module.Order.create(**arguments)


def test_order_create_preserves_required_fields_at_version_one() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    total = order_module.Money(Decimal("10.00"), "USD")

    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=total,
        created_at=NOW,
    )

    assert order.id == ORDER_ID
    assert order.idempotency_key == "create-001"
    assert order.total == total
    assert order.status is order_module.OrderStatus.PENDING_PAYMENT
    assert order.created_at == NOW
    assert order.payment_reference is None
    assert order.version == 1


@pytest.mark.parametrize("idempotency_key", ["", "   "])
def test_order_create_rejects_blank_idempotency_key(idempotency_key: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(ValueError, match="idempotency_key.*blank"):
        order_module.Order.create(
            order_id=ORDER_ID,
            idempotency_key=idempotency_key,
            total=order_module.Money(Decimal("10.00"), "USD"),
            created_at=NOW,
        )


def test_order_create_rejects_naive_timestamp() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(ValueError, match="timezone-aware"):
        order_module.Order.create(
            order_id=ORDER_ID,
            idempotency_key="create-001",
            total=order_module.Money(Decimal("10.00"), "USD"),
            created_at=datetime(2026, 7, 15),
        )


def test_order_module_exposes_invalid_order_transition_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidOrderTransition, RuntimeError)


def test_order_type_exposes_start_payment_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.start_payment)


def test_start_payment_retries_failed_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order(
        id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        status=order_module.OrderStatus.PAYMENT_FAILED,
        created_at=NOW,
        version=3,
    )

    order.start_payment()

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 4


def test_start_payment_moves_pending_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )

    order.start_payment()

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 2


def test_order_type_exposes_mark_payment_failed_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.mark_payment_failed)


def test_mark_payment_failed_moves_in_progress_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    order.mark_payment_failed()

    assert order.status is order_module.OrderStatus.PAYMENT_FAILED
    assert order.payment_reference is None
    assert order.version == 3


def test_order_type_exposes_mark_paid_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.mark_paid)


def test_mark_paid_moves_in_progress_order_and_records_reference() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    order.mark_paid("provider-001")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_same_reference_replay_preserves_paid_state() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()
    order.mark_paid("provider-001")

    order.mark_paid("provider-001")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_rejects_different_reference_and_preserves_paid_state() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()
    order.mark_paid("provider-001")

    with pytest.raises(order_module.InvalidOrderTransition, match="PAID.*PAID"):
        order.mark_paid("provider-002")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_rejects_blank_provider_reference_without_mutation() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    with pytest.raises(ValueError, match="provider_reference.*blank"):
        order.mark_paid("   ")

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 2


@pytest.mark.parametrize(
    (
        "operation",
        "source_name",
        "target_name",
        "payment_reference",
        "version",
    ),
    [
        (
            "start_payment",
            "PAYMENT_IN_PROGRESS",
            "PAYMENT_IN_PROGRESS",
            None,
            2,
        ),
        ("start_payment", "PAID", "PAYMENT_IN_PROGRESS", "provider-001", 3),
        ("mark_payment_failed", "PENDING_PAYMENT", "PAYMENT_FAILED", None, 1),
        ("mark_payment_failed", "PAYMENT_FAILED", "PAYMENT_FAILED", None, 3),
        ("mark_payment_failed", "PAID", "PAYMENT_FAILED", "provider-001", 3),
        ("mark_paid", "PENDING_PAYMENT", "PAID", None, 1),
        ("mark_paid", "PAYMENT_FAILED", "PAID", None, 3),
    ],
)
def test_illegal_transition_matrix_preserves_order_state(
    operation: str,
    source_name: str,
    target_name: str,
    payment_reference: str | None,
    version: int,
) -> None:
    order_module = importlib.import_module("order_service.domain.order")
    source = getattr(order_module.OrderStatus, source_name)
    target = getattr(order_module.OrderStatus, target_name)
    order = order_module.Order(
        id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        status=source,
        created_at=NOW,
        payment_reference=payment_reference,
        version=version,
    )
    before = (order.status, order.payment_reference, order.version)

    with pytest.raises(
        order_module.InvalidOrderTransition,
        match=f"{source.name}.*{target.name}",
    ):
        if operation == "start_payment":
            order.start_payment()
        elif operation == "mark_payment_failed":
            order.mark_payment_failed()
        else:
            order.mark_paid("provider-002")

    assert (order.status, order.payment_reference, order.version) == before


def test_domain_package_exposes_public_order_symbols() -> None:
    domain_module = importlib.import_module("order_service.domain")

    for name in (
        "InvalidAmount",
        "InvalidCurrency",
        "InvalidOrderTransition",
        "Money",
        "Order",
        "OrderStatus",
    ):
        assert hasattr(domain_module, name), name


def test_domain_package_all_is_exact_public_order_api() -> None:
    domain_module = importlib.import_module("order_service.domain")

    assert domain_module.__all__ == [
        "InvalidAmount",
        "InvalidCurrency",
        "InvalidOrderTransition",
        "Money",
        "Order",
        "OrderStatus",
    ]
```

固定的 timezone-aware 时间和 UUID 让失败可复现，也让差异只指向被测行为。这里不调用当前时间或随机 ID，因为它们与本章政策无关；后续需要验证生成策略时，再把 clock 和 ID generator 作为明确边界测试。

异常类型通常比完整消息更稳定。`match="positive"` 和 `match="PENDING_PAYMENT.*PAID"` 只锁定对排障有价值的关键词，不把标点与整句文案变成公共 API；若消息本身属于外部契约，则应在对应 contract test 精确断言，而不是让所有 unit tests 都脆弱地复制文案。

## 设计取舍

### 行为断言与实现断言

行为测试通过公开 API 建立状态并检查公开结果。它允许把条件分支改成 transition table、把 `_reject` 内联，或改变内部辅助函数，而无需修改测试。实现断言若检查 `_reject` 被调用一次、属性按某个次序赋值，测试会把当前代码形状误当成业务规则。

覆盖率只回答“哪些行执行过”，不回答“结果是否被有效检查”。一个测试可执行 `self.version += 1` 却不断言版本，覆盖率仍是绿色；把 `+= 1` mutation 成 `+= 2` 后测试也可能继续通过。mutation testing 反过来做 oracle audit：人为改变比较符、删除增量或反转分支，确认测试能杀死这些错误。它不替代代码审查，也不要求追求 100% mutation score；存活 mutation 是提示读者检查遗漏政策、等价实现和无意义代码。

### 等价类、边界与参数化

参数化适合“同一政策、不同代表值”。本章的零、负整数、负小数都应因同一个金额不变量失败，因此共享一个测试体；无效币种属于不同政策，单独命名。若参数行需要不同 setup、不同异常类型和不同解释，继续塞进一张大表只会让失败难诊断，应拆成行为测试。

边界选择来自规则而非数据类型的所有可能值。规则是严格大于零，所以 `0` 是关键边界，`-0.01` 代表边界外的小数；没有必要穷举所有 `Decimal`。同理，本章没有货币精度、舍入和换汇规则，因此不提前测试或实现它们。

### Classical 与 London TDD

Classical TDD 倾向用真实协作者验证一小块对象图和最终状态；London TDD 倾向从交互协议出发，用 doubles 推动 ports 与职责设计。两者都可以产生好设计，也都可能被滥用。本章领域对象没有 I/O 协作者，真实对象更简单、更可信，mock 只会复制实现。后续支付 adapter、repository 和 clock 出现时，是否用 fake、stub 或 mock 应由风险与边界决定，不以流派身份决定。

## 贯穿 lab

所有命令从 `python-testing/lab/` 执行。重跑本章的聚焦证据：

```bash
uv run pytest tests/unit/test_order.py -q
```

Task 4 完成时的局部快照是 `49 passed`；后续任务会增加数量。运行所有 unit 测试：

```bash
uv run pytest tests/unit -q
```

默认 Docker-free 反馈仍由 track README 的 fast 命令定义；本章只增加纯 stdlib 领域代码和真实对象测试，不打开数据库、网络、容器或 framework 边界。

把变更评审成一条证据链：先看测试名是否表达政策，再看 RED 是否因目标能力缺失而失败，然后看 GREEN 实现是否只满足该政策，最后用参数化和 mutation 思维寻找 oracle 漏洞。代码覆盖率是辅助地图，不是完成定义。

## 故障工单

### 工单：测试断言私有调用顺序，重构后业务未变却红灯

**症状**

支付成功逻辑从“先调用私有校验、再调用私有版本更新、最后写状态”重构为一个 transition table。公开结果仍是 `PAID`，引用与版本都正确，但测试报告 `_validate_transition` 与 `_increment_version` 的调用顺序不匹配。

**证据**

- 通过公开 API 重放订单流程，状态、provider reference 和版本均符合政策。
- 失败测试 patch 了两个私有方法，并用 mock call list 断言内部顺序。
- 删除顺序断言后，已有公开状态断言能在真实对象上通过。
- mutation 掉版本增量时，公开行为测试会失败，说明真正风险已有 oracle。

**假设**

测试把一次实现步骤记录当成业务契约；无害重构改变了内部结构，却没有改变调用者可观察行为。

**修复**

删除对私有方法与调用顺序的 patch，使用真实 `Order`，只断言目标状态、支付引用和版本变化。若顺序其实是外部协议要求，例如必须先持久化再发布消息，应把它提升为 port 的明确契约并在相应 component/contract 边界验证，而不是借私有方法名称暗示。

**regression test**

保留 `test_mark_paid_moves_in_progress_order_and_records_reference` 与幂等测试；再次交换内部实现次序时它们应继续绿色。把版本增量删除或把目标状态改错时，它们必须红。

**工单结论**

对无害重构敏感、对业务错误不敏感的测试是负资产。先问“调用者能观察什么”，再选择 assert；只有外部协议本身规定交互时，调用约束才属于行为。

## Java/Go 对照

| 主题 | Python / pytest | Java / JUnit | Go testing |
|---|---|---|---|
| 参数化 | `@pytest.mark.parametrize` 生成独立 case | `@ParameterizedTest` 与 arguments source | 常见 table-driven test + `t.Run` |
| 值对象 | frozen dataclass 可集中校验 | record / immutable class + constructor validation | struct + validating constructor convention |
| 异常政策 | 类型 + 必要消息片段 | `assertThrows` 后检查类型／消息 | 显式 error 值与 `errors.Is/As` |
| doubles | fixture/plugin 生态容易过度 patch | Mockito 等易锁定 interactions | interface fake 常见，但也会复制实现 |

JUnit 使用者可能习惯对 service 的每个 collaborator 做 verify，Go 使用者可能把所有 case 放进一张 table；迁移到 pytest 时仍应先判断这些行是否真是同一政策。语言工具不同，“测试公开行为、让失败只指向一个规则”的标准不变。

## 验收与面试卡

### 验收

- 能展示 11 个 symbol/API 循环与 23 个后续行为／export-policy RED→GREEN 循环，以及最后受全套行为测试保护的 REFACTOR。
- 金额只接受 `Decimal`，明确拒绝 float、零与负数；币种校验并规范为大写。
- 合法支付转换把版本从 1 增到 3；未开始支付不能标记成功。
- 相同 provider reference 的成功重放幂等，不再次增加版本。
- 测试使用固定的 timezone-aware 时间与 UUID，不依赖 mock 或 I/O。
- 章节中的 Python 代码逐字来自 runnable lab 源文件。

检查机制锚点：

```bash
rg -n "behavior|Arrange|Given|失败理由|测试名|等价类|边界|异常|确定性|coverage|mutation|London|Classical|私有|调用顺序" python-testing/02-test-design-and-tdd.md
```

### 面试卡 1：覆盖率高为什么仍可能漏掉严重 bug？

**一句话：** 覆盖率证明代码被执行，不证明测试的 oracle 能区分正确与错误结果。

**深答：** 我会挑业务不变量做 mutation audit，例如删除版本增量、反转金额比较、取消幂等早退；若测试仍绿，说明 assertion 质量不足。先补公开行为断言，再考虑是否提高覆盖率门槛，而不是用更多无断言执行堆数字。

### 面试卡 2：什么样的测试能支持重构？

**一句话：** 通过公开 API 建立前提并断言可观察结果，不把私有方法、调用顺序和对象形状当契约。

**深答：** 我先区分业务行为和实现路径。订单支付的契约是状态、引用、版本与非法转换；内部是否使用 helper 或 table 可以改变。只有跨边界协议确实规定交互时，才在那个边界验证调用，而不是在 unit test patch 私有方法。

### 面试卡 3：何时用参数化，何时拆测试？

**一句话：** 同一规则的不同等价类代表值用参数化，不同失败理由分别命名。

**深答：** 零、负整数和负小数都违反 `amount > 0`，共享测试体能减少重复并保留独立 case ID；币种长度是另一政策，应单独测试。若表中每行需要不同 setup、异常和解释，我会拆开，使每个红灯直接指向一条业务规则。

完成本章后返回 [Python 测试工程 track](README.md)。下一章会在不改变这些领域不变量的前提下建立 fixture 与参数化的数据组织方式。
