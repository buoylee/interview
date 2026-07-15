# 11 · 自定义类型、CoreSchema 与性能：先守边界，再下沉

> **本章目标**：能按“最低成本扩展阶梯”选择 Pydantic 扩展点，解释 `ProviderReference` 的 CoreSchema、JSON Schema 与序列化路径，并用可复现的观测决定是否优化。可运行事实来自 [`advanced_types.py`](lab/src/order_contracts/advanced_types.py)、[`performance.py`](lab/src/order_contracts/performance.py) 及其 [高级类型](lab/tests/test_advanced_types.py)／[性能观测](lab/tests/test_performance_observations.py) 测试。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_advanced_types.py tests/test_performance_observations.py -v -s
```

当前应有 7 个测试通过：5 个锁住 `ProviderReference` 的 Python／JSON 校验、JSON Schema、序列化和错误行为，2 个只确认性能观测器能工作。测试**没有**规定某条路径必须快多少；机器耗时不能成为契约。

## 事故开场：为“复用一个字符串规则”，为什么升级成本突然扩散？

团队想复用支付渠道引用，于是直接实现 `__get_pydantic_core_schema__`。运行时验证通过，后来又补 serializer；前端生成器却仍把它当任意对象，因为 JSON Schema 没同步。再一次 Pydantic／`pydantic-core` 升级后，低层 schema 组合发生变化，几十个类型都要逐个审查。

另一支团队为了“性能”，在每次请求和循环每项里构造 `TypeAdapter`，还把所有 `model_validate()` 改成 `model_construct()`。结果 schema 编译成本进入 hot path，外部数据绕过校验，吞吐量也没有稳定改善。

两起事故的根因相同：**在没有必要和证据时过早下沉**。自定义类型与性能工作的正确顺序是：

```text
先定义边界语义
    ↓
选择能表达它的最高层扩展点
    ↓
锁 validation / serialization / JSON Schema 三面行为
    ↓
profile 确认瓶颈
    ↓
只优化被证实的路径，再用同一 workload 复测
```

## 最低成本扩展阶梯

选择扩展点时，从上向下停在第一个足够表达需求的层级：

| 顺序 | 扩展点 | 适合的问题 | 主要成本／风险 |
|---|---|---|---|
| 1 | 标准类型与 Pydantic 内置类型 | strictness、范围、长度、URL、日期等已有语义 | 最低；优先使用 |
| 2 | `Annotated` + `Field`／约束 + functional validator | 可复用的单值规则与 normalize | 声明式、可组合；注意 validator 与 schema 语义是否一致 |
| 3 | `field_validator`／`model_validator` | 依赖字段名、同模型上下文或跨字段不变量 | 与具体模型耦合；model-level 错误通常定位到 root |
| 4 | `ValidateAs`／高层 custom type 映射 | 自定义 Python 对象能先由受支持类型／模型校验，再实例化 | 需要定义中间表示和映射；序列化政策仍要审查 |
| 5 | `GetPydanticSchema` | 局部字段需要低层 CoreSchema 调整，但不值得创建 marker class | 已进入 CoreSchema 层；版本与可读性成本上升 |
| 6 | `__get_pydantic_core_schema__` | 类型本身必须跨模型拥有 validation／serialization，或高层 API 无法表达 | 最强也最贵；需同时维护 JSON Schema、测试和升级审查 |

functional validator 包括 `BeforeValidator`、`AfterValidator`、`PlainValidator` 和 `WrapValidator`。它们不是按“高级程度”排序：before 适合输入 normalize，after 适合在类型校验后检查，plain 会替代内部校验，wrap 能包围并决定是否调用 handler。越能改变默认流水线，越应明确其错误、schema 与性能含义。

### 两个停止下沉的判断题

1. 规则是否只是在普通值上增加约束或 normalize？若是，优先 `Annotated`；不要为一个 regex 创建 CoreSchema hook。
2. 规则是否需要跨字段事实？若是，它属于 model validator 或更外层 application/domain policy；塞进一个字符串 custom type 会隐藏依赖。

`ValidateAs` 适合“对象表示特殊，但校验输入并不特殊”的场景：

```python
from typing import Annotated

from pydantic import BaseModel, TypeAdapter, ValidateAs


