# 05 · 模型行为与生命周期：配置不是永久安全证明

> **本章目标**：能为 `extra`、`frozen`、`validate_assignment`、实例重验、copy、private／computed field 与动态模型写出边界政策，并识别“模型已经验证过”之后仍然存在的逃生舱。可运行事实以 [创建订单契约](lab/src/order_contracts/inbound/create_order.py)、[事件版本](lab/src/order_contracts/events/) 和 [Settings](lab/src/order_contracts/config.py) 为准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest \
  tests/test_create_order.py \
  tests/test_serialization.py \
  tests/test_event_compatibility.py -v
```

当前应有 24 个测试通过。它们固定了三个起点：HTTP 输入拒绝未知字段；V1 事件 reader 忽略 additive V2 payload 字段，而当前 V2 writer 拒绝未知字段；订单 DTO、事件 envelope 及其嵌套模型都使用不可重新赋值的形状。

## 事故开场：`frozen=True` 的订单为什么还是变了？

团队把一个模型配置成 `ConfigDict(extra="forbid", frozen=True)`，于是 code review 中出现一句结论：“对象是不可变的，而且所有字段已经验证过。”几周后，列表子字段被原地 `append`；另一个调用点通过 `model_copy(update=...)` 放入了错误类型；缓存又把一个被绕过验证构造的实例交回边界层。三条路径都没有被那句结论覆盖。

真正可成立的说法更窄：

- `extra="forbid"` 管的是**某次正常验证中出现的未知输入键**；
- `frozen=True` 管的是**模型属性的重新赋值和删除**，不是任意对象图的深冻结；
- 验证描述的是**一次构造或显式验证路径**，不是实例余生的永久证明；
- copy、trusted construction、mutable child、private state 和跨边界复用都有各自政策。

因此本章把模型看成一个状态机，而不是一个贴了“安全”标签的 dict：

```text
raw data
  │ normal validation
  ▼
validated boundary DTO
  ├─ attribute assignment ── validate_assignment / frozen
  ├─ nested mutation ─────── child 自己的类型与可变性决定
  ├─ model_copy ──────────── shallow/deep 引用政策；update 默认可信
  ├─ model_construct ─────── 跳过验证的 trusted-only 路径
  ├─ model_validate(instance) ─ revalidate_instances 政策
  └─ projection / serialization ─ computed、extra、subclass 泄漏面
