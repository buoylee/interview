# 02 · 字段语义、类型与 coercion：把“可转换”变成显式政策

> **本章目标**：把字段拆成彼此独立的语义维度，并为 HTTP、Webhook、MQ、Settings 写出逐字段 coercion policy。可运行事实以 [Order Contracts Lab](lab/README.md) 的 `OrderId`、`CurrencyCode`、`Money`、`CreateOrderItem` 和 [test_value_objects.py](lab/tests/test_value_objects.py) 为准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_value_objects.py tests/test_create_order.py -v
```

当前应有 10 个测试通过。它们固定了三项不能靠印象回答的契约：ID 和 quantity 不接受“看起来能转”的值，currency 允许有意的规范化，Money 拒绝 binary float。

## 事故开场：`quantity="2"` 为什么不能“帮客户端转一下”？

订单接口曾把字符串数量、布尔值和整数都交给宽松的 `int` 字段。于是下面三个来源最终都得到 `quantity == 1`：

```json
{"quantity": 1}
{"quantity": "1"}
{"quantity": true}
```

它们在业务上不是同一种输入。第一个符合 JSON 契约；第二个可能是客户端 schema 漂移；第三个利用了 Python 中 `bool` 是 `int` 子类这一事实。若入口把差异静默抹平，监控只看见“合法订单”，而看不见生产者已经偏离协议。

本 lab 因此把数量定义为：

```python
Quantity = Annotated[StrictInt, Field(ge=1, le=100)]
```

`StrictInt` 决定输入表示必须真的是整数，并拒绝 `"2"` 与 `True`；`Field(ge=1, le=100)` 再限制值域。**coercion 不是便利开关，而是每个信任边界、每个字段都要审查的兼容政策。**

## 字段有五个独立维度

讨论一个字段时，至少分开问五个问题：

1. **required**：输入能否省略这个 key？
2. **nullable**：key 出现时，值能否是 `None`／JSON `null`？
3. **default**：省略后是否使用固定值？
4. **default_factory**：省略后是否为这次实例动态生成值？
5. **coercion**：输入表示不完全匹配 annotation 时，是否允许转换？

required／nullable 是最容易混淆的 2×2：

```python
from pydantic import BaseModel, Field


class FieldMatrix(BaseModel):
    # required + non-nullable
    account_id: str

    # required + nullable：key 必须出现，但值可以是 null
    middle_name: str | None

    # not required + non-nullable：省略时取固定 default
    locale: str = "zh-CN"

    # not required + nullable：省略与显式 null 都得到 None
    referral_code: str | None = None

    # not required + non-nullable：每个实例动态生成
    tags: list[str] = Field(default_factory=list)
```

| 输入语义 | non-nullable | nullable |
|---|---|---|
| required | `account_id: str` | `middle_name: str | None` |
| not required | `locale: str = "zh-CN"` | `referral_code: str | None = None` |

本章把 **optional** 严格用作 “not required／key 可以省略”，把 **nullable** 用作“值可以是 `None`”。Python typing 里的 `Optional[T]` 实际是 `T | None`，描述的是 nullable，名字却容易让人误以为字段 optional；判断输入是否可省略，仍要看有没有 default／`default_factory`。

关键结论是：**`str | None` 只扩大“允许的值集合”，不会自动给字段添加默认值。** `middle_name` 缺失仍产生 `type="missing"`；传入 `middle_name=None` 才是合法。Pydantic v2 不再像 v1 那样给 `Optional[T]` 隐式补 `None`。

还要区分“省略”和“显式传 `None`”。`locale` 省略会得到 `"zh-CN"`，但 `locale=None` 仍因 non-nullable 而失败；默认值不是允许 `null` 的许可证。若 PATCH 需要表达“未提供”“明确清空”“设置新值”三态，不能只靠 `T | None = None`，应另设 patch DTO 或使用字段是否被设置的信息。

### annotation、赋值与 `Field` 各管什么

| 语法元素 | 核心职责 | 不代表什么 |
|---|---|---|
| `name: T` | 声明值的类型空间；`T | None` 决定 nullability | 不自动决定默认值 |
| `= value` | 声明固定 default，因此字段可省略 | 不会把 annotation 扩成可接受 `None` |
| `= Field(...)` | 附加约束、alias、schema/展示元数据；若没有 `default`，字段仍 required | 右侧有赋值符号不等于“有默认值” |
| `Field(default=...)` | 显式固定 default | 不应与 `default_factory` 同时给出 |
| `Field(default_factory=...)` | 每个实例调用工厂生成默认值 | 不是输入 normalization |

例如 `name: str = Field(frozen=True)` 仍然 required；为了类型检查器和读者，不建议用 `Field(...)` 的省略号来强调 required。另一个生产注意点是：默认值默认不验证；若默认值来自易错配置或生成逻辑，可使用 `validate_default=True` 或模型配置，但要把这项成本和失败时机写进测试。

### mutable defaults：Pydantic 会保护你，但意图仍应显式

普通 Python 函数参数不能安全地写 `items=[]`。Pydantic 对不可 hash 的字段默认值会在每次模型创建时 deep copy，所以两个模型通常不会共享同一个 list：

```python
class Batch(BaseModel):
    items: list[str] = []  # Pydantic 会为实例复制
