# 07 · 序列化与数据泄漏防御：输出也是信任边界

> **本章目标**：把 serialization 当成独立的安全边界，而不是 `model_dump()` 的语法收尾。读完后，应能为 response、event、log、error 分别定义字段白名单，解释 Pydantic v2 的 subclass serialization 与 `serialize_as_any` 风险，并为 field／model serializer、plain／wrap 和 context 划清适用范围。完整分层与 projection 流水线见 [06 · 契约分层与领域边界](06-contract-layering-and-domain-boundaries.md)；本章聚焦字段已经进入内存后，如何防止它从错误通道离开系统。

先运行本章安全基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_serialization.py tests/test_errors.py tests/test_settings.py -v
```

当前应有 31 个测试通过。与本章直接相关的事实是：customer projection 只输出四个获准字段；基类注解默认隐藏运行时子类的内部字段；`serialize_as_any=True` 会恢复这些字段；错误响应不回显非法 input；`SecretStr` 在 Settings repr 中保持掩码。

## 事故开场：代码没有“返回 secret”，为什么日志里仍有？

某订单接口谨慎地从 response 排除了 `internal_note`，团队便认为数据泄漏问题已解决。事故发生时，中间件把整个 `InternalOrderView` 记入结构化日志；异常处理器又把 `ValidationError.errors()` 原样返回。客户响应本身是安全的，但支付引用、内部备注和一段非法客户输入分别从 log 与 error 两条通道离开了系统。

这类事故的共同根因是把“可序列化”误当成“允许发布”。一个值进入受信任内存后，仍可能从多条边离开：

```text
domain / internal model
  ├─ customer response ──► public client
  ├─ integration event ──► other services / long retention
  ├─ structured log ─────► operators / search / vendor
  └─ error response ─────► caller / proxy / monitoring
```

四个接收方、权限面、保留期限和兼容承诺都不同，因此必须有四份政策。**验证 schema 回答“允许什么进入”；出站白名单回答“允许什么从这条通道离开”。两者不能复用一个 model 再靠临时 exclude 补洞。**

## 两阶段安全模型：先 project，再 serialize

在本 lab 中，安全客户路径是：

```text
Order
  │ project_customer_order()：逐字段授权
  ▼
CustomerOrderView
  │ model_dump(mode="json")：选择表示
  ▼
customer response dict
```

[project_customer_order()](lab/src/order_contracts/adapters.py) 是白名单：

```python
def project_customer_order(order: Order) -> CustomerOrderView:
    return CustomerOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
    )
```

projection 决定**哪些事实**进入客户契约；serialization 决定 `OrderStatus`、`Decimal` 等事实**如何表示**。前者是权限和版本决策，后者是编码决策。`model_dump()`、serializer、alias、include／exclude 都不能从对象本身推导当前 caller 的授权。

[`test_customer_projection_is_an_explicit_whitelist`](lab/tests/test_serialization.py) 比只断言“没有 secret”更强：它断言完整输出恰好是 `order_id`、`status`、`total`、`item_count`。新增 domain 字段默认不传播；只有 projection、view 与测试的显式 diff 才能扩大公开面。

## 三种 dump 的安全语义

[Money](lab/src/order_contracts/value_objects.py) 让三种模式的差异可见：

```python
money = Money(amount="12.30", currency="usd")

money.model_dump()
# {'amount': Decimal('12.30'), 'currency': 'USD'}

money.model_dump(mode="json")
# {'amount': '12.30', 'currency': 'USD'}

