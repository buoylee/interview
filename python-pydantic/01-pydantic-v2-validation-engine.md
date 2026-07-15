# Pydantic v2 验证引擎：从类型标注到 Rust 执行器

这一章解释的不是某个 validator 装饰器怎么写，而是 Pydantic v2 为什么能把一组 Python 类型标注变成可复用的数据契约。掌握这条主线后，strict、联合类型、序列化、JSON Schema、性能优化就不再是互不相关的 API 清单。

本文以 lab 中的 [`CreateOrderRequest`](lab/src/order_contracts/inbound/create_order.py) 和模块级 [`ORDER_CREATED_ADAPTER`](lab/src/order_contracts/events/envelope.py) 为事实来源。先运行两条真实入口：

```bash
cd python-pydantic/lab
uv run pytest tests/test_create_order.py tests/test_event_compatibility.py -v
```

## 事故开场：每条消息都重建 TypeAdapter，CPU 为什么突然升高？

某订单消费者上线后，消息吞吐没有变化，CPU 却明显升高。业务代码看起来只有一行：

```python
def consume(raw: bytes) -> object:
    adapter = TypeAdapter(OrderCreatedMessage)
    return adapter.validate_json(raw)
```

问题不在 JSON 大小，而在对象生命周期。`TypeAdapter(...)` 不只是保存一个 Python 类型；它需要为该类型生成 CoreSchema，并准备底层 validator／serializer。把它放进逐消息热路径，就会反复支付本可复用的构建成本。

lab 的做法是把 adapter 建在模块级：

```python
ORDER_CREATED_ADAPTER = TypeAdapter(OrderCreatedMessage)


def parse_order_created(raw: bytes) -> OrderCreatedMessage:
    return ORDER_CREATED_ADAPTER.validate_json(raw)
```

事故复盘时应先问两个问题：schema 执行器在哪里构建，生命周期是否覆盖整个进程？这比一开始就更换 JSON 库更接近根因。

## 一句话心智：Python 构建 CoreSchema，pydantic-core 执行验证与序列化

可以把 v2 的主路径压缩成下面这张图：

```text
Python annotation / Annotated metadata / model_config / decorators
                              │
                              ▼
                   Pydantic 生成 CoreSchema
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
        SchemaValidator             SchemaSerializer
        validate_python/json        to_python/json
                   │                     │
                   └──────────┬──────────┘
                              ▼
                    已验证对象 / 对外数据

CoreSchema ──GenerateJsonSchema──> JSON Schema（文档／交换契约）
```

这里有三个不能混淆的“schema”：

- Python 类型标注描述开发者意图，也供 mypy、Pyright 等静态工具分析；Python 本身不会因为函数参数标成 `int` 就在运行时拒绝字符串。
- CoreSchema 是 Pydantic 与 pydantic-core 之间的运行时验证／序列化图，不是给 API 消费者看的 JSON Schema。
- JSON Schema 是从 CoreSchema 派生的描述性产物，可供 OpenAPI、代码生成和契约审查使用；它不等于运行时执行器，也未必能表达任意 Python validator 的全部语义。

架构师应把 Pydantic 放在“不可信数据进入可信代码”的边界，而不是把它误解为 Java 编译器或 JVM 的运行时类型系统。

## 类定义阶段发生什么

定义 `BaseModel` 子类时，Pydantic 的 metaclass 会收集字段 annotation、`model_config`、validators、serializers、私有属性和泛型信息。以 `CreateOrderRequest` 为例：

```python
class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: CustomerId
    idempotency_key: IdempotencyKey
    items: Annotated[
        tuple[CreateOrderItem, ...],
        Field(min_length=1, max_length=100),
    ]
```

大致会经历四层工作：