```

没有一个单独开关覆盖全部箭头。

## 生命周期仍然从信任边界开始

同一个 `ConfigDict` 不应该复制到所有模型。边界来源、兼容承诺和失败责任不同，政策也不同：

| 边界 | `extra` 政策 | coercion／实例信任 | 生命周期与失败政策 |
|---|---|---|---|
| HTTP request producer/client input | `forbid`；尽早暴露拼写错误并阻断 mass assignment | 默认严格；lab 拒绝 `quantity="2"`，只允许明确的币种规范化 | 验证失败映射为稳定 4xx；成功后显式 DTO → command，不把 request model 当领域对象 |
| Webhook | envelope 与 payload 均 `forbid` | **先对原始 bytes 验签，再 parse**；不能验证重编码后的 JSON | 签名失败与 schema 失败分开计数；Pydantic 不决定提供方是否重试 |
| MQ envelope／当前 writer | header 和 V2 payload `forbid` | 按 `schema_version` 解析，不猜版本，不默认相信已有实例 | 未知版本是 incompatible；字段错误是 permanent；timeout／connection 才是 transient 重试候选 |
| MQ 旧版 reader | V1 payload 明确使用 `ignore` | 只忽略承诺为 additive 的新 payload 字段 | 换取 forward compatibility，也承担拼写错误被吞掉的成本；永久错误应隔离而非无限重试 |
| Settings startup | 顶层 `ignore` 无关环境键；嵌套支付配置 `forbid` | 环境介质天然是文本，只为已知格式转换；不复用外部构造的 Settings 实例 | 必需配置缺失时启动失败；`SecretStr` 只降低意外展示风险，不替代秘密管理 |
| application command／domain | 普通 dataclass 没有 JSON extra 概念 | 只接受 adapter 显式映射的精确值，不再做边界便利 coercion | 幂等、授权、库存和状态迁移由 application/domain 处理；不是 DTO validator 职责 |
| outbound projection | 通常 `forbid`，模型字段就是输出白名单 | 从 domain 显式 project，不把整个内部对象 `model_dump()` | 按消费者生成 view/event；computed field 和宽泛 subclass serialization 要进入泄漏审查 |

lab 没有启动 broker、数据库或网络服务。上表中的 ack／retry／DLQ、幂等存储和 HTTP 部署是生产 adapter 必须实现的政策；本章只用纯模型、映射函数与单元测试明确分类，不伪造基础设施。

## `extra`：未知字段政策属于每一层模型

`ConfigDict(extra=...)` 有三个值：

| 模式 | 正常验证遇到未知键 | 适合场景 | 主要代价 |
|---|---|---|---|
| `extra="forbid"` | 产生 `extra_forbidden` | HTTP 写入 DTO、webhook envelope、协议 header、当前 event writer | 新字段发布需要协调；对需要向前兼容的旧 reader 可能过严 |
| `extra="ignore"` | 接受输入但丢弃未知键 | 已明确承诺 additive compatibility 的旧 reader、含大量无关键的 Settings 来源 | 拼写错误和未审查字段也会静默消失，不能靠 dump 恢复原输入 |
| `extra="allow"` | 保留到 `model_extra`／`__pydantic_extra__` | 真正需要透传 extension bag 的协议 | 动态内容进入序列化、存储和日志面；未注解时其 value 缺少业务约束 |

`allow` 不是“兼容性更好”的免费选择。若协议真的有扩展字段，优先把它命名成显式 mapping：

```python
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ExtensionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str
    extensions: dict[str, JsonValue] = Field(default_factory=dict)