class Coordinates:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class CoordinatesInput(BaseModel):
    x: int
    y: int


CoordinatesContract = Annotated[
    Coordinates,
    ValidateAs(CoordinatesInput, lambda value: Coordinates(value.x, value.y)),
]

adapter = TypeAdapter(CoordinatesContract)
point = adapter.validate_python({"x": 3, "y": 4})
```

这里 `CoordinatesInput` 负责结构校验，hook 只负责从已校验对象实例化 domain-like class。若对象还需要特殊 wire serializer 或必须由类型包跨项目拥有完整契约，再考虑更低层方案。

## `CurrencyCode`：高层组合已经足够

[`value_objects.py`](lab/src/order_contracts/value_objects.py) 的货币代码由普通组件组合：

```python
CurrencyCode = Annotated[
    StrictStr,
    BeforeValidator(_normalize_currency),
    Field(pattern=r"^[A-Z]{3}$"),
]
```

数据路径很清楚：

1. before validator 对 string 做 `strip().upper()`；
2. `StrictStr` 拒绝非 string 输入，而不是把数字随意变成文本；
3. `Field(pattern=...)` 校验 canonical value；
4. Pydantic 能从标准 string schema 与 `Field` 约束生成 JSON Schema。

它没有独立 subclass identity，也不需要自定义 serializer。对订单边界来说，“校验后得到普通大写 string”正是所需结果。为它实现 CoreSchema hook 不会增加业务表达力，只会增加维护面。

这仍有一个 schema 评审点：before validator 的 trim／uppercase 是运行时输入转换，JSON Schema 的 regex 只表达 canonical pattern，不能自动向其他语言客户端描述 normalize 动作。若跨语言 producer 必须预先得知转换政策，应在 API 文档或 examples 中明确；不要假设 validator 已自动变成完整协议描述。

## `ProviderReference`：类型包拥有三面契约

[`advanced_types.py`](lab/src/order_contracts/advanced_types.py) 选择直接 hook：

```python
class ProviderReference(str):
    @classmethod
    def validate(cls, value: str) -> "ProviderReference":
        normalized = value.strip()
        if re.fullmatch(PROVIDER_REFERENCE_PATTERN, normalized) is None:
            raise ValueError("invalid provider reference")
        return cls(normalized)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )
```

它比 `CurrencyCode` 多承担三项所有权：

- validation：strip、完整 regex 校验，并返回 `ProviderReference` subclass；
- serialization：JSON 路径明确写成 string；
- JSON Schema：对 schema consumer 发布 `type: string` 与同一 pattern。

这种选择只有在 subclass identity 和跨模型类型所有权确实有价值时才成立。源文件的注释也明确建议：普通业务契约仍优先 `Annotated`，这个类型用于把版本敏感扩展隔离在一个小边界中。

### CoreSchema hook 是 middleware

可以把 `__get_pydantic_core_schema__` 看成 schema 构建期 middleware，而不是“每次校验时执行的 validator”：

| 参数／结果 | 本例含义 | 高级用法注意点 |
|---|---|---|
| `source_type` | 简单非泛型场景通常就是请求生成 schema 的类型 | 对泛型／`Annotated` 组合，它可能携带实例化后的类型信息，不应总是假设等于 `cls` |
| `handler` | 请求下游为另一类型生成 CoreSchema | `handler(str)` 委托 Pydantic 建立标准 string schema；直接对原 custom type 递归委托可能造成错误递归 |
| returned schema | Pydantic 最终编译、缓存并执行的 CoreSchema graph | 可以委托后包装，也可以替换；越偏离默认 graph，升级验证责任越大 |

本例返回 `no_info_after_validator_function`：先执行 `handler(str)` 得到的 string 校验，再把结果交给 `cls.validate`；因为函数不需要 `ValidationInfo`，使用 `no_info` 版本减少不必要上下文。`serialization=to_string_ser_schema()` 则把输出政策绑定在同一个 graph 上。

`GetPydanticSchema` 是同一低层能力的轻量入口：它可作为 `Annotated` metadata 接收生成 CoreSchema／JSON Schema 的 callable，省去只为一个字段建立 marker class。它减少 boilerplate，不会把低层 API 变成高层 API；回调仍要理解 handler、schema graph 和版本差异。

CoreSchema hook 是公开扩展协议，但它直接依赖 `pydantic-core` 的 schema constructors 与组合语义，相比 `Field`、内置类型和 functional validator 更靠近实现层。升级 Pydantic 时应针对锁定版本重跑三面契约测试；不要把一个版本生成的 CoreSchema dict 持久化成长期业务格式。

## CoreSchema 与 JSON Schema 不会自动等价

direct hook 的运行时行为不会自动完整翻译成 JSON Schema。`ProviderReference` 因此另写：

```python
@classmethod
def __get_pydantic_json_schema__(
    cls,
    schema: CoreSchema,
    handler: GetJsonSchemaHandler,
) -> JsonSchemaValue:
    json_schema = handler.resolve_ref_schema(handler(schema))
    json_schema.update(
        type="string",
        pattern=PROVIDER_REFERENCE_PATTERN,
    )
    return json_schema
