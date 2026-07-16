# 03 · 验证管线与规范化：顺序、纯度与错误契约

> **本章目标**：能精确推演 Pydantic v2 validator 的执行顺序，知道何时选 before／plain／wrap／after、field／model，并把 normalization 限制为无 I/O、可重复、可测试的边界变换。可运行事实以 [Money](lab/src/order_contracts/value_objects.py) 与 [CreateOrderRequest](lab/src/order_contracts/inbound/create_order.py) 为准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_value_objects.py tests/test_create_order.py -v
```

当前应有 10 个测试通过。它们固定了两条主线：`Money` 在 Decimal 解析前拒绝 binary float／整数，`CreateOrderRequest` 在全部 item 成功后拒绝重复 SKU。

## 事故开场：每个 validator 单看都对，组合后为什么错了？

假设金额字段先做 trim，再拒绝 float，最后量化小数；请求模型还要检查重复 SKU。若工程师只知道“validator 会执行”，却不知道**哪一个先拿到 raw input、哪一个拿到已验证值、谁能终止内部验证**，会产生三类事故：

- `PlainValidator` 返回原始字符串，绕过本应执行的 `Decimal` 类型和范围约束；
- 依赖另一个字段的 field validator 因字段声明顺序，读取到缺失或尚未验证的数据；
- before validator 原地修改 union 输入后抛错，污染该值随后尝试的另一个 union 分支。

因此不要把 validator 理解为一组无序 callback。更准确的模型是：**Pydantic 把 annotation、metadata 与 decorator 编译成一条有方向的验证管线；不同 mode 决定代码运行在核心类型验证的哪一侧，以及是否必须调用核心验证。**

## lab 主线一：金额在 Decimal 解析前拒绝错误表示

lab 的真实实现使用 `_validate_money_input`，同时拒绝 float 与 int：

```python
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, Field


def _validate_money_input(value: Any) -> Any:
    if not isinstance(value, (Decimal, str)):
        raise ValueError("money amount must be a Decimal or decimal string")
    return value


MoneyAmount = Annotated[
    Decimal,
    Field(gt=Decimal("0"), max_digits=12, decimal_places=2),
    BeforeValidator(
        _validate_money_input,
        json_schema_input_type=Annotated[str, Field(pattern=MONEY_STRING_PATTERN)],
    ),
]
```

若只想突出本章标题中的 binary-float 风险，可以把相同位置的窄策略写成下面这个教学版本；`BeforeValidator(_reject_binary_float)` 仍然在 Decimal 核心解析之前运行：

```python
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, Field


def _reject_binary_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("binary float is not accepted for money")
    return value


MoneyAmountTeachingExample = Annotated[
    Decimal,
    BeforeValidator(_reject_binary_float),
    Field(gt=Decimal("0"), max_digits=12, decimal_places=2),
]
```

教学版本只拒绝 float，仍会让 int 进入 Decimal 解析；生产 lab 的政策更严格，所以源码使用 `_validate_money_input`。不要只复制更窄的示例后声称和 lab 完全等价。

当金额嵌在创建订单请求中时，失败路径保留完整容器位置：

```python
try:
    CreateOrderRequest.model_validate(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-001",
            "items": [
                {
                    "sku": "sku-001",
                    "quantity": 1,
                    "unit_price": {"amount": 12.30, "currency": "USD"},
                }
            ],
        }
    )
except ValidationError as exc:
    error = exc.errors()[0]
    assert error["loc"] == ("items", 0, "unit_price", "amount")
    assert error["type"] == "value_error"
```

这里的 `value_error` 来自自定义 `ValueError`，不是 Decimal 核心错误。若传入获准进入内部解析、但不能解释为 Decimal 的字符串，例如 `"not-money"`，错误 type 会来自核心 schema（当前为 `decimal_parsing`）。**validator 放在管线的哪一侧，会同时影响接受集合和错误契约。**

## lab 主线二：全部字段成功后再检查重复 SKU

[CreateOrderRequest](lab/src/order_contracts/inbound/create_order.py) 的完整 class-level 检查如下：

```python
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: CustomerId
    idempotency_key: IdempotencyKey
    items: Annotated[
        tuple[CreateOrderItem, ...],
        Field(min_length=1, max_length=100),
    ]

    @model_validator(mode="after")
    def reject_duplicate_skus(self) -> Self:
        skus = [item.sku for item in self.items]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate sku is not allowed")
        return self