```

这样 code review、schema 和输出策略都能看到扩展面。必须使用 `extra="allow"` 时，可以显式声明 `__pydantic_extra__` 的 value 类型，但仍需限制总键数、键名、数据尺寸和哪些下游允许透传；“值能验证成某类型”不等于字段具有受认可的业务语义。

extra policy 是**逐模型**的。外层 envelope `forbid` 不会自动替内层 payload 决定政策。lab 正是有意组合：

```python
class EventEnvelope(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OrderCreatedV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class OrderCreatedV2(OrderCreatedV1):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

这表达的是“header 不容漂移，旧 payload reader 接受 additive 字段，当前 V2 契约严格写入”，不是一个全局风格偏好。[事件兼容测试](lab/tests/test_event_compatibility.py) 同时固定 ignore 与 forbid，避免一方在重构中被另一方抹平。

### extra 与 coercion 是两个正交决策

`extra="forbid"` 只检查“字段名是否被声明”，并不会让已声明字段自动严格。HTTP 的 `quantity: StrictInt`、金额的 before validator 和 Settings 的文本转换分别定义 value policy。审查模型时应至少分开问：

1. 这个键是否允许出现？
2. 允许的键可以接受哪些原始类型？
3. 哪些规范化有明确边界语义？
4. 验证后的值还能否在生命周期中被改变？

## `frozen=True` 是浅层属性冻结

[CreateOrderRequest](lab/src/order_contracts/inbound/create_order.py) 的结构体现了 lab 的选择：

```python
class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: CustomerId
    idempotency_key: IdempotencyKey
    items: tuple[CreateOrderItem, ...]
```

外层和 `CreateOrderItem` 都 frozen，集合使用 tuple，金额也是 frozen nested model。这样 `request.items = ...` 和 `request.items.append(...)` 都不可用，常见误改面显著缩小。

但 `frozen=True` 是 Pydantic 所称的 faux immutability：它阻止模型属性的正常重新赋值／删除，不会递归把任意 mutable child 变成不可变值。下面的例子可以直接在 lab venv 运行：

```python
from pydantic import BaseModel, ConfigDict


class FrozenBasket(BaseModel):
    model_config = ConfigDict(frozen=True)

    tags: list[str]


basket = FrozenBasket(tags=["new"])

# basket.tags = []          # ValidationError: frozen_instance
basket.tags.append("vip")   # 合法的 list 原地 mutation
assert basket.tags == ["new", "vip"]
```

所以冻结政策必须沿对象图审查：

- 可变容器优先换成 tuple／`frozenset`／不可变 mapping 表示；
- nested model 也要有自己的 mutation 政策；
- 任意第三方对象、list、dict、set 或 mutable dataclass 都可能保留修改入口；
- 需要强隔离时，在边界显式 copy 成自己的不可变表示，而不是保存调用方传入的 mutable reference。

“能 hash”也不能作为深不可变证明：子对象是否 hashable、是否共享引用、对象背后是否持有外部状态，都是另一层问题。

## 不可变 DTO ≠ 不可变聚合根

DTO 的 `frozen=True` 表达“这份边界事实不要被就地改写”。领域聚合则要表达业务行为和状态迁移。两者即使都使用 frozen dataclass，也不是同一个生命周期概念。

lab 的流水线是：

```text
CreateOrderRequest (Pydantic inbound DTO)
  │ to_create_order_command：逐字段白名单映射
  ▼
CreateOrderCommand (frozen dataclass)
  │ Order.create：单币种等领域规则
  ▼
Order (frozen domain dataclass)
  ├─ project_customer_order → CustomerOrderView
  └─ project_order_created_v2 → OrderCreatedEnvelopeV2
```

[应用命令](lab/src/order_contracts/application/commands.py) 和 [领域订单](lab/src/order_contracts/domain/order.py) 使用普通 `@dataclass(frozen=True, slots=True)`，不依赖 `BaseModel` 继续做 JSON coercion。真实系统若允许支付、取消等状态迁移，可以用返回新聚合的行为、受控的 mutable aggregate 或事件溯源表达；关键是由领域 API 维护不变量，不是把 request DTO 解冻后直接改 `status`。

`idempotency_key` 也说明了这个界线。Pydantic 只能验证键的格式，并通过 mapper 放入 `CreateOrderCommand`；它不能证明这个键是否已执行。生产应用层需要在正确作用域内（例如 caller + operation）原子登记请求指纹与结果，处理“同键同请求重放”和“同键不同请求冲突”。本 lab 不连接数据库，因此没有声称已经实现 exactly-once。

## `validate_assignment` 只守属性赋值路径

需要可修改的 Pydantic model 时，可以启用：

```python
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class MutableLine(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    quantity: int = Field(ge=1)


line = MutableLine(quantity=1)
try:
    line.quantity = 0
except ValidationError as exc:
    assert exc.errors()[0]["type"] == "greater_than_equal"
```

这只说明 `line.quantity = 0` 会重新走该字段的赋值验证。它不是“实例始终有效”模式：

- `line.child.tags.append(...)` 修改的是 child 内部对象，没有给 `line.child` 赋新值；
- child 自己若没有 `validate_assignment`，`line.child.value = ...` 由 child 的政策决定；
- `model_copy(update=...)` 的 update 被当作可信数据，不自动走正常字段验证；
- `model_construct()` 绕过正常验证；
- `object.__setattr__` 等 Python 逃生舱本就有能力绕过模型协议，业务代码不应使用它们制造“合法”对象。

lab 的 DTO 已经 `frozen=True`，所以不再叠加 `validate_assignment=True` 来制造虚假的双重保险：正常属性赋值先被冻结政策拒绝。若用例确实需要 mutable working model，才单独启用 assignment validation，并测试具体修改路径。

## `revalidate_instances`：跨边界复用时重新决定信任

这里的实例重验（instance revalidation）专指“输入已经是模型实例时，是否重新执行该模型 schema”，不是重跑网络验签、权限或领域规则。

嵌套模型或 `model_validate(existing_instance)` 收到的可能已经是目标模型实例。默认 `revalidate_instances="never"` 倾向于信任它，避免重复工作；这不等于实例来源永远可信。

可选政策如下：

| `revalidate_instances` | 同类实例 | 子类实例 | 合理风险模型 |
|---|---|---|---|
| `"never"`（默认） | 不重验 | 不重验 | 同一受控组件刚创建并保持不可变的 trusted value |
| `"always"` | 重验 | 重验并收敛为声明类型 | 跨插件、缓存、反序列化层或不清楚实例历史的边界 |
| `"subclass-instances"` | 不重验 | 重验 | 信任精确类型，但防止带额外状态／被修改行为的子类穿越边界 |

配置应放在**被重验的模型类型**上：

```python
from pydantic import BaseModel, ConfigDict, Field


class TrustedAmount(BaseModel):
    model_config = ConfigDict(revalidate_instances="subclass-instances")

    cents: int = Field(ge=0)


class ExtendedAmount(TrustedAmount):
    debug_note: str
```

当另一个模型字段声明为 `TrustedAmount` 并收到 `ExtendedAmount` 时，subclass policy 会重验并收敛为基类契约；精确 `TrustedAmount` 实例仍被信任。若可能收到曾被不安全代码修改的精确实例，应选 `"always"`，或者更清楚地只接受 raw wire data 并在边界重建。

风险判断按来源做，而不是按性能直觉做：

- **可信模型实例**：同一纯 mapper 刚构造、对象图不可变、未经过 extension hook，可以避免重验；
- **子类实例**：可能携带额外字段、serializer 或行为，至少使用 `subclass-instances`，出站仍显式 project；
- **跨边界复用**：缓存、插件、任务队列 wrapper、测试 fixture 或旧进程生成的实例，不应仅凭 Python class name 提升信任；
- **原始网络／broker data**：接受 bytes／mapping 并使用正式 parse 入口，不能要求上游“先帮我构造 Pydantic model”。

即使 `"always"` 也不是深层安全证明：子对象可能有自定义 schema、mutable state 或副作用。它只重新执行声明的 Pydantic schema。

## `model_copy`：deep 控制引用，不替 update 验证

`model_copy(deep=False)` 默认浅复制；`deep=True` 递归复制模型持有的对象。用一个 mutable child 可以看到差异：

```python
from pydantic import BaseModel


class Child(BaseModel):
    tags: list[str]


class Parent(BaseModel):
    child: Child


original = Parent(child={"tags": ["new"]})
shallow = original.model_copy()
deep = original.model_copy(deep=True)

assert shallow.child is original.child
assert shallow.child.tags is original.child.tags
assert deep.child is not original.child
assert deep.child.tags is not original.child.tags
```

`deep=True` 回答的是“新对象是否共享引用”，不回答“新值是否满足契约”。尤其危险的是：

```python
class Quantity(BaseModel):
    value: int


valid = Quantity(value=1)
copied = valid.model_copy(update={"value": "not-an-int"})
assert copied.value == "not-an-int"  # update 默认没有重验
```

所以 update 数据的规则应明确：

- 只允许内部已验证／已类型化的数据进入 `update`；
- 输入来自请求、事件、配置、dict patch 或不可信插件时，合并 raw mapping 后重新 `model_validate(...)`；
- 对每个依赖 update 的封装写测试，不能根据方法名中的 `copy` 推断会重新验证；
- deep copy 可能成本高，也未必能正确复制持有锁、连接或进程资源的任意对象；Pydantic model 不应持有这类边界资源作为普通数据字段。

## `model_construct()`：trusted-only 的显式逃生舱

`model_construct()` 不执行正常验证，可以制造与 annotation 不一致的实例：

```python
from pydantic import BaseModel, ConfigDict


class Constructed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int


unsafe = Constructed.model_construct(quantity="not-an-int", typo=1)
assert unsafe.quantity == "not-an-int"
assert not hasattr(unsafe, "typo")
```

注意第二行的细节：正常验证会因 `typo` 产生 `extra_forbidden`；`model_construct()` 不会抛这个错，在 `forbid`／`ignore` 下直接忽略 extra，而 `allow` 下仍保留 extra。它不能作为“更快但语义相同”的通用构造器。

合理使用条件非常窄：数据已经由等价或更强的可信过程验证、validator 具有不应重复的非幂等行为，或者性能证据表明这一段构造确实重要。即便如此，也应把 construct 封装在名字明确的内部函数中，测试输入前置条件，并禁止边界 handler 直接调用。Pydantic v2 的正常验证已经很快；是否优化要测量，不要凭旧版本经验。

## private attribute：进程内状态，不是字段契约

以下划线命名并通过 `PrivateAttr` 声明的属性，不属于普通字段契约：

```python
from pydantic import BaseModel, PrivateAttr


class Quote(BaseModel):
    amount: int
    _cache: dict[str, int] = PrivateAttr(default_factory=dict)


quote = Quote(amount=10)
quote._cache["tax"] = 1

assert quote.model_dump() == {"amount": 10}
assert "_cache" not in Quote.model_json_schema()["properties"]
```

private attribute 的含义是“不参加普通 validation／serialization／JSON Schema”，不是“秘密已经加密”或“对象已经深冻结”。它仍在进程内存中，仍可被业务代码读取和修改，也可能被调试器、自定义日志或显式属性访问暴露。

适合 private state 的例子是惰性缓存、解析过程中的非契约 metadata、不可序列化的内部 helper；不适合把权限、幂等状态或必须跨进程传递的数据藏进去。若该值影响业务结果，它应进入可测试的应用／领域状态；若它是秘密，使用秘密存储、最小权限和明确的 redaction，而不是只加下划线。

## computed field：派生值会扩大输出契约

`@computed_field` 把 property 纳入 Pydantic 序列化：

```python
from pydantic import BaseModel, computed_field


class Price(BaseModel):
    cents: int

    @computed_field
    @property
    def display(self) -> str:
        return f"${self.cents / 100:.2f}"


price = Price(cents=1230)
assert price.model_dump() == {"cents": 1230, "display": "$12.30"}
assert price.model_dump(exclude_computed_fields=True) == {"cents": 1230}
```

computed field 通常不出现在 validation-mode JSON Schema，因为调用方不需要提供它；它会出现在 `model_json_schema(mode="serialization")` 中，并标记 `readOnly: true`。这正好说明“进入 schema”必须问是哪一种 mode。FastAPI response schema、独立 schema export 和客户端生成应使用与实际输出一致的模式并做 artifact diff。

泄漏风险也因此很直接：一个原本只供进程内使用的 property，一旦加上 `@computed_field`，默认会进入 dump；它还可能进入 repr。内部成本、风控分数、完整姓名、秘密派生片段等不应靠调用方每次 `exclude` 才安全。优先用显式 outbound projection；确需 computed field 时，明确 alias、return type、serialization schema、repr 和排除测试。

private／computed 的对照可以压缩为：

| 机制 | validation input | 普通 dump | JSON Schema | 生命周期风险 |
|---|---:|---:|---:|---|
| `PrivateAttr` | 不接受 | 不进入 | 不进入 | 可变进程内状态、误当秘密保险箱 |
| `@property` | 不接受 | 默认不进入 | 不进入 | 普通 Python 行为，不是契约 |
| `@computed_field` | 不接受 | 默认进入 | serialization mode 进入 | 派生敏感值或昂贵计算意外扩散 |

## `create_model()`：只给真正动态的 schema

当字段集合在运行时才知道，例如租户配置驱动的有限问卷，可以使用 `create_model()`。下面是一个最小但完整的例子：

```python
from pydantic import ConfigDict, Field, ValidationError, create_model


RuntimeJob = create_model(
    "RuntimeJob",
    code=(str, ...),
    retries=(int, Field(default=0, ge=0, le=5)),
    __config__=ConfigDict(extra="forbid", frozen=True),
)

job = RuntimeJob.model_validate({"code": "export", "retries": 2})
assert job.model_dump() == {"code": "export", "retries": 2}
assert RuntimeJob.model_json_schema()["title"] == "RuntimeJob"

try:
    RuntimeJob.model_validate({"code": "export", "retries": 9})
except ValidationError as exc:
    assert exc.errors()[0]["type"] == "less_than_equal"
```

动态模型仍然需要稳定名字、明确 config、约束、测试和 schema 发布政策。它的成本包括：

- **可发现性**：工程师无法只靠源码搜索列出运行时全部字段；
- **IDE／静态分析**：工具通常看不到生成类的精确属性，调用端容易退化成 `Any`；
- **错误定位**：工厂输入和生成后的 schema 分离，stack trace 不如静态 class 直接；
- **版本治理**：字段配置变化仍是契约变化，必须生成、评审、diff 并保留 schema version；
- **缓存与资源**：不能按每条请求无限生成新 class；应按已审查的 schema identity 有界缓存。

如果字段在开发时已经知道，就写普通 class。不要为了减少几行声明而动态化 HTTP DTO、事件版本或领域命令；那会把明确的编译／review 成本推到运行时。

## 边界适配器决定对象何时出生、何时失效

### HTTP 与 FastAPI：自动验证不等于自动分层

[FastAPI 示例](lab/examples/fastapi_adapter.py) 把 route 参数声明成 `CreateOrderRequest`，框架会调用 Pydantic 并生成 OpenAPI；异常 handler 只返回安全的 error `type` 和 `loc`，且把未知字段名替换为 `<extra>`。但 FastAPI 不替应用决定：

- 幂等记录的原子写入和 replay 结果；
- 当前 caller 是否有权为 customer 下单；
- 库存、额度、订单状态等外部／领域事实；
- request DTO 如何映射成 command；
- domain 如何显式 project 成客户 view；
- 日志、trace、错误响应中哪些输入必须删除或脱敏。

`response_model=CustomerOrderView` 是最后一道输出契约，不是把 domain object 全量交给框架的许可。lab route 仍显式调用 `project_customer_order(order)`。

### Webhook：模型生命周期必须晚于签名验证

[parse_payment_webhook](lab/src/order_contracts/adapters.py) 的顺序是：验证 signature 格式 → 对原始 `raw: bytes` 计算 HMAC → constant-time compare → `PaymentWebhookEnvelope.model_validate_json(raw)`。因此恶意的未签名 payload 不会先进入 JSON／Pydantic 生命周期。

若先 parse 成 model，再 dump 回 JSON 验签，键顺序、空白、数字表示和 alias 都可能变化；验证的已经不是提供方发送的 bytes。签名失败是 authenticity failure，schema 失败是 contract failure，两者的响应和观测维度也不应混为一个 “validation_error”。

### MQ：模型验证结果要进入 delivery 分类

[错误分类器](lab/src/order_contracts/errors.py) 明确区分：

| 故障 | 分类 | 典型 broker 政策 |
|---|---|---|
| `schema_version` missing／unknown、协议 tag 不兼容 | incompatible | 隔离／DLQ，触发契约告警；等待部署新 consumer 才可能恢复 |
| 字段约束、必填字段、JSON shape 错误 | permanent | 隔离／DLQ；无限重试只会制造 poison-message loop |
| timeout、connection failure | transient | 有界指数退避和 jitter；超过预算后隔离或人工处理 |
| 业务重复消息 | 不是 validation failure | 用 event/message id 或业务幂等键查重，按既定结果 ack |

Pydantic 能提供分类输入，不能执行 ack／nack、retry 或 DLQ。消费 adapter 必须保证：解析成功不等于业务 side effect 已提交；side effect 与 ack 的先后、崩溃窗口和幂等存储要一起设计。本 lab 刻意不启动 broker，也不模拟 exactly-once。

已有 `OrderCreatedEnvelopeV1` 实例也不应让 MQ handler 跳过 raw envelope 入口。wire bytes 才包含真实版本、大小和签名／metadata 上下文；Python 实例只是进程内表示。跨进程时仍序列化、按版本解析，并根据失败分类决定 delivery 生命周期。

### Settings：在启动边界一次建立可信快照

[AppSettings](lab/src/order_contracts/config.py) 使用 `SettingsConfigDict(extra="ignore", frozen=True)`。顶层 ignore 让 dotenv 中的无关键不会阻止启动；嵌套 `PaymentProviderSettings` 仍 forbid 拼错的支付配置。`load_settings()` 缺少必需支付配置时直接抛 `ValidationError`，测试将它固定为 startup fail-fast。

推荐生命周期是：启动时读取来源 → 验证完整配置 → 形成 frozen snapshot → 通过依赖注入传递。不要在每个请求里反复读取环境，也不要把配置错误降级成业务流量中的随机 500。若系统支持动态配置，版本、刷新原子性、旧 snapshot 的存活期和失败回退必须另行设计，不能用 `validate_assignment` 在共享 Settings 对象上逐字段热改。

## 可观测性：记录契约坐标，不记录整份对象

模型生命周期越长，数据进入 log、trace、metric label 和 crash dump 的机会越多。推荐记录低基数、可聚合的坐标：

- boundary／operation，例如 `http.create_order`、`mq.order_created`；
- error `type` 和脱敏后的 `loc`；
- 明确白名单的 `schema_version`、`event_type`；
- request／message correlation id 的安全表示；
- failure kind：incompatible／permanent／transient；
- retry attempt、DLQ reason code，而不是完整 payload。

不要默认记录 `ValidationError.errors()` 中的 `input`，也不要 dump 整个 request、Settings、private state 或 `model_extra`。字段路径本身也可能含调用方提供的 extra key；lab 的 FastAPI handler 对它做 `<extra>` 替换。`SecretStr` 的 repr redaction 只是防误操作，显式 `.get_secret_value()` 后仍是普通字符串。

computed field 也必须接受隐私审查：它虽然不是输入字段，却可能把多个非敏感字段组合成敏感推断。metrics label 不得使用 customer id、idempotency key、原始 error message 等高基数或个人数据。

## Java／Go 对照：浅不可变是跨语言共同陷阱

### Java record 与 Lombok immutable

Java record 的 component reference 是 final，编译器生成构造器、accessor、`equals/hashCode`；它不深复制 component：

```java
record CreateOrder(List<String> skus) {}

var source = new ArrayList<>(List.of("sku-1"));
var order = new CreateOrder(source);
source.add("sku-2");
// order.skus() 现在也能看到 sku-2
```

需要快照语义时，应在 compact constructor 中 `skus = List.copyOf(skus)`，并继续审查元素本身是否可变。Lombok `@Value` 生成 final field 和无 setter 的 class，也同样只冻结引用；它不是递归 immutable，也不会自动执行 Bean Validation。Java DTO → command → domain → response record 的 mapper 仍有权限与版本价值。

Pydantic `frozen=True` 与 record／`@Value` 的共同点正是 shallow：都不能只看外层语法就宣布对象图深不可变。差异在于 Pydantic 运行时验证 raw data；Java 编译期类型和 final reference 不能验证网络 JSON，仍需 Jackson／Bean Validation／显式构造器政策。

### Go value copy 与 slice alias

Go struct 赋值通常做 value copy，但 slice 字段复制的是 slice header，底层 array 仍可能共享；map 和 pointer 也保留引用语义：

```go
type Order struct {
    SKUs []string
}

source := []string{"sku-1"}
a := Order{SKUs: source}
b := a
b.SKUs[0] = "changed"
// a.SKUs[0] 也变成 "changed"
```

需要隔离时使用 `slices.Clone`／`append([]T(nil), src...)` 并继续审查元素；固定长度 array 的赋值才复制整段元素值。Go 没有 `frozen=True` 或自动 `validate_assignment`，团队通常通过不导出字段、constructor、只返回副本和显式 validator 维护边界。语言机制不同，问题仍相同：值复制、引用隔离、运行时输入验证与领域状态迁移必须分别回答。

## 生命周期决策表

| 问题 | 优先选择 | 不要误认为 |
|---|---|---|
| 公网写入 DTO 是否接受未知键 | `extra="forbid"` | 会自动让已声明字段 strict |
| 旧事件 reader 是否容忍 additive payload | 针对该版本 `extra="ignore"` + 兼容测试 | 所有 MQ 模型都应该 ignore |
| 需要 vendor extension | 显式 `extensions` mapping；必要时受约束的 `extra="allow"` | 动态字段天然安全或应全量透传 |
| DTO 不允许属性改写 | `frozen=True` + immutable children | 深冻结整个对象图 |
| mutable model 赋值时重验 | `validate_assignment=True` | 能拦 nested mutation、copy update、construct |
| 接收已有 model instance | 按来源选择 `revalidate_instances` | class 相同就一定可信 |
| 复制后避免共享引用 | `model_copy(deep=True)`，先测对象类型 | update data 自动验证 |
| 已验证数据的快速内部构造 | 封装 `model_construct()` 并证明前置条件 | 与正常 validation 语义相同 |
| 存放非契约内部状态 | `PrivateAttr` | 秘密管理或持久化状态 |
| 输出派生字段 | `@computed_field` + serialization schema／泄漏测试 | 普通 property 不会改变输出契约 |
| 运行时才知道字段集合 | 有界缓存的 `create_model()` + schema 版本治理 | 替代普通 class 的少写代码技巧 |
| 领域状态需要变化 | 领域行为返回新聚合或受控 mutation | 修改 request DTO 即完成业务动作 |

## 面试回答与审查清单

如果面试官问“`frozen=True` 后模型是否安全不可变”，可以这样回答：

> 它阻止 Pydantic model 属性的正常重新赋值，是浅层 faux immutability。要获得快照语义，我还会把 list／dict 换成 tuple／不可变表示，冻结 nested model，并审查第三方 mutable child。`validate_assignment` 只管赋值，`model_copy(update=...)` 与 `model_construct()` 也必须单独治理。DTO 的不可改写不替代领域聚合的不变量。

如果问“为什么不对所有输入统一 `extra="forbid"`”，回答应包含兼容边界：

> HTTP command 和当前 event writer 用 forbid 防 typo、mass assignment 与泄漏；旧 event reader 若承诺 additive forward compatibility，可以在 payload 层用 ignore，但 envelope header 仍严格。Settings 顶层可忽略无关环境键，嵌套关键配置仍 forbid。政策属于边界和版本，不属于全项目审美。

提交模型前逐项检查：

- `extra` 是在哪一层生效，nested model 是否另有政策；
- value coercion 是否与边界介质一致，是否有 explicit test；
- `frozen` 对象图中是否仍有 list／dict／set／mutable child；
- mutable model 的 assignment 与 nested mutation 是否分别测试；
- 已有实例从哪里来，`revalidate_instances` 是否匹配其信任等级；
- `model_copy` 是否共享引用，update 是否来自可信数据；
- `model_construct` 是否被隔离在 trusted-only 内部入口；
- private／computed field 是否影响权限、隐私、repr、dump 或 serialization schema；
- 动态模型是否真的运行时才可知，是否有名字、版本、缓存和 schema diff；
- FastAPI 自动验证后是否仍显式 DTO → command → domain → projection；
- webhook 是否 signature-before-parse，MQ 是否区分永久／不兼容／暂时故障；
- 幂等是否由应用层原子处理，观测是否只记录低基数脱敏坐标；
- 测试是否覆盖生命周期逃生舱，而不只覆盖第一次构造成功。

核心原则是：**配置只约束它声明的那条生命周期路径。先说清数据从哪个边界出生、由谁持有、如何复制／修改／重验、最终向谁序列化，才能把“已验证模型”变成可持续的工程信任，而不是一次构造成功后的过度承诺。**