```

`handler(schema)` 先把 CoreSchema 转成 JSON Schema；`resolve_ref_schema(...)` 取得可能被 `$ref` 指向的具体 schema，再加上公开约束。这里复用 `PROVIDER_REFERENCE_PATTERN` 常量，减少 runtime regex 与文档 regex 的文本漂移。

测试也必须双向锁住：

```python
adapter = TypeAdapter(ProviderReference)

assert adapter.validate_python("  pay_ABC12345  ") == "pay_ABC12345"
assert adapter.json_schema()["pattern"] == PROVIDER_REFERENCE_PATTERN
```

当前 [高级类型测试](lab/tests/test_advanced_types.py) 正是分别检查运行时正反例和 schema pattern。它仍揭示一个值得公开评审的语义差异：runtime 接受首尾空格后再 strip，而 JSON Schema pattern 对原始 string 不表达 strip，因此严格按 schema 预检的客户端可能拒绝 runtime 会接受的输入。三种政策都可以成立，但必须显式选择：取消 trim、把输入 normalize 写进协议文档，或只承诺 canonical output pattern。不能把“pattern 字符串相同”误称为完整 runtime parity。

同理，自定义 serializer 也不会自动反推为 JSON Schema。验证、序列化、schema 是相关但独立的三面；直接 hook 的 owner 必须分别测试。

## 一张类型的四条数据路径

复用一个 `TypeAdapter(ProviderReference)` 可以观察真实路径：

| 调用 | 输入 | 结果／输出 | 本例负责的 schema 节点 |
|---|---|---|---|
| `validate_python(...)` | Python `str` | normalize 后的 `ProviderReference` subclass | string → after validator |
| `validate_json(...)` | JSON `bytes`／`str` | JSON decoder 后进入同一验证 graph，返回 subclass | JSON parse → string → after validator |
| `dump_python(value)` | validated object | Python mode 保留 `ProviderReference`（它也是 `str`） | Python representation |
| `dump_python(value, mode="json")`／`dump_json(value)` | validated object | plain `str`／JSON string bytes | `to_string_ser_schema()` |

[高级类型测试](lab/tests/test_advanced_types.py) 锁住 JSON-mode dump 和 JSON bytes，而不是假设 Python-mode 与 wire-mode 类型完全一样。边界 writer 应使用 JSON mode 或 `dump_json()`；内部 Python 表示不等于线上 wire 表示。

无论从 Python 还是 JSON 进入，验证后的值都是 subclass。这一点是 direct custom type 相对 `Annotated[str, ...]` 的主要语义收益之一；若业务从不观察该 identity，就应重新考虑是否值得下沉。

## schema 与 `TypeAdapter` 要复用，不能在 hot loop 里重建

模型 class 会复用其已构建的 validator／serializer；对 bare type、union、`Annotated` 或容器，`TypeAdapter` 提供同样的统一入口。构造 adapter 需要解析 annotation、生成并编译 schema，因此应在稳定生命周期中创建一次：

```python
provider_reference_adapter = TypeAdapter(ProviderReference)


def parse_many(values: list[str]) -> list[ProviderReference]:
    return [provider_reference_adapter.validate_python(value) for value in values]
```

不要这样写：

```python
def parse_many(values: list[str]) -> list[ProviderReference]:
    return [TypeAdapter(ProviderReference).validate_python(value) for value in values]
