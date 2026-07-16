# Test doubles 与 seams

## 核心问题

测试订单创建时，真实数据库、支付网络、系统时钟和随机 UUID 会把应用政策与基础设施故障混在一起。全用 mock 又会得到另一种假象：测试只证明自己配置的调用链能返回自己配置的值，却没有证明订单和 outbox 在同一个事务边界内发布。

本章把可替换边界设计成应用拥有的 port，并用 handwritten fake 执行真实的 repository 与 unit-of-work 协议。目标不是“mock 越多越快”，而是让证据对应风险：领域结果用 state verification，重要协作协议才用 interaction verification；时间、ID 与持久化边界都由构造器注入，并保持确定性。

## 直觉模型

### Meszaros taxonomy 是角色，不是库名称

| double | 提供什么 | 本章例子 | 主要风险 |
|---|---|---|---|
| dummy | 只填参数，不参与行为 | 不会被读取的 callback 参数 | 一旦系统开始读取，dummy 已不完整 |
| stub | 给出预设响应 | 固定返回时间的 `FrozenClock` | 容易只覆盖 happy path |
| spy | 记录真实调用供事后断言 | 记录通知次数的轻量对象 | interaction assertion 绑死实现顺序 |
| mock | 预先声明期望交互并验证 | 支付 port 的一次调用契约 | 测到配置而非业务结果 |
| fake | 以简化实现保留生产语义 | `MemoryUnitOfWork` 与 repositories | fidelity 不足会“说谎” |

同一个对象可能承担多个角色；分类看测试如何使用它，而不是看它来自 `unittest.mock` 还是手写 class。`FrozenClock` 常被称为 fake，也可视为只返回固定值的 stub；重要的是它替代了非确定性 seam。

### state verification 与 interaction verification

订单创建的主要输出是状态：一个确定的 `Order` 和一个 `payment_requested` outbox message 被一起提交；同一幂等键重放不增加记录。这应通过 fake store 的最终状态验证。支付 provider 是否被调用一次、是否带某个 idempotency header，属于跨边界协作契约，才适合 interaction verification。

若每个断言都是 `assert_called_once_with`，重构内部协作顺序会造成无业务回归的失败。若对外部副作用完全不验证，只看返回值，又会遗漏“返回成功但没发请求”。先问风险位于状态还是交互，再选证据。

## 机制深入

### consumer-defined ports

port 由应用消费者定义最小能力，不由 SQLAlchemy、HTTP client 或某个 vendor SDK 的 API 反推。以下内容逐字来自 [`lab/src/order_service/ports/uow.py`](lab/src/order_service/ports/uow.py)：

```python
"""Persistence and unit-of-work ports."""

from collections.abc import Callable
from datetime import datetime
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

    async def claim_batch(
        self, *, limit: int, now: datetime
    ) -> list[OutboxMessage]: ...

    async def mark_done(self, message_id: UUID) -> None: ...

    async def mark_failed(
        self, message_id: UUID, *, available_at: datetime
    ) -> None: ...


class UnitOfWork(Protocol):
    orders: OrderRepository
    outbox: OutboxRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]
```

`Protocol` 使用 structural typing：真实 SQL adapter 和内存 fake 不必继承共同基类，只需满足同一签名。`datetime` 在 claim/backoff 参数上显式出现，避免 later adapter 把时间类型解释成任意值。`UnitOfWorkFactory` 每次执行创建事务边界；把一个已进入的 UoW singleton 注入多个请求，会混淆 snapshot 和并发所有权。

### 构造器注入与非确定性 seams

以下 message 定义逐字来自 [`lab/src/order_service/application/messages.py`](lab/src/order_service/application/messages.py)：