1. 解析 annotation，包括类型别名、前向引用、泛型与嵌套模型。未能及时解析的前向引用可能需要 `model_rebuild()`。
2. 按 Pydantic 规则合并 `Annotated` metadata、`Field` 约束、model config 和 decorator 定义的 validator／serializer。
3. 生成 CoreSchema 节点图；例如 tuple、模型字段、长度约束和 after model validator 都会成为执行图的一部分。
4. 基于这张图准备可复用的 `SchemaValidator` 与 `SchemaSerializer`。正常情况下，它们属于模型类的构建产物，不应在每次请求中手工重建。

为了排障，可以观察：

```python
print(type(CreateOrderRequest.__pydantic_validator__).__name__)
print(type(CreateOrderRequest.__pydantic_serializer__).__name__)
print(type(CreateOrderRequest.__pydantic_core_schema__).__name__)
```

这些属性能帮助确认“schema 是否已构建”，但不要把 `__pydantic_core_schema__` 的内部字典布局写进业务逻辑或 golden test。稳定契约应放在公开 API、验证行为和生成的 JSON Schema 上。

补充一个版本敏感点：`ConfigDict(defer_build=True)` 可以把 validator／serializer 构建推迟到首次使用。它能改善大量冷门模型的启动成本，却会把成本转移到首个请求；是否使用必须结合启动延迟、首请求 SLO 与预热策略决定。

## 调用阶段发生什么

类构建完成后，每次验证主要是在复用既有执行器。不同入口的关键差异是输入模式，而不是“哪个更高级”。

### Python mode

`model_validate()` 和常规 `Model(...)` 接收 Python 对象。底层执行的是 Python 分支，因此会看到 `dict`、`Decimal`、`datetime`、已有模型实例等真实 Python 类型。

```python
request = CreateOrderRequest.model_validate(payload_dict)
```

是否 coercion 由 CoreSchema 决定。本 lab 的 quantity 使用 strict integer，所以字符串 `"2"` 会失败；Money 则有意接受 `Decimal` 或十进制字符串。

### JSON mode

`model_validate_json()` 或 `TypeAdapter.validate_json()` 接收 JSON 的 `str`、`bytes` 或 `bytearray` 表示，直接走 JSON 解析与 CoreSchema 的 JSON 输入路径：

```python
request = CreateOrderRequest.model_validate_json(raw_request_bytes)
event = ORDER_CREATED_ADAPTER.validate_json(raw_event_bytes)
```

这不是简单的 `json.loads(raw)` 加 `model_validate(...)` 别名。JSON mode 知道输入来自 JSON 类型系统，并能避免先构造完整 Python 中间对象；个别类型在 strict 模式下的 JSON 接受规则也可能与 Python mode 不同。因此测试必须覆盖服务真实使用的入口。这里执行的始终是 CoreSchema；生成给 OpenAPI／代码生成器使用的 JSON Schema 从不参与运行时验证。

### string mode

`model_validate_strings()` 面向“外层是字符串映射”的数据源，例如表单、INI 或查询参数聚合结果。它会按 JSON-mode 风格处理叶子字符串：

```python
class RetryPolicy(BaseModel):
    attempts: int
    enabled: bool


policy = RetryPolicy.model_validate_strings(
    {"attempts": "3", "enabled": "true"}
)
```

不要先把任意 HTTP body 变成字符串映射再调用它；真正的 JSON body 应使用 JSON 入口，否则错误语义与性能路径都会改变。

## 四个入口的契约

| 入口 | 适合输入 | 返回 | 典型边界 | 主要提醒 |
|---|---|---|---|---|
| `Model(**data)` / `__init__` | 关键字形式的 Python 数据 | model | 应用内部创建简单 DTO | 不是 JSON bytes 入口；自定义 `__init__` 会增加静态分析与继承复杂度 |
| `Model.model_validate(obj)` | mapping、已有对象、可选 attributes | model | 已解码 HTTP／任务数据 | 走 Python mode；不要假设与 JSON mode 完全相同 |
| `Model.model_validate_json(raw)` | JSON `str`／`bytes`／`bytearray` | model | 单一模型的 HTTP、文件、消息 body | 避免手工 `json.loads` 中间层；错误包含 JSON 解析失败 |
| `TypeAdapter(T).validate_json(raw)` | 任意受支持类型 `T` 的 JSON | `T` 对应结果 | union、`list[T]`、dataclass、TypedDict | adapter 要复用；本 lab 用它解析版本化事件 union |