money.model_dump_json()
# '{"amount":"12.30","currency":"USD"}'
```

| 调用 | 返回类型与值 | 安全审查重点 |
|---|---|---|
| `model_dump()`／`mode="python"` | Python `dict`；可能保留 `Decimal`、`datetime`、`SecretStr` 等对象 | 不是“内部所以安全”；dict 仍可能被 logger、ORM helper 或另一 encoder 继续展开 |
| `model_dump(mode="json")` | JSON-compatible Python dict／list／scalar；本例金额为 string | 已选择 JSON 表示，但还没有决定发送给谁；不要因此跳过 projection |
| `model_dump_json()` | JSON `str` | 已形成可直接传播的文本，调用前完成白名单与 redaction，发送前执行大小限制；返回的不是 bytes |

mode 改变表示，不改变权限。Python mode 中的 `SecretStr` 对象也不是“不会泄漏”：后续代码若主动调用 `get_secret_value()`、自定义 encoder 或 serializer，原文仍可离开。

## include／exclude 是表示选择，不是权限模型

各参数的语义是数据状态，不是访问控制：

| 参数 | 保留／排除规则 | 典型用途 | 权限陷阱 |
|---|---|---|---|
| `include={...}` | 只保留指定字段；支持 nested selector | 稳定 view 上的稀疏字段集 | 用户请求集合必须先与服务端 allowlist 求交，不能原样透传 |
| `exclude={...}` | 排除指定字段；支持 nested selector | 临时省略已获准字段 | 黑名单对未来新增字段默认开放；最不适合隐藏 secret |
| `exclude_unset=True` | 排除构造时未显式设置的字段 | PATCH 表达 missing 与 explicit value | 显式 `None` 仍会输出；也不证明 caller 有权更新该字段 |
| `exclude_defaults=True` | 排除与默认值相等的字段 | 减少冗余表示 | 会丢失“调用者显式设回默认值”的动作语义 |
| `exclude_none=True` | 排除所有 `None` 值 | 某些 wire contract 的 omission 政策 | 混淆 missing 与 explicit null，可能吞掉清空意图 |

一个最小例子固定后三项区别：

```python
class PatchProfile(BaseModel):
    display_name: str = "anonymous"
    note: str | None = None


