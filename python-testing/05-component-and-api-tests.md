# Component 与 API 测试

## 1. 核心问题

路由测试要证明 HTTP 解析、验证、依赖装配、use case、序列化和生命周期能在同一应用边界协作。它不需要监听端口，也不能把被验证的路由函数 mock 掉。这里用真实 `CreateOrder` 和内存 adapters；未证明真实网络、数据库或支付端行为。

## 2. 直觉模型

`httpx.ASGITransport` 把请求直接交给 ASGI app：协议边界是真的，网络进程是省掉的。`AsyncClient` 与异步业务代码共享清晰的 event-loop ownership；同步项目也可用 FastAPI `TestClient`，但不要在已经异步的测试里混入第二套循环管理。

## 3. 机制深入

HTTPX 不替 app 启停 lifespan，所以 fixture 必须显式进入 `app.router.lifespan_context(app)`，并在 client 外层持有它。依赖覆盖也是 app 的可变状态，yield fixture 的 teardown 必须 `clear()`，否则下一测试可能继承假依赖并产生顺序依赖。

请求 schema 在调用领域前拒绝非正金额和非法币种；header 约束把空白幂等键映射成稳定 422，而不是让领域 `ValueError` 泄漏成 500。响应 schema 对 Decimal 使用字符串 serializer，避免金额变成 JSON float。

```python
# python-testing/lab/src/order_service/api/dependencies.py
from order_service.application.create_order import CreateOrder
from order_service.application.refund_order import RefundOrder


def get_create_order() -> CreateOrder:
    raise RuntimeError("CreateOrder dependency is not configured")


def get_refund_order() -> RefundOrder:
    raise RuntimeError("RefundOrder dependency is not configured")
```

```python
# python-testing/lab/src/order_service/api/schemas.py
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from order_service.domain.order import Order


class CreateOrderRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")


class OrderResponse(BaseModel):
    id: UUID
    status: str
    amount: Decimal
    currency: str
    version: int

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)

    @classmethod
    def from_domain(cls, order: Order) -> Self:
        return cls(
            id=order.id,
            status=order.status.value,
            amount=order.total.amount,
            currency=order.total.currency,
            version=order.version,
        )


class RefundResponse(BaseModel):
    order_id: UUID
    status: Literal["accepted"]
```

## 4. 设计取舍

少量精确响应断言适合稳定公共契约；大面积 snapshot 容易把无关 OpenAPI 或错误文本变化变成噪声。golden 文件适合体积大且需人工评审的版本化产物，但必须有明确更新流程。OpenAPI 是可比较、可发布的契约 artifact，却不能替代运行时路由测试。

错误 handler 应按公共错误类型断言状态、代码和安全信息，避免锁死框架生成的全部文字。结构化日志用 `caplog` 检查事件名、业务 ID、level 与必要字段，不比较整行时间戳，也不记录敏感 body/header。

## 5. 贯穿 lab

fixture 对 app、lifespan、client 和 override 各自负责：

```python
@contextmanager
def configured_app(use_case: CreateOrder) -> Iterator[FastAPI]:
    application = create_app()
    application.dependency_overrides[get_create_order] = lambda: use_case
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
def app(use_case: CreateOrder) -> Iterator[FastAPI]:
    with configured_app(use_case) as application:
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as value:
            yield value
```

完整可运行测试见 [`lab/tests/component/test_api.py`](lab/tests/component/test_api.py)，应用入口见 [`lab/src/order_service/api/app.py`](lab/src/order_service/api/app.py)。测试使用两个 ID 创建 order 与 outbox；同一幂等键第二次请求仍能成功，因而也证明重放没有再消费 ID。

## 6. 故障工单

**症状：** 单独运行 API 测试通过，整套运行时下一测试意外使用前一测试的 `CreateOrder`。

**证据：** `dependency_overrides` 在 app 上仍包含 provider；改变测试顺序会改变结果。

**假设：** fixture 只创建 override，没有拥有 teardown。

**修复：** yield 后无条件 `application.dependency_overrides.clear()`；client 则显式关闭 `AsyncClient` 并退出 lifespan。

**Regression test：** 创建两个 app，证明覆盖隔离；清理第一个后断言映射为空。不要 mock 路由再断言它被调用，那只验证 mock wiring。

## 7. Java/Go 对照

Spring 的 MockMvc/WebTestClient 与 Go `httptest` 都能构建类似的进程内 HTTP 边界。名称不决定层级：若替换了数据库，它们不能证明数据库约束；若把 service mock 掉，它们也不能证明真实 use case 与 route 的装配。

## 8. 验收与面试卡

从 `python-testing/lab/` 运行：

```bash
uv run pytest tests/component/test_api.py -q
uv run pytest tests/unit tests/component -q
uv run pytest -m "not integration and not e2e and not docker" -q
```

完成定义：成功响应精确匹配 UUID、status、Decimal 字符串、规范化币种和 version；非法 header/body 为 422；幂等重放完整相同；lifespan 和 overrides 无泄漏；没有启动网络进程或 Docker。

**一句话：** 用 ASGITransport 保留 HTTP/ASGI 真实边界，用真实 use case 与可控 adapters 获得快速 component 证据，并显式拥有 lifespan 和 overrides。

**深答：** 我把框架解析和序列化留在测试内，把进程外依赖换成行为可信的内存 adapter。AsyncClient 不隐式管理 lifespan，因此 fixture 按嵌套生命周期关闭资源；输入约束提前映射为 422。路由测试断言公共结果而非函数调用顺序，OpenAPI/snapshot 只补充版本化契约审查。

完成本章后返回 [Python 测试工程 track](README.md)。下一章使用真实 Postgres 验证本组件测试无法证明的约束与事务语义。