面试里被问“为什么不用 `BaseModel` 包住所有东西”，可以回答：`TypeAdapter` 把验证、序列化与 JSON Schema 能力应用到任意受支持类型，尤其适合顶层 union 或容器；但它没有模型方法与业务命名带来的语义边界。

## model_construct() 是可信数据逃生舱

`model_construct()` 创建模型但不执行正常验证。它不是“更宽松的 validate”，而是调用方声明：数据已经可信，我愿意承担绕过全部约束的后果。

下面的代码可以同时绕过 quantity 和 duplicate SKU 校验：

```python
from decimal import Decimal

from order_contracts.inbound.create_order import (
    CreateOrderItem,
    CreateOrderRequest,
)
from order_contracts.value_objects import Money

unsafe_line = CreateOrderItem.model_construct(
    sku="SKU-RED-1",
    quantity=0,  # 正常验证要求 1..100
    unit_price=Money.model_construct(
        amount=Decimal("12.30"),
        currency="USD",
    ),
)
unsafe_request = CreateOrderRequest.model_construct(
    customer_id="cus_0123456789ab",
    idempotency_key="checkout-2026-0001",
    items=(unsafe_line, unsafe_line),  # 正常 after validator 拒绝重复 SKU
)

assert unsafe_request.items[0].quantity == 0
assert len(unsafe_request.items) == 2
```

适用场景必须非常窄，例如同一进程中刚完成验证、随后从可信缓存恢复，而且调用链有明确证明。不要用于 HTTP、MQ、数据库行、缓存内容或第三方 SDK 返回值等外部边界；这些数据都可能漂移或被污染。

也不要把它当成默认性能优化。Pydantic v2 对简单模型的正常验证已经很快，`model_construct()` 不保证永远更快；先用生产形状做 benchmark，再决定是否用逃生舱换取风险。

## 错误树如何形成

CoreSchema 是节点图，验证失败也因此不是一条随意拼接的字符串。嵌套字段、容器索引、union 分支和自定义 validator 会共同形成结构化错误：

```python
try:
    CreateOrderRequest.model_validate(bad_payload)
except ValidationError as exc:
    for item in exc.errors(include_url=False):
        print(item["type"], item["loc"])
```

常见结构包括：

- `type`：稳定的 machine-readable 错误类别，如 `int_type`、`extra_forbidden`。
- `loc`：字段、union 分支与容器索引组成的路径。
- `input`：触发错误的原始输入。
- `ctx`：约束参数或自定义错误上下文。

服务不能直接把完整 `errors()` 或 `str(exc)` 回给客户端或日志平台，因为 `input`、`ctx`，甚至攻击者构造的 extra-field 路径都可能含敏感信息。lab 的 [`ErrorResponse`](lab/src/order_contracts/errors.py) 只移除 `input`／`ctx`，保留 machine type 与原始 `loc`；因此它并不自动保证 path 安全。HTTP 示例在 [`fastapi_adapter.py`](lab/examples/fastapi_adapter.py) 中进一步把 `extra_forbidden` 的用户自定义 key 替换为 `<extra>`。其他协议若允许任意 key，也必须按自己的模型策略清洗 location 后再跨边界输出。

结论是：Pydantic 的错误树用于诊断，服务错误 DTO 用于跨边界，两者应显式映射，不能直接透传。

## schema/adapter 复用与缓存

性能设计应从生命周期开始，而不是从微优化开始：

