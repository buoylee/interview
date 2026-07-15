# 06 · 契约分层与领域边界：显式映射，安全出站

> **本章目标**：能把同一笔订单拆成 HTTP request、application command、domain aggregate、customer view 与 integration event，并能解释每次逐字段映射保护了什么。出站部分进一步区分 projection 与 serialization，准确选择 `model_dump()`、`model_dump(mode="json")`、`model_dump_json()`、alias、include／exclude、serializer 与 JSON Schema 模式。可运行事实以 [adapters.py](lab/src/order_contracts/adapters.py)、[Money](lab/src/order_contracts/value_objects.py)、[outbound views](lab/src/order_contracts/outbound/views.py) 和 [serialization tests](lab/tests/test_serialization.py) 为准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_adapters.py tests/test_domain_order.py tests/test_serialization.py -v
```

当前应有 8 个测试通过。它们锁定三条主线：request → command 的显式 mapper、`Order.create()` 的单币种领域规则，以及 customer projection 的字段白名单与 duck typing 泄漏风险。

## 事故开场：验证过的对象为什么仍泄漏了字段？

一次重构把客户响应写成 `order.model_dump()`。当时领域对象里只有客户可见字段，响应看起来完全正确。后来支付接入增加了 `provider_reference`，运营功能又增加了 `internal_note`；复用同一对象的响应端点没有改一行代码，却开始把两个新字段发给客户。

问题不是“少配了一个 exclude”。它混淆了两个动作：

- **projection** 决定某个消费者**有权看哪些事实**；
- **serialization** 决定这些已获准事实**如何编码成 Python／JSON 表示**。

`model_dump()` 只做后者。它不会读取权限政策，也不知道数据库列、领域状态、客户响应和事件版本之间的所有权差异。安全流水线应是：

```text
raw JSON
  │ parse / validate / normalize
  ▼
CreateOrderRequest                  HTTP contract
  │ explicit map
  ▼
CreateOrderCommand                  application intent
  │ authorize + act
  ▼
Order                               domain aggregate
  ├─ explicit project ──► CustomerOrderView ── serialize ──► HTTP JSON
  └─ explicit project ──► OrderCreatedV2     ── serialize ──► event JSON
