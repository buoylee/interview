# fixture 与参数化

## 核心问题

fixture 不是“把 setup 搬到装饰器里”。它定义资源由谁创建、可以共享多久、谁负责释放，以及测试能否依赖执行顺序。对可变 `Order` 而言，错误的 module/session scope 会让前一个测试的状态成为后一个测试的隐式输入；扩大 scope 也许少做几次 setup，却把隔离性换成了顺序依赖。

本章建立两条仓库级规则：测试数据工厂必须给出确定性默认值并保留显式覆盖；可变领域对象不得由 module/session-scoped fixture 直接返回。共享的是无状态 factory，不是它创建的对象。

## 直觉模型

### fixture 是按名字解析的依赖 DAG

以下依赖不是按文件中的书写顺序执行，而是由测试函数和 fixture 参数名形成有向无环图：

```text
test_create_order
├── order_factory
└── app
    ├── repository
    │   └── database
    └── clock
```

pytest 在 item 的 setup 阶段按参数名做 request-time lookup。它从测试所在目录向上寻找适用的 `conftest.py`，再考虑注册 plugin 暴露的 fixture；离测试更近的同名 fixture 可以覆盖更远的定义。测试不应 import `conftest.py`，因为 import 绕过了 pytest 的可见性和生命周期协议。

一次 request 中，同一 fixture 只计算一次并从 cache 返回；cache 的寿命由 scope 控制。function scope 的 cache 随 item 结束，module scope 跨同一模块中的 items，session scope 跨整次运行。scope 不是“快慢档位”，而是所有权声明：只有对象真的能被这些消费者安全共享，才允许扩大 scope。

### factory fixture 与 object fixture

object fixture 在 setup 时创建一个对象，同一 request 的消费者拿到同一实例。factory fixture 返回 callable，测试每调用一次便获得一个新对象：

| 选择 | 适合 | 风险 |
|---|---|---|
| `order` object fixture | 单个测试只需要一个固定前提 | 测试需要多个变体时容易再叠 fixture |
| `order_factory` factory fixture | 同一测试需要多个新实例或关键字覆盖 | 默认值若不确定，会隐藏输入 |
| module/session object fixture | 真正只读、线程安全、生命周期昂贵的资源 | 可变状态泄漏、顺序依赖、并行失败 |

工厂本身无状态，因此 function-scoped fixture 很便宜；`make_order()` 每次调用真实的 `Order.create`，不是 mock，也没有为测试向生产类增加方法。

## 机制深入

### cache、scope mismatch 与 teardown

高 scope fixture 不能依赖低 scope fixture。session-scoped fixture 若请求 function-scoped fixture，低 scope 资源会在高 scope 对象仍持有它时过期；pytest 因而在 setup 报 `ScopeMismatch`。修复应重新判断所有权，不能只把下游 fixture 一路扩大到 session。

`yield` fixture 在 `yield` 前 setup，在 `yield` 后 teardown。依赖按拓扑顺序 setup，已完成 setup 的 fixture 按后进先出（LIFO）释放：若 `app` 依赖 `repository`，而 `repository` 依赖 `database`，正常 teardown 是 `app → repository → database`。

setup failure 的边界也很具体：

- 在某 fixture setup 失败后，依赖它的测试和后续 fixture 不会运行。
- 先前已成功 setup 的 fixture 仍会 teardown。
- 失败 fixture 若尚未执行到 `yield`，其 `yield` 后代码不会运行。
- 用 `request.addfinalizer` 注册的 finalizer 一经注册，即使随后 setup 失败也会运行；因此只应在资源成功取得后注册释放动作。
- 多个 finalizer 同样按 LIFO 执行。

这解释了为什么一个 fixture 最好只获取一种资源：setup 做到一半失败时，释放责任才容易证明。

### 本章的类型化工厂

以下文件逐字来自 [`lab/tests/factories.py`](lab/tests/factories.py)：