```python
"""Application message contracts."""

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

command 是不可变输入；outbox delivery state 则必须能更新 attempts、claim、available time 和 done。应用通过构造器接收 `Clock`、`IdGenerator` 与 `UnitOfWorkFactory`。测试给出 `FrozenClock` 和 `SequenceIdGenerator`，生产可给出系统时钟和 UUID generator；业务代码不 patch `datetime.now()` 或 `uuid4()` 的全局名字。

随机数、时间和 UUID 都应在靠近应用边界处形成 seam。确定性不是为了让断言好写，而是为了能重放失败：相同输入得到相同 aggregate/message ID 和 timestamp，exhaustion 也有稳定错误。

### Mock 的约束工具

下面是概念伪代码（pseudocode，不是 runnable lab 源码）：

```python
gateway = Mock(spec_set=PaymentGateway)
charge = create_autospec(PaymentGateway.charge, spec_set=True)
charge.side_effect = [TimeoutError, PaymentResult.approved("pay-001")]
```

`spec_set` 阻止读取或设置接口不存在的属性，`create_autospec` 还校验 callable 签名；它们能尽早暴露拼错的方法和参数。`side_effect` 可依次抛异常／返回结果，也可接受 callable 模拟输入相关结果。它们仍不能证明远端真实 schema，因此 versioned contract test 不能被 mock unit test 取代。

异步 port 需要 awaitable double。`AsyncMock` 能记录 await 次数和参数；同步 `Mock` 返回普通值，放进 `await` 会产生类型错误。即使使用 `AsyncMock(spec_set=...)`，也只对真正需要 interaction evidence 的外部协作断言，repository/UoW 行为继续由 handwritten fake 验证。

## 设计取舍

### fake fidelity 是明确的事务契约

[`lab/src/order_service/adapters/memory.py`](lab/src/order_service/adapters/memory.py) 不是共享 list/dict 的便利容器。进入 UoW 时，它 deep-copy store，repository 读写 transaction-local snapshot；未 commit 或 context exception 不发布；commit 再 deep-copy 到 store 并增加 commit count。同一实例顺序 re-enter 时重新取 snapshot，不保留上次未提交写入。

outbox fake 也保留 later worker 所需行为：只 claim due、未 done 且 lease 可用的 message；30 秒边界可重新 claim；正数 limit 截断，零不 claim，负数拒绝且不改状态；claim 写入 timestamp；done 清 claim；failed 增 attempts、设置 backoff 并清 claim。不存在的 ID 明确抛 `KeyError`。这些都由真实对象状态断言覆盖，不靠 `AsyncMock` 假装事务成立。

fake 仍不是数据库替代品。它不能证明 unique constraint、隔离级别、并发锁、serialization、migration 或 driver mapping；这些风险属于后续真 Postgres integration tests。fake 的职责是快速且忠实地执行应用级所有权规则。

### 为什么不 mock SQLAlchemy query chain

把 `session.execute(...).scalars().first()` 每一级都配置成 mock，测试的是自己重造的 SQLAlchemy 调用形状。查询从 `scalars().first()` 改为 `scalar_one_or_none()` 时，业务语义没变却全部失败；更严重的是 join、constraint、transaction isolation 错误仍不会被发现。应用测试面向 `OrderRepository`；adapter integration test 面向真 Session 与数据库。不要把 ORM 内部 fluent chain 当成应用 port。

依赖注入也不要求 DI framework。当前 use case 的构造器已把所有可变边界显式列出，lambda factory 清楚表达每次 UoW 的创建时机。只有 object graph 复杂到手工 wiring 本身成为风险时，container 才有收益。

## 贯穿 lab

以下实现逐字来自 [`lab/src/order_service/application/create_order.py`](lab/src/order_service/application/create_order.py)：

```python
"""Order creation use case."""

from order_service.application.messages import CreateOrderCommand, OutboxMessage
from order_service.domain.order import Money, Order
from order_service.ports.system import Clock, IdGenerator
from order_service.ports.uow import UnitOfWorkFactory


class CreateOrder:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._ids = ids
        self._clock = clock

    async def execute(self, command: CreateOrderCommand) -> Order:
        async with self._uow_factory() as uow:
            existing = await uow.orders.get_by_idempotency_key(
                command.idempotency_key
            )
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

先查 idempotency key，使 replay 返回已存在订单、不增加 outbox，也不消耗 ID。新订单和 payment intent 都写入 transaction-local snapshot，取得两个 ID 后才 commit；若 message ID exhaustion，context 退出但 store、outbox 与 commit count 保持不变。

从 `lab/` 运行：

```bash
uv run pytest tests/unit/test_messages.py tests/unit/test_memory_adapter.py tests/component/test_create_order.py -q
```

这些测试使用 strict asyncio mode、真实 `Order` 和 handwritten fakes，没有 `AsyncMock`。再运行所有快速层：

```bash
uv run pytest tests/unit tests/component -q
uv run pytest -q
```

默认 suite 不选择 Docker；数据库语义留给显式 `integration and docker` 层。

## 故障工单

### 工单：测试 patch 成功，worker 却发出真实支付请求

**症状**

测试 patch 了 `order_service.payments.client.charge`，断言仍观察到真实网络调用。CI 有时因 provider sandbox 可达而通过，有时超时。

**证据**

下面是最小 import-binding 伪代码（pseudocode，不是 runnable lab 源码）：

```python
# worker.py
from order_service.payments.client import charge

async def handle(message):
    return await charge(message.payload)

# bad test: changes client.charge, not worker.charge
with patch("order_service.payments.client.charge", new_callable=AsyncMock):
    await handle(message)
```