```

每条箭头都是一次责任切换，不是“相同数据换个类名”。

## 同一笔订单的五张表

下面不是五个互相同步的数据库表，而是五份由不同 owner 管理的模型。它们在某个时刻描述同一笔订单，却不拥有相同的信任、版本、权限和失败语义。

### 1. HTTP request：`CreateOrderRequest`

| 维度 | 决策 |
|---|---|
| owner | 下单 HTTP API 团队；与客户端共同维护 wire contract |
| 信任 | 公网原始输入，不可信；必须 parse、validate、normalize |
| 版本 | API 兼容政策；字段增删不应由数据库结构意外驱动 |
| 权限 | 只描述“客户端可以请求什么”，校验通过不等于操作者被授权 |
| 失败含义 | JSON／字段／局部不变量错误，adapter 映射为稳定 4xx；不得进入领域动作 |

[CreateOrderRequest](lab/src/order_contracts/inbound/create_order.py) 负责 items 非空、`quantity` 为 1～100 的严格整数、SKU 不重复、币种规范化及未知字段拒绝。这些只依赖当前 payload，是协议局部不变量。

### 2. application command：`CreateOrderCommand`

| 维度 | 决策 |
|---|---|
| owner | 创建订单 use case／application service |
| 信任 | 只接受受控 adapter 显式构造的进程内意图，不接 raw JSON |
| 版本 | 随用例演进，不承担 HTTP 或事件的兼容承诺 |
| 权限 | command 只携带执行意图；application 仍须 authorize、处理幂等和外部协作 |
| 失败含义 | mapper 构造错误通常是编程错误；授权、幂等冲突和依赖失败由应用层分类 |

[CreateOrderCommand](lab/src/order_contracts/application/commands.py) 使用 frozen stdlib dataclass。它不需要 JSON alias、coercion 或 `extra` 政策，因为不位于 wire boundary。

### 3. domain aggregate：`Order`

| 维度 | 决策 |
|---|---|
| owner | 订单领域；命名和行为应表达业务语言 |
| 信任 | 接受 application command 和领域标识；不相信 DTO 已替它维护聚合不变量 |
| 版本 | 领域模型按业务行为演进，不直接等同 API、事件或数据库 schema 版本 |
| 权限 | 不决定当前 caller 身份；但只有领域行为能创建合法状态和维护状态迁移 |
| 失败含义 | 违反聚合不变量，例如混合币种；应与 HTTP 字段错误、基础设施失败区分 |

[Order](lab/src/order_contracts/domain/order.py) 也是 frozen dataclass，但多了行为：`Order.create()` 计算领域状态，并拒绝非单币种订单。

### 4. customer view：`CustomerOrderView`

| 维度 | 决策 |
|---|---|
| owner | 客户查询／响应 API；字段集合就是公开读取权限白名单 |
| 信任 | 不能直接 dump domain／ORM；先从已授权的 `Order` 显式 project |
| 版本 | 按客户 API 兼容政策演进；不因内部字段新增而扩张 |
| 权限 | 只暴露 `order_id`、`status`、`total`、`item_count`；没有 customer id、支付引用和内部备注 |
| 失败含义 | projection 错误是服务端缺陷；serialization 失败不应伪装成领域拒绝 |

[project_customer_order()](lab/src/order_contracts/adapters.py) 创建 [CustomerOrderView](lab/src/order_contracts/outbound/views.py)，随后才选择 JSON 表示。

### 5. `OrderCreated` event

| 维度 | 决策 |
|---|---|
| owner | 发布事件的订单服务；与下游消费者共同维护 integration contract |
| 信任 | 从已成功创建的 domain order 显式 project；消费者仍按版本重新验证 bytes |
| 版本 | envelope 的 `schema_version` 明确选择 V1／V2；不能借 domain class 形状隐式版本化 |
| 权限 | 只发布下游获准使用的事实；客户可见字段集合与事件字段集合并不必然相同 |
| 失败含义 | writer projection／serialization 失败是发布侧缺陷；reader schema 不兼容是永久错误，通常不应无限重试 |

[project_order_created_v2()](lab/src/order_contracts/adapters.py) 单独构造 V2 payload 与 envelope。event 是跨服务、可能长期留存的事实，不是“把 response 发到 broker”。

## `to_create_order_command()`：重复是可审计的安全边界

lab 的 mapper 完整代码如下：

```python
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

逐字段写出的价值恰好在“看起来重复”：

| 映射 | 为什么不能视为机械复制 |
|---|---|
| `customer_id` | 允许这项身份进入用例，但不把未来的 `is_admin`、`status` 一并带入 |
| `idempotency_key` | 把格式已验证的 key 传给 application；真正的去重仍需应用层持久化政策 |
| `items` → `lines` | 外部集合名与内部业务语言可以独立演进 |
| `unit_price.amount` → `unit_amount` | 拆开 wire value object，明确 command 需要的精确事实 |
| list-like input → tuple | command 得到不可变快照，不共享调用方的可变容器 |

mapper 是一个可 code review 的 allowlist：新增 request 字段不会自动获得进入应用层的权利；新增 command 字段会迫使编译／测试失败，要求开发者决定来源。字段重复换来的是变更时的显式决策点。

### 两个错误实现

以下代码**仅为反例，不进入 lab**：

```python
# 错误：边界 DTO 被当成 aggregate constructor 参数袋。
order = Order(**request.model_dump())

# 错误：PATCH payload 被直接当成 persistence columns。
repository.update(**payload.model_dump())
```

第一行在当前 lab 会因为字段形状不同而立刻失败；这并不能证明模式安全。只要未来重命名后“刚好匹配”，它就会制造三类耦合：