```python
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

默认 UUID、时间、金额和币种固定，使失败可复现；关键字参数让测试只突出与政策相关的差异。`Callable[..., Order]` 是消费者所需的最小类型面：它承诺 callable 会返回 `Order`，但不重复维护函数签名。若未来需要让静态检查器验证每个关键字，可在需求出现时改为带 `__call__` 的 `Protocol`，本章不提前增加它。

fixture 逐字来自 [`lab/tests/conftest.py`](lab/tests/conftest.py)：

```python
import pytest

from tests.factories import OrderFactory, make_order

pytest_plugins = ["pytester"]


@pytest.fixture(scope="function")
def order_factory() -> OrderFactory:
    return make_order
```

显式 `scope="function"` 让 `--setup-show` 展示每个 item 的 ownership 边界，并阻止团队把共享可变对象悄悄塞进这个 fixture。`pytest_plugins` 启用 pytest 内建的 pytester plugin；它只为测试 pytest 本身的 fixture 生命周期服务，不改变生产行为。

scope regression 逐字来自 [`lab/tests/unit/test_order_factory.py`](lab/tests/unit/test_order_factory.py)：

```python
def test_order_factory_is_function_scoped(pytester: pytest.Pytester) -> None:
    test_file = Path(__file__).resolve()
    result = pytester.runpytest_subprocess(
        "--setup-show",
        "-q",
        f"{test_file}::test_order_factory_preserves_keyword_overrides",
        f"{test_file}::test_order_factory_is_callable_and_returns_fresh_orders",
    )

    result.assert_outcomes(passed=2)
    output = result.stdout.str()
    lifecycle_counts = (
        output.count("SETUP    F order_factory"),
        output.count("TEARDOWN F order_factory"),
    )

    assert lifecycle_counts == (2, 2), output
```

子进程只选择两个非 meta consumer node IDs，两个测试都调用仓库实际的 `order_factory` 并断言真实 `Order` 行为，因此不会递归收集 scope regression。先把 fixture 临时设为 module scope 时，inner tests 仍是 `2 passed`，但输出只有一组 `SETUP M / TEARDOWN M`，回归以 `(0, 0) != (2, 2)` 失败；只把 scope 改为 function 后才出现两组生命周期并变绿。它验证运行行为，不靠 decorator 或源码字符串猜 scope。

### indirect parametrization、request.param 与 IDs

直接参数化适合纯输入：`@pytest.mark.parametrize("currency", ["USD", "EUR"])` 会把值直接传给测试。只有当参数需要经过 fixture setup 才用 `indirect=True`；此时参数进入 `request.param`，测试参数名最终收到 fixture 的返回值。

下面是伪代码（pseudocode，不是 runnable lab 源码）：

```python
@pytest.fixture
def payment_gateway(request: pytest.FixtureRequest) -> PaymentGateway:
    return build_gateway(request.param)


@pytest.mark.parametrize(
    "payment_gateway",
    ["approved", "declined"],
    indirect=True,
    ids=["gateway-approves", "gateway-declines"],
)
def test_payment_result(payment_gateway: PaymentGateway) -> None:
    ...