```

第二段把 schema 构建与编译混进每次迭代，测到的主要可能是 setup。若整个列表本身就是一个可信边界契约，还可以构建一次 `TypeAdapter(list[ProviderReference])`；但这会改变错误收集、输入规模和内存形态，应按真实 workload 测量，不是机械替换。

复用也有边界：不要根据无界用户输入动态生成 annotation 并永久缓存 adapter，否则缓存本身会变成内存攻击面。缓存 key 集合应来自有限、受控的契约版本。

## JSON 直达路径与两阶段路径到底在比较什么

[`performance.py`](lab/src/order_contracts/performance.py) 的 `compare_json_validation()` 比较：

```python
adapter = TypeAdapter(CreateOrderRequest)

adapter.validate_json(raw)
adapter.validate_python(json.loads(raw))
```

两条路径都先各 warm-up 一次，然后用同一个 adapter、同一个 payload 和同一 iteration count 顺序计时：

```text
raw JSON bytes/string
  ├─ TypeAdapter.validate_json ─────────────► pydantic-core parse + validate
  └─ json.loads ─► Python dict/list/scalars ─► validate_python
```

`BaseModel.model_validate_json(raw)` 与前者属于 JSON 直达入口；`json.loads(raw)` + `Model.model_validate(data)` 属于显式两阶段入口。当前 helper 实际测的是 `TypeAdapter` 两个入口，不应把数字冒充为 model class method 的精确 benchmark；生产代码使用哪个入口，就测哪个入口。

JSON 直达路径常能避免先构造完整 Python 中间树再进入 validator，但这只是可验证假设，不是永恒结论：

- payload 大小、嵌套深度、合法／非法比例会改变成本；
- before／wrap／model validators 可能需要 Python 对象，改变两条路径的工作量；
- Python、Pydantic、`pydantic-core` 与 JSON decoder 版本都会改变结果；
- 顺序计时会受到 CPU 频率、cache、GC 和背景负载影响；
- 若业务本来就需要 `json.loads()` 后的 dict 做别的工作，中间树未必是额外成本。

因此只能报告这样的结论：“在锁定的 Python/Pydantic 版本、输入集合、机器和 benchmark 配置下，观察到 A 与 B 的分布。”不能从一次 laptop 计时推出“永远快 N 倍”，也不能把 `direct_json_seconds < loads_then_validate_seconds` 写进普通 CI。

### 当前测试为什么不比较快慢

[性能观测测试](lab/tests/test_performance_observations.py) 用很少迭代确认：

- 返回的 `iterations` 与请求值一致；
- 两个 duration 都是正数；
- 非正 iteration 被拒绝。

这是 observation harness smoke test，不是性能回归测试。它避免在 CI 上引入机器阈值，却也不证明某条路径更快。真正 benchmark 至少应：

1. 锁 Python、Pydantic、`pydantic-core`、payload corpus 和机器／runner；
2. 把 adapter/schema 构建放在计时区外，并做 warm-up；
3. 覆盖小／大、合法／非法、典型／极端输入，而不是一个 happy payload；
4. 多轮重复，报告分布而非单次值，必要时交替路径顺序并观察 allocation；
5. 优化后重跑契约测试，确认输出、错误和 schema 没有漂移。

如果要建立回归 gate，应在专用、稳定 runner 上按历史噪声设统计政策，并保留 raw observations；本章的普通 pytest suite 有意不承担这项工作。

## `model_construct()` 不是通用性能开关

`Model.model_construct()` 跳过正常 validation。它只适合调用方已经用其他方式建立了可信、正确的 field values，并且愿意承担不变量责任的窄边界。风险包括：

- raw nested dict 不会因为 annotation 就自动变成所需 nested model；
- field／model validators、normalize 与拒绝政策不会执行；
- invalid object 可进入后续 domain／serialization 路径，失败位置更远；
- Pydantic v2 已缩小简单模型 validation 与 construct 的性能差距，简单场景中 construct 不保证更快。

所以决策顺序不是“数据来自内部 → construct”，而是：先证明 producer 已建立相同不变量，再 profile 两条真实路径，并用等价后置条件检查结果。外部 HTTP、MQ、webhook 或配置边界不应为了未经证明的微优化绕过 validation。

## `FailFast` 与 wrap validator：少做工作，也会少给信息

对大型 sequence，`Annotated[list[Item], FailFast()]` 可以在第一个 item error 时停止，而不是继续收集后续错误。它可能减少大量非法输入的工作，但会改变错误契约：用户、批处理运营和 telemetry 只能看到第一个失败项。只在以下条件同时成立时考虑：

- profile 表明大量时间确实花在失败后的继续校验；
- 产品只需要 valid/invalid 或首个错误；
- 测试与 API 文档允许错误数量／位置集合变化；
- 攻击者不能借超大输入绕过更外层 body size／batch size 限制。

`WrapValidator` 同样能 short-circuit、调用 handler、捕获错误后重试或提供 default。灵活性意味着 Python callback 和异常控制流开销，也意味着它可能改变接受集合和错误形状。不要把 wrap 当成默认性能技巧；若 `Field` constraint 或 after validator 已足够，它们通常更易读、更易生成 schema，也更容易由 core 执行。

## profiler-first 优化决策树

```text
profile：validation CPU / allocation 是显著瓶颈吗？
  ├─ 否 → 停止；优化更大的瓶颈，保留清晰边界
  └─ 是
      ├─ adapter/schema 构建出现在 hot path？
      │   └─ 是 → 提升到稳定生命周期并复用，再测
      ├─ JSON decode + Python 中间树占主导？
      │   └─ 是 → 比较 validate_json/model_validate_json 与两阶段真实入口
      ├─ Python before/wrap/model validator 占主导？
      │   └─ 是 → 能否改为内置 constraint／更窄的 after validator？
      ├─ 大批非法 sequence 仍在收集错误？
      │   └─ 是 → 业务允许时评估 FailFast，并锁错误政策
      ├─ payload／batch 本身过大？
      │   └─ 是 → 先限流、限 body/batch；再评估分批或流式边界
      └─ custom Python 对象转换占主导？
          └─ 按扩展阶梯比较 ValidateAs、高层组合与 CoreSchema；锁三面行为