1. **mass assignment**：客户端能提交或未来 DTO 新增的字段，未经逐字段授权便进入状态，例如 `status`、`internal_note`、`owner_id`。
2. **字段漂移**：request 新增一个兼容字段，domain constructor 的输入面会在没有 mapper diff 的情况下改变；反过来 domain 重命名也会迫使 wire contract 跟着动。
3. **persistence coupling**：`repository.update(**...)` 把 API 字段名、可空语义、默认值和数据库列绑定在一起，绕开领域行为、并发控制与审计。

repository 应接受领域对象、专用 update command 或明确的方法参数；它负责 session／transaction 与持久化映射，而不是让任意 dict 决定写哪些列。

## 协议局部不变量与跨行业务规则

边界判断不应简化为“能放 validator 的都放进去”。要看规则依赖的事实范围和 owner：

| 规则 | 放置位置 | 理由 |
|---|---|---|
| `items` 非空 | `CreateOrderRequest` | 单看 payload 即可判断；空请求没有可解释的创建意图 |
| `quantity` 为严格整数且 1～100 | `CreateOrderItem` | 字段局部协议约束；错误应定位到具体输入路径 |
| payload 内 SKU 不重复 | request model validator | 依赖同一份 payload 的多个 item，仍是入口局部不变量 |
| 整张订单只能使用一种币种（single currency） | `Order.create()` | 约束领域聚合；不能因换成 CLI、批处理或内部调用而绕过 |
| caller 是否有权替 customer 下单 | application | 依赖身份和资源，不是 payload 形状 |
| 库存是否足够 | application／domain service | 依赖并发变化的外部状态 |

[domain test](lab/tests/test_domain_order.py) 直接构造混合 USD／EUR 的 `CreateOrderCommand`，不经过 HTTP request，然后断言 `Order.create()` 抛出包含 `single currency` 的错误。这证明单币种不是“入口已验证过就无需再管”的规则；所有创建路径都必须经过领域行为。

## 值对象共享只因语义相同，不因形状相同

lab 在 inbound、customer view 与 event 中共享 `Money`，因为三处都承诺相同的语义：正数、最多 12 位／2 位小数、ISO 风格三字母大写币种，并在 JSON 中把金额写成精确十进制字符串。

共享前应同时满足：

- 单位、范围、舍入和规范化政策相同；
- 可空、缺省和错误语义相同；
- 版本兼容承诺相同，或值对象足够稳定；
- 序列化形状和敏感性相同。

“同形”远远不够：

- `status: str` 可能分别代表客户公开状态、支付提供方状态和内部工作流状态；枚举值、迁移和兼容政策都不同。
- `id: str` 可能是可公开、不可猜测的 order id，也可能是租户内数据库主键或第三方 provider id；格式相同不代表权限相同。
- `Money` 若某个结算场景允许负数、要求四位小数或携带汇率来源，就应使用另一个语义类型，而不是放宽全局 `Money`。

类型复用应减少同一概念的重复，而不是把不同概念压成一个“万能 schema”。

## 每层该用哪种 Python 表示

| 表示 | 最适合 | 优势 | 不适合／代价 |
|---|---|---|---|
| Pydantic model | HTTP、webhook、event、Settings、outbound JSON contract | 运行时 parse／validate、alias、JSON Schema、稳定 serialization | 不应因便利而吞掉授权、领域行为或 repository boundary |
| stdlib dataclass | application command、轻量不可变领域值／聚合 | framework-independent、构造显式、易于静态分析；`frozen`／`slots` 可表达生命周期 | 不直接验证不可信 JSON；复杂行为仍需方法与测试 |
| 普通 class | 有身份、行为、受控 mutation 或复杂构造流程的 aggregate／domain service | API 可以围绕业务动作设计，不受“字段容器”思维限制 | 需要自己设计 equality、repr、serialization boundary |
| `TypedDict` | 已经是可信 mapping、只需静态描述的内部胶水；或第三方 dict API 的类型视图 | 零运行时包装、适合渐进 typing | 运行时仍是 dict，不会验证、拒绝 extra、冻结或执行 serializer；不能替 Pydantic 边界 |