```

`request.param` 只在该 fixture 被 indirect parametrization 提供参数时存在。若 fixture 也支持非参数化调用，应显式定义默认政策，而不是捕获任意 `AttributeError`。IDs 应描述业务 case；可用 `ids=[...]`、生成 ID 的 callable，或 `pytest.param(..., id="...")`。可读 ID 会进入 node ID，直接改善 `-k`、CI 报告和失败重跑。

## 设计取舍

### conftest、plugin 与 autouse 的边界

`conftest.py` 的可见性沿目录树向下。根 `tests/conftest.py` 适合整个测试套件都理解的能力；局部 fixture 放在最近的子目录。可跨仓库复用且有独立版本生命周期的 fixture 才适合 plugin，通过 entry point 或 `pytest_plugins` 注册。plugin fixture 仍参与名字解析，本地同名定义可能覆盖它；升级 plugin 后应检查 `--fixtures` 和 `--trace-config`，不能把 fixture 来源当成全局唯一。

`autouse=True` 把依赖从函数签名中隐藏。它适合必须对该可见范围内每个测试成立的隔离政策，例如重置全局时区；不适合“大家大概都要”的数据库、网络或业务对象。autouse fixture 仍会先 setup，它请求的依赖也随之对所有 item 生效，扩大 scope 时更容易制造全局状态。

### session scope 是所有权决策

扩大 scope 前回答四个问题：对象是否不可变或有可靠 reset；并行 worker 是否共享它；失败中途是否仍能释放；一个测试的写入是否能改变另一个测试的观察。如果任一答案不清楚，保留 function scope。昂贵资源可以在 session scope 共享“资源管理器”或连接池，再由 function fixture 创建事务／namespace；不要直接共享可变领域实体。

## 贯穿 lab

先运行聚焦工厂契约：

```bash
uv run pytest tests/unit/test_order_factory.py -q
```

它证明 `make_order` 返回真实 `Order`、默认值确定、每次调用产生独立可变实例、关键字覆盖被保留，并且 `order_factory` 是 callable 且返回 fresh orders。

再观察 fixture setup/teardown：

```bash
uv run pytest tests/unit -q --setup-show
```

`order_factory` 对使用它的每个测试分别出现 `SETUP F` 与 `TEARDOWN F`。最后运行默认 suite：

```bash
uv run pytest -q
```

`pyproject.toml` 的 `testpaths = ["tests"]` 只收集默认绿色套件，不会收集 `scenarios/fixture-leak/`。默认命令 Docker-free；只有后续显式选择 `docker` marker 的 integration/E2E 才允许接触容器。

## 故障工单

### 工单：单测单独通过，整模块运行时第二个测试失败

**症状**

第一个测试调用 `shared_order.start_payment()` 并通过；第二个测试期望 pending order，却观察到 `payment_in_progress`。单独运行第二个测试则通过。

**证据**

以下 fixture 逐字来自 [`lab/scenarios/fixture-leak/conftest.py`](lab/scenarios/fixture-leak/conftest.py)：

```python
import pytest

from order_service.domain.order import Order
from tests.factories import make_order


@pytest.fixture(scope="module")
def shared_order() -> Order:
    return make_order()
```

测试逐字来自 [`lab/scenarios/fixture-leak/test_leak.py`](lab/scenarios/fixture-leak/test_leak.py)：

```python
def test_a_mutates_shared_order(shared_order) -> None:
    shared_order.start_payment()


def test_b_expected_fresh_order(shared_order) -> None:
    assert shared_order.status.value == "pending_payment"
