# 09 · 错误契约与可观测性：分类、清洗、再决定处置

> **本章目标**：能把 Pydantic `ValidationError` 与服务错误政策分开：先从结构化 error item 中提取有限事实，再按 HTTP、Webhook、MQ、Settings 或内部命令边界决定响应、重试、隔离和告警。可执行事实来自 [errors.py](lab/src/order_contracts/errors.py)、[adapters.py](lab/src/order_contracts/adapters.py)、[FastAPI adapter](lab/examples/fastapi_adapter.py) 及其 [error](lab/tests/test_errors.py)、[webhook](lab/tests/test_webhook.py)、[settings](lab/tests/test_settings.py) 和 [example](lab/tests/test_examples.py) 测试。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_errors.py tests/test_webhook.py tests/test_settings.py -v
```

当前应有 50 个测试通过。它们固定了错误清洗、消息失败分类、签名先于解析、Settings fail fast 与 secret repr 掩码；broker ack／nack、HTTP 部署和真实日志后端仍是生产 adapter 的责任，lab 没有伪造这些集成。

## 事故开场：把 `errors()` 原样返回，为什么成了数据泄漏？

一次请求把客户标识写成非法值。Pydantic 正确拒绝了它，异常处理中却直接 `return error.errors()`。响应因此包含 raw `input`；另一个 extra field 的键名本身是 token，进入 `loc` 后又被当成“安全路径”回显。与此同时，监控把完整 `loc` 和 customer id 做 metric labels，短时间制造了数百万条时序。

问题不是 Pydantic 产生了错误，而是服务把**诊断对象**误当成**公开错误契约和观测维度**。正确流水线是：

```text
exception / ValidationError
  │ inspect structured fields
  ▼
boundary classification
  ├─ safe public projection ──► HTTP / webhook response
  ├─ delivery policy ─────────► retry / park / DLQ / ack
  └─ bounded telemetry ───────► metrics / trace / redacted log
```

三条输出各有白名单。没有一条应该默认携带完整异常、payload 或 secret。

## `ValidationError.errors()`：字段含义与稳定性

一个 error item 常见这些键，但具体错误不保证每个键都存在：

| 字段 | 含义 | 稳定性与安全政策 |
|---|---|---|
| `type` | 机器可读错误 code，例如 `missing`、`string_pattern_mismatch`、`union_tag_invalid` | 比 `msg` 稳定，适合测试和分类；仍可能随 model／Pydantic major 改变。公开后应视为自己的 API，或映射到自有 code |
| `loc` | 从 root 到失败点的 tuple，成员通常为字段／alias、索引、union 分支标签 | 适合定位和结构测试；重构 nested/union 会改变。extra key 可由攻击者控制，完整 loc 不是天然安全或低基数 |
| `msg` | 给人看的格式化说明 | 文案、标点、模板和版本可能变化；不要锁整句测试，也不要当机器分类 key |
| `input` | 导致失败的原始值，有时是整个 nested container | 可能包含 PII、secret、自由文本或超大 payload；默认不得进入 response、metric、trace 或普通 log |
| `ctx` | 渲染错误模板的上下文，如 limit、expected value，或原始 exception object | 可能敏感、不可 JSON 化或高基数；custom error context 也必须最小化 |
| `url` | Pydantic 内置错误的版本化文档链接 | `include_url=False` 可去掉；custom error 可能没有。不是稳定业务文档 URL |

以 validator 抛 `ValueError("zero is not accepted")` 为例，当前 runtime item 含：

```python
{
    "type": "value_error",
    "loc": ("quantity",),
    "msg": "Value error, zero is not accepted",
    "input": 0,
    "ctx": {"error": ValueError("zero is not accepted")},
    "url": "https://errors.pydantic.dev/...",
}
```

这段形状用于说明字段，不应复制成 golden：`msg` 和 `url` 会随版本变化，`ctx.error` 还是 Python exception。lab 测试有意锁 `type`／`loc`，不锁整句 `msg`。

### `type`／`loc` 也要由服务拥有

“更稳定”不等于“永远稳定”：

- 把普通 union 改成 discriminated union，会改变 error type 和 loc 路径；
- 字段 rename／alias、nested model 或 list 层级会改变 loc；
- Pydantic 升级可能调整内置错误 code；
- `PydanticCustomError` 的 type 是开发者定义的，只有团队自己能保证其版本政策。

内部测试可以精确锁定关键 `type`／`loc`，用来提示契约变化；公开 API 若承诺长期稳定，通常再映射成自有 `code`、`reason` 和审查过的 path，而不是把所有 Pydantic 内部 code 永久透传。

## `to_error_response()`：结构化 allowlist 比字符串 redact 强

[errors.py](lab/src/order_contracts/errors.py) 的完整清洗代码是：

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

它只构造 `reason` 和 `path`，没有序列化 `msg`、`input`、`ctx` 或 `url`。[`test_error_response_exposes_type_and_loc_but_not_input`](lab/tests/test_errors.py) 使用 `top-secret-customer-value` 作为非法 input，并断言最终 JSON 不含该值。

这比先 `str(error)`／`json.dumps(errors())` 再用正则 redact 可靠：

- allowlist 对未来新增诊断字段默认不传播；
- 不依赖值的引号、转义、Unicode、嵌套或 message 格式；
- 不会在 redact 之前先把 secret 复制到日志 formatter／APM；
- response schema 能明确声明只有 reason/path。

`errors(include_input=False, include_context=False, include_url=False)` 可以减少诊断 item，但仍应 project 成自己的错误 DTO。调用参数是纵深防御，明确的输出模型才是长期权限边界。

### loc caveat：字段路径也可能泄漏

核心 `to_error_response()` 直接复制 loc；它不声称能安全处理所有公网 extra key。攻击者可以发送名为 `api_key_sk_live_...` 的未知字段，`extra_forbidden` 的最后一个 loc segment 就是该键。

[FastAPI adapter](lab/examples/fastapi_adapter.py) 因此增加边界专属处理：

```python
path = list(item["loc"])
if item["type"] == "extra_forbidden" and path:
    path[-1] = "<extra>"