选择标准不是“哪个类最强”，而是哪一层需要什么保证。对 raw payload 用 `TypedDict` 只会让类型检查器满意，运行时并没有建立信任；对纯 domain object 强行继承 `BaseModel`，则容易把 JSON alias 和 coercion 带进业务核心。

## 出站先 projection，再 serialization

lab 的客户 projection 是明确的字段白名单：

```python
def project_customer_order(order: Order) -> CustomerOrderView:
    return CustomerOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
    )
```

它没有先 dump `Order` 再删字段。其安全属性是**默认不传播**：`Order` 将来新增字段时，客户响应不变；只有显式修改 projection 和 view schema，字段才会出站。[`test_customer_projection_is_an_explicit_whitelist`](lab/tests/test_serialization.py) 用完整 JSON dict 固定了这个集合。

`include`／`exclude` 可以做按调用点裁剪，但不应代替这道长期权限边界。黑名单 `exclude={"internal_note"}` 尤其脆弱：明天新增 `provider_reference` 时，它默认会泄漏。若确实要在同一稳定 view 上返回稀疏字段，可把用户请求的 field set 与服务端 allowlist 求交，再传给 `include`；allowlist 仍由服务端拥有。

## 三种 dump：Python 值、JSON 兼容值与 JSON 文本

对 lab 的 `Money`：

```python
money = Money(amount="12.30", currency="usd")

money.model_dump()
# {'amount': Decimal('12.30'), 'currency': 'USD'}

money.model_dump(mode="json")
# {'amount': '12.30', 'currency': 'USD'}

money.model_dump_json()
# '{"amount":"12.30","currency":"USD"}'
```

三者不能只按“都能打印”来互换：

| API | 返回值 | 适合 | 注意 |
|---|---|---|---|
| `model_dump()` / `mode="python"` | Python dict；可保留 `Decimal`、`datetime`、`SecretStr` 等对象 | 进程内 adapter、测试 Python 值 | 不保证可被标准库 `json.dumps()` 直接编码；也不是 persistence dict |
| `model_dump(mode="json")` | 只含 Pydantic JSON conversion 后的 dict／list／scalar | Web framework 还需要操作结构、签名或 envelope 时 | 仍不是 bytes／str；后续重编码策略会影响签名和字节稳定性 |
| `model_dump_json()` | JSON `str` | 直接需要 JSON 文本时 | 返回 str，不是 bytes；网络发送时仍须明确 UTF-8 与 content type |

`mode="json"` 与 `model_dump_json()` 使用同一 serialization policy；区别是结果容器。不要用 `str(model_dump())` 冒充 JSON。

### `Decimal`、`datetime` 与 `SecretStr`

在 Python mode 中，它们仍是对应 Python 对象；JSON mode 的常见结果是：

```python
{
    "at": "2026-01-02T03:04:05Z",
    "price": "12.30",
    "token": "**********",
}
```

- `Decimal` 默认 JSON 化为字符串，避免先变 binary float；lab 的 `Money.amount` 又用 field serializer 明确固定 `format(value, "f")`。
- aware `datetime` 变为 ISO 8601 字符串；协议仍应明确是否一律 UTC、接受哪些输入 offset，而不是只说“能序列化”。
- `SecretStr` 默认输出掩码，降低 repr／dump 的意外泄漏风险；`get_secret_value()` 仍能取得原文，所以它不是加密、访问控制或日志脱敏系统。

金额不能靠一次 round-trip 猜精度政策。生产契约还需明确 currency minor unit、量化时机、舍入模式和最大范围；这里的 `Money` 选择两位小数是本 lab 的业务约束，不是所有币种的通则。

## `include`／`exclude` 与 unset／default／none

设一个 PATCH DTO：

```python
class PatchProfile(BaseModel):
    display_name: str = "anonymous"
    note: str | None = None


patch = PatchProfile(note=None)
assert patch.model_fields_set == {"note"}
```

各选项回答不同问题：