```

从 `lab/` 显式运行：

```bash
uv run python -m pytest scenarios/fixture-leak -q
```

`python -m pytest` 按 Python module runner 规则把当前工作目录放入模块搜索路径，因此场景可导入正常 package 边界下的 `tests.factories`；pytest console script 不保证同一入口路径。这里选择明确的 runner contract，不修改 `sys.path`、不复制 helper，也不改变已通过 editable install 提供的生产包。显式运行退出码为 `1`，结果是 `1 passed, 1 failed`；失败在第二个 test call 的 assertion，不是 collection/setup error。

**假设**

module cache 把同一个可变 `Order` 返回给两个 items。第一个 item 的合法领域行为把 `status` 和 `version` 原地修改，第二个 item 因此读取了泄漏状态。

**修复**

首选让 fixture 返回 `make_order` factory，由每个测试明确调用；如果每个测试只需一个订单，则把 object fixture 改为默认 function scope。不要在 teardown 中“猜测”如何把实体改回旧状态，也不要让第二个测试依赖第一个测试先运行。

**regression test**

[`lab/tests/unit/test_order_factory.py`](lab/tests/unit/test_order_factory.py) 同时创建两个订单，先改变第一个，再断言第二个仍为 `PENDING_PAYMENT` 且身份不同；fixture 版本也执行同一政策。恢复命令是 `uv run pytest tests/unit/test_order_factory.py -q`，而故障场景永久保留原始红灯作为 opt-in 证据。详见[场景 README](lab/scenarios/fixture-leak/README.md)。

## Java/Go 对照

| pytest | Java / JUnit | Go | 常见误判 |
|---|---|---|---|
| fixture 参数名与 DAG | extension、parameter resolver、生命周期 callback | helper + `t.Cleanup` | pytest 依赖由名字和可见性解析，不是 import 调用 |
| function/module/session cache | per-method/per-class 实例与 extension store | package 变量、`TestMain` | 高 scope 不自动安全，只是共享更久 |
| `yield` / finalizer LIFO | `@AfterEach` / closeable resource | `defer` 与 `t.Cleanup` | setup 失败时只释放已取得且已登记的资源 |
| indirect parametrization | parameterized source + resolver | table-driven test 中构建 fixture | `request.param` 是 setup recipe，不应把所有输入都间接化 |

JUnit 的 per-class lifecycle 与 Go 的 package globals 都可能复制 module-scoped mutable fixture 的泄漏。迁移经验时应保留“每个 case 拥有自己的领域实体”，而不是照搬框架的最大共享能力。Go 的 `t.Parallel` 和 pytest-xdist 还会放大未声明共享状态的风险。

## 验收与面试卡

### 验收

- 能从测试参数画出 fixture DAG，并解释名字查找、目录可见性与 plugin 来源。
- 能解释同一 scope 的 cache、`ScopeMismatch`、yield/finalizer LIFO 和 setup failure 后哪些 teardown 会运行。
- 能根据所有权选择 function/module/session scope，不把 session 当成单纯加速器。
- 能区分 factory fixture 与 object fixture，并证明真实 `Order` 的默认值、覆盖和 freshness。
- 能说明 `indirect=True`、`request.param` 与可读 IDs 如何改变 setup 和 node ID。
- 能限制 conftest、plugin 与 autouse 的隐式影响。
- opt-in 泄漏场景稳定得到第一项通过、第二项失败；默认 suite 稳定绿色且不收集场景。

检查章节锚点：

```bash
rg -n "依赖 DAG|request-time|cache|ScopeMismatch|LIFO|setup failure|factory fixture|pytester|indirect|request.param|IDs|conftest|plugin|autouse|所有权" python-testing/03-fixtures-and-parametrization.md
```

### 面试卡 1：为什么不把昂贵 fixture 全改成 session scope？

**一句话：** scope 表达共享所有权和释放时机；速度收益不能证明可变状态、并行访问和失败清理是安全的。

**深答：** 我先拆分资源管理器与每个测试拥有的状态。连接池可以高 scope，共享事务中的业务数据不可以；function fixture 为每个 item 创建事务或 namespace，并用 LIFO teardown 回收。若高 scope 请求低 scope，pytest 的 `ScopeMismatch` 正在提示生命周期倒置，不应机械扩大下游 scope。

### 面试卡 2：factory fixture 比 object fixture 好在哪里？

**一句话：** 它共享无状态构造能力，让一个测试按需创建多个带确定默认值和局部覆盖的新实体。

**深答：** 本章的 `order_factory` 返回真实 `make_order`，每次调用都经过 `Order.create` 和 `Money` 校验。测试能突出 `amount` 或 `idempotency_key` 这类政策差异，同时用身份和状态断言证明没有共享可变实例。它不是 mock，也不要求给生产 `Order` 添加 reset/destroy 之类测试专用 API。

### 面试卡 3：什么时候使用 indirect parametrization？

**一句话：** 当参数是 fixture 的 setup recipe，而不是测试函数直接消费的纯数据时才使用。

**深答：** `indirect=True` 把 case 值交给 fixture 的 `request.param`，fixture 完成资源构建后再把结果给测试；普通业务输入继续直接参数化，避免隐藏数据流。我会给每个 case 稳定业务 ID，使 CI node ID、`-k` 选择和失败重跑可读，并保证非参数化路径对缺失 `request.param` 有明确政策。

完成本章后返回 [Python 测试工程 track](README.md)。下一章会在这些 ownership 规则上增加 ports 和 handwritten fakes。