`from ... import charge` 在 import 时把对象绑定到 `worker.charge`。之后改变 definition module 的 `client.charge`，不会重写 worker 已持有的名字。

**假设**

patch target 选择了定义位置，而被测代码在 lookup site 读取另一个绑定。真实 coroutine 因此仍被 await。

**修复**

patch 被测模块查找的名字，例如 `patch("order_service.worker.charge", new_callable=AsyncMock)`；需要签名约束时可先对实际 async callable 使用 `create_autospec`。更稳健的设计是把 payment gateway 作为 constructor dependency 注入 worker，使替换点与对象所有权显式。使用 patch 时必须在 import binding 已确定后 patch lookup site，并验证 double 是 async-aware。

**regression test**

回归应断言 handler 的业务状态和真正关键的 payment interaction；同时让任何未预期网络访问直接失败。不要只断言 “mock 存在”。后续支付 adapter 还需独立 contract test，证明真实 request/response schema。

## Java/Go 对照

| Python | Java | Go | 容易误判 |
|---|---|---|---|
| `Protocol` structural typing | interface | implicit interface | Python runtime 默认不替你做完整静态验证 |
| constructor injection | constructor/interface injection | struct field/function parameter | patch 全局名字不是依赖所有权设计 |
| `Mock(spec_set)` / autospec | Mockito strict stubs/spec | generated/manual mock | spec 只约束表面，不证明远端契约 |
| handwritten fake UoW | in-memory repository + transaction fake | fake store | 简化实现必须保留 commit/rollback fidelity |
| patch lookup site | static/import binding 替换 | package variable replacement | 定义位置不一定是被测代码 lookup 位置 |

Java 的 nominal interface 会在编译期检查 adapter；Go 的 implicit interface 更接近 Python `Protocol`，但 Go compiler 总会检查赋值点。Python 若不运行 type checker，必须用精确的接口 regression、adapter tests 与实际执行共同守住边界。三种语言都不能靠 ORM mock 证明数据库 constraint 和 transaction semantics。

## 验收与面试卡

### 验收

- 能按 dummy/stub/spy/mock/fake 解释 double 在当前测试中的角色。
- 能按风险选择 state 或 interaction verification，不把 call count 当成所有证据。
- ports 由应用消费者定义，并保留 async repository/UoW 的精确签名。
- command frozen/slotted；outbox delivery state 可变且默认值明确。
- clock、ID、repository、outbox 与 UoW fake 的行为由真实状态测试覆盖。
- UoW 具有 copy-on-enter、read-your-writes、rollback/no-commit isolation、deep-copy commit 与 safe re-entry。
- create-order replay 不复制记录或消耗 ID；message-ID exhaustion 不发布部分状态。
- 能解释 autospec/spec_set/side_effect、AsyncMock 和 patch-at-lookup-site 的限制。
- 不用 mock SQLAlchemy query chain 替代真数据库 integration test。

检查章节锚点：

```bash
rg -n "dummy|stub|spy|mock|fake|state verification|interaction verification|consumer-defined|Protocol|constructor|spec_set|create_autospec|side_effect|lookup site|AsyncMock|Clock|IdGenerator|fidelity|SQLAlchemy" python-testing/04-test-doubles-and-seams.md
```

### 面试卡 1：fake 和 mock 的关键区别是什么？

**一句话：** fake 执行一个简化但可工作的状态模型；mock 主要验证预先声明的交互，两者都必须对应具体风险。

**深答：** 本章的 fake 会真的 add/get/claim/commit，并通过 deep-copy 模拟事务发布边界，所以适合验证幂等与 atomic outbox intent。payment provider 的调用次数和参数属于外部协作，才适合严格 mock；真实 HTTP schema 仍由 contract test 验证。

### 面试卡 2：为什么 patch 定义位置可能无效？

**一句话：** 被测模块可能早已用 `from ... import ...` 建立本地绑定，运行时 lookup 的不是定义模块当前属性。

**深答：** 我先定位被测代码实际读取的名字，再 patch lookup site；async callable 用 `AsyncMock` 或正确 autospec。更长期的修复是 constructor injection，使 dependency ownership 和替换点不依赖 import 细节。

### 面试卡 3：内存 repository 通过后，为什么还要真数据库测试？

**一句话：** fake 证明应用政策，不能证明数据库的 constraint、locking、isolation、migration 与 driver mapping。

**深答：** 我让 component tests 快速覆盖幂等、outbox intent 和 rollback fidelity；再用较少的 Postgres integration tests 覆盖 unique race、事务可见性和映射。mock ORM chain 同时失去两类证据：既绑死调用形状，也没执行数据库语义。

完成本章后返回 [Python 测试工程 track](README.md)。下一章会在这些 ports 上增加无网络进程的 FastAPI component tests。