| 调用 | 输出 | 语义 |
|---|---|---|
| `patch.model_dump()` | `{"display_name": "anonymous", "note": None}` | 全部已声明字段，包括补上的默认值 |
| `exclude_unset=True` | `{"note": None}` | 排除本次构造未显式提供的字段；显式 `null` 仍是 set |
| `exclude_defaults=True` | `{}` | 排除与默认值相等的字段，即使调用者显式提供了同值 |
| `exclude_none=True` | `{"display_name": "anonymous"}` | 排除值为 `None` 的字段，不区分缺失与显式 null |

因此 PATCH 常以 `model_fields_set`／`exclude_unset=True` 区分“未触碰”与“显式清空”，但它仍然不是完整更新语义：

- `None` 是“清空”“恢复默认”还是“不允许”，必须逐字段定义；`exclude_none=True` 会抹掉显式清空意图。
- `exclude_defaults=True` 无法保留“显式把值设回默认”的动作。
- nested object 是整体替换还是递归 merge，不能由 `model_dump()` 猜测。
- 即使 `exclude_unset=True`，把结果直接传给 `repository.update(**changes)` 仍有 mass assignment、字段名耦合、授权绕过与乐观锁缺失。

正确做法是专用 PATCH contract → 显式 update command → authorize → domain behavior → repository 持久化。`include`／`exclude` 是表示选择工具，不是授权引擎或变更语义。

## alias 有输入方向与输出方向

内部 Python 名称和 wire 名称不必相同：

```python
class OrderWire(BaseModel):
    order_id: str = Field(
        validation_alias="orderId",
        serialization_alias="orderId",
    )
```

- `validation_alias` 控制验证时从什么名字读取；
- `serialization_alias` 控制 serialization 时可使用什么名字；
- `model_dump(by_alias=True)`／`model_dump_json(by_alias=True)` 才请求按输出 alias 写出；默认 dump 使用字段名；
- `alias=` 可同时参与输入和输出，但当两个方向需要独立迁移时，分开写更清楚；
- 是否同时接受 Python field name 与 alias，由 `validate_by_name`／`validate_by_alias` 配置决定，不要靠模糊默认值承担兼容政策。

alias 是 wire compatibility 工具，不是领域命名的替代品。若旧客户端发 `orderId`、新内部代码使用 `order_id`，应在 boundary model 吸收差异；不要把 camelCase 传播到 command 和 domain。修改 alias 时同时检查 validation schema、serialization schema、真实 parse 与 dump 测试。

## field serializer、model serializer 与 computed field

[Money](lab/src/order_contracts/value_objects.py) 的现有实现展示了窄范围 field serializer：

```python
@field_serializer("amount", when_used="json")
def serialize_amount(self, value: Decimal) -> str:
    return format(value, "f")
```

`when_used="json"` 让 Python mode 保留 `Decimal`，JSON mode 才变字符串。返回类型注解也帮助 serialization JSON Schema 描述输出为 string。

三种扩展点的合理边界：

| 扩展点 | 适合 | 风险 |
|---|---|---|
| `@field_serializer` | 单字段 wire 格式，例如金额、枚举或时间 | 若偷偷读取外部状态，输出将不再确定；不要在此做授权 |
| `@model_serializer` | 整体 envelope、tagged representation 或必须同时观察多个字段的输出形状 | 很容易变成不可见的字段过滤层；return shape 必须有 schema 与测试 |
| `@computed_field` | 从当前、已获准字段纯计算出的出站值，如 `item_count`／display label | 默认参与 serialization 会扩大公开表面；昂贵计算、I/O、秘密和权限判断不应藏在 property 中 |

本 lab 选择在 projection 时计算 `item_count`，而不是给 domain `Order` 加 Pydantic computed field：customer view 与 event 可以各自决定是否发布。computed field 适合**已经位于该出站 contract 内**的派生表示，不应成为绕过 projection 的捷径。

serializer 应尽量纯、确定、无 I/O；同一对象与同一 serialization context 应产生相同结果。权限或租户差异应先选择不同 projection／view，不能寄希望于某个 serializer 在所有调用路径都收到正确 context。

## subclass serialization、duck typing 与 `SerializeAsAny`

Pydantic v2 对“字段声明为基类，运行时传入子类”的默认 serialization 按**声明类型的 schema**输出。lab 刻意利用这一点：

