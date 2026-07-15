# 04 · 组合、多态与批量数据：让边界模型保持可判定

> **本章目标**：能在 nested model、普通 union、discriminated union、generic model、`RootModel` 与 `TypeAdapter` 之间做有依据的选择，并读懂组合之后的错误路径。可运行事实以 [支付 webhook](lab/src/order_contracts/inbound/payment_webhook.py)、[版本化事件 envelope](lab/src/order_contracts/events/envelope.py) 及其测试为准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_webhook.py tests/test_event_compatibility.py -v
```

当前应有 38 个测试通过。它们固定了两条主线：支付 payload 以字符串 `event_type` 选择成功／失败分支；`order.created` 事件以整数 `schema_version` 选择 V1／V2 envelope，并拒绝类型不精确的版本号。

## 先定问题：组合工具不是同一层抽象

下列工具都能“把类型放在一起”，但解决的问题不同：

| 工具 | 它表达的契约 | 典型输入 | 本章案例 |
|---|---|---|---|
| nested `BaseModel` | 一个对象由有名字的子对象组成 | JSON object | webhook envelope 包含 `payload`，金额包含 `amount`／`currency` |
| 普通 `A | B` | 输入可能符合若干候选结构，但没有可靠 tag | 标量 union，或确实无 tag 的遗留协议 | 不推荐用于已有 `event_type` 的支付事件 |
| discriminated union | 一个稳定字段先选择唯一分支 | tagged JSON object | `PaymentPayload`、`OrderCreatedMessage` |
| `EventEnvelope[PayloadT]` | 多种 payload 共享相同结构骨架 | 一组同构 envelope | `OrderCreatedEnvelopeV1`／`V2` |
| `RootModel[T]` | 整个文档本身就是 `T` | 顶层 array／scalar／mapping | 顶层订单事件数组 |
| `TypeAdapter(T)` | 不创建额外模型名，也为任意类型取得验证／schema 能力 | union、list、`TypedDict`、dataclass | `ORDER_CREATED_ADAPTER`、支付 payload 列表 |

决策顺序比 API 名称重要：先问 wire data 是 object 还是顶层容器，再问候选分支有没有稳定 tag，最后才问是否需要一个命名模型承载字段、配置和方法。

## nested model：对象边界也进入错误路径

支付 webhook 不是一个扁平模型。外层负责传输头，内层负责业务事件：

```python
class PaymentWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: EventId
    schema_version: Literal[1]
    payload: PaymentPayload
```

`PaymentSucceeded` 又嵌套 `paid_amount: Money`。这种组合让每层模型分别拥有自己的 unknown-field、冻结和字段约束政策，也让 `ValidationError.errors()` 的 `loc` 保留从根到失败点的路径。

lab 已锁定两个有代表性的路径：

```python
# payment.failed 分支缺少 failure_code
("payload", "payment.failed", "failure_code")

# payment.succeeded 分支里的 occurred_at 没有时区
("payload", "payment.succeeded", "occurred_at")
```

三个片段分别表示：

1. `payload`：外层字段名；
2. `payment.failed`／`payment.succeeded`：discriminator 选中的 union tag；
3. 最后一段：该分支内部失败的字段。

tag 出现在 `loc` 中不是多余噪声。它使错误映射器能区分“两个分支里同名字段的错误”，也使监控能按事件种类聚合。不要把 `loc` 直接拼成人类文案后暴露完整 input；把它当作稳定的机器路径，再由 API 层映射成安全错误响应。

## 支付多态：有 tag 就不要让 union 猜

lab 的两个分支各自声明唯一的 `Literal`：

```python
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