- `BaseModel` 的 validator／serializer 随类复用；不要在请求内动态创建等价 model。
- `TypeAdapter` 应在模块初始化、应用启动或明确缓存层构建一次。`ORDER_CREATED_ADAPTER` 就是事件消费者的单例执行器。
- 动态租户 schema 确有必要时，缓存键必须包含所有会改变契约的版本／配置，并设置容量与淘汰策略，避免把 schema cache 变成内存泄漏。
- 修改运行时 annotation 或直接篡改 CoreSchema 不是热更新方案。契约变更应产生新模型／新版本，并通过测试与发布流程生效。

一次合理的排障顺序是：确认 adapter/model 是否重复构建；用 profiler 分离 schema build、JSON parse、validation 和业务耗时；最后才评估 validator 形态或自定义 CoreSchema。

## Java／Go 对照

| 关注点 | Python + Pydantic v2 | Java | Go |
|---|---|---|---|
| 类型描述 | annotation + `Annotated` metadata | class/record + Jackson 注解 + Bean Validation 注解 | struct field type + JSON tag + validator 调用 |
| 解码与校验 | CoreSchema 驱动 pydantic-core；可组合 parse、coercion、constraint | Jackson 先反序列化，Bean Validation 通常再执行约束；二者生命周期需框架整合 | `json.Decoder` 显式 decode，再显式调用 validation/domain function |
| 运行时引擎 | Python 生成执行图，Rust `SchemaValidator`／`SchemaSerializer` 执行热点 | JVM 反射、生成 accessor 或框架预计算 metadata | 标准库反射解码；校验常由库或手写代码完成 |
| 静态保证 | type checker 与 Pydantic 各司其职 | 编译器/JVM 类型系统更强，但外部 JSON 仍需反序列化校验 | 编译期 struct 类型明确，外部输入仍需 decode + validate |
| 复用单元 | model class、模块级 `TypeAdapter` | 复用 `ObjectMapper`、validator factory，不逐请求重建 | 复用配置；避免逐请求重建昂贵 validator metadata |

最重要的对照不是“谁更严格”，而是谁负责哪一步。Java 的静态类型同样不能证明一段外部 JSON 合法；Go 的 `json.Unmarshal` 成功也不代表业务约束成立。Pydantic 把 decode、类型转换与约束组合得更紧，但领域不变量仍应留在 domain。

## 版本敏感边界

`__pydantic_core_schema__` 适合教学观察和诊断，不是应用级稳定协议。官方把 Architecture 页面放在 internals 文档中；CoreSchema 的可用节点由 pydantic-core 理解，内部组合方式可能随版本优化。

因此本章遵循三条边界：

1. 业务建模优先使用 `Annotated`、`Field`、公开 validator／serializer 与 `TypeAdapter`。
2. 测试公开行为：输入、输出、错误 `type/loc` 和必要的 JSON Schema，而不是固定整棵 CoreSchema 字典。
3. 直接实现 `__get_pydantic_core_schema__` 的完整方法留到教程第 11 章（编号 10：高级扩展）；届时也必须通过公开 handler/core-schema API，并把 Pydantic minor upgrade 纳入兼容测试。

进一步核对可参考 Pydantic 官方的 [Architecture](https://docs.pydantic.dev/latest/internals/architecture/)、[Models](https://docs.pydantic.dev/latest/concepts/models/)、[TypeAdapter](https://docs.pydantic.dev/latest/concepts/type_adapter/) 与 [Performance](https://docs.pydantic.dev/latest/concepts/performance/) 文档。

本章的判断标准可以浓缩为一句面试答案：Python 类型标注表达意图，Pydantic 在类／adapter 构建期把意图编译成 CoreSchema，pydantic-core 复用 `SchemaValidator` 和 `SchemaSerializer` 执行边界契约；性能与正确性都取决于是否复用这份编译产物，以及是否把可信逃生舱限制在真正可信的数据上。