```

`mode="after"` 收到已构造的 `self`：`items` 已经是不可变 tuple，每个元素也已经是 `CreateOrderItem`，不需要在这里重新解析 dict。异常属于整个模型，当前错误路径位于 root：

```python
try:
    CreateOrderRequest.model_validate(payload_with_duplicate_skus)
except ValidationError as exc:
    error = exc.errors()[0]
    assert error["loc"] == ()
    assert error["type"] == "value_error"
    assert "duplicate sku is not allowed" in error["msg"]
```

root 路径不是信息丢失，而是在表达“单个 item 都合法，组合关系不合法”。若 API 需要指出具体重复项，应建立稳定的错误映射政策，而不是让客户端解析人类文案。

## 四种 functional validator：核心验证在中间

先把核心类型 schema 想成管线中心：

```text
raw input
  → before / wrap 的入口侧
  → Pydantic core：类型解析、Field 约束、嵌套模型
  → after 的结果侧
  → validated value

plain：可以从入口直接返回，终止其所替代的内部验证
wrap：通过 handler 决定调用、重试或跳过内部验证
```

| mode | 接收到什么 | 是否保证执行内部验证 | 适合做什么 | 主要风险 |
|---|---|---:|---|---|
| `BeforeValidator` | raw input，类型通常应写 `Any` | 是；返回值继续进入管线 | 窄 coercion、trim、拒绝危险输入表示 | 输入形状任意；在 union 中原地 mutate 后抛错会污染其他分支 |
| `AfterValidator` | 已通过内部验证的目标类型 | 是；已经执行完 | 对 typed value 做局部不变量、canonicalization | 返回类型错误仍可能破坏契约；不要以为 after 返回后会再做一次类型验证 |
| `PlainValidator` | raw input | **否**；它终止内部验证 | 极少数完全自行实现解析与校验的适配层 | 一次漏检就能绕过 annotation 和约束 |
| `WrapValidator` | raw input + `handler` | 由代码决定，可调用 0／1／多次 | 观察、截断后重试、翻译后重抛 | 吞掉 `ValidationError`、重复副作用、无意跳过核心验证 |

### Before：只做窄而纯的入口变换

```python
def trim_string(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


TrimmedName = Annotated[str, BeforeValidator(trim_string)]
```

before 必须接受 annotation 之外的输入，因为它运行时核心类型验证还没发生。若输入不属于该函数负责的形状，通常原样返回，让后续 schema 给出标准类型错误；不要把任意对象都 `str(value)`，那会隐藏协议漂移。

### After：利用已验证类型表达局部不变量

```python
from pydantic import AfterValidator


def require_even(value: int) -> int:
    if value % 2:
        raise ValueError("must be even")
    return value


EvenInt = Annotated[int, AfterValidator(require_even)]
```

这里可以安全使用 `%`，因为核心验证已经保证 `value` 是 int。after 仍必须返回值；漏写 `return value` 会把成功值变成 `None`，Pydantic 不会自动替你保留原值。

### Plain：一个看似成功、实际绕过类型的危险示例

```python
from pydantic import BaseModel, PlainValidator


def accept_as_is(value: Any) -> Any:
    return value


class Dangerous(BaseModel):
    quantity: Annotated[int, PlainValidator(accept_as_is)]


danger = Dangerous.model_validate({"quantity": "not-an-int"})
assert danger.quantity == "not-an-int"  # int 核心验证没有运行
```

这不是 Pydantic “忘了校验”，而是 `PlainValidator` 的定义：函数返回后结束该内部验证路径。只有当函数自己完整承担 parsing、type check、constraints 与错误政策时才考虑 plain；大多数 normalization 应使用 before 或 after。

### Wrap：观察、截断、重抛，而不是默认吞错

```python
from typing import Annotated, Any

from pydantic import Field, ValidationError, ValidatorFunctionWrapHandler, WrapValidator


def truncate_once(
    value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    try:
        return handler(value)  # 正常路径：调用内部验证一次
    except ValidationError as exc:
        first = exc.errors()[0]
        if first["type"] == "string_too_long" and isinstance(value, str):
            return handler(value[:8])  # 只对已知错误做一次有界重试
        raise  # 未知错误保留原错误路径与 type


ShortCode = Annotated[str, Field(max_length=8), WrapValidator(truncate_once)]
```

wrap 可以：

- 在 `handler(value)` 前后观察耗时或结果，但观测不得记录完整敏感 input；
- 捕获一个**明确、稳定的**错误 type，做有界修正后再次调用 handler；
- 不调用 handler，直接返回或抛错，从而截断内部验证；
- 捕获后使用裸 `raise` 重抛，保留原始验证错误。

正因为它能调用零次、多次，wrap 比 before／after 更强，也更容易破坏可推理性。handler 及其内部 validator 应当纯净；否则重试会重复副作用。

## `Annotated` 与 decorator 是同一条 metadata 管线

以下规则与 [Pydantic 官方 Validators 文档](https://docs.pydantic.dev/latest/concepts/validators/#ordering-of-validators) 的 ordering 定义一致，并已在本章对应 venv 中用记录调用顺序的探针核验。

对于 `Annotated[T, metadata_1, metadata_2, ...]`，Pydantic v2 的 validator ordering 是：

- `BeforeValidator` 与 `WrapValidator`：**从右向左**执行；
- `AfterValidator`：**从左向右**执行。

例如：

```python
Pipeline = Annotated[
    str,
    AfterValidator(after_1),
    AfterValidator(after_2),
    BeforeValidator(before_1),
    WrapValidator(wrap_1),
    BeforeValidator(before_2),
]
```

入口阶段从最右边开始：`before_2 → wrap_1(进入 handler) → before_1 → core`；核心成功返回后，after 从左向右：`after_1 → after_2`。wrap 在 handler 返回后还有自己的“出口半边”，所以完整嵌套视图是：

```text
before_2
  wrap_1 before-handler
    before_1
      core(str)
    after_1
    after_2
  wrap_1 after-handler
```

`@field_validator` 等 decorator 不是另一套调度器。Pydantic 会把 decorator 转成对应 validator metadata，并**追加在字段已有 metadata 的末尾**，然后遵循同一顺序规则。因此：

- decorator `mode="before"`／`mode="wrap"` 因为追加在最右边，通常比已有的 Annotated before／wrap 更早进入；
- decorator `mode="after"` 因为追加在最右边，会在已有的 Annotated after 之后运行。

不要靠 decorator 在源码中的视觉上下顺序猜执行路径；把 alias 展开为 metadata，再按“before／wrap 右向左，after 左向右”推演。

## field validator 还是 model validator？

| 需求 | 优先选择 | 原因 |
|---|---|---|
| 单字段 raw 表示规范化／拒绝 | field before | 在核心解析前控制输入表示 |
| 单字段 typed value 不变量 | field after（默认 mode） | 类型已成立，函数更简单 |
| 完全接管单字段解析 | field plain | 仅在确实能完整替代核心 schema 时 |
| 需要包围内部验证、观察或有界重试 | field wrap | handler 明确暴露内部验证 |
| 多字段关系，字段都应先有效 | model after | 获得完整 typed model；重复 SKU 即此类 |
| 整体 raw mapping 迁移／拒绝 | model before | 可检查旧版本 shape，但输入可能不是 dict |
| 包围整个模型验证 | model wrap | 可观察、重抛或短路整个模型管线 |
| 依赖数据库、库存、权限、HTTP | **都不是** | 属于 application／domain／adapter，不应塞进 validator |

### `ValidationInfo.data` 的字段顺序陷阱

field validator 可以接收 `ValidationInfo`。其中 `info.data` 只包含**已经按字段定义顺序完成验证**的字段，而不是原始 input 的所有 key，也不是最终模型：

```python
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator


class Credentials(BaseModel):
    password: str = Field(min_length=8)
    password_repeat: str

    @field_validator("password_repeat", mode="after")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("passwords do not match")
        return value


try:
    Credentials.model_validate(
        {"password": "short", "password_repeat": "also-short"}
    )
except ValidationError as exc:
    assert [error["loc"] for error in exc.errors()] == [("password",)]
```

这段代码成立，是因为 `password` 定义在 `password_repeat` 前，但仍然必须用 `.get()`／membership guard：若调换字段定义顺序，校验 `password_repeat` 时 `info.data` 还没有 `password`；即使顺序未变，若前一个字段验证失败，它也不会以成功值出现在 `data`。此时 validator 应跳过依赖性比较，让原始 `password` 错误成为 `ValidationError`，不能用未保护的下标访问泄漏 `KeyError`。跨字段关系若天然属于整个对象，model after 通常更稳健。

对 model validator，`ValidationInfo.data` 为 `None`；after model validator 直接读取 `self`，before／wrap 则使用传入的整体值或 handler。不要把 field validator 的 partial-data 心智套到 model validator。

## default：省略输入默认不会触发字段验证

Pydantic 默认不验证字段 default，也不会为它运行对应 validator。这样能降低每次构造成本，但错误 default 可能绕过 annotation：

```python
class LeakyDefault(BaseModel):
    retries: int = "three"  # 默认配置下可偷渡成错误运行时值


assert LeakyDefault().retries == "three"
```

当 default 不是经过静态保证的简单常量，或你要求它与用户输入共享完全相同的契约时，开启验证：

```python
from pydantic import BaseModel, Field


class SafeDefault(BaseModel):
    retries: int = Field(default="3", validate_default=True)


assert SafeDefault().retries == 3
```

也可在 `model_config` 使用 `validate_default=True` 统一开启。决策应由测试锁定，因为它改变构造时机、性能与失败行为。特别是某些类型复用 validator 来处理 default 时，例如从枚举取出 `.value`，没有 `validate_default` 就不会执行该转换。

两条团队规则：

1. **禁止用 invalid default 偷渡**。类型与约束若声明为真，省略字段也必须得到契约内的值。
2. **禁止依赖 mutable default 的隐式复制语义**。Pydantic 会 deep-copy 不可 hash 的默认值，但应优先 `Field(default_factory=list)`／`dict`／`set` 明确表达“每个实例一份”，也避免大型对象的隐藏复制成本。

`default_factory` 若接收已验证数据，同样只看到定义在它之前的字段，因此也有字段顺序依赖；复杂派生值更适合显式构造函数或应用层 mapper。

## context：传入逐调用上下文，不把 I/O 藏进 validator

`model_validate(..., context=...)` 可以把调用方已有的逐调用上下文传给 validator：

```python
from pydantic import BaseModel, ValidationInfo, field_validator


class Message(BaseModel):
    text: str

    @field_validator("text", mode="after")
    @classmethod
    def remove_stopwords(cls, value: str, info: ValidationInfo) -> str:
        context = info.context if isinstance(info.context, dict) else {}
        stopwords = frozenset(context.get("stopwords", ()))
        return " ".join(word for word in value.split() if word not in stopwords)


message = Message.model_validate(
    {"text": "this is an example"},
    context={"stopwords": frozenset({"this", "is", "an"})},
)
assert message.text == "example"
```

Pydantic 会把调用方给出的**同一个 context 对象**传给 validator，不会替调用方复制或冻结它；示例的外层 dict 仍然可变。团队应约定 validator 把 context 当作只读输入，绝不原地修改，否则后续 validator 与调用方都会观察到变化。词表等成员适合使用 `frozenset` 或不可变值对象，降低误修改风险，但这不等于整个 context 自动不可变。

这里的“纯”描述 validator 的行为：只读取当前值和逐调用 context，保持确定、快速且无 I/O；不是在声称 context 对象具有不可变性。context 适合携带租户已有的词表、locale、已解析协议版本等调用期政策，不适合传数据库 session 后在 validator 内查询。

直接 `Model(...)` 不能直接传 validation context：`Message(text="...", context=...)` 只会把 `context` 当作候选模型字段，具体结果由 extra policy 决定。Pydantic 文档给过覆写 `__init__` 配合 `ContextVar` 的高级方案，但本教程**不覆写 `__init__`**；需要 context 时显式使用 `model_validate(..., context=...)`，让调用点可见。

context 也可用于 serialization，但 validation context 与 serialization context 是各自调用显式传入的，不要假设它们自动共享。

## union 中的 before validator：先复制，再修改；能不改就不改

before validator 收到的对象可能随后被多个 union 分支尝试。危险写法是先对共享 list／dict **原地 mutate**，再抛错：

```python
def dangerous_before(value: Any) -> Any:
    if isinstance(value, dict):
        value["kind"] = "legacy"  # 污染调用方对象与后续 union 分支
        raise ValueError("not this branch")
    return value
```

当当前分支失败，Pydantic 仍可能把这个已经变形的值送进 union 的其他分支；调用方持有的原对象也可能被改坏。安全策略按优先级排序：

1. 只检查，不修改；
2. 需要规范化时返回新对象，例如 `{**value, "kind": "legacy"}`；
3. 一旦计划抛错，绝不先原地修改；
4. 对有明确 tag 的协议优先 discriminated union，避免猜测式分支试探。

这一规则不限于 union：validator 接收的是外部不可信对象，不应给调用方制造隐蔽副作用。

## normalization 的纯度白名单

允许进入 validator 的 normalization 应同时满足：只依赖当前值与显式传入、按约定只读的逐调用 context，确定、快速、无外部副作用、重复执行结果稳定。

| 白名单 | 示例 | 条件 |
|---|---|---|
| trim | `" usd " → "usd"` | 空白在该字段协议中不携带语义 |
| case canonicalization | `"usd" → "USD"` | 大小写不区分且 canonical form 已约定 |
| timezone canonicalization | aware datetime → UTC aware datetime | 不能把 naive 时间猜成某个时区；必须保留明确时刻 |

禁止放进 validator：

- DB lookup、库存或幂等记录查询；
- HMAC／签名验证（应由 adapter 对原始 bytes 按协议完成）；
- HTTP／RPC 调用；
- `sleep`、重试、锁等待；
- 日志记录完整 input、token、卡号、secret 或 webhook body。

签名检查不仅是 I/O／安全职责问题，还依赖**解析前的原始 bytes**；一旦 dict 被规范化再重编码，字节序列已经变化。库存则是并发外部状态，即使 validator 查询时通过，真正写入时也可能改变。二者都不是“多写一个 validator”能获得的可靠性。

日志若确实需要记录 validation 失败，只记录 error type、允许的结构路径、契约版本与 trace id，并在 adapter 的统一错误边界做脱敏；不要让每个 validator 自由打印 raw value。

## 稳定错误：对外映射 `type + loc`，不要暴露实现细节

`ValidationError.errors()` 的每项常见字段包括 `type`、`loc`、`msg`、`input` 和可选 `ctx`。工程上应区分：

- `type`：机器可读分类；内建约束通常比英文 `msg` 稳定；
- `loc`：结构路径，例如 `("items", 0, "quantity")`；适合映射为 API field path；
- `msg`：给开发者诊断，不应要求客户端按整句匹配；
- `input`／`ctx`：可能包含敏感或不可 JSON 序列化对象，对外响应和日志都要审查。

同样抛 `ValueError` 的多个 validator 都会得到较宽泛的 `value_error`。若业务边界确实需要稳定细分，可用 `pydantic_core.PydanticCustomError` 定义受控 code，再由 HTTP／MQ adapter 映射为版本化错误；不要把异常类名、Python repr 或完整 input 原样返回。

```python
from pydantic_core import PydanticCustomError


def reject_duplicate_skus_for_api(skus: list[str]) -> list[str]:
    if len(skus) != len(set(skus)):
        raise PydanticCustomError(
            "duplicate_sku",
            "duplicate sku is not allowed",
        )
    return skus
```

是否采用 custom error 是契约版本决策。当前 lab 已用测试锁定 `value_error` 与路径；若切换 code，必须同步 adapter 映射与消费者契约，而不是只改文案。

## 边界规则还是领域规则？

| 问题 | 放置位置 | 示例 |
|---|---|---|
| 仅看当前 payload 就能稳定回答的 shape、type、局部值 | Pydantic field validator／约束 | 金额拒绝 float、币种大写、数量范围 |
| 仅看当前 payload，但涉及多个字段／元素关系 | Pydantic model validator | 同一请求内重复 SKU |
| 需要身份、时间、数据库或其他当前状态 | application／domain service | 权限、实时库存、额度、幂等记录 |
| 聚合自身必须始终成立的不变量 | domain entity／aggregate | 订单单币种、合法状态迁移 |
| 依赖传输原文或交付协议 | adapter | webhook 签名、ack／nack、重试、DLQ |

一个实用判断：规则如果必须问“谁在做、现在库存多少、之前发生了什么、远端怎么说”，它不是 validation pipeline 的职责。Pydantic 产出的是“可进入应用层的可信局部事实”，不是“业务动作已获准”。

## Java／Go 对照：机制不同，分层问题相同

### Java：Bean Validation group 与 class-level constraint

Java Bean Validation 常用字段 annotation 表达单字段约束，用 class-level constraint 表达多字段关系：

```java
@UniqueSkus
public record CreateOrderRequest(
    @NotBlank(groups = BasicChecks.class) String customerId,
    @Valid List<CreateOrderItem> items
) {}
```

validation group 可以为 create／update 或 basic／expensive 阶段选择不同约束集合，group sequence 还能规定组间先后；但它不是把库存查询塞进 constraint 的许可证。`@UniqueSkus` 类似 Pydantic `model_validator(mode="after")`：对象级读取多个已映射字段。若约束依赖 repository、当前用户或事务状态，应留在 application／domain service。

与 Pydantic validator metadata 不同，不能只凭 Java annotation 在字段上的排列推导完整执行次序；需要看 provider 与 group sequence 的保证。两边都应把错误 path/code 映射为自己的 API 契约，而不是暴露框架默认文案。

### Go：显式 normalization function

Go 通常没有 annotation 驱动的隐式管线，最易审计的做法是显式串联纯函数：

```go
func NormalizeCurrency(raw string) (string, error) {
    value := strings.ToUpper(strings.TrimSpace(raw))
    if !currencyPattern.MatchString(value) {
        return "", ErrInvalidCurrency
    }
    return value, nil
}

func ParseCreateOrder(raw []byte) (CreateOrderRequest, error) {
    var req CreateOrderRequest
    if err := decodeStrictJSON(raw, &req); err != nil {
        return CreateOrderRequest{}, err
    }
    currency, err := NormalizeCurrency(req.Currency)
    if err != nil {
        return CreateOrderRequest{}, err
    }
    req.Currency = currency
    if err := ValidateCreateOrder(req); err != nil {
        return CreateOrderRequest{}, err
    }
    return req, nil
}
```

显式代码减少了 metadata 顺序推演，却仍要回答相同问题：normalize 在 type decode 前还是后、错误 path 如何保留、函数是否纯、跨字段检查何时运行。Pydantic 的优势是编译和复用契约；Go 的优势是控制流直接可见。架构边界不因语言而改变。

## 面试推演与 code review 清单

看到一个 validator，不要只问“逻辑对不对”，按以下顺序审查：

1. 它运行在 core schema 前还是后？输入究竟是 `Any` 还是 typed value？
2. Annotated 展开后，before／wrap 是否按右向左，after 是否按左向右？decorator 追加后位置如何变化？
3. plain／wrap 是否可能不调用内部验证？wrap 是否可能重复调用有副作用的代码？
4. field validator 若读取 `ValidationInfo.data`，依赖字段是否已按定义顺序成功验证？是否应改为 model after？
5. default 是否需要 `validate_default`？是否存在 invalid 或 mutable default 偷渡？
6. before 是否原地 mutate，尤其是在 union 分支失败之前？
7. normalization 是否只做 trim、case、timezone 等语义等价变换，且无 DB／HTTP／sleep／敏感日志？
8. context 是否由 `model_validate(..., context=...)` 逐调用显式传入并按约定只读？调用点是否可见？
9. 对外是否映射稳定的 `type + loc`，并移除敏感 `input`？
10. 规则只依赖当前输入，还是实际属于 authorize／库存／领域状态／传输协议？

最终应能用一句话解释本章两个案例：`Money` 的 before validator 在 Decimal 核心验证前控制可接受的输入表示；`CreateOrderRequest` 的 model after validator 在子模型全部成功后检查请求内的组合不变量。前者回答“这个值能否进入金额契约”，后者回答“这份 payload 自身是否自洽”，两者都不回答“现在能否下单”。