```python
internal = project_internal_order(order, provider_reference="pay_demo_001")
envelope = CustomerOrderEnvelope(order=internal)  # 注解为 CustomerOrderView

envelope.model_dump(mode="json")
# order 中没有 customer_id / provider_reference / internal_note
```

但调用 `serialize_as_any=True`，或把字段注解成 `SerializeAsAny[CustomerOrderView]`，会启用 duck-typed serialization，按运行时子类字段输出：

```python
envelope.model_dump(mode="json", serialize_as_any=True)
# customer_id、provider_reference、internal_note 重新出现
```

这正是 [`test_serialize_as_any_demonstrates_the_leak_risk`](lab/tests/test_serialization.py) 固定的行为。`SerializeAsAny` 不是永远错误：插件型 payload 或明确承诺保留子类字段的内部协议可能需要它；但在客户响应、安全审计、日志和跨租户数据中，它会把“未来子类新增字段”变成默认公开，必须视为泄漏面变更。

而且默认基类 serialization 只是纵深防御，不是权限证明。最稳妥的客户路径仍是 `Order` → `project_customer_order()` → 精确 `CustomerOrderView`；不要故意把 `InternalOrderView` 塞进客户 envelope，再依赖默认裁剪永远救场。

## JSON round-trip：验证输入契约，不证明业务等价

对稳定出站 contract，最小 round-trip 可以写成：

```python
wire = view.model_dump_json()
again = CustomerOrderView.model_validate_json(wire)
assert again == view
```

它能证明“当前 writer 的输出可被当前 reader 接受”，但不能证明：

- V1 reader 能读取 V2 writer，或反向兼容成立；
- `12.30` 与 `12.3` 的原始字节、签名、展示或审计意义相同；
- timezone normalization、alias 迁移和默认字段保留了原始输入；
- 领域对象经历 response DTO round-trip 后仍拥有相同身份与行为。

serialization 通常是有损 projection：unset 信息、子类字段、secret 原文、原始键顺序和数字文本都可能消失。需要兼容性时，应写 producer/consumer 版本矩阵和 golden payload 测试，而不是只做同版本自环。

### JSON Schema 也有 validation／serialization 两种模式

Pydantic 可以分别描述 reader 与 writer：

```python
input_schema = Money.model_json_schema(mode="validation")
output_schema = Money.model_json_schema(mode="serialization")
```

在当前 lab 中，`Money.amount` 的 validation schema 会生成 number 或 decimal string 两个分支；但 `_validate_money_input()` 的真实 runtime policy 只接受 `Decimal` 或 `str`，JSON number 先解析成 `int`／`float` 后反而会被它拒绝。也就是说，这里还暴露了一个应在生产契约中修正的 **schema/runtime mismatch**：不能把生成出的 number 分支发布给客户端，却在运行时拒绝它。可选择让 validator 与 schema 对齐，或为自定义 validator 提供同样精确的 JSON Schema。serialization schema 则因 serializer 的 `-> str` 而声明 string。validation／serialization 两份 schema 不同可以是有意设计，但每一份都必须与对应 runtime 路径一致。

发布 OpenAPI／AsyncAPI 或 codegen schema 时必须声明用途：

- request body 用 validation schema；
- response／event writer 用 serialization schema；
- alias 政策和 `by_alias` 必须与真实 runtime dump 一致；
- schema 只能描述结构，不能替代授权、跨行单币种、库存或幂等规则。

## 性能：先选对边界，再优化热路径

显式 mapper 和独立 view 会分配对象，但对典型 API，请求解析、网络、数据库和 broker I/O 往往更显著。不要为了省一份小对象复制，把外部 DTO、domain、ORM 和 response 合成一层，换来权限与版本事故。

有测量证据后再做这些优化：