details.append(ErrorDetail(reason=item["type"], path=path))
```

[`test_fastapi_validation_handler_redacts_unknown_field_name`](lab/tests/test_examples.py) 固定了该行为。生产政策还可把 union branch 名、过深路径和数组 index 规范化；是否公开 body/query/header 前缀也由 API owner 决定。

完整 loc 也不适合作 metric label：数组索引、未知键和动态 map key 会造成高基数。日志若确需定位，可记录经过 allowlist 的 path class，例如 `items.*.quantity`，而不是原始 loc。

## validator 应抛什么异常？

| 选择 | Pydantic v2 行为 | 适合 | 风险／政策 |
|---|---|---|---|
| `ValueError` | 收集成 `ValidationError`，type 通常为 `value_error` | 简单的输入无效；不需要自有机器 code | message/ctx 会携带异常信息；不要拼 secret，公开层也不应回显 msg |
| `PydanticCustomError` | 生成开发者定义的 type、模板 msg 和 ctx | 需要稳定细粒度机器 code，例如 `currency_mismatch` | type 成为团队维护的契约；ctx 只放安全、有限、可序列化值 |
| `AssertionError`／`assert` | 普通解释器下会成为 `assertion_error` | 不建议用于 runtime 输入验证 | `python -O` 会删除 assert，非法值可能直接通过 |
| `TypeError` | Pydantic v2 不把 validator 内 TypeError 包成 ValidationError，通常向外传播 | 表示调用／实现错误 | 不要用它表达用户输入无效；应走 5xx／bug alert，而不是 4xx |

自定义 error 示例：

```python
from pydantic_core import PydanticCustomError


if currency not in allowed:
    raise PydanticCustomError(
        "unsupported_currency",
        "currency is not supported",
        {"supported_count": len(allowed)},
    )
```

不要把 `allowed` 全列表、customer id、secret 或原始值塞进 ctx；公开层通常仍只取 type/loc。custom type 应使用固定代码，不根据用户输入动态生成，否则 metric cardinality 和兼容性都会失控。

### 为什么 validator 里不能用 `assert`

下面代码在普通运行时看似有效：

```python
@field_validator("quantity")
@classmethod
def positive(cls, value: int) -> int:
    assert value > 0, "must be positive"
    return value