```

每个叶子都要回到同一闭环：**一次只改一个变量，用同一 workload 复测，再运行 validation、serialization、JSON Schema 和 error tests**。优化目标不能以模糊边界、泄漏字段或绕过不变量为代价。

profile 工具也要匹配问题：CPU profiler 找 validator/callback 热点，allocation profiler 找中间 dict/list 与复制，端到端 tracing 判断 validation 是否真的占请求延迟。只看一段 `timeit` 无法说明数据库、网络、队列等待中的真实比例。

## Java 与 Go：低层扩展的责任不会消失

### Java：Jackson module／custom deserializer

Java 也应先用标准 value type、Bean Validation／字段 annotation 与 Jackson 内置配置。只有 wire grammar 或对象构造无法表达时，才注册 custom `JsonDeserializer`／`JsonSerializer` 或 module。

这与 CoreSchema hook 的责任相似：deserializer 决定接受与 normalize，serializer 决定 wire output；OpenAPI／JSON Schema generator 却不一定自动理解自定义逻辑，仍需显式 schema annotation／module 与契约测试。`ObjectMapper` 和 module 应作为长期对象复用，不要在循环里重建。性能结论用 JMH 在固定 JVM、warm-up、fork 和 payload corpus 下取得，不用一次 `System.nanoTime()` 断言。

### Go：`UnmarshalJSON`、text contract 与 codegen

Go 应先用标准类型、struct tags 和边界 validator。字符串 value object 若只需要文本转换，可评估 `encoding.TextUnmarshaler`；需要直接拥有 JSON token 解析时才实现 `json.Unmarshaler`，输出方向另由 `json.Marshaler` 控制。

`UnmarshalJSON` 与 direct CoreSchema hook 一样会把 raw parsing、错误和类型构造交给 custom code；OpenAPI／schema generator 不会自然推导所有分支。应同时写正反例、marshal round-trip 与 schema artifact tests。

protobuf、OpenAPI 或专用 JSON codegen 可减少反射和 allocation，但 generated artifact、版本兼容和 unknown-field 政策仍是契约。用 `go test -bench`、`-benchmem` 和 `benchstat` 比较固定 corpus；“生成代码通常快”也不是跳过测量或边界校验的理由。

三种生态的共同原则是：

```text
declarative built-ins first
→ reusable high-level validation
→ custom parser/schema hook last
→ cache compiler/mapper/adapter artifacts
→ profile and benchmark exact production path
```

## 面试追问

### 1. “什么时候会为一个字符串实现 `__get_pydantic_core_schema__`？”

先问是否需要 subclass identity、跨模型所有权和自定义 serializer。普通 normalize + regex 用 `Annotated` 足够；只有高层组合无法表达，且类型包愿意拥有 validation／serialization／JSON Schema 三面与升级测试时，才直接 hook。

### 2. “`source_type` 和 `handler` 分别做什么？”

hook 处于 schema 构建链。`source_type` 是这次请求生成 schema 的源类型，泛型场景可能携带 type arguments；`handler(other_type)` 请求下游为该类型生成 schema。本例 `handler(str)` 先取得标准 string graph，再由 after validator 包装，最终返回可编译 CoreSchema。

### 3. “已有 CoreSchema，为什么还要 `__get_pydantic_json_schema__`？”

运行时 callable、normalize 和 serializer 不能自动完整翻译成 JSON Schema。需要显式发布 type/pattern 等 consumer 可理解的约束，并测试常量同步；还要审查 strip 这类 JSON Schema 无法表达的 runtime 语义差异。

### 4. “为什么不在 for loop 里创建 `TypeAdapter`？”

adapter 构造包含 annotation 解析和 schema 编译，会把 setup 重复计入 hot path。对有限、稳定契约在模块、service 或 worker 生命周期复用；动态无界类型不能无脑永久缓存。

### 5. “`model_validate_json()` 一定比 `json.loads()` + `model_validate()` 快吗？”

不一定。它常避免 Python 中间树，但 validator 形态、payload、依赖版本和后续是否需要 dict 都会改变结论。固定环境与 corpus，测生产的精确入口并报告分布，不在普通 CI 锁跨机器倍率。

### 6. “`model_construct()` 为什么可能更危险，也未必更快？”

它绕过 validation、normalize 和 nested conversion，把不变量证明转移给调用方；Pydantic v2 简单模型的 validation 已很高效，construct 不保证胜出。只有 trusted prevalidated values、等价后置条件和 profile 证据同时存在时才评估。

### 7. “何时使用 `FailFast`？”

大型非法 sequence 的继续校验被 profile 证明昂贵，而且产品只需要首错时。它改变 error count 与诊断完整性，所以必须作为错误契约变化评审，不是透明优化。

## 本章检查清单

- [ ] 从标准类型、`Annotated`、`Field` 与 functional validator 开始，而不是直接写 CoreSchema
- [ ] 跨字段规则放在 field/model 边界或 domain 层，不伪装成单值类型规则
- [ ] 使用 `ValidateAs`／`GetPydanticSchema` 前，明确它们解决的表示问题和版本成本
- [ ] direct hook 同时锁 validation、serialization、`__get_pydantic_json_schema__`
- [ ] 解释 `source_type`、`handler` 和 returned schema，而不是复制不可维护的 schema dict
- [ ] 复用 model schema／`TypeAdapter`，不在 hot loop 构造
- [ ] benchmark 锁版本、输入、机器和入口，普通测试不写耗时／倍率阈值
- [ ] profile 先确认 validation CPU／allocation，再优化 JSON 路径、validator 或 batch
- [ ] `model_construct`、`FailFast` 和 wrap validator 的语义代价已进入评审
- [ ] 优化后重跑 runtime、错误、serialization 与 JSON Schema 契约测试

## 小结

Pydantic 的强项不是让每个团队都手写 schema graph，而是提供从声明式类型到低层 CoreSchema 的连续扩展层级。`CurrencyCode` 展示了大多数规则应停在 `Annotated`；`ProviderReference` 展示了 direct hook 必须如何同时拥有类型 identity、序列化与 JSON Schema，并承认版本敏感性。

性能也遵循同一边界纪律：复用 schema／adapter，区分 JSON 直达和 Python 中间树路径，拒绝把 smoke timing 当 benchmark，不把 `model_construct()` 当万能开关。只有 profile 指向明确成本时，才沿决策树做最小变化；契约清晰度和不变量始终是优化的前置条件。