```

这不意味着推荐依赖隐藏复制。`Field(default_factory=list)` 更清楚地表达“每个实例一份”，也与 dataclass 的规则一致，并避免大型默认对象的无意深复制成本。工厂本身也应无副作用、可测试；若依赖前面已验证的字段，还会受字段声明顺序影响。

## `Annotated`：把可复用类型与字段位置解耦

lab 没有在每个模型字段上重复正则和 strict，而是把值对象契约做成 `Annotated` alias：

```python
OrderId = Annotated[
    StrictStr,
    Field(pattern=r"^ord_[0-9a-f]{12}$"),
]

Sku = Annotated[
    StrictStr,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._-]+$",
    ),
]
```

职责可以按“先定集合，再收窄”理解：

- annotation／`StrictStr` 决定基本输入类型与 strict 行为；
- `StringConstraints` 提供字符串专属的长度、pattern、去空格、大小写等约束或变换，适合组成可复用字符串类型；
- `Field` 提供字段级约束和元数据，包括数值范围、default、alias、discriminator、JSON Schema 描述等；
- `Annotated[T, ...]` 只是把这些 metadata 绑定到 `T`，让 alias 能跨模型复用；静态类型工具仍把它看成 `T`。

这不是“后面的约束覆盖前面的类型”。基本类型先定义候选值空间，约束再缩小它。若把 `Field` 放在 union 的某个成员内，它可能只作用于该成员；字段级 metadata 应放在顶层 union 上。validator metadata 的执行次序属于下一章的验证管线，本章不展开。

`Annotated` 也有一个静态工具边界：`default`、`default_factory`、`alias` 会影响合成的 `__init__` 签名，类型检查器通常只理解普通赋值形式。因此，可复用的值约束适合放 alias；模型字段自己的 default 与 alias 优先写成 `field: T = Field(...)`。

### 三种 alias 的方向与优先级

```python
class PartnerOrder(BaseModel):
    order_id: OrderId = Field(
        alias="legacyOrderId",
        validation_alias="orderId",
        serialization_alias="order_id",
    )