```

执行 `python -O` 时，assert statement 被优化掉，`quantity=-1` 会通过。校验器必须显式 `raise ValueError(...)` 或 `PydanticCustomError(...)`；assert 只适合不会参与生产正确性的开发期断言。

## 五类边界，五种失败政策

| 边界 | 典型失败 | 对外／交付政策 | 不能混淆成 |
|---|---|---|---|
| HTTP | JSON、字段、局部契约无效 | 安全 `invalid_request` + 稳定 4xx；lab FastAPI 选 422 | 领域冲突或所有 5xx |
| Webhook | 签名无效；签名有效但 payload 无效 | 先验签并分开计数／响应；provider retry 由 adapter 协议决定 | 同一个 Pydantic validator 错误 |
| MQ | unknown version、字段永久错误、基础设施暂时失败 | 分类后由 consumer policy 决定 park／DLQ／retry／ack | Pydantic 自动 nack 或自动重试 |
| Settings | 必需配置缺失、格式错误 | 启动 fail fast，不进入 ready；修部署配置后重启 | 某个用户请求的 4xx |
| 内部 command | trusted producer 构造无效意图 | producer/programmer bug；拒绝领域动作并告警 | “外部数据总会错”的普通 validation noise |

分类的目标不是给所有异常贴同一种 `ValidationError`，而是保留责任方和可恢复性。

## HTTP：契约错误、领域冲突、未处理异常分开

[FastAPI example](lab/examples/fastapi_adapter.py) 给 `RequestValidationError` 注册 handler，返回：

```json
{
  "code": "invalid_request",
  "details": [{"reason": "string_pattern_mismatch", "path": ["body", "customer_id"]}]
}
```

它使用 422，并在 OpenAPI 中显式声明 `ErrorResponse`。生产 API 也可以按团队政策使用 400；关键是 code、status、字段和隐私政策稳定，不直接返回 Pydantic msg/input。

后续错误属于不同层：

| 失败 | 示例 | 推荐映射 |
|---|---|---|
| request contract | quantity 类型／范围错误、缺字段、extra | `invalid_request`，400/422 |
| authorize | caller 不能替该 customer 下单 | 自有 `forbidden`，403；不要伪装字段错误 |
| domain conflict | 混合币种、状态不允许取消、幂等 key 冲突 | 自有业务 code，如 `mixed_currency`／`order_state_conflict`；选择 409/422 并文档化 |
| dependency unavailable | DB／broker 暂时不可用 | 503 或受控 5xx；是否重试取决于方法幂等性 |
| unexpected bug | TypeError、KeyError、未识别异常 | 通用 500 + correlation id；原异常保留给受控观测，不回显 stack/message |

lab route 只演示 request validation、DTO → command → domain → projection，没有实现完整 exception hierarchy。不能据此宣称 FastAPI 会自动把 domain `ValueError` 变成正确业务 code；application/API adapter 必须显式映射已知领域异常，让未知异常继续成为 5xx 和告警。

## Webhook：原始 bytes 验签必须先于 parsing

[parse_payment_webhook()](lab/src/order_contracts/adapters.py) 的顺序是：

```python
def parse_payment_webhook(
    raw: bytes,
    signature: str,
    secret: SecretStr,
) -> PaymentWebhookEnvelope:
    if not isinstance(signature, str) or re.fullmatch(
        r"[0-9A-Fa-f]{64}", signature
    ) is None:
        raise InvalidWebhookSignature("invalid webhook signature") from None
    supplied = bytes.fromhex(signature)
    expected = hmac.new(
        secret.get_secret_value().encode(),
        raw,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected, supplied):
        raise InvalidWebhookSignature("invalid webhook signature")
    return PaymentWebhookEnvelope.model_validate_json(raw)
