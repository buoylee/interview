# 13 · 集成矩阵与 V1 → V2 迁移：让 adapter 薄，让行为证据厚

> **本章目标**：能为 FastAPI、消息队列、ORM 和 LLM structured output 划清 transport／contract／application 责任，并把 Pydantic V1 → V2 从“方法改名”升级为有 golden、有集成测试、有灰度和回滚的行为迁移。可执行事实来自 [FastAPI adapter](lab/examples/fastapi_adapter.py)、[event example](lab/examples/consume_event.py)、[`adapters.py`](lab/src/order_contracts/adapters.py)、[ORM integration test](lab/tests/test_integrations.py)、[event compatibility tests](lab/tests/test_event_compatibility.py) 与 [failure classifier tests](lab/tests/test_errors.py)；迁移语义对照当前 [官方 Migration Guide](https://docs.pydantic.dev/latest/migration/)。

先运行本章证据：

```bash
cd python-pydantic/lab
uv run pytest \
  tests/test_examples.py \
  tests/test_integrations.py \
  tests/test_event_compatibility.py \
  tests/test_errors.py -v
```

当前实际收集并通过 35 个测试。它们证明 route/OpenAPI、安全错误、event bytes、V1/V2 envelope、失败分类、显式 event projection 和 plain attribute object 能工作；它们不声称启动了真实 HTTP server、broker、database 或外部生成服务。

## 事故开场：把 framework object 一路传进 domain

团队最初觉得 adapter 只是“胶水”，于是把 HTTP request model 直接交给 domain，把 broker message object 存进 application command，再把 ORM entity 直接作为 response。短期少了几行 mapping；随后三类变化互相传染：

- HTTP 字段 rename 迫使 domain 改名；
- broker retry metadata 意外进入 event schema；
- database 新增内部列后，通用序列化把它发给客户。

薄 adapter 不是“没有 adapter”，而是**只承担边界翻译且所有权清楚**：

```text
transport owns bytes / headers / status / ack / session
                 ↓
contract owns accepted shape / types / errors / wire schema
                 ↓ explicit mapper
application/domain owns use-case intent / invariants
                 ↓ explicit projection
outbound contract owns recipient-specific whitelist
                 ↓
transport sends response / bytes / ack decision
```

Pydantic 位于 contract 与 projection 层。它不拥有认证、消息交付、事务、truthfulness 或 deployment。

## 集成矩阵：每层做什么，也写清不做什么

| 边界 | transport/framework 拥有 | Pydantic contract 拥有 | adapter／application 拥有 | 明确非目标 |
|---|---|---|---|---|
| FastAPI | HTTP body/query、status、OpenAPI wiring | request validation、response schema/serialization | request → command、domain call、domain → view | 身份认证、部署、server tuning |
| Kafka／RocketMQ | bytes、topic/queue metadata、offset/message id、ack/retry API | event bytes → typed versioned envelope | failure classification → delivery policy | broker connection、exactly-once、consumer group 管理 |
| ORM | row/entity attribute access | declared attribute projection | repository query、domain mapping | lazy-load、session、transaction、N+1 |
| LLM structured output | request/response transport、raw generated data | JSON Schema、raw output validation | retry/fallback/use-case decision | truth verification、authorization、业务不变量替代 |

矩阵中的“非目标”不是说它们不重要，而是防止把 transport correctness 误归功于 Pydantic model。

## FastAPI：request、mapper、domain、response whitelist 四段

[FastAPI example](lab/examples/fastapi_adapter.py) 的完整 route 是：

```python
@app.post(
    "/orders",
    response_model=CustomerOrderView,
    responses={422: {"model": ErrorResponse}},
)
def create_order(payload: CreateOrderRequest) -> CustomerOrderView:
    command = to_create_order_command(payload)
    order = Order.create("ord_0123456789ab", command)
    return project_customer_order(order)
```

四行对应四个 owner，不能压成 `Order(**payload.model_dump())`：

### 1. Request validation

framework 根据 `CreateOrderRequest` 解析 body。该模型负责 strict quantity、Money、unknown field、items 长度和 duplicate SKU 等输入契约。失败时 example 的 `RequestValidationError` handler 只投影安全 `reason/path`，对 attacker-controlled extra field name 还替换为 `<extra>`；不把 raw input/msg 直接回显。

### 2. Application mapping

`to_create_order_command(payload)` 逐字段构造普通 frozen dataclass：

```text
CreateOrderRequest
  └─ to_create_order_command
       └─ CreateOrderCommand + tuple[CreateOrderLine, ...]
```

mapper 明确允许 `customer_id`、`idempotency_key`、SKU、quantity、amount、currency 进入 use case。未来 request 增加 marketing metadata，不会自动进入 domain；domain command 改 representation，也只影响 mapper。

### 3. Domain operation

`Order.create(...)` 检查同币种不变量并创建领域对象。Pydantic 已确认 shape，不代表业务动作必然允许：库存、幂等冲突、账户状态等仍属于 application/domain collaboration。

### 4. Response whitelist

`project_customer_order(order)` 只构造 `CustomerOrderView` 的四个字段：order id、status、total、item count。`response_model=CustomerOrderView` 让 OpenAPI 和 response validation/serialization 对齐，但不能替代显式 projection；如果先返回一个过宽内部对象再期望 framework 永远替你隐藏字段，权限政策会藏在 annotation 偶然行为中。

[`test_fastapi_adapter_registers_route_and_function_is_callable`](lab/tests/test_examples.py) 直接调用 route function，证明 mapper/domain/view 链路；[`test_fastapi_openapi_declares_contract_response_schema`](lab/tests/test_examples.py) 锁 200/422 schema；两个 handler tests 锁错误不泄漏。它们仍是 in-process integration tests，不覆盖真实 network stack。

### HTTP adapter 的审查问题

- request model 是否只描述外部输入，而非 domain entity？
- mapper 是否逐字段，还是 `**model_dump()` mass assignment？
- route 返回值是否已经是 recipient-specific view？
- error handler 是否只输出稳定 code/path，清洗可控字段名？
- framework 升级后 OpenAPI response schema 与 status 是否仍受测试保护？

本节到此为止；认证、部署和 server lifecycle 是独立主题，不借 Pydantic 集成章节展开。

## Kafka／RocketMQ：交付与解析是两条责任线

一个 consumer adapter 至少面对两种输入：

```text
transport payload: raw bytes
transport metadata: topic/queue, partition/offset or message id, retry count, timestamp
```

metadata 用于 trace、delivery、dedup 和 observability，不应为了“统一对象”塞进 `OrderCreatedEnvelope`。只有 producer/consumer 协议明确把某字段写入 payload bytes，它才属于 event contract。

### client 层只提供 bytes／metadata／ack capability

Kafka 或 RocketMQ client 的职责是：

1. 拉取／接收 raw bytes 与 transport metadata；
2. 在 application 给出结果后执行 ack、retry、park 或 publish-to-DLQ 等平台动作；
3. 管理 connection、consumer group、offset／message id 和 backpressure。

Pydantic model 不调用 ack，也不知道 partition、rebalance 或 visibility timeout。为保持 lab 可运行，本章不安装任何 broker SDK。

### `parse_order_created()` 只拥有 event contract

[`parse_order_created()`](lab/src/order_contracts/events/envelope.py) 极薄：

```python
ORDER_CREATED_ADAPTER = TypeAdapter(OrderCreatedMessage)


def parse_order_created(raw: bytes) -> OrderCreatedMessage:
    return ORDER_CREATED_ADAPTER.validate_json(raw)
```

cached `TypeAdapter` 根据 `schema_version` discriminator 选择 V1/V2 envelope，要求 aware datetime、strict integer version、准确 payload，并返回 typed object。它既不读 transport metadata，也不决定失败后是否重投。

[event example](lab/examples/consume_event.py) 把 JSON 编成 bytes 后调用 parser；compatibility tests 证明：

- version 1/2 选择正确 subtype；
- missing/unknown discriminator 产生 native union error；
- bool/float version 在 discriminator 前被拒绝；
- V2 producer unknown payload field 被拒绝；
- domain → V2 event 是显式 projection，canonical JSON shape 固定。

### `classify_consume_failure()` 只是示例政策

[`classify_consume_failure()`](lab/src/order_contracts/errors.py) 将示例异常分三类：

| kind | lab 条件 | transport 层可能采用的政策 |
|---|---|---|
| `INCOMPATIBLE` | unknown/missing version，协议 header literal 不匹配 | park／DLQ／告警；是否 ack 由平台 runbook 决定 |
| `PERMANENT` | 其他 `ValidationError`，输入在当前契约下永久非法 | park／DLQ／ack-drop，必须有审计与重放政策 |
| `TRANSIENT` | `TimeoutError`／`ConnectionError` | retry/nack；设置退避、上限与 poison-message 防护 |

未知 `TypeError`、`KeyError`、`AssertionError` 被重新抛出，因为它们更像 consumer bug；不能伪装成坏消息后 ack 掉。tests 精确锁住这点。

表中右列只是可能动作，不是 lab 自动行为。`classify_consume_failure()` 没有 broker SDK、没有 side effect，也不知道平台 ack 语义。真实 adapter 必须把 kind 映射到本系统的 delivery policy，并测试：ack 时机、retry limit、DLQ payload/redaction、crash/rebalance 与 idempotency。Pydantic validation 不能提供 exactly-once。

### 一个 transport-neutral orchestration skeleton

```python
def handle_message(raw: bytes, metadata: MessageMetadata) -> ConsumeResult:
    try:
        event = parse_order_created(raw)
        apply_order_created(event, metadata)
        return ConsumeResult.success()
    except Exception as error:
        kind = classify_consume_failure(error)
        return ConsumeResult.failure(kind=kind)
```

这里 `MessageMetadata`／`ConsumeResult` 是 application-owned ports，不是 event schema 或 broker object。transport adapter 根据 result 执行具体 ack；application service 负责幂等和领域操作。示意代码故意没有吞掉 classifier 重新抛出的 programmer error。

## ORM：`from_attributes` 只是一种读取模式

[`tests/test_integrations.py`](lab/tests/test_integrations.py) 没有 database 依赖，而是用普通 Python object 锁住最小语义：

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


row = OrderRow("ord_0123456789ab", "pending_payment")
view = OrderAttributeView.model_validate(row)

assert view.model_dump() == {
    "order_id": "ord_0123456789ab",
    "status": "pending_payment",
}
```

`from_attributes=True` 告诉 `model_validate()` 从 object attributes 获取已声明字段，而不是要求 input 是 mapping。它适合小型 read projection，也可以接收 dataclass／framework row-like object。

它**不**负责：

- 建立或关闭 session；
- 开启、提交或回滚 transaction；
- 判断 attribute 是否触发 lazy-load；
- 预加载 relation 或消除 N+1；
- 处理 detached/expired entity；
- 实现 repository query、identity map 或 persistence mapping。

事实上，读取 property/descriptor 可能执行任意代码或 I/O；Pydantic 不知道代价。repository 应先决定 query shape 和加载策略，再把一个可安全读取的 row/projection 交给 contract。对 customer response 仍推荐显式 mapper：attribute projection 不能从数据库对象推导 authorization。

这个 plain-object test 的价值是隔离 Pydantic 语义：若测试需要真实 session 才能证明 `from_attributes`，就难以区分 library binding regression 与 database integration failure。另建 repository integration test 覆盖真实 query/transaction，不让两者互相替代。

## LLM structured output：schema 可复用，信任不能复用

已有 input contract 可以提供两件事：

```python
schema = CreateOrderRequest.model_json_schema()

# raw_text 是外部系统返回的 JSON 文本
request = CreateOrderRequest.model_validate_json(raw_text)

# 若边界层已显式解码为 Python object
request = CreateOrderRequest.model_validate(decoded_value)
```

`model_json_schema()` 可把 fields、required、nested shape、pattern、range 等机器可表达约束交给 structured-output mechanism；`model_validate*()` 则在本地执行最终验证。两者复用与 HTTP 相同的 reviewed contract，避免另写一套容易漂移的 schema。

但生成结果仍是不可信外部输入：

- 可能不是合法 JSON，或不符合 schema；
- 可能通过结构校验却捏造 customer/order/SKU 事实；
- 可能包含语义上危险但 type 正确的文本；
- 可能重放旧数据、越权引用资源或违反领域不变量；
- schema 不能替代 payload size、timeout、rate limit、authorization 和 domain check。

因此边界顺序仍是：限制 raw size → parse/validate → 显式 mapper → application/domain check → recipient-specific output。validation error 应按自己的安全错误政策分类，不把 raw generated text 直接写日志。

本章只复用 JSON Schema 与 validation 这两个标准能力，不增加任何 LLM integration dependency。不同生成后端如何接收 schema、是否严格约束、失败是否重试，属于外层 adapter；不能把某个后端的“结构化”承诺提升为本地 trusted data。

## V1 → V2：API 改名表只是第一层

### BaseModel 公共 API 地图

| Pydantic V1 | Pydantic V2 | 迁移审计点 |
|---|---|---|
| `Model.parse_obj(data)` | `Model.model_validate(data)` | coercion、strictness、input subtype、error shape |
| `Model.parse_raw(raw)` | JSON 用 `Model.model_validate_json(raw)`；其他格式显式 decode 后 `model_validate()` | 不再把文件/编码/反序列化隐含在 model |
| `model.dict(...)` | `model.model_dump(...)` | mode、alias、exclude unset/default/none、subclass fields |
| `model.json(...)` | `model.model_dump_json(...)` | JSON 更紧凑；旧 `indent`／encoder 参数不能机械照搬 |
| `Model.schema(...)` | `Model.model_json_schema(...)` | validation/serialization mode、definitions、golden artifact |
| `model.copy(...)` | `model.model_copy(...)` | shallow/deep；`update` 仍应按 trusted data 审计 |
| `Model.construct(...)` | `Model.model_construct(...)` | 跳过 validation，不是普通 constructor 或万能优化 |
| `Model.from_orm(obj)` | `Model.model_validate(obj)` + `ConfigDict(from_attributes=True)` | attribute I/O 与 repository 责任不变 |
| `parse_obj_as(T, data)` | `TypeAdapter(T).validate_python(data)` | adapter/schema 应复用，不在 hot loop 重建 |
| `schema_of(T)` | `TypeAdapter(T).json_schema()` | bare type schema 也要 golden/review |
| `update_forward_refs()` | `model_rebuild()` | recursive/generic model 的 rebuild 时机 |

deprecated alias 暂时还能运行，不代表迁移完成。把 warning 关掉只会延后风险；应让 CI 把目标 deprecation warnings 升级为可见失败，并逐包消除。

### `parse_raw` 的关键 caveat

`parse_raw` 不应无条件文本替换为 `model_validate_json`。只有输入确实是 JSON bytes/string 时语义对应；旧代码若依赖 pickle、custom content type、file loading 或额外 decoder，必须把这层 I/O/decoding 移到 adapter，再调用 `model_validate()`。这正是 transport 与 contract 分离。

### dump 不是只换方法名

迁移时逐个记录 call site：

- 是 Python-mode dict 还是 wire JSON？
- 是否按 alias 输出？
- unset/default/None 是否需要排除？
- old `.json()` 是否依赖空格、Unicode、key stringification 或 custom encoder？
- 结果用于 response、event、cache key、signature 还是 log？

尤其签名与 cache key 不能只比较“decode 后对象相等”；bytes、separator、key order 和 Unicode policy 都可能破坏兼容。

## Validator migration：签名、顺序、default、异常都要测

### decorator 对照

| V1 | V2 | 注意 |
|---|---|---|
| `@validator("x")` | `@field_validator("x", mode="after")` | V2 default 也是 after，但已校验 value 与签名需审查 |
| `@validator("x", pre=True)` | `@field_validator("x", mode="before")` | before 收 raw input，返回值继续进入 field schema |
| `@validator("x", each_item=True)` | `Annotated` container item constraint/validator | 约束应标在 type argument，不是 container field 外层 |
| `@validator(..., always=True)` | `Field(validate_default=True)` + 合适 validator | built-in type validation 也会作用于 default，写 missing/default tests |
| `@root_validator(pre=True)` | `@model_validator(mode="before")` | 通常接 raw object；不要假设永远是 dict |
| `@root_validator` | `@model_validator(mode="after")` | 常见签名是 instance method，返回 `Self` |

V1 validator 的 `field`／`config` 参数不能照搬。V2 需要时接 `ValidationInfo`，从 `info.config` 和 `cls.model_fields[info.field_name]` 获取公开信息。不要把旧 quasi-internal object 模拟出来。

### ordering 回归

validator 顺序会直接改变 normalize 与拒绝：trim 在 regex 前还是后、default 是否先出现、model-before 是否改 discriminator、field validator 是否读取已验证的 earlier field。迁移时为每条链画出 raw → before → core → after，并测试：

- 同一 input 的 canonical value；
- 同时有多个非法点时的 error type/loc；
- field declaration order 变化后，`ValidationInfo.data` 是否仍满足假设；
- `Annotated` metadata 与 decorator 混用时的顺序；
- assignment validation 若启用，model validator 收到 dict 还是 instance。

lab 的 `schema_version` 是典型 regression：before validation 必须在 discriminator selection 前拒绝 `True`／`1.0`／`2.0`，否则 `Literal[1]`/`Literal[2]` 可能接受非 raw integer。compatibility tests 同时覆盖 union adapter 与 concrete envelope。

### default 回归

BaseModel field default 通常不会自动走完整 validation，除非启用 `validate_default`。V1 `always=True` 的迁移也可能让 annotated type 的标准 validators 对 default 生效。至少测试三种输入：missing、显式 default value、显式 `None`；Optional、nullable 和 default 是不同维度。

Settings 的 defaults 又默认受 validation，不能把 BaseModel 经验无条件复制过去。迁移 golden 要按模型类别分组。

### `TypeError` 是程序错误信号

V1 中 validator 内 `TypeError` 可能被包装成 `ValidationError`；V2 不再包装，会原样向外传播。这能避免错误签名/错误函数调用被当成用户 4xx，但会改变 exception handler 和 consumer ack 路径。

用 `ValueError` 或稳定 custom validation error 表示输入非法；`TypeError` 保留给实现 bug。迁移测试应故意触发一条 validator programmer error，确认 HTTP 层走 5xx/alert、consumer classifier 重新抛出，而不是把它标为 permanent bad message。lab 的 classifier tests 已锁住 `TypeError` 传播。

## Config、root 与 generic migration

### config 对照

| V1 | V2 | 行为审计 |
|---|---|---|
| inner `class Config` | `model_config = ConfigDict(...)` | inheritance/multiple inheritance merge，不只语法 |
| `orm_mode = True` | `from_attributes=True` | 只改变 attribute lookup；不接管 repository |
| `allow_mutation=False` | `frozen=True` | 仍是浅层 faux immutability |
| `allow_population_by_field_name` | `populate_by_name`／新版本可用更细的 name/alias validation flags | 输入兼容矩阵与版本 pin |
| `schema_extra` | `json_schema_extra` | generated artifact diff |
| `validate_all` | `validate_default` | missing/default 行为 |
| `anystr_strip_whitespace` | `str_strip_whitespace` | normalize 与 schema/test |
| `regex=` | `pattern=` | Python regex 与 JSON Schema consumer parity |
| `min_items`／`max_items` | `min_length`／`max_length` | list/string/container 目标类型 |

removed config（例如 fields-based mutation、custom JSON loaders/dumpers）不能靠名称替换复活；使用 `Annotated`、validator/serializer 或 transport adapter 重新表达，并为新 owner 写测试。

### `__root__` → `RootModel`

V1 的 custom root field：

```python
class OrderIds(BaseModel):
    __root__: list[str]
```

V2 应显式写：

```python
class OrderIds(RootModel[list[str]]):
    pass
```

调用方从 `.__root__` 迁到 `.root`，schema title/root shape、dump 与 validation entrypoint 都要更新。`RootModel` 表示整个文档就是 array/scalar/mapping；如果还需要 batch id、cursor 或 source metadata，应回到普通 field model，不要硬塞隐藏字段。

### generic 不再需要 `GenericModel`

V2 直接组合 `BaseModel` 与 `Generic[T]`：

```python
class EventEnvelope(BaseModel, Generic[PayloadT]):
    payload: PayloadT
```

lab 的 `EventEnvelope[PayloadT]` 就是这种形状。不要混用 V1/V2 model type parameter；也避免 `isinstance(value, Envelope[Payload])` 这类 parametrized generic check。若确需 runtime check，建立命名 concrete subclass。

## Serialization migration：默认变安全，也可能破坏旧输出

V1 recursive dump 通常按 runtime subclass 包含新增字段。V2 默认按 parent field 的**注解类型**序列化 nested model，因此 annotation 是 `CustomerOrderView` 时，即使 runtime value 是 `InternalOrderView`，也只输出 base fields。

这项变化能阻止未来 subclass secret/internal field 自动外泄，也是 breaking change。[官方 serialization 文档](https://docs.pydantic.dev/latest/concepts/serialization/#serializing-subclasses) 与 lab 都展示了 opt-in widening。

lab 的 regression 形状：

```python
internal = InternalOrderView(
    order_id="ord_0123456789ab",
    status="pending_payment",
    total={"amount": "12.30", "currency": "USD"},
    item_count=1,
    customer_id="cus_0123456789ab",
    provider_reference="pay_ABC12345",
    internal_note="fraud review",
)
envelope = CustomerOrderEnvelope(order=internal)

safe = envelope.model_dump(mode="json")
```

`safe["order"]` 没有 customer id、payment reference 或 internal note。若调用 `serialize_as_any=True`，runtime subclass fields 会重新出现，接近 V1 行为。

迁移时不能全局打开 `serialize_as_any` 只为“让 snapshot 变绿”。逐 call site 分类：

- public response/error/log：保持 annotated-type whitelist，新增 negative leak assertions；
- internal protocol 确实承诺 subtype fields：声明清晰 union／具体类型，或局部审查 widening；
- legacy consumer 依赖 runtime subclass：把它当协议 migration，先定义 explicit output model 与版本，而非恢复隐式 recursive dump。

同时审计 V1 `json_encoders`、custom `.json()` kwargs、computed output、alias 和 Decimal/datetime bytes。机械 API replacement 无法证明 wire compatibility。

## 分阶段迁移流程

### Phase 0：锁版本与 inventory

- pin 当前 Pydantic、framework 和相关 plugins；记录 Python version；
- 扫描旧 method/decorator/config/root/generic/custom type/serializer；
- 为每个 call site 标注边界：HTTP、event、settings、ORM projection、internal-only；
- 禁止升级与业务字段大改同时进入同一 diff。

### Phase 1：建立 V1 行为证据

在旧 runtime 先锁：

- coercion matrix：string/int/bool/float/None、边界值、unknown fields；
- error golden：关键 `type`/`loc` 和自己的安全 error projection，不锁整句 message；
- serialization golden：canonical response/event JSON、alias/unset/default/None、敏感字段 absence；
- JSON Schema artifact 与 producer/consumer compatibility；
- validator call/default/ordering 和 TypeError regression；
- framework route/OpenAPI、event bytes/classifier、ORM plain-object integration tests。

没有旧行为证据，就无法区分“有意采用 V2 政策”与“迁移误改”。

### Phase 2：机械 API 替换

按表替换 `parse_obj`／`dict`／`json` 等公开 API，迁移 decorator 名和 `ConfigDict` 位置，先保持业务规则不变。自动转换工具可以减少拼写劳动，但输出必须 review；deprecation warning 归零只是这一阶段完成。

### Phase 3：行为审计

逐项处理测试 diff：

- coercion 变化是收紧、放宽还是 bug？
- errors 是否改变公开 code/path 或 delivery classification？
- validator signature/order/default 是否仍表达原规则？
- `TypeError` 是否正确成为 5xx/programmer failure？
- `from_attributes` 是否在已加载 projection 上使用？
- nested subclass output 是否保持 whitelist；哪里真的需要 `serialize_as_any`？
- RootModel/generic/schema/wire output 是否兼容 consumer？

每个差异写决策，不通过批量更新 golden 掩盖。

### Phase 4：framework integration gate

至少跑与 lab 同类的 integration：route 可调用、OpenAPI response schema、错误清洗、event raw bytes、unknown version classification、canonical producer JSON、plain attribute object。真实系统再加 broker delivery、repository/transaction 和 deployed HTTP smoke；contract unit test 不能替代这些。

### Phase 5：分阶段上线

- 先 canary/低风险 worker，比较 validation rejection、error kind、response/event shape 和 5xx；
- 对 old/new consumer 做 compatibility matrix，producer 最后切 writer；
- 保留明确 rollback artifact，不在 rollback 时混回半套 V1/V2 model graph；
- 扩容前观察一段完整业务周期，确认 cold paths/defaults 也被触发；
- rollout 完成后删除 compatibility shim 与 deprecated imports，更新 golden ownership。

短期可用 `pydantic.v1` namespace 隔离尚未迁移的 package，但它是迁移脚手架，不是永久双栈。跨边界传 plain data／own DTO，不把 V1 model 嵌进 V2 generic/model 或反向混合。

## Java 与 Go：只比较 adapter ownership

### Java

HTTP binding framework 可以把 JSON 绑定到 request DTO，Jackson 可以编码 event/view，ORM 可以给 repository entity；但 request → command、domain invariant 和 response whitelist 仍应是显式 application adapters。broker listener 的 record/ack 仍归 transport layer，JSON deserializer 只负责 bytes → versioned event。升级 validation/serialization library 时同样要锁 coercion、error projection、subtype output 和 framework integration。

### Go

HTTP handler 负责 body/status，JSON decoder 负责 bytes → input struct，application mapper 负责 command，response struct 是 whitelist。broker client 拿 bytes/metadata 并执行 ack，decoder/parser 不拥有 retry。database row scanning/query lifecycle 在 repository，validation library 不负责 transaction。生成输出即使结构受限，仍先 decode/validate 再进入 use case。

语言不同，责任线相同：

```text
transport object stops at adapter
contract object stops before domain
domain object stops before public writer
delivery/session/retry never hides inside validation model
```

## 面试追问

### 1. “FastAPI 已有 `response_model`，为什么还需要 `project_customer_order()`？”

`response_model` 提供 framework schema/validation/serialization guard；显式 projection 才拥有授权和版本选择。返回值先成为 `CustomerOrderView`，未来内部字段不会依赖 framework filtering 的偶然配置。

### 2. “consumer parse 失败后 Pydantic 会自动 nack 吗？”

不会。`parse_order_created()` 只产生 typed event 或 validation error；classifier 只给示例 kind；transport adapter 才按具体平台政策 ack/retry/DLQ，并负责幂等、退避和观测。

### 3. “`from_attributes=True` 能解决 N+1 吗？”

不能。它只允许按声明字段读取 attributes；property/descriptor 甚至可能触发 I/O。repository 负责 query/load/session/transaction，Pydantic 只验证读取结果。

### 4. “structured output 已按 JSON Schema 生成，为什么还要 validate？”

schema 是约束说明，不是信任证明。raw output 仍可能格式错误、结构漂移、事实捏造、越权引用或违反 domain invariant；必须在本地 model_validate 后再 mapping/domain check。

### 5. “`parse_raw` 能直接换成 `model_validate_json` 吗？”

仅当旧输入确实是 JSON。其他 encoding/content type/file behavior 应移到 transport adapter 显式 decode，然后 `model_validate()`；同时重测 size/error/security policy。

### 6. “V2 validator 最大的迁移风险是什么？”

不是 decorator 名，而是 signature、before/after ordering、default validation 和 TypeError 不再包装。用 raw/canonical/error/default/programmer-error cases 锁行为，尤其 discriminator 前置检查。

### 7. “为什么不全局 `serialize_as_any=True` 恢复 V1 输出？”

它会把所有 runtime subclass 新字段重新纳入输出，可能把内部字段变成公开 API。按 recipient 建 explicit view/union，只对明确承诺 subtype 的窄字段局部审查。

### 8. “你会怎样上线 V2？”

锁版本与 inventory → 在 V1 建 coercion/error/serialization/schema/integration evidence → mechanical replacement → 行为审计 → framework gate → canary/compatibility matrix/逐步扩容；每个差异有 owner 和 rollback。

## 本章检查清单

- [ ] FastAPI request、mapper、domain、response whitelist 四段分开
- [ ] broker bytes/metadata/ack 与 parser/classifier ownership 分开
- [ ] `from_attributes` 只用于已知 attribute projection，不冒充 repository
- [ ] LLM structured output 在本地复用 schema + validation，仍按不可信输入处理
- [ ] `parse_obj`／`parse_raw`／`dict`／`json`／`schema`／`copy`／`construct` 全部有 V2 mapping
- [ ] `@validator`／`@root_validator` 的 signature/order/default/TypeError 有 regression tests
- [ ] inner Config、`orm_mode`、`__root__`、`GenericModel` 都有显式迁移方案
- [ ] subclass serialization 与 `serialize_as_any` 做了泄漏和兼容双审计
- [ ] rollout 包含旧行为 golden、framework integration、canary 与 rollback
- [ ] 没有为了教程安装 broker、database 或 LLM integration dependency

## 小结

集成的质量不取决于 framework 代码有多少，而取决于 owner 是否可指出：FastAPI 只把 request 送到 mapper，broker client 只把 bytes/metadata 送到 parser 并消费 delivery decision，ORM attribute mode 只做 projection，structured output 仍必须本地验证。domain 与 public writer 不接收 transport object。

V1 → V2 也不能只靠方法改名。API、validator、config、root、generic 和 serialization 每层都有行为变化；特别是 TypeError 传播、default/ordering 和 annotated-type subclass serialization。先建立 golden，再 mechanical replacement、行为审计、integration gate 与 staged rollout，才是可回滚的迁移。