```

| 参数 | validation 输入 | serialization 输出（`by_alias=True`） |
|---|---|---|
| `alias="x"` | 使用 `x` | 使用 `x` |
| `validation_alias="x"` | 只在读入时使用 `x` | 不影响输出 |
| `serialization_alias="x"` | 不影响读入 | 只在输出时使用 `x` |

同一字段同时设置时，明确的单向 alias 优先：validation 阶段 `validation_alias` 高于 `alias`，serialization 阶段 `serialization_alias` 高于 `alias`。若模型还配置 `alias_generator`，显式字段 alias 与生成 alias 的关系由 `alias_priority` 控制。

不要把 alias 当作无期限兼容层。它只改变键名解析／输出，不会自动记录旧键使用率，也不会解决同一 payload 同时出现新旧键时的业务冲突。迁移期应有版本、指标、冲突测试与下线日期。

## lab 的三列 coercion 决策矩阵

下表直接对应 [test_value_objects.py](lab/tests/test_value_objects.py) 与 [test_create_order.py](lab/tests/test_create_order.py)。“错误 type”是 `ValidationError.errors()[0]["type"]`，不是面向用户的文案。

| 输入表示 | 理由 | 错误 type |
|---|---|---|
| `CreateOrderItem.quantity`: 接受 Python／JSON 整数 `2`；拒绝字符串 `"2"` 和布尔值 `true` | 数量的 wire type 是整数；转换会隐藏生产者漂移，`StrictInt` 还阻断 `bool <: int` 的陷阱 | `"2"`／`True` → `int_type`；合法整数但越界 → `greater_than_equal` 或 `less_than_equal` |
| `CurrencyCode`: 接受字符串 `" usd "` 并规范成 `"USD"`；拒绝非字符串与非三位代码 | 空白和大小写不改变 ISO 风格币种语义，属于有意 normalize；数字转字符串没有同等语义依据 | 非字符串 → `string_type`；规范化后不匹配 → `string_pattern_mismatch` |
| `Money.amount`: Python mode 接受 `Decimal("12.30")` 或十进制字符串 `"12.30"`；JSON wire 只接受十进制字符串；拒绝 `12.30` float 和整数 `12` | 在进入 `Decimal` 前阻断 binary float 与形状漂移；金额表示、精度和输出格式都必须稳定 | float／int → `value_error`；无法解析的字符串 → `decimal_parsing`；精度/范围违反相应 Decimal 约束 type |

可执行事实：

```python
from pydantic import TypeAdapter

from order_contracts.inbound.create_order import Quantity
from order_contracts.value_objects import CurrencyCode, Money

assert TypeAdapter(Quantity).validate_python(2) == 2
assert TypeAdapter(CurrencyCode).validate_python(" usd ") == "USD"

money = Money.model_validate({"amount": "12.30", "currency": "usd"})
assert money.model_dump(mode="json") == {
    "amount": "12.30",
    "currency": "USD",
}
```

注意错误码的来源：Money 的 float／int 被 `_validate_money_input` 主动拒绝，所以当前 lab 锁定的是通用 `value_error`；若以后改用 Pydantic 内建 strict Decimal，错误 type 可能改变。错误 type 是对外错误映射和测试的一部分，修改实现时必须当作契约变更审查。

## Python mode 与 JSON mode：strict 不是同一张接受表

Pydantic 有 Python、JSON 和 strings 三种输入模式。strict 大体减少转换，但它不是“所有模式只接受目标类实例”。JSON 本身没有 `date`、`datetime`、`UUID`、`Decimal` 对象，只能用 string／number／boolean／null／array／object 表示；因此部分类型在 JSON strict 下仍允许其标准字符串表示。

```python
from datetime import date
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

date_adapter = TypeAdapter(date)
uuid_adapter = TypeAdapter(UUID)

# Python mode + strict：字符串不是 date / UUID 实例，均失败
try:
    date_adapter.validate_python("2026-07-15", strict=True)
except ValidationError as exc:
    assert exc.errors()[0]["type"] == "date_type"

try:
    uuid_adapter.validate_python(
        "12345678-1234-5678-1234-567812345678",
        strict=True,
    )
except ValidationError as exc:
    assert exc.errors()[0]["type"] == "is_instance_of"