```

`InvalidWebhookSignature` 在任何 JSON parsing 前产生。即使 `raw == b"not-json"`，错误签名也先失败；只有签名有效，才让 Pydantic 检查 envelope/payload。这保护三个事实：

- HMAC 覆盖 provider 实际发送的原始 bytes，不是 parse 后重新编码、键顺序或数字格式已变化的 JSON；
- 未认证 payload 不进入复杂 schema 处理和业务路径；
- `webhook_signature_invalid` 与 `webhook_payload_invalid` 可以分别观察，责任与 provider retry 决策不同。

签名格式、digest、raw payload 和 secret 都不得记日志。外部 response 是否故意合并状态以避免 oracle、签名失败是否重试、payload 永久错误是否返回 2xx 防止 provider 风暴，取决于 provider contract；Pydantic 和 `InvalidWebhookSignature` 只给 adapter 足够的分类事实。

不要把签名校验写成 model validator：Pydantic 收到的通常已经是解析后的结构，无法证明它对应被签名的原始 bytes；secret、header 与 body 的边界职责也会被揉进 payload schema。

## MQ：先判断可恢复性，再决定交付动作

[classify_consume_failure()](lab/src/order_contracts/errors.py) 的核心政策是：

```python
def classify_consume_failure(error: Exception) -> MessageFailureKind:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return MessageFailureKind.TRANSIENT
    if isinstance(error, ValidationError):
        errors = error.errors(include_url=False)
        if any(
            item["type"] in {"union_tag_invalid", "union_tag_not_found"}
            or (
                item["type"] == "literal_error"
                and item["loc"]
                and item["loc"][-1] in {"schema_version", "event_type"}
            )
            for item in errors
        ):
            return MessageFailureKind.INCOMPATIBLE
        return MessageFailureKind.PERMANENT
    raise error
```

| kind | 当前 lab 证据 | 含义 |
|---|---|---|
| `incompatible` | unknown/missing union tag；协议 header 的 version/type literal 错误 | 当前 consumer 不认识协议；重复执行同一 binary 通常不会自行成功 |
| `permanent` | 普通字段／literal validation error | 这份 message 在当前契约下无效；不应无界重试 |
| `transient` | `TimeoutError`、`ConnectionError` | delivery 之外的依赖暂时不可用，稍后可能成功 |

一个**示例 application policy**可以是：

```text
incompatible → 写入独立 parking/quarantine 成功后 ack，等待 consumer 升级
permanent    → 发布到 DLQ（含安全 metadata）成功后 ack
transient    → bounded exponential backoff + jitter；当前不进 DLQ
unknown      → 不吞掉；让 supervisor/alert 捕获 programmer bug
```

这里“只有 permanent 进入 DLQ”只是示例，不是 Pydantic 规则。团队也可能把 incompatible 放版本专用隔离队列、让 transient 超过预算后进操作队列，或按 broker 能力选择 nack。ack 与隔离写入的原子性、最大次数、backoff、jitter、消费幂等、ordering 和 retention 都由 application/consumer adapter 决定。

不要把所有 `ValidationError` 一律 DLQ：unknown version 可能在新 consumer 部署后可重放，和字段永久损坏的运营动作不同。也不要 `except Exception: transient`，那会把 TypeError／KeyError bug 变成重试风暴。[unknown-exception tests](lab/tests/test_errors.py) 要求 classifier 原样重新抛出 TypeError、KeyError、AssertionError。

当前 classifier 只显式识别 Python `TimeoutError`／`ConnectionError`。真实 DB driver、HTTP client 和 broker 的 timeout hierarchy 未必继承它们；生产 adapter 应把**已知**基础设施异常规范成受控 transient 类型，不能靠 broad name matching 或 message string 猜测。

### DLQ payload 仍是出站契约

DLQ 不是“内部所以可全量 dump”。安全 metadata 通常只含：原 topic/partition/offset、受控 event type/version bucket、failure kind、error type、attempt count、trace/correlation id 和加密对象存储引用。是否保存原始 payload 取决于 PII 分类、访问控制、加密与 retention；不要把 secret、完整 `errors()` 或 customer id 默认复制进 DLQ header。

## Settings：无效配置应让启动失败

[get_settings()](lab/src/order_contracts/config.py) 在首次调用时验证必需 payment 配置；缺失时 `ValidationError.loc == ("payment",)`。[`test_startup_factory_fails_fast_without_required_settings`](lab/tests/test_settings.py) 证明服务不能拿一份半有效 Settings 继续启动。

生产进程应在 readiness 之前调用 factory：

- 必需配置无效 → 启动失败／not ready，部署系统修复配置后重启；
- 不把配置错误映射成某个业务请求 4xx，也不在每次 request 重试加载；
- 指标可用固定 `settings_invalid{component="payment"}`，日志记录字段分类而非 value；
- `SecretStr` 的 repr 掩码只是纵深防御，不能打印 `get_secret_value()`、完整 env、dotenv 或 file secret。

`get_settings()` 的 `lru_cache` 只缓存成功返回；异常不会成为有效 singleton。测试在前后调用 `clear_settings_cache()`，避免一个测试的环境和缓存污染另一个。生产 reload／rotation 是否允许是独立生命周期设计，不要在失败后静默使用旧默认值。

## 内部 command 无效：producer bug，不是边界噪声

[`CreateOrderCommand`](lab/src/order_contracts/application/commands.py) 是 trusted application dataclass，由显式 mapper 构造，不接 raw JSON。application/domain 仍会维护单币种、状态迁移等不变量；但若内部调用方绕开 mapper、构造缺行或非法类型的 command，这说明 producer 违反内部 API。

处置应当：拒绝领域动作、保留 transaction 一致性、产生 bug-level alert，并修调用方／测试。不要把它计入公网 `invalid_request` 比例、自动转成“用户输错”，也不要因为来源在进程内就继续写数据库。

同一个领域拒绝要结合来源解释：HTTP 合法 payload 映射出的混合币种可成为公开 `mixed_currency` 业务错误；测试／内部 job 手造同样无效 command 则是 producer bug。Pydantic error type 不能替 application 判断责任方。

## 可观测性：高信息，不制造高基数与二次泄漏

### metrics 只使用低基数维度

适合 counter label 的值必须是代码控制、有限集合：

```text
contract_rejection_total{
  boundary="http",
  model="create_order",
  reason="string_pattern_mismatch"
}