- raw JSON bytes 直接用 `model_validate_json()`，避免先 `json.loads()` 再验证的中间步骤；
- 复用模型类／`TypeAdapter`，不要在请求循环里动态创建 schema；
- 直接需要 JSON 文本时用 `model_dump_json()`，避免先建 JSON-mode dict 再由另一套 encoder 重做；
- 大集合采用分页／流式协议，不能靠跳过 validation 或 `SerializeAsAny` 解决内存问题；
- profile parse、projection、serialization 各阶段，记录 payload 大小和 p95／p99，而不是只跑无代表性的单对象微基准；
- trusted-only 快捷路径必须有调用边界和不变量证明，不能把 `model_construct()` 当普通性能开关。

性能预算应和风险预算一起审查：出站 projection 即使占到可测时间，也可能是值得保留的权限边界。优化目标是减少不必要的转换，不是删除责任分层。

## ORM `from_attributes` 不能替 repository boundary

`model_validate(orm_obj, from_attributes=True)` 能从属性读取数据，适合某些 adapter 内的受控转换；ORM 集成将在第 13 章展开。本章只锁定一条边界：**`from_attributes` 不是 repository／session boundary。**

它不会自动解决：

- transaction 与 session 生命周期；
- lazy loading 引发的 N+1 或已关闭 session 错误；
- optimistic locking、并发写和审计；
- ORM column／relationship 与领域概念的映射；
- 哪些内部属性有权进入 customer view 或 event。

repository 仍负责加载／保存 aggregate 和持久化映射；outbound adapter 仍负责显式 projection。直接 `CustomerOrderView.model_validate(order_row, from_attributes=True)` 即使今天可用，也会把响应契约耦合到 ORM 属性名和加载行为。

## Java／Go 对照：显式 mapper 不是 Python 特例

三种语言的推荐责任链相同：

```text
Controller request DTO
  → application command
  → domain aggregate
  → response DTO / integration event
```

- **Java**：Jackson request DTO + Bean Validation 守 HTTP 结构；Controller／assembler 显式转成 command；application service 授权并调用 aggregate；repository 映射 JPA entity／aggregate；response DTO 由专用 assembler 构造。MapStruct 可以生成机械代码，但 mapping definition 仍应显式列出忽略、重命名和转换，不能用 entity 全字段自动映射替代权限审查。
- **Go**：`encoding/json` struct tags 只决定 wire name，validator 只建立入口局部事实；handler 把 request struct 手写映射为 command，domain constructor 维护单币种等不变量，再手写 response/event struct。Go 的样板更显眼，却也让 code review 一眼看出新增字段是否跨边界；这正是 mapper 的可审计性。
- **Python/Pydantic**：可以把 parsing、validation 和 serialization 写得更紧凑，但 `BaseModel` 的便利没有消除 command、aggregate、projection 与 repository 的 owner 差异。

面试中可以这样概括：Java Controller DTO → command → aggregate → response DTO、Go request struct → command → domain → response struct，与本 lab 完全同构；Pydantic 改善的是边界实现，不是取消边界。

## 评审清单

遇到“少写模型／少写 mapper”的重构，逐项问：

1. 当前对象的 owner 是 HTTP、application、domain、customer API 还是 event consumer？
2. 当前箭头是在 parse、map、act、project，还是 serialize？
3. 新字段是默认传播还是默认阻断？谁有权批准它跨边界？
4. `model_dump()` 的 mode、alias 和 unset／default／none 语义是否与目标协议一致？
5. serializer／computed field 是否纯、确定、无 I/O，是否扩大公开 schema？
6. 是否启用了 `SerializeAsAny` 或把内部子类放进公共 envelope？
7. PATCH 是否区分 missing、explicit null、default 和 nested merge，且通过领域行为？
8. validation 与 serialization JSON Schema 是否分别验证过？
9. round-trip 测的是同版本自环，还是实际 producer/consumer 兼容矩阵？
10. `from_attributes` 是否意外替代了 repository、session 或 projection boundary？

本章的核心不是“每层必须使用不同库”，而是**每个 owner 拥有自己的模型与失败语义，每次跨层都显式选择字段**。Pydantic 在边界上非常强；正因为它能方便地 dump、alias 和 customize，更要把“如何编码”与“有权发布什么”分开。