# JSON mode + strict：标准 JSON 字符串是这两种 wire representation
assert date_adapter.validate_json('"2026-07-15"', strict=True).isoformat() == "2026-07-15"
assert str(
    uuid_adapter.validate_json(
        '"12345678-1234-5678-1234-567812345678"',
        strict=True,
    )
) == "12345678-1234-5678-1234-567812345678"
```

所以测试必须调用生产真实入口：HTTP framework 已经解成 dict 时通常是 Python mode；直接处理 raw body／MQ bytes 时可能走 `model_validate_json()`／`validate_json()`。不要只测其中一种再推断另一种。

### 为什么 Settings 可以采用不同策略

Settings 的存储介质天然是文本。环境变量里的超时 `"5"` 并不表示部署工具违反了 JSON schema，因为环境变量根本没有 JSON integer 类型。lab 因此只对已知格式做窄转换：

```text
ORDER_PAYMENT__TIMEOUT_SECONDS="5"   -> 5
ORDER_ALLOWED_CURRENCIES="usd, eur" -> ("USD", "EUR")
```

`"3.0"` 不在整数文本语法内，仍由 `StrictInt` 产生 `int_type`；CSV 只在自定义 settings source 中拆分，再由每个 `CurrencyCode` 规范化。这个策略不是让 Settings 全局 lax，而是把“介质必然文本”显式编码在 source／字段上。

## HTTP／Webhook／MQ／Settings 的逐字段 coercion policy

下面的表是本 lab 的边界政策，而不是 Pydantic 的通用默认值。

| 边界与字段 | 接受并可能 normalize | 明确拒绝 | 决策依据 |
|---|---|---|---|
| HTTP `customer_id`、`idempotency_key`、`sku` | 符合 pattern 的 string | number、bytes、自动 `str(...)` | 标识符的词法形式属于协议，`StrictStr` 防止信息丢失 |
| HTTP `items[].quantity` | JSON integer `1..100` | `"2"`、`2.0`、`true`、越界整数 | 数量 wire type 必须稳定；错误落在 `items.0.quantity` |
| HTTP `items[].unit_price.amount` | JSON decimal string，如 `"12.30"` | JSON number、integer、NaN/Infinity | 避免 binary float，并保留小数表示政策 |
| HTTP `items[].unit_price.currency` | string；trim + upper，如 `" usd "` → `"USD"` | 非 string、规范化后非三位大写字母 | 只允许语义等价的 normalize |
| Webhook `event_id`、`provider_reference`、`order_id` | 符合各自 pattern 的 string | number-to-string | 第三方协议字段需要可审计的原始表示 |
| Webhook `schema_version` | 原始 JSON integer `1` | `true`、`1.0`、`"1"` | 版本是分派键，禁止相等但形状不同的值；当前失败为 `value_error` |
| Webhook `event_type` | 精确 Literal `payment.succeeded`／`payment.failed` | 大小写修正、未知 tag | discriminator 不能猜测；未知值为 `union_tag_invalid` |
| Webhook `occurred_at` | JSON RFC 3339 风格、有时区的 datetime string | naive datetime string | 时间线事件必须有 offset；naive 输入为 `timezone_aware` |
| MQ envelope `event_id`、`event_type` | strict string；`event_type` 还须匹配 Literal | number-to-string、未知事件名 | header 决定路由，envelope 使用 `extra="forbid"` |
| MQ envelope `schema_version` | 原始 JSON integer `1`／`2` | `true`、float、未知版本 | 它既是 strict header 又是 union discriminator；不做跨版本猜测 |
| MQ envelope `occurred_at` | 有时区 datetime string | naive datetime | 保证跨服务时间语义；当前使用 `AwareDatetime` |
| MQ payload `total`、V2 `item_count` | Money decimal string/currency normalize；V2 item_count 为 strict `1..100` | float 金额、字符串 item_count | 复用值对象，但版本 payload 的 unknown-field 政策另行决定 |
| Settings `environment`、`log_level` | 精确 Literal string；环境键本身大小写不敏感 | 猜测未知枚举值、自动大小写修正 value | 值的枚举仍是部署契约，键名兼容不等于值兼容 |
| Settings `allowed_currencies` | CSV string 拆分，再逐项 trim + upper | 非法币种 token | 环境介质是文本，CSV 是显式 source policy |
| Settings `payment.base_url`、`webhook_secret` | URL／秘密的文本表示；秘密用 `SecretStr` | 无效 URL、缺失 required secret | 启动时 fail fast；`SecretStr` 只防 repr 泄漏，不替代 secret manager |
| Settings `payment.timeout_seconds` | 纯 ASCII 十进制文本 `"5"` → int `5` | `"3.0"`、符号/空白等未声明格式、越界值 | 只补偿环境变量的文本介质，不接受任意数字语法 |

Webhook 还有一个比字段 coercion 更早的边界：lab 的 adapter 先对原始 bytes 验 HMAC，再解析 JSON。重编码后的对象不能替代签名覆盖的原始输入。

## Decimal：选择十进制路径，不等于解决了货币

lab 的 `MoneyAmount` 有两层防线：

```python
MoneyAmount = Annotated[
    Decimal,
    Field(gt=Decimal("0"), max_digits=12, decimal_places=2),
    BeforeValidator(_validate_money_input, json_schema_input_type=str),
]
```

第一层只允许 `Decimal` 或 string；第二层解析并限制正数、总位数和小数位。HTTP／Webhook／MQ 的 JSON 没有 `Decimal` 类型，因此 wire policy 选择十进制字符串：

```json
{"amount": "12.30", "currency": "USD"}
```

拒绝 JSON number 的原因不是说每个 number 都立刻错，而是它经过某些客户端／中间件后可能先成为 binary float。例如 `0.1` 不能由有限二进制小数精确表示；一旦 `Decimal` 从 float 构造，误差已经进入系统。应从原始十进制文本构造，不能先 `float(value)` 再“修复”为 Decimal。

输出端同样有政策。lab 的 `field_serializer` 在 JSON mode 用 `format(value, "f")` 输出 string，因此 `Decimal("12.30")` 保持为 `"12.30"`，避免消费者再次走 float，也明确了 wire type。Python mode 的 `model_dump()` 仍可保留 `Decimal` 对象；`model_dump(mode="json")`／`model_dump_json()` 才是 wire 形状。

但不能写成“Decimal 天然解决所有货币问题”。它没有替你决定：

- 币种及其 minor unit；JPY、USD 等不能一律假设两位小数；
- rounding mode、在哪个业务步骤 round、税费如何分摊；
- 最大金额、溢出／资源限制和是否允许负数、零；
- 汇率的有效时间、精度和来源；
- `12.3` 与 `12.30` 是否在展示、签名或幂等语义上等价。

Decimal 只是精确十进制表示工具。真正的 Money 契约必须把 amount、currency、scale／rounding 和序列化政策一起定义，并由业务不变量补全。

## 常见反直觉转换清单

### bool 与 int

Python 中 `isinstance(True, int)` 为真，而且 `True == 1`。宽松 `int`、某些 `Literal[1]` 判断或手写 `isinstance(value, int)` 都可能误收 boolean。数量、版本、页码等协议字段优先用 `StrictInt`，或在必须区分原始形状时检查 `type(value) is int`。lab 的 Webhook／MQ `schema_version` 正是如此。

反方向也要小心：宽松 `bool` 可接受 `0/1` 和多种文本，如 `"yes"`、`"off"`。协议若声明 JSON boolean，应使用 `StrictBool`，不要把“人类看得懂”当成机器契约。

### 日期、datetime 与时区

`date` 与 `datetime` 的 string 接受规则会受 Python／JSON mode 和 strict 影响；数字时间戳还引入秒／毫秒猜测风险。事件时间应明确 wire format，并使用 `AwareDatetime` 或等价约束拒绝 naive datetime。

“有 offset”也不等于“统一为 UTC”。`2026-07-15T08:30:00-04:00` 与 `2026-07-15T12:30:00Z` 表示同一 instant，但字符串不同。比较、存储和输出是否统一 UTC 是单独的 normalization 政策，不应由“验证通过”暗中决定。

### UUID、Enum 与 Literal

- UUID 在 Python strict mode 通常要求 `UUID` 实例；JSON strict mode仍可接受标准 string，因为 JSON 无 UUID 原生类型。不要把两种入口混测。
- `Enum` 的值匹配、成员实例和 strict 行为不同；`IntEnum` 又可与整数相等。外部协议优先使用稳定字符串值，并测试未知值和大小写，而不是依赖成员序号。
- `Literal` 做的是精确候选匹配，但 Python 的相等语义可能让 `True` 命中 `Literal[1]`。版本字段若必须保留 JSON token 形状，仍需要 `StrictInt` 或原始类型检查。

这些例子说明：类型名字不足以定义协议。应把真实入口、候选表示、normalize 和错误 type 一起测试。

## `extra="forbid"`、兼容性与版本策略

HTTP `CreateOrderRequest`、Webhook envelope/payload、MQ envelope 和 Money 都使用 `extra="forbid"`。它有两项收益：

1. 及时暴露客户端拼写错误与 schema drift，而不是静默丢字段；
2. 缩小 mass assignment 风险，不让“模型没声明但下游可能使用”的字段混入流程。

代价是新增字段会让旧消费者失败。对单一版本的命令式 HTTP 请求，这通常是可接受且有价值的；对独立部署、需要 additive forward compatibility 的事件消费者，答案可能不同。

本 lab 的 MQ V1 就刻意采用 `OrderCreatedV1.model_config = ConfigDict(extra="ignore")`：旧 V1 reader 可以忽略新 producer 增加的 `item_count`。V2 则改为 `extra="forbid"`，更早暴露漂移。**这不是“MQ 都宽松”，而是 payload 按版本选择；envelope/header 始终严格。** 第 08 章会完整讨论 MQ V1 的版本兼容、discriminator 与失败处理，本章只记录这项字段政策。

做取舍时至少问：生产者与消费者是否原子发布、添加字段是否承诺向前兼容、拼写错误被忽略的代价、是否有 schema registry／契约测试、poison message 如何隔离。`forbid`／`ignore` 是协议决策，不是代码风格。

## `frozen=True` 不是深度不可变

lab 的 `Money`、`CreateOrderItem`、`CreateOrderRequest` 都配置：

```python
model_config = ConfigDict(extra="forbid", frozen=True)
```

`frozen=True` 防止正常的字段重绑定，例如 `item.quantity = 3` 会产生 `frozen_instance`。它不会递归冻结字段内部对象：若字段是 dict，`model.metadata["x"] = 1` 仍可能成功。Pydantic 官方因此称其为 faux immutability。

当前订单请求进一步使用 `tuple[CreateOrderItem, ...]`，每个 item 与嵌套 Money 也 frozen，叶子又是 str／int／Decimal 这类不可变值，所以对公开字段形成了实用的深层不可变结构。[test_create_order.py](lab/tests/test_create_order.py) 的 `test_validated_items_are_immutable` 至少锁定 items 是 tuple。若将来加入 list／dict／可变自定义对象，外层 frozen 不会自动维持这个性质；应改用不可变容器、复制后封装，或在领域构造器建立更强不变量。

不可变也不等于防恶意反射或 `object.__setattr__`。它主要防普通应用代码的意外 mutation，并让 validated snapshot 更适合在线程、缓存和事件投影之间传递。

## BaseModel、Pydantic dataclass 与领域对象的边界

“能用 Pydantic 验证”不代表“所有类都应继承 BaseModel”。

| 形态 | 适合职责 | 本 lab 的选择 |
|---|---|---|
| `BaseModel` | 不可信边界、嵌套解析、错误树、JSON Schema、稳定 serialization | `CreateOrderRequest`、`Money`、Webhook、事件 envelope |
| Pydantic dataclass | 想保留 dataclass API，同时需要 Pydantic validation/schema；仍是边界工具 | lab 当前没有使用；不要把它误认为自动生成领域行为 |
| 标准 `@dataclass(frozen=True, slots=True)` | 已经由 mapper 建立信任的 command／domain state，构造和行为语义由应用负责 | `CreateOrderCommand`、`Order`、`OrderLine` |
| 手写领域类／工厂 | 复杂状态迁移、封装、仓储协作与业务不变量 | 可在聚合复杂度上升时替代简单 dataclass |

lab 从 `CreateOrderRequest` 显式映射到 `CreateOrderCommand`，再由 `Order.create()` 检查整单单币种。这样 HTTP 的 alias、extra、coercion 或默认值不会渗入领域；领域对象也不需要知道 JSON、OpenAPI 或 Pydantic 错误 type。

Pydantic dataclass 与 BaseModel 都会消费 annotation 并执行边界验证，但 API、extra 行为、序列化入口和继承语义不同。选型依据应是层的职责，不是“dataclass 写起来少几个字符”。

## Java／Go 面试对照

### Java：Jackson coercion 与 `BigDecimal`

Jackson 也会在 JSON token shape 与 Java target type 之间做 coercion。资深回答不能停在“Java 是静态类型所以不会转”：外部 JSON 进入 POJO 时仍由 `ObjectMapper` 和 deserializer 决定 string→number、number→boolean、empty string→null 等策略。

可用 `CoercionConfig` 按具体 class、logical type 与 input shape 选择 `Fail`、`AsNull`、`AsEmpty` 或 `TryConvert`；还要配合 unknown-property、null-for-primitive、enum number 等设置。对应 Pydantic 的设计原则相同：不要只开一个全局“严格模式”，要按 DTO 边界和关键字段固定 token policy。Java primitive `int` 还无法表达 null，wrapper `Integer` 才能表达；required、nullable 与 default 仍是三件事，必须由 constructor/record、Jackson 配置和 Bean Validation 共同明确。

Money 应使用 `BigDecimal`，但要从十进制 string／精确 JSON number token 构造并固定 scale／rounding。`new BigDecimal(0.1)` 会精确保留那个 binary double 的近似值，而不是十进制 0.1；`new BigDecimal("0.1")` 才是可预测路径。Jackson 是否保留 trailing zeros、输出 number 还是 string 也需显式测试，`BigDecimal` 类型名本身不定义 wire contract。

### Go：`json.Number` 与自定义 unmarshaler

Go 的 struct 字段类型比 `map[string]any` 更早暴露 shape 不匹配，但 `encoding/json` 仍有边界决策。解到 `any` 时，旧版默认数字表示会落到 `float64`；使用 `Decoder.UseNumber()` 可保留为 `json.Number`，其 `String()` 返回原始 number literal，再由应用选择 `Int64()`、decimal 库或拒绝。

对 Money、严格版本号或兼容旧字段，常见做法是定义值对象并实现 `UnmarshalJSON([]byte) error`：先检查 token 是 quoted decimal string 还是 JSON number，再解析、校验范围并保存规范表示。这样等价于把 Pydantic 的 `BeforeValidator + Decimal + serializer` 收进 Go 类型。不要先 unmarshal 成 `float64` 再转 decimal；精度丢失发生后无法恢复。

Go 还需显式调用 `Decoder.DisallowUnknownFields()` 才能获得类似 `extra="forbid"` 的入口行为；但 MQ V1 是否忽略新增 payload 字段仍应按版本策略决定，不能把 decoder 全局配置当作所有协议的答案。

面试时可以把三种语言统一成一句话：**静态目标类型只描述希望得到什么；真正的外部契约还必须定义 source token、允许的 coercion、null／missing、unknown fields、精确数值路径与稳定输出。**

## 评审清单与对应 pytest

字段评审不要只看 annotation。逐字段确认：

- 缺失和 `null` 是否分别测试；default 与 `default_factory` 是否符合语义；
- Python mode 与 JSON mode 的真实入口是否都覆盖；
- 每项 coercion 是否有边界理由，而不是“框架能转”；
- normalize 是否幂等，是否可能把两个不同业务值合并；
- Decimal 是否从十进制原始表示进入，scale／rounding／输出 string 政策是否明确；
- alias 的读写方向、冲突和迁移期限是否明确；
- `extra` 与 `frozen` 是否被误当成向前兼容或深度不可变；
- 错误 `type`／`loc` 是否与 adapter 的对外错误映射一致。

本章的最小回归集是：

```bash
cd python-pydantic/lab
uv run pytest tests/test_value_objects.py tests/test_create_order.py -v
```

重点阅读：

- `test_order_id_rejects_non_string_input`：`OrderId` 的非字符串输入是 `string_type`；
- `test_quantity_does_not_coerce_string`：`"2"` 在嵌套 quantity 上是 `int_type`；
- `test_currency_is_normalized_to_uppercase`：允许的 normalization 收敛到 `USD`；
- `test_money_accepts_decimal_string_and_serializes_as_string`：输入和 JSON 输出都走十进制字符串；
- `test_money_rejects_binary_float`：binary float 在进入 Decimal 前以 `value_error` 被拒绝；
- `test_http_contract_forbids_unknown_fields` 与 `test_validated_items_are_immutable`：入口字段白名单和不可变容器均被固定。

进一步核对可参考 Pydantic 官方的 [Fields](https://docs.pydantic.dev/latest/concepts/fields/)、[Strict Mode](https://docs.pydantic.dev/latest/concepts/strict_mode/)、[Models](https://docs.pydantic.dev/latest/concepts/models/) 和 [Standard Library Types](https://docs.pydantic.dev/latest/api/standard_library_types/)，以及 Java [`BigDecimal`](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/math/BigDecimal.html) 与 Go [`encoding/json`](https://pkg.go.dev/encoding/json) 文档。

本章的架构结论不是“strict 越多越好”，而是：**required、nullable、default、类型约束、coercion、unknown-field 与 serialization 是独立决策；每项允许的转换都应能说出边界语义、稳定错误和回归测试。**