message_failure_total{
  event_family="order_created",
  failure_kind="incompatible",
  version_bucket="unknown"
}
```

合理维度包括：

- `boundary`: `http|webhook|mq|settings|internal`；
- 稳定 model/event family，不使用用户传入的原始 event_type；
- allowlisted error `type` 或映射后的 reason；
- `failure_kind`: incompatible/permanent/transient；
- 固定 model version bucket：`v1|v2|unknown`，不直接用攻击者提交的任意 version。

禁止做 metric label：完整 `loc`、数组 index、extra field name、msg、input、customer/order id、idempotency key、URL、exception message、trace id。它们要么高基数，要么敏感；customer id 也不能因为“方便查图”进入 label。

错误类型集合也应 allowlist。`PydanticCustomError.type` 必须是源码常量；若动态拼接用户值，同样会炸 cardinality。Pydantic 升级新增 type 时，先落入 `other` 并通过 dashboard/测试审查，再扩展 label allowlist。

### trace／log 使用不同字段预算

log 可以携带 request/trace correlation id，trace 系统本身也有 trace id；这些用于单次定位，不应复制到 metrics labels。推荐结构：

```json
{
  "event": "contract_rejected",
  "boundary": "http",
  "model": "create_order",
  "reason": "string_pattern_mismatch",
  "path_class": "customer_id",
  "request_id": "req_opaque"
}
```

这是字段集合示意，真实 request id 应由基础设施生成。不要记录 raw payload、完整 loc、input、ctx、signature、Authorization、cookie、webhook secret、Settings、自由文本或 `SecretStr.get_secret_value()`。

APM `record_exception()` 也要审查：exception message、locals、stack frame 和 request capture 可能重新带回 input/secret。配置 server-side redaction、body capture policy、数据保留和访问控制，并用 canary secret 测试观测管线，而不是只检查业务 logger。

对公网无效请求按 type/boundary 聚合、采样或 rate limit 日志，避免攻击者用 validation failures 制造成本和告警风暴。metric 保留总体计数；详细安全样本进入受控日志，不需要每次错误都复制完整诊断。

## Java／Go 对照

### Java / Spring

Spring MVC request binding／Bean Validation 常产生 `MethodArgumentNotValidException`。`@ControllerAdvice` 应从 `BindingResult` 映射自有 code 和审查过的 field path，不直接返回 `FieldError.getRejectedValue()` 或依赖完整 message；message bundle 和 validator 版本会变化，机器分类使用稳定 code。

领域异常、授权异常和 unexpected exception 分别映射 4xx／业务 conflict／5xx，不能把所有异常包装成 `MethodArgumentNotValidException`。Webhook HMAC 应在 Jackson 反序列化前针对原始 body 验证。Kafka/Rabbit listener 的 nack、backoff、DLT/DLQ 是 error handler/container/application 配置，不由 Jakarta Bean Validation 自动决定。

### Go

Go handler 通常显式 `json.Decoder` + validator，再把 validation details project 成公开 error struct。用 `%w` wrap 保留 cause，通过 `errors.Is`／`errors.As` 和 typed/sentinel errors 分类；不要解析 `err.Error()` 字符串决定 HTTP status 或 retry。

领域 conflict、context deadline／network timeout 和 programmer bug 走不同路径。broker consumer 明确调用 ack/nack、安排 backoff／parking／DLQ，并在 unknown error 时返回给 supervisor；Go struct tag 或 validator 库同样不会替应用选择重试政策。日志记录固定 kind 与 correlation id，不把 wrapped error chain 中可能含有的 payload／secret 盲目展开。

## 面试场景

### “为什么不直接返回 `ValidationError.errors()`？”

它是内部诊断结构，可能含 input、ctx、versioned url 和不安全 loc。显式 project type/loc，再对 extra loc 做边界 redaction；公开 code/path 由 API owner 维护。

### “测试为什么断言 type/loc，不断言 msg？”

type/loc 适合机器分类和定位，变化需要审查；msg 是人类文案，可能随 Pydantic 版本、模板和上下文变化。即使 type/loc 对外发布，也应承认 model refactor 会改变并维护兼容政策。

### “`assert` 很简洁，为什么 validator 不能用？”

`python -O` 会删除 assert，生产正确性随启动参数改变。显式 `ValueError` 或固定 `PydanticCustomError` 才会持续执行。

### “MQ validation error 是否都进 DLQ？”

不。unknown version/tag 是 incompatible；普通字段错误是 permanent；timeout 是 transient；unknown exception 应暴露 bug。DLQ、parking、retry、ack 是团队的 application policy，“只有 permanent 进 DLQ”也只是本章示例。

### “Webhook 为什么不能先 parse 再验签？”

签名覆盖原始 bytes；parse/re-encode 会改变空白、键序、数字文本。未认证 payload 也不应先进入 schema／业务逻辑。签名失败与 payload validation 失败必须分开分类。

### “怎样让错误可观测又不泄漏？”

metrics 用 boundary/model/allowlisted type/version bucket 等低基数维度；日志/trace 用 opaque correlation id 和规范化 path class；input、完整 loc、客户 ID、signature、secret 不进入 labels 或普通日志。

## 最终评审清单

1. 异常来自 HTTP、Webhook、MQ、Settings 还是内部 command？责任方和恢复方式是什么？
2. 是否只 project 公开 code/type/path，排除 msg/input/ctx/url？
3. loc 是否含 extra key、index、union tag 或内部字段，需要 normalize/redact？
4. validator 是否显式抛 ValueError／固定 PydanticCustomError，而不是 assert 或 TypeError？
5. HTTP contract、domain conflict、dependency failure 和 unknown bug 是否有不同 mapping？
6. Webhook 是否对原始 bytes 先验签，且不记录 signature/body/secret？
7. MQ incompatible/permanent/transient 是否按真实异常分类，unknown 是否传播？
8. retry／DLQ／parking／ack 是否明确标为 application policy，并有幂等、预算和回滚？
9. Settings 是否在 readiness 前 fail fast，内部 command bug 是否告警？
10. metric labels 是否低基数且无 loc/input/customer id，trace/log 是否通过隐私审查？

最终原则：**Pydantic 提供结构化失败事实；服务必须把它清洗成安全契约、按边界判断可恢复性，再用低基数、无 secret 的信号观察。**