PaymentPayload = Annotated[
    PaymentSucceeded | PaymentFailed,
    Field(discriminator="event_type"),
]
```

`event_type` 同时承担 wire protocol tag 和 branch key。Pydantic 先读取它，再只验证对应分支。对合法输入，返回值因此是明确的 `PaymentSucceeded` 或 `PaymentFailed`，业务代码无需根据字段是否存在来猜类型。

### 普通 union 与 discriminated union 的失败模式

若写成下面这个普通 union：

```python
PlainPaymentPayload = PaymentSucceeded | PaymentFailed
```

Pydantic 需要尝试候选分支并收集失败原因。对一个带 `event_type="payment.refunded"`、形状又像成功事件的 payload，本 lab 环境中的探针得到四条错误：

```text
literal_error    ('PaymentSucceeded', 'event_type')
literal_error    ('PaymentFailed', 'event_type')
missing          ('PaymentFailed', 'failure_code')
extra_forbidden  ('PaymentFailed', 'paid_amount')
```

后三条并不都能指导调用方修复输入；它们只是“尝试失败分支”留下的痕迹。分支越多、结构越重叠，选择阶段可能做的验证工作和错误聚合量越大。不要把普通 union 的策略假定为“第一个成功就永远停止”；具体 union mode 还会影响选择，但它仍没有协议 tag 可直接路由。

同一输入交给 `PaymentPayload`，只有一条：

```text
union_tag_invalid  ()
```

嵌入 envelope 后，路径变成 `("payload",)`。若 tag 合法但分支字段错误，才进入该唯一分支并产生 `("payload", <tag>, ...)`。这带来两个工程收益：

- **选择复杂度更稳定**：tag lookup 后验证一个分支，而不是让候选数放大分支试错；
- **错误更聚焦**：未知 tag 与选中分支内部错误被明确分开。

这不是“所有 union 都必须加 discriminator”。`int | None`、互不重叠的简单标量，或者 wire protocol 确实没有 tag 时，普通 union 仍合理。不要为了使用 discriminated union 凭空推断 tag；应先修订协议或在明确的边界适配层补足语义。

### 每个分支的 tag 必须是唯一 `Literal`

`Field(discriminator="event_type")` 要求各分支都存在该字段，且值是可唯一映射的 `Literal`。常见错误包括：

- 把 `event_type` 写成宽泛 `str`，Pydantic 无法建立 branch mapping；
- 两个分支复用同一个 tag，选择不再唯一；
- validator 在选择分支前偷偷把多个外部 tag 改成同一个值，使 schema 与运行时接受集合不一致；
- alias 只在一部分分支改变 discriminator 名称，导致生产者和 schema 工具看到不同协议。

tag 是协议字段，不是普通展示文案。它的拼写、类型、大小写和演进方式都应进入兼容测试。

## 数字 `schema_version`：`Literal` 不等于原始类型守卫

字符串事件 tag 不容易与别的 JSON primitive 相等；数字版本号则有 Python 的精确类型陷阱。下面的探针在本章环境中成立：

```python
version = TypeAdapter(Literal[1])

assert version.validate_python(1) == 1
assert version.validate_python(True) == 1   # True == 1
assert version.validate_python(1.0) == 1    # 1.0 == 1
```

因此 `schema_version: Literal[1]` 本身表达的是“允许的 literal 值”，不能替代 wire representation 政策。`isinstance(value, int)` 也不够，因为 `bool` 是 `int` 的子类。lab 在分支模型和 union 选择前都执行原始类型守卫，核心条件是：

```python
if type(value) is not int:
    raise ValueError("schema_version must be an integer")
```

版本 union 的关键结构是：

```python
_DiscriminatedOrderCreatedMessage = Annotated[
    OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2,
    Field(discriminator="schema_version"),
]

OrderCreatedMessage = Annotated[
    _DiscriminatedOrderCreatedMessage,
    BeforeValidator(_validate_discriminator_header),
]
```

`_validate_discriminator_header` 还有一个刻意的分支：输入 mapping 缺少 `schema_version` 时不自行抛 `ValueError`，而是把输入交给 Pydantic discriminator。于是错误保持为原生且稳定的：

```text
缺少 schema_version  -> type='union_tag_not_found', loc=()
schema_version=3      -> type='union_tag_invalid',   loc=()
schema_version=true   -> type='value_error',         loc=('schema_version',)
schema_version=2.0    -> type='value_error',         loc=('schema_version',)
```

这是三种不同故障：tag 缺失、tag 未知、tag 表示类型错误。不要用一个笼统的 before validator 把它们全部压成同一种自定义错误。若协议可选，字符串版本如 `"v1"`／`"v2"` 能避开数字相等陷阱；若现有协议已经使用整数，就保留 explicit raw-type guard。

## generic envelope：复用骨架，不隐藏版本语义

事件 envelope 的公共字段只定义一次：

```python
PayloadT = TypeVar("PayloadT")