patch = PatchProfile(note=None)
assert patch.model_fields_set == {"note"}
assert patch.model_dump(exclude_unset=True) == {"note": None}
assert patch.model_dump(exclude_defaults=True) == {}
assert patch.model_dump(exclude_none=True) == {"display_name": "anonymous"}
```

`InternalOrderView.model_dump(exclude={"internal_note", "provider_reference"})` 不是可靠客户权限模型：今天若新增 `fraud_score`，黑名单没有任何失败信号，它会默认输出。禁止复用 `InternalOrderView` 后靠 exclude 拼装 public response；应先构造精确的 `CustomerOrderView`。

即使 include 白名单比 exclude 安全，也应把稳定权限集合落实为独立 view schema 与 projection。调用点散落的 include set 缺少 owner、JSON Schema 和集中兼容审查，容易在多个 endpoint 之间漂移。

## Money field serializer：窄、纯、只管表示

lab 的完整 serializer 如下：

```python
class Money(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: MoneyAmount
    currency: CurrencyCode

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")
```

这个设计有三个值得保留的边界：

1. 只负责 `amount` 的 wire representation，不决定订单总额是否可见。
2. `when_used="json"` 让 Python mode 保留 `Decimal`，JSON mode 才输出精确十进制字符串。
3. `-> str` 使 serialization schema 有机会准确描述 writer 输出；schema 仍需对照真实 dump 测试。

serializer 不应查询数据库、调用 secret manager、检查当前用户权限或改变领域状态。隐藏 I/O 会让一次 dump 产生 N+1、超时和不可重放输出；隐藏授权则会让任何忘记传 context 的调用点变成安全分支。

### field 与 model，plain 与 wrap

| 选择 | 行为 | 适合 | 主要风险 |
|---|---|---|---|
| field serializer | 只定制一个字段 | 金额、时间、枚举或已获准字段的格式 | 在字段函数中做跨字段授权，政策会碎片化 |
| model serializer | 定制整个模型结果 | tagged representation、特殊 envelope、真正需要观察多个字段的稳定 wire shape | 容易暗中删加字段，实际输出与声明 schema 漂移 |
| `mode="plain"` | serializer 的返回值替代正常 serialization | 完全拥有一个小而明确的输出表示 | 不再自动获得默认 handler 的 nested serialization；必须自己维护完整契约 |
| `mode="wrap"` | 收到 handler，可在默认结果前后包裹／调整 | 保留正常 nested 行为，只加 envelope 或集中后处理 | 修改 handler 结果仍可能扩大字段面；顺序与 nested policy 要测试 |

例如 wrap model serializer 先委托 Pydantic，再添加固定 discriminator：

```python
class TaggedOrderView(BaseModel):
    order_id: str

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        data = handler(self)
        return {"kind": "customer_order", **data}
```

plain serializer 则完全接管结果。接管越多，越要同时测试 Python／JSON mode、include／exclude、alias、nested model 和 serialization JSON Schema；“能 dump 出 dict”不是契约一致性证明。

### serialization context 是参数，不是授权来源

Pydantic 允许调用方把 context 传给 serializer：

```python
from pydantic import BaseModel, FieldSerializationInfo, field_serializer


class ContextView(BaseModel):
    note: str

    @field_serializer("note", mode="plain")
    def serialize_note(self, value: str, info: FieldSerializationInfo) -> str:
        allowed = isinstance(info.context, dict) and info.context.get("show_note")
        return value if allowed else "[redacted]"


view = ContextView(note="internal-only")
view.model_dump(context={"show_note": True})
# {'note': 'internal-only'}
```

context 适合 locale、明确的格式版本或已经由上游批准的展示参数。它只是 serializer 调用方提供的数据：`{"show_note": True}` 本身不是认证或授权证明。若公共 response 的安全依赖每个调用点都传对布尔值，一次漏传、误传或内部复用就会改变输出。

权限差异优先用不同 projection／view 类型表达；context 只在获准字段集合已经确定后调整表示。context 内容也不要塞整个 request、session、token 或 secret，以免 serializer 获得不必要的能力并难以测试。

### computed field 也扩大出站面

`@computed_field` 默认参与 serialization。即使它不存储在模型字段中，依然是公开 schema 的一部分：新增 computed field 应接受与新增普通 response 字段相同的权限、兼容和泄漏审查。它应是便宜、纯、确定的派生值；不要在 property 中读取 lazy ORM relationship、当前用户或 secret。

本 lab 在 `project_customer_order()` 中显式计算 `item_count`，因此 event 与 customer response 可独立决定是否发布，而不是让 domain object 上的一个 computed serializer 自动传播到所有通道。

## Pydantic v2 默认按注解类型序列化子类

[outbound views](lab/src/order_contracts/outbound/views.py) 有一个有意的继承关系：

```python
class CustomerOrderView(BaseModel):
    order_id: OrderId
    status: OrderStatus
    total: Money
    item_count: StrictInt


class InternalOrderView(CustomerOrderView):
    customer_id: CustomerId
    provider_reference: StrictStr | None
    internal_note: StrictStr | None


class CustomerOrderEnvelope(BaseModel):
    order: CustomerOrderView
```

把 `InternalOrderView` 实例放入 `CustomerOrderEnvelope.order` 时，运行时对象确实携带内部字段；但 Pydantic v2 对 BaseModel 等 model-like subclass 默认按**字段注解中的 schema**序列化，而不是自动遍历运行时子类的全部字段：

```python
internal = project_internal_order(order, provider_reference="pay_demo_001")
envelope = CustomerOrderEnvelope(order=internal)

envelope.model_dump(mode="json")
# {
#   'order': {
#     'order_id': 'ord_0123456789ab',
#     'status': 'pending_payment',
#     'total': {'amount': '24.60', 'currency': 'USD'},
#     'item_count': 1,
#   }
# }
```

因此 `customer_id`、`provider_reference`、`internal_note` 默认不输出。[`test_base_annotation_hides_internal_subclass_fields_by_default`](lab/tests/test_serialization.py) 锁定了这一行为。

这是一层有价值的 defense in depth，但不是 permission model：

- 注解若被重构成 `InternalOrderView`，公开面会扩大；
- 基类以后新增字段，envelope 仍会输出该字段；
- custom serializer 可以自行返回额外字段；
- 另一条代码路径可能直接 dump `internal`；
- 运行时选项可以恢复 duck typing。

所以生产路径仍应 `Order → project_customer_order() → CustomerOrderView`，而不是故意把内部子类传进去，再依赖默认裁剪替代 projection。

## `serialize_as_any` 会恢复运行时字段

两种方式可选择 duck-typed serialization：字段声明使用 `SerializeAsAny[CustomerOrderView]`，或调用时传 `serialize_as_any=True`。后者对 lab envelope 的影响是：

```python
unsafe = envelope.model_dump(mode="json", serialize_as_any=True)

unsafe["order"]["customer_id"]
# 'cus_0123456789ab'

unsafe["order"]["provider_reference"]
# 'pay_demo_001'
```

`internal_note` 也重新成为字段，即使当前值是 `None`。这与 [`test_serialize_as_any_demonstrates_the_leak_risk`](lab/tests/test_serialization.py) 的实际输出一致。

`SerializeAsAny` 不是“更完整所以更正确”。它把未来子类新增字段改成默认传播，绕过基于注解 schema 的收敛。只在契约**明确要求多态输出**时局部使用，例如一个受控插件 envelope 确实承诺保留每个注册 subtype 的字段；同时必须：

- 限定允许的 subtype，不接受任意对象；
- 为每个 subtype 固定完整 golden payload／serialization schema；
- 证明接收者有权看到 subtype 的全部字段；
- 测试未来新增敏感字段不会未经审查传播；
- 避免在顶层或公共 helper 中全局设置 `serialize_as_any=True`。

对客户 response、日志、审计 export 和跨租户 payload，默认拒绝 duck typing 是更稳健的政策。

## `SecretStr` 是防误展示，不是秘密系统

`SecretStr` 的价值很具体：默认 repr／str 和 JSON serialization 使用掩码，降低模型被打印或普通 dump 时的偶发泄漏。[`test_settings_repr_redacts_payment_secret`](lab/tests/test_settings.py) 证明 `repr(settings)` 不包含 webhook secret。

但边界也必须写清：

- 它不加密底层值，不保证进程内存被清除，也不阻止 debugger／heap dump 读取；
- 它不负责 secret 的获取、轮换、租户隔离、访问审计或最小权限；
- `secret.get_secret_value()` 会主动取出原文，此后普通 `str`、异常、日志和返回值都由调用方负责；
- custom serializer 若返回 `get_secret_value()`，会有意绕过默认掩码；
- 把 SecretStr 当 dict key、拼入 URL、header debug log 或 error context，同样可能泄漏。

只有在真正调用提供方时才在最窄作用域取原文，不要先展开成普通 string 再跨多层传递。日志记录“secret configured／provider name／rotation version”之类非秘密元数据，而不是值、前缀或可离线猜测的 hash。

## response、event、log、error：四份白名单

| 通道 | owner／消费者 | 白名单原则 | 禁止的捷径 |
|---|---|---|---|
| response | endpoint 与特定 caller | 每个角色／资源建立精确 response DTO；字段名、null、alias、兼容均是公开 API | 复用 `InternalOrderView` 后靠 exclude 拼权限；直接 dump domain／ORM |
| event | producer 与版本化 consumer | 每个 event type/version 显式 payload；只发布完成下游用例所需的稳定事实 | 把 response DTO 或 aggregate 全量发送；依赖 broker 私有便忽略 PII 与长期保留 |
| log | 服务 owner、运维、日志平台 | 事件名、opaque id、结果、耗时、稳定错误分类；按数据分类做 redaction／截断／采样 | `logger.info("%r", model)`、完整 request/response、token、secret、支付引用或异常 input |
| error | API caller／consumer adapter | 稳定错误 code、可公开 reason/type、字段 path、correlation id | 原样返回 `ValidationError.errors()`／`str(error)`、内部 exception、SQL、URL、raw input 或 stack trace |

同一个字段在不同通道的决定可以不同。`customer_id` 也许是 OrderCreated consumer 的必要关联键，却不应出现在公开客户响应；支付 provider reference 也许只属于受限运营视图，不应进入普通 log 或公共 event。所谓“非 secret”不等于“所有通道均可见”。

### error 需要重新 project

Pydantic `ValidationError` 的结构化 item 可能包含 `input`、`ctx` 和文档 URL；其中 input 正是攻击者提供的原值，ctx 也可能含不适合公开的对象。lab 没有直接序列化它，而是显式降维：

```python
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
```

[`test_error_response_exposes_type_and_loc_but_not_input`](lab/tests/test_errors.py) 输入 `top-secret-customer-value`，并断言最终 JSON 中没有该值。这里只公开稳定的 type 与 loc；国际化 message、内部诊断和原始 input 可以进入访问受控、经过 redaction 的服务端观测路径，但不能自动回显。

### log 不是较宽松的 response

日志通常保留更久、可全文搜索、会复制到 vendor 或数据湖，并向更多人开放。应设计专用 structured log event，而不是给业务 model 加一个“日志 serializer”。推荐记录：

```text
event=order_create_rejected
request_id=req_...
error_kind=validation
error_types=[string_pattern_mismatch, too_short]
paths=[customer_id, items]
```

不记录完整 payload、SecretStr 原文、idempotency key、用户自由文本或 stack trace 中的 SQL 参数。若必须关联实体，优先使用已批准的 opaque id；hash 也可能被字典攻击、跨数据集关联，必须按组织的数据分类政策处理，不能自动视为匿名化。

## validation schema 与 outbound schema 必须分离

`CreateOrderRequest` 允许客户提交 `customer_id`、`idempotency_key` 和 item 明细；`CustomerOrderView` 允许服务返回 order id、状态、总额和 item count。两者不是同一 field set 的 validation／serialization mode，而是不同 owner 的模型。

```python
request_schema = CreateOrderRequest.model_json_schema(mode="validation")
response_schema = CustomerOrderView.model_json_schema(mode="serialization")
```

`mode="validation"` 与 `mode="serialization"` 能表达同一模型 reader／writer representation 的差异，例如 serializer 把 Decimal 输出成 string；它们不会自动删除无权出站的字段。**权限分离靠不同 request/view/event/error 模型和显式 projection，schema mode 只负责准确描述各自方向。**

安全测试至少包含：

- 完整相等断言或 reviewed golden，不能只检查一两个字段存在；
- 明确的 negative assertion，覆盖已知高风险字段；
- runtime subclass 与 `serialize_as_any` 回归；
- validation／serialization schema diff 的人工审查；
- 错误、日志 adapter 不含 raw input／secret 的测试；
- event 每个版本的 producer/consumer 兼容矩阵。

## Java／Go 对照

### Java：`@JsonView` 与专用 DTO

Jackson `@JsonView` 可以按 view group 选择字段，适合受控、较简单的表示差异；风险与 Pydantic 调用点 exclude 类似：Controller 忘记选择 view、字段被加入错误 group、继承 group 变宽，都可能改变输出。它也容易让一个 entity／DTO 同时承载多个权限面。

高风险公开 API 通常更适合专用 response DTO + assembler：Controller request DTO → command → aggregate → `CustomerOrderResponse`／`OrderCreatedEventV2`。Jackson annotation 只决定这些出站 DTO 怎么编码，不决定 entity 的所有字段是否获准发布。Bean Validation 的 request schema 也不应复用为 response permission schema。

### Go：`json:"-"` 与显式 response struct

Go 的 `json:"-"` 能永久排除某个 struct 字段，`omitempty` 能按零值省略字段；两者都不是多角色权限模型。复用内部 struct 时，未来新增 exported field 若没有正确 tag，`encoding/json` 可能用字段名默认输出；`omitempty` 只看值，不看 caller 权限。

更可审计的方式是手写精确 response／event struct，并从 domain 逐字段赋值：

```go
type CustomerOrderResponse struct {
    OrderID   string `json:"order_id"`
    Status    string `json:"status"`
    Total     Money  `json:"total"`
    ItemCount int    `json:"item_count"`
}
```

这与 `project_customer_order()` 的价值相同：内部 struct 新增字段不会默认传播，code review 能看到公开面变化。日志和 error 也使用各自的小 struct，不 marshal 完整 request／aggregate。

## 面试场景：先问通道，再选工具

### 场景一：运营与客户只差两个字段，能否复用 DTO？

先问两个 audience 的授权、版本和发布频率是否相同。若客户面高风险，使用独立 `CustomerOrderView` 和 `InternalOrderView` projection；不要把 internal 作为主模型再散落 exclude。继承可减少声明重复，但不能替 projection 与完整输出测试。

### 场景二：多态响应是否一律开启 `serialize_as_any`？

不。先定义封闭 discriminator union 和每个 subtype 的公开 schema；只有契约明确承诺 runtime subtype 字段时，才对该字段局部启用 `SerializeAsAny` 或更直接地声明 union。全局 runtime flag 会让未来内部字段默认外泄。

### 场景三：serializer context 能否放当前用户权限？

技术上能读取 context，架构上不应让它成为唯一授权点。application 先授权并选择 projection；serializer context 只调 locale、format version 等表示。否则每个 dump 调用点都成为安全关键点。

### 场景四：SecretStr 已掩码，能否打印整个 Settings／request？

不能据此得出一般结论。只有 SecretStr 字段享受默认掩码，其他 token、PII、自由文本和 nested object 仍会显示；custom serializer 与 `get_secret_value()` 还能恢复 secret。日志必须有自己的 allowlist。

### 场景五：返回 Pydantic 的 `errors()` 是否足够安全？

不。错误 item 可能包含 raw `input`、`ctx` 与内部 URL。像 `to_error_response()` 一样重新 project 成稳定 code／type／path，并为非法输入和敏感字符串写 negative test。

## 出站安全评审清单

1. 这是 response、event、log 还是 error？接收者、权限和保留期限是谁拥有？
2. 是否先 project 成该通道的精确模型，再 serialize？
3. 输出测试是否断言完整白名单，而不只是当前已知 secret 的黑名单？
4. include／exclude 是否只在已获准 view 上做表示裁剪？
5. serializer 是 field 还是 model、plain 还是 wrap？是否纯、确定、无 I/O？
6. context 是否只调表示，而非充当认证／授权证明？
7. model-like subclass 是否可能进入基类字段？是否有人启用 `SerializeAsAny`／`serialize_as_any=True`？
8. computed field、alias 或 custom serializer 是否悄悄扩大 serialization schema？
9. `SecretStr.get_secret_value()` 在哪里调用，原文随后能到哪些日志、异常和返回路径？
10. validation schema 与 response／event／error serialization schema 是否由不同 owner 审查？

最终原则很窄也很强：**每条出站通道都有显式白名单；serializer 只编码已获准事实；新增内部字段默认不能离开系统。**