class EventEnvelope(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: MessageId
    event_type: StrictStr
    schema_version: StrictInt
    occurred_at: AwareDatetime
    payload: PayloadT
```

generic 负责“payload 类型变化，envelope 骨架不变”。版本语义则由具体子类显式固定：

```python
class OrderCreatedEnvelopeV1(EventEnvelope[OrderCreatedV1]):
    event_type: Literal["order.created"]
    schema_version: Literal[1]


class OrderCreatedEnvelopeV2(EventEnvelope[OrderCreatedV2]):
    event_type: Literal["order.created"]
    schema_version: Literal[2]
```

不要写成 `EventEnvelope[OrderCreatedV1 | OrderCreatedV2]` 后再让 `payload` 自己猜版本，也不要让 generic 基类用 validator 推导 `schema_version`。那会把 envelope tag 与 payload 分支的对应关系藏进过程代码，JSON Schema 无法完整表达，错误路径也会变得含糊。

generic 的边界还包括：

- `EventEnvelope[T]` 复用结构，不代表所有 `T` 共享业务语义；
- 对外协议应暴露命名的 concrete specialization，便于生成独立 schema 和兼容测试；
- 不要依赖 `isinstance(event, EventEnvelope[OrderCreatedV2])` 做运行时分派；若确实需要类级识别，声明一个具体子类再判断；
- 版本 tag 仍属于 envelope，不能因为 payload 是 generic 就挪进领域对象。

## 版本演进：宽读旧版本，严写新版本

lab 采用不对称的 extra policy：

```python
class OrderCreatedV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    # order_id, customer_id, total


class OrderCreatedV2(OrderCreatedV1):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item_count: Annotated[StrictInt, Field(ge=1, le=100)]
```

V1 reader 的 `extra="ignore"` 让只理解 V1 公共字段的旧消费者可以读取带新增 `item_count` 的 payload；测试明确确认被忽略字段不会出现在 V1 模型中。V2 的 `extra="forbid"` 则保护当前 producer／consumer 契约：例如 `internal_note` 意外进入 V2 payload 时，版本 union 的错误路径是：

```python
(2, "payload", "internal_note")  # tag 2 + nested field path
```

这不是“所有旧模型都应该 ignore、所有新模型都应该 forbid”的普遍定律，而是一项明确的兼容策略：只在承诺 additive forward compatibility 的旧 reader 上放宽；当前写模型仍拒绝未审查字段，防止内部数据外泄和拼写错误静默通过。

版本增加时，把新版本作为新的 concrete envelope 加入 discriminator union。不要直接修改 V1 的字段含义，也不要让 V1／V2 共用同一 tag。移除旧分支前，需要先观察生产流量、回放历史消息并确认 retention window，而不是只看当前单元测试。

### 在边界把多版本输入收敛成应用命令

`OrderCreatedMessage` 是输入边界的 union，不应一路传进领域层。应用适配器应把各版本投影成当前 use case 所需的稳定命令：

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RecordOrderCreated:
    order_id: str
    customer_id: str
    total_amount: Decimal
    currency: str


def to_record_order_created(message: OrderCreatedMessage) -> RecordOrderCreated:
    payload = message.payload
    return RecordOrderCreated(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        total_amount=payload.total.amount,
        currency=payload.total.currency,
    )
```

这个 use case 只需要两版共有的业务事实，因此不携带 V2 的 `item_count`。若另一个用例确实需要该字段，应在版本适配器中明确决定 V1 缺失时是拒绝、使用可证明的默认语义，还是走独立补全流程；不要把 `OrderCreatedV1 | OrderCreatedV2` 变成领域服务的参数，让每个业务函数重复版本判断。

## `RootModel`：当整个文档就是一个容器

假设批量入口的 JSON 根节点就是订单事件数组，没有 wrapper object。此时 `RootModel[list[OrderCreatedMessage]]` 精确描述 wire shape：

```python
import json

from pydantic import RootModel

from order_contracts.events.envelope import (
    OrderCreatedEnvelopeV1,
    OrderCreatedEnvelopeV2,
    OrderCreatedMessage,
)


class OrderCreatedBatch(RootModel[list[OrderCreatedMessage]]):
    pass


raw = json.dumps(
    [
        {
            "event_id": "msg_111111111111",
            "event_type": "order.created",
            "schema_version": 1,
            "occurred_at": "2026-07-15T12:30:00Z",
            "payload": {
                "order_id": "ord_111111111111",
                "customer_id": "cus_aaaaaaaaaaaa",
                "total": {"amount": "12.30", "currency": "USD"},
            },
        },
        {
            "event_id": "msg_222222222222",
            "event_type": "order.created",
            "schema_version": 2,
            "occurred_at": "2026-07-15T12:31:00Z",
            "payload": {
                "order_id": "ord_222222222222",
                "customer_id": "cus_bbbbbbbbbbbb",
                "total": {"amount": "24.60", "currency": "USD"},
                "item_count": 2,
            },
        },
    ]
).encode()

batch = OrderCreatedBatch.model_validate_json(raw)
assert isinstance(batch.root[0], OrderCreatedEnvelopeV1)
assert isinstance(batch.root[1], OrderCreatedEnvelopeV2)
assert batch.root[1].payload.item_count == 2
```

若第 0 个元素的 V2 `item_count` 为 `0`，本 lab 环境的错误为：

```text
type = 'greater_than_equal'
loc  = (0, 2, 'payload', 'item_count')
```

`0` 是 list index，`2` 是 `schema_version` tag。容器索引、union tag 和 nested field 都会进入同一条路径。

`RootModel` 适合**根节点就是该类型**的协议；它不是“所有批量请求”的默认答案。一旦需要 batch metadata，普通 field model 更清楚：

```python
class OrderCreatedBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: StrictStr
    source: StrictStr
    items: list[OrderCreatedMessage] = Field(min_length=1, max_length=500)
```

此时 `batch_id`、来源、幂等键、分页游标或校验模式都是协议的一部分，不应塞进 `RootModel.root` 元素，也不应依赖 HTTP header 暗中补齐后再声称模型代表完整文档。

## `TypeAdapter`：给模型之外的类型一个可复用入口

`BaseModel` 提供字段名、配置、方法和命名 schema；但 union、list 和 `TypedDict` 本身未必值得包一层模型。`TypeAdapter` 可以直接为任意 Pydantic-supported type 编译 core schema：

```python
from pydantic import TypeAdapter

from order_contracts.inbound.payment_webhook import PaymentPayload


PAYMENT_BATCH_ADAPTER = TypeAdapter(list[PaymentPayload])


def parse_payment_payloads(raw: bytes) -> list[PaymentPayload]:
    return PAYMENT_BATCH_ADAPTER.validate_json(raw)
```

现有事件入口遵循同一模式：

```python
ORDER_CREATED_ADAPTER = TypeAdapter(OrderCreatedMessage)


def parse_order_created(raw: bytes) -> OrderCreatedMessage:
    return ORDER_CREATED_ADAPTER.validate_json(raw)
```

adapter 应在 module／service 生命周期内复用，不要在每条消息、每次循环中重新 `TypeAdapter(...)`。构造 adapter 需要解析 annotation 并建立 validator／serializer；把它提升为模块常量同时统一了入口参数、strict 政策和 schema 来源。

适合 `TypeAdapter` 的边界包括：

- discriminated union：`TypeAdapter(PaymentPayload)`；
- 容器：`TypeAdapter(list[PaymentPayload])`；
- `TypedDict`：只需要 dict 结果和静态键约束，不需要模型行为时；
- 标准／Pydantic dataclass 或可支持的 `Annotated` alias。

需要命名字段、model-level validator、私有属性或清晰领域方法时，仍应选择 `BaseModel`。需要顶层容器的命名类型和 `.root` 语义时，选择 `RootModel`。`TypeAdapter` 是验证入口，不是领域对象的替代品。

## 递归模型：只有数据真的递归时才使用

递归模型适合树或图形输入，例如规则组包含子规则组：

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class EventGroup(BaseModel):
    name: str
    children: list[EventGroup] = Field(default_factory=list)
```

像这种同类 self-reference，Pydantic v2 通常能自动解析。`model_rebuild()` 主要用于 schema 初次构建时引用的类型还不可用，例如互相引用的模型在稍后定义、跨模块 forward reference，或动态补齐类型 namespace：

```python
class RetryEdge(BaseModel):
    target: "RetryNode"


class RetryNode(BaseModel):
    event_id: str
    outgoing: list[RetryEdge] = Field(default_factory=list)


# 所有引用类型均已定义后再显式重建。
RetryEdge.model_rebuild()
```

若模型已经完整，机械地到处调用 `model_rebuild()` 没有收益，还可能掩盖 import cycle 和模块职责问题。订单创建消息、支付成功／失败事件都是有限层级的 envelope → payload → value object；不要为了展示高级 API 把它们改造成递归节点。递归还会引入深度、cycle detection、错误体积和拒绝服务风险，必须由真实协议需求证明合理。

## JSON Schema：discriminator 也必须出现在机器契约中

runtime 能正确选择分支还不够，OpenAPI、代码生成器和 schema registry 也需要知道 tag mapping：

```python
payment_schema = TypeAdapter(PaymentPayload).json_schema()

assert payment_schema["discriminator"] == {
    "propertyName": "event_type",
    "mapping": {
        "payment.failed": "#/$defs/PaymentFailed",
        "payment.succeeded": "#/$defs/PaymentSucceeded",
    },
}

version_schema = ORDER_CREATED_ADAPTER.json_schema()
assert version_schema["discriminator"]["propertyName"] == "schema_version"
assert set(version_schema["discriminator"]["mapping"]) == {"1", "2"}
```

JSON object key 必须是字符串，所以数值 tag 的 mapping key 在 schema 中是 `"1"`／`"2"`；运行时 wire value 仍是 JSON number `1`／`2`。这一区别值得在目标 OpenAPI／client generator 上做生成测试，不能假设所有工具都同样支持 numeric discriminator。

schema 生成应复用生产使用的 alias／adapter，并以 reviewed artifact 做兼容 diff。不要为了文档另造一个近似 union；否则 runtime 接受集合和发布出去的 discriminator mapping 会漂移。本章只讨论组合如何进入 schema，不展开 serialization alias、dump mode 和 round-trip，它们属于序列化章节。

## 大批次：验证成功不等于可以无界加载

无论使用 `RootModel[list[T]]` 还是 `TypeAdapter(list[T])`，`validate_json()` 面对的是完整 JSON 文档。Pydantic 不会因为 annotation 是 list 就自动把一个巨大 JSON array 变成流式、常量内存解析。

大批次至少有三类风险：

- **内存**：raw bytes、解析中的 Python 对象、成功模型和错误信息可能同时存活；
- **错误聚合**：大量坏元素会生成大量 `errors()` 项，日志或响应体可能比输入还难控制；
- **尾延迟**：必须处理前面大量元素，调用方才看到后部错误；一次重试又重复整批工作。

优先让消息系统保持“一条消息一个事件”，逐条调用已复用的 `ORDER_CREATED_ADAPTER`，并按消息独立 ack／dead-letter。若外部协议只能批量传输，使用有界 chunk：

```python
from collections.abc import Iterable, Iterator


ORDER_CREATED_CHUNK_ADAPTER = TypeAdapter(list[OrderCreatedMessage])
MAX_CHUNK_SIZE = 200


def validate_chunks(chunks: Iterable[list[object]]) -> Iterator[OrderCreatedMessage]:
    for raw_chunk in chunks:
        if len(raw_chunk) > MAX_CHUNK_SIZE:
            raise ValueError("chunk exceeds configured limit")
        yield from ORDER_CREATED_CHUNK_ADAPTER.validate_python(raw_chunk)
```

这里“流式”的前提是上游 parser／协议已经给出独立 chunk；这段代码没有把一个巨大 JSON array 自动流式拆开。生产策略还应限制 HTTP body／MQ message bytes、元素数、单元素尺寸、错误返回数和处理 deadline。需要 partial success 时，必须显式定义每项结果、顺序、幂等与重试语义，不能只捕获一次整批 `ValidationError` 后猜哪些项成功。

## Java 与 Go 对照：同一协议，不同运行时成本

### Java：sealed hierarchy + Jackson 显式类型信息

Java 可以用 sealed interface 表达封闭分支，再让 Jackson 按现有字段分派：

```java
@JsonTypeInfo(
    use = JsonTypeInfo.Id.NAME,
    include = JsonTypeInfo.As.EXISTING_PROPERTY,
    property = "event_type",
    visible = true
)
@JsonSubTypes({
    @JsonSubTypes.Type(value = PaymentSucceeded.class, name = "payment.succeeded"),
    @JsonSubTypes.Type(value = PaymentFailed.class, name = "payment.failed")
})
sealed interface PaymentPayload
    permits PaymentSucceeded, PaymentFailed {}
```

`sealed` 给编译器封闭继承层级，`@JsonTypeInfo`／`@JsonSubTypes` 给 Jackson runtime tag mapping；两者职责不同。`visible = true` 是否需要取决于 record/class 是否还要绑定 `event_type` 字段，必须与 wire model 测试一致。

Java 泛型会类型擦除，反序列化 `EventEnvelope<OrderCreatedV2>` 时不能只传 `EventEnvelope.class`，否则 payload 常退化为未定型 map。Jackson 通常需要 `new TypeReference<EventEnvelope<OrderCreatedV2>>() {}` 或显式 `JavaType` 保留参数信息。Pydantic 的 `EventEnvelope[OrderCreatedV2]` 会在 runtime 建立参数化 schema，但仍应通过命名版本子类固定 discriminator 语义。

### Go：envelope + `json.RawMessage` + 手工 switch

Go 没有直接等价的 sealed tagged union。常见做法先解析 envelope header，把 payload 暂存为 `json.RawMessage`，再手工分派：

```go
type RawEnvelope struct {
    EventType    string          `json:"event_type"`
    SchemaVersion int            `json:"schema_version"`
    Payload      json.RawMessage `json:"payload"`
}

switch env.EventType {
case "payment.succeeded":
    var payload PaymentSucceeded
    err = json.Unmarshal(env.Payload, &payload)
case "payment.failed":
    var payload PaymentFailed
    err = json.Unmarshal(env.Payload, &payload)
default:
    err = fmt.Errorf("unknown event_type %q", env.EventType)
}
```

版本事件还要对 `SchemaVersion` 做第二层明确 switch。这个方案直观，但 branch completeness、unknown-field policy、数字精确类型、错误路径和 schema mapping 都要自行实现并测试。Pydantic discriminated union 把 mapping 与验证 schema 组合起来；它减少样板，不会替团队决定 tag、版本兼容或应用命令边界。

## 选型树与审查清单

```text
wire 根节点是 JSON object？
├─ 是：它有命名字段／metadata？ → BaseModel + nested model
│   └─ 某字段存在多个对象分支？
│       ├─ 有稳定且唯一 tag → Annotated[A | B, Field(discriminator=...)]
│       └─ 无 tag → 普通 union；审查重叠、选择策略与错误体积
└─ 否：根节点本身是 list／scalar／mapping？
    ├─ 需要命名类型、方法或 root schema → RootModel[T]
    └─ 只需验证／dump／JSON Schema → 复用 TypeAdapter(T)

多个 payload 共享 envelope 骨架？ → EventEnvelope[PayloadT]
协议版本不同？ → 每版 concrete subclass 固定 Literal tag
数据结构真的自相似？ → recursive model；未解析 forward ref 才 model_rebuild()
批次可能很大？ → 单消息或有界 chunk，不把 list validation 称为自动流式解析
```

提交组合模型前，再逐项确认：

- tag 名称、值与类型是否写入协议并由 `Literal` 固定；
- 数字 discriminator 是否在选择分支前检查原始 exact type；
- tag missing、unknown、wrong-type 是否保留为可区分的错误；
- nested `loc` 是否包含 container index、union tag 与字段路径；
- generic 是否只复用结构，版本语义是否仍在 concrete envelope；
- V1 `ignore`／V2 `forbid` 是否是经过测试的兼容决定；
- 多版本输入是否已在边界映射成稳定应用命令；
- adapter 是否复用，schema 是否来自同一个生产类型；
- body size、chunk size、错误数和 deadline 是否有界；
- 是否把非递归订单结构误建成递归图。

核心原则可以压缩成一句话：**组合应让输入的分支选择更可判定、错误位置更精确、版本边界更集中；如果抽象让领域层看到更多 union、让错误更嘈杂或让批次变得无界，它就没有真正降低复杂度。**
