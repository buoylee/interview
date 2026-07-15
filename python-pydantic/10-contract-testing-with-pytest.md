# 10 · 使用 pytest 进行契约测试：锁行为，不锁偶然实现

> **本章目标**：能把 Pydantic 测试拆成行为、错误、序列化、schema、兼容性、Settings、examples/import 和性能八类，并为每类选择不会制造假稳定性的断言。可运行事实来自 [Order Contracts Lab](lab/README.md) 的全部测试；本章不增加 Hypothesis 或外部服务依赖。

先运行完整 suite：

```bash
cd python-pydantic/lab
uv run pytest -v
```

当前应有 103 个测试通过。这个数量是当前仓库事实，不是教程永远不变的门槛；测试增删时应审查行为覆盖。输出中的机器耗时更不能复制成性能承诺，CPU、Python、依赖版本、CI 负载都会影响它。

## 事故开场：happy path 全绿，为什么升级后仍然接收了坏数据？

一个订单测试只做了这件事：构造合法 payload，断言 `customer_id` 相等。后来有人把 `StrictInt` 改成 `int`，`quantity="2"` 开始被静默转换；又有人在 response 上启用 duck typing，内部支付引用开始出站。原 happy-path 仍然全绿。

契约测试要锁定的不是“模型能构造”，而是每个边界的政策：

```text
接受什么 ───── behavior / coercion / boundary cases
拒绝什么 ───── error type + loc
输出什么 ───── canonical serialization + leak absence
如何演进 ───── schema golden + producer/consumer compatibility
从哪里配置 ─── Settings source isolation + cache lifecycle
能否运行 ───── examples/import smoke
能否测量 ───── performance observation smoke
```

这些观察维度共同把领域与边界行为组织成一座测试金字塔，而不是堆一批相似的 model-construction tests。

## 八类测试各自回答什么

| 类别 | 核心问题 | 主要断言 | 不应替代 |
|---|---|---|---|
| 行为 | 输入是否按政策接受、拒绝、normalize？domain 是否维护不变量？ | canonical value、精确类型、边界正反例 | 错误安全、输出权限 |
| 错误 | 失败能否稳定定位和分类？ | `type`、`loc`、安全 error projection | 整句 `msg` snapshot |
| 序列化 | writer 输出是否为 reviewed canonical shape？ | JSON-mode 完整值、敏感字段不存在 | schema compatibility |
| schema | 生成 artifact 是否发生变化？ | live JSON Schema == reviewed golden | runtime parity、语义兼容 |
| 兼容性 | old/new producer 与 consumer 能否共存？ | 真实 V1/V2 payload matrix、unknown version | 只看 schema diff |
| Settings | source precedence、文本转换、secret 和 cache 是否受控？ | `monkeypatch`／`tmp_path`、fail-fast、redaction | 读取开发机 ambient env |
| examples/import | 教程脚本、package、FastAPI/OpenAPI 是否还能导入执行？ | import + 调用 `main`／handler + 返回契约 | 真实生产 E2E |
| 性能 | 观测函数能否在合法输入上产生可比较的正数？ | iterations、正数、非法参数 | 硬编码耗时／倍率 benchmark |

同一功能可以跨多类。例如 Money 的 validation 是行为测试，JSON string 是序列化测试，生成的 amount schema 是 schema 测试；三者都通过，才接近完整契约。

## 参数化 coercion policy：case 必须同时写输入与结果

coercion 很适合 `pytest.mark.parametrize`，但 case 不能只写一串值再模糊断言“raises”。每行应明确：**input、成功后的 canonical expected，或失败的 error type 与 loc**。

下面是基于真实 `CreateOrderRequest` 的完整示例：

```python
import pytest
from pydantic import ValidationError

from order_contracts.inbound.create_order import CreateOrderRequest


def payload(
    *,
    quantity: object = 2,
    amount: object = "12.30",
    currency: object = "usd",
    root_extra: tuple[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "customer_id": "cus_0123456789ab",
        "idempotency_key": "checkout-2026-0001",
        "items": [
            {
                "sku": "SKU-RED-1",
                "quantity": quantity,
                "unit_price": {"amount": amount, "currency": currency},
            }
        ],
    }
    if root_extra is not None:
        value[root_extra[0]] = root_extra[1]
    return value


@pytest.mark.parametrize(
    ("input_payload", "expected", "error_type", "loc"),
    [
        pytest.param(
            payload(),
            {"quantity": 2, "amount": "12.30", "currency": "USD"},
            None,
            None,
            id="canonical-and-currency-normalization",
        ),
        pytest.param(
            payload(quantity=1),
            {"quantity": 1, "amount": "12.30", "currency": "USD"},
            None,
            None,
            id="quantity-at-minimum",
        ),
        pytest.param(
            payload(quantity=100),
            {"quantity": 100, "amount": "12.30", "currency": "USD"},
            None,
            None,
            id="quantity-at-maximum",
        ),
        pytest.param(
            payload(quantity="2"),
            None,
            "int_type",
            ("items", 0, "quantity"),
            id="string-quantity-is-not-coerced",
        ),
        pytest.param(
            payload(quantity=0),
            None,
            "greater_than_equal",
            ("items", 0, "quantity"),
            id="quantity-below-minimum",
        ),
        pytest.param(
            payload(quantity=101),
            None,
            "less_than_equal",
            ("items", 0, "quantity"),
            id="quantity-above-maximum",
        ),
        pytest.param(
            payload(amount=12.30),
            None,
            "value_error",
            ("items", 0, "unit_price", "amount"),
            id="binary-float-money-is-rejected",
        ),
        pytest.param(
            payload(amount=12),
            None,
            "value_error",
            ("items", 0, "unit_price", "amount"),
            id="integer-money-is-rejected",
        ),
        pytest.param(
            payload(root_extra=("is_admin", True)),
            None,
            "extra_forbidden",
            ("is_admin",),
            id="unknown-root-field-is-rejected",
        ),
    ],
)
def test_create_order_coercion_policy(
    input_payload: dict[str, object],
    expected: dict[str, object] | None,
    error_type: str | None,
    loc: tuple[str | int, ...] | None,
) -> None:
    if error_type is None:
        request = CreateOrderRequest.model_validate(input_payload)
        line = request.items[0]
        assert {
            "quantity": line.quantity,
            "amount": format(line.unit_price.amount, "f"),
            "currency": line.unit_price.currency,
        } == expected
        return

    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(input_payload)
    error = caught.value.errors()[0]
    assert error["type"] == error_type
    assert error["loc"] == loc
```

case id 进入 pytest 输出，失败时立即说明哪条政策破坏。输入 dict 每个 case 独立创建；不要共享后再原地 mutation，否则参数之间会串状态。测试代码也要通过 lint／review，不能因“只是教程”降低标准。

为便于审查，上述表的政策可再写成矩阵：

| input 差异 | expected | error type | loc |
|---|---|---|---|
| quantity `2`、amount `"12.30"`、currency `"usd"` | quantity `2`、amount `"12.30"`、currency `"USD"` | — | — |
| quantity `1`／`100` | 对应边界值，其他字段 canonicalize | — | — |
| quantity `"2"` | — | `int_type` | `items.0.quantity` |
| quantity `0` | — | `greater_than_equal` | `items.0.quantity` |
| quantity `101` | — | `less_than_equal` | `items.0.quantity` |
| amount `12.30` float | — | `value_error` | `items.0.unit_price.amount` |
| amount `12` int | — | `value_error` | `items.0.unit_price.amount` |
| root extra `is_admin=True` | — | `extra_forbidden` | `is_admin` |

### 不要为 DRY 把 case 含义藏起来

参数化适合“同一行为，不同输入”。若每行需要不同 setup、不同边界和十几个条件分支，应拆成命名测试。`test_quantity_does_not_coerce_string` 这样的单独 regression test 很有价值：失败名就是事故语义，不必把所有用例压进一张万能表。

## 正例不能替代反例，边界值要两侧都测

至少覆盖“最小合法／最大合法／刚好非法”，而不是只取中间 happy value：

| 规则 | 正例 | 反例 | 现有事实来源 |
|---|---|---|---|
| unknown field policy | 只有声明字段 | root `is_admin`、nested `unexpected` | `test_create_order.py`、`test_webhook.py` |
| quantity strict/range | `1`、`100`，且类型为 int | `"2"`、`0`、`101`、`True` | `StrictInt` + range；现有 string regression |
| Money input | decimal string `"12.30"`、Python `Decimal` | float `12.30`、int `12`、零、过多小数 | `test_value_objects.py` |
| datetime awareness | `2026-07-15T12:30:00Z`、有 offset | naive `2026-07-15T12:30:00` | `test_webhook.py`／`test_event_compatibility.py` |
| discriminator | `payment.succeeded`、`payment.failed`；event V1/V2 | unknown tag、missing/unknown version | webhook/event compatibility tests |
| signature grammar | lower／upper hex digest | non-hex、Unicode、非 string、前中后空格 | `test_webhook.py` |

现有 suite 已锁住最危险的反例：unknown field、string quantity、float Money、naive datetime 和 bad discriminator。若补充 `1/100/0/101` 等范围 case，应先确认实际业务边界，再把四个 case 放在同一参数表；不要为了覆盖率凭空发明限制。

正例还要断言 canonical 类型和值，而不只是“没有异常”：`type(timeout_seconds) is int`、validated items 是 tuple、ProviderReference 是自定义 subclass、Money 内部是 Decimal。否则 coercion 或 representation 漂移可能悄悄通过。

## 错误测试：锁 `type`／`loc`，不把诊断全文变成 API

推荐模式与 lab 一致：

```python
with pytest.raises(ValidationError) as caught:
    CreateOrderRequest.model_validate(bad_payload)

error = caught.value.errors()[0]
assert error["type"] == "int_type"
assert error["loc"] == ("items", 0, "quantity")
```

- `type` 适合机器分类；变更通常说明约束或 Pydantic 行为改变。
- `loc` 证明错误落在正确字段／分支；nested index 和 discriminator tag 都可见。
- `msg` 是版本化的人类文案，模板、标点可能变化，不锁整句。
- `url` 是 Pydantic 文档地址，不是业务 API。
- `input` 可能含 PII／secret，也不应进入 snapshot 或 assertion failure message。

若公开错误契约承诺自己的 code/path，应测试安全 projection，而不是直接 snapshot `errors()`。[错误章节](09-error-contracts-and-observability.md) 进一步说明 extra key 进入 loc 的 redaction caveat。

对 model-level validator 的 `loc == ()` 不要草率认定“定位不够精确”：它可能正确表示整个 payload／discriminator 失败。若产品要求字段级 path，应在 adapter 映射自有 path 并测试；不要通过断言 msg 文本猜位置。

## round-trip：模型 canonical 对称，不等于 raw input 原样返回

有意义的 round-trip 是：

```python
raw = {
    "customer_id": "cus_0123456789ab",
    "idempotency_key": "checkout-2026-0001",
    "items": [
        {
            "sku": "SKU-RED-1",
            "quantity": 2,
            "unit_price": {"amount": "12.30", "currency": "usd"},
        }
    ],
}

first = CreateOrderRequest.model_validate(raw)
wire = first.model_dump_json()
second = CreateOrderRequest.model_validate_json(wire)

assert second == first
assert second.items[0].unit_price.currency == "USD"
assert json.loads(wire) != raw  # raw 的 "usd" 已 canonicalize 为 "USD"
```

它证明当前 canonical writer 输出能被当前 reader 接受，并恢复等价模型；不证明 bytes、键顺序、原始大小写或 unset 信息保留。

三类常见非原样变化：

- currency before validator 把 `"usd"` normalize 为 `"USD"`；
- Money 内部使用 Decimal，JSON serializer 写 `"12.30"` string，而不是 Python Decimal 或 float；
- validation/serialization alias 可把 `orderId` 读入 `order_id`，默认 dump 或 `by_alias=True` 决定写出哪个名字。

round-trip 只有在该 contract 有意对称时才断言。computed field、one-way serializer、`SecretStr` 掩码、exclude flags、migration alias、旧 reader ignore extra 都可能有损；这时应分别断言 reader acceptance 和 canonical writer shape，而不是强求 `raw == dumped`。

## 序列化与泄漏测试：既断言完整白名单，也断言不存在

[`test_customer_projection_is_an_explicit_whitelist`](lab/tests/test_serialization.py) 用完整 dict 锁客户视图，这是正向 allowlist。仍需高风险字段的 negative assertions：

```python
safe = envelope.model_dump(mode="json")
assert "customer_id" not in safe["order"]
assert "provider_reference" not in safe["order"]
assert "internal_note" not in safe["order"]
```

为什么不是只比较一个 happy-path field？

- `assert safe["order_id"] == ...` 对额外泄漏字段完全无感；
- subclass、`serialize_as_any=True`、computed field 或未来 model field 会扩大输出面；
- error response、Settings repr、example output 也可能从另一通道泄漏。

因此组合三种断言：完整 canonical dict／golden；已知敏感字段不存在；故意启用危险路径时测试它确实会泄漏，用来教育和锁定风险。[`test_serialize_as_any_demonstrates_the_leak_risk`](lab/tests/test_serialization.py) 就是第三类。测试用的 fake secret 也不能被 pytest failure 自动打印到共享日志，尽量使用明显测试假值并只断言 absence。

## schema golden 与 semantic compatibility 是两层门

### 第一层：deterministic schema artifact

工作流是：

```bash
uv run python scripts/export_schemas.py
git diff -- schemas
uv run pytest tests/test_json_schema.py -v
```

`test_json_schema.py` 把 live validation schema 与三份 reviewed golden 作 JSON 对象比较。golden 发现 required、type、constraint、`additionalProperties`、discriminator 等结构 diff；禁止 CI 失败后无条件 update snapshot。

正确顺序：生成 → 看 diff → 判断 planned/unplanned → 补测试与迁移 → 有意提交。即使 diff 只有 description，也要判断文档/codegen 影响；即使无 diff，`item_count` 从行数改成数量总和仍是语义 breaking。

### 第二层：old/new producer × consumer 行为

[`test_event_compatibility.py`](lab/tests/test_event_compatibility.py) 用真实 payload 固定：

| writer | V1-only envelope reader | V2-only envelope reader | union reader |
|---|---:|---:|---:|
| V1 envelope | 接受 | 拒绝 | 接受为 V1 |
| V2 envelope | 拒绝 version | 接受 | 接受为 V2 |
| unknown version | 拒绝 | 拒绝 | `union_tag_invalid` |
| missing version | 拒绝 | 拒绝 | `union_tag_not_found` |

另有 payload-level case：V1 payload reader 因 `extra="ignore"` 忽略 V2 additive `item_count`；这不等于 V1 envelope 能读取 `schema_version=2`。

golden 测试回答“schema artifact 是否变”；兼容测试回答“具体旧／新 reader 能否处理具体旧／新 data”。两层均不可省略。迁移还应测试 dual-reader rollout、历史 fixture、unknown version 分类与 V2 producer 拒绝 `internal_note` 等未审查字段。

## Settings：测试必须隔离 ambient process state

[settings tests](lab/tests/test_settings.py) 的 autouse fixture 是关键基础设施：

```python
@pytest.fixture(autouse=True)
def isolate_order_environment(monkeypatch) -> Iterator[None]:
    order_keys = set(ENV_KEYS)
    order_keys.update(key for key in os.environ if key.upper().startswith("ORDER_"))
    for key in order_keys:
        monkeypatch.delenv(key, raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()
```

设计理由：

- 删除已知 key 还不够；host 可能带未知 `ORDER_` 或不同大小写，必须扫描并按 case-insensitive policy 清理；
- `monkeypatch.setenv/delenv` 自动恢复 process env，不污染其他测试；
- `get_settings()` 有 `lru_cache`，每个测试前后都清 cache，避免第一个模型吞掉后续 env 变化；
- fixture 在 yield 两侧清理，即使测试失败也恢复 cache 生命周期。

文件来源用 `tmp_path` 创建明确 dotenv／secrets directory，不读取用户 home 或仓库外文件。`test_default_loader_does_not_read_ambient_dotenv` 切换到含 `.env` 的临时目录，并证明默认 loader 仍保持 `INFO`；这是负向 isolation test，不是只测试显式 dotenv happy path。

secret 测试只比较受控 placeholder，并断言原文不在 `repr(settings)`／example result。测试失败输出也要遵守秘密政策：不要读取真实 secret manager、CI credential 或开发者 `.env` 再做断言。

source precedence 要成对测试：init > env、env > explicit dotenv、dotenv > file secrets、file secrets > defaults；CSV、nested JSON、strict timeout、prefix、case、extra 分别用小测试定位，避免一个巨型“所有 Settings 都正确”用例失败后无法判断边界。

## examples 与 import safety：教程代码也要被执行

[`test_examples.py`](lab/tests/test_examples.py) 直接 import 并调用：

- HTTP validation example；
- V2 event consumer；
- Settings loader，并断言 secret 只返回掩码；
- FastAPI route、OpenAPI response schema 和 safe validation handler。

这能发现重命名、过期 API、缺依赖、错误输出和 Markdown 周边脚本腐化。examples 应把工作放在 `main()`／显式 factory 中，并用 `if __name__ == "__main__"` 运行 CLI；import 不应连接网络、读取生产 Settings、创建 DB session、消费 broker 或打印 secret。

[`test_package_smoke.py`](lab/tests/test_package_smoke.py) 验证 package 可 import 且 version 存在；[`test_integrations.py`](lab/tests/test_integrations.py) 用纯对象证明 `from_attributes` 只投影属性，不伪造真实 ORM session。import smoke 很窄，但能尽早发现 packaging／module-level side effect；它不替真实 adapter integration 或 E2E。

文档中的长 snippet 若无法直接 import，可以把权威实现放在 `lab/examples/`，Markdown 只引用并解释；pytest 执行脚本，避免两份代码各自漂移。本章的参数化示例属于教学组合，提交前仍通过独立 probe 验证其 type/loc。

## 性能：correctness suite 只做 observation smoke

[`test_performance_observations.py`](lab/tests/test_performance_observations.py) 只断言：

```python
observation = compare_json_validation(raw, iterations=10)
assert observation.iterations == 10
assert observation.direct_json_seconds > 0
assert observation.loads_then_validate_seconds > 0
```

另一个 test 拒绝 `iterations=0`。它证明 measurement path 可执行、返回结构合理；没有断言 direct JSON 必须快多少，也没有把某台机器的秒数写进教程。

普通 CI 不适合硬阈值／倍率门槛：scheduler、CPU frequency、thermal、Python／pydantic 版本、虚拟化和极短计时噪声都会造成 flaky failure。真正 benchmark 应单独运行，包含 warm-up、足够样本、统计分布、固定环境、payload 尺寸、版本基线和显著回归政策；结果是工程观测，不是业务正确性测试。

性能 smoke 也要测参数错误，防止 `iterations<=0` 产生看似合法的零值。不要为了让 benchmark 快而使用 `model_construct()` 或跳过 validation，除非测试明确比较 trusted-only path 并证明边界。

## factories、fixtures 与测试金字塔

### factory 保持 baseline 可读，mutation 保持局部

lab 使用小 factory：`valid_payload()`、`succeeded_payload()`、`v1_message()`／`v2_message()`、`make_order()`、`set_required_env()`。推荐模式：

1. factory 每次返回新对象；
2. case 只修改与测试名相关的一处；nested dict 先 `deepcopy`；
3. expected type/loc 就地写在 test，避免藏进万能 assertion helper；
4. factory 默认值都是公开 placeholder，不读取 ambient state；
5. 领域 factory 经过正常 constructor，除非专门测试 invalid producer。

避免 session-scoped mutable payload、自动填满几十个无关字段的“神 fixture”和把 production model dump 反过来当 expected；这些做法会让 source 与 oracle 共享同一个 bug。

### test pyramid 按反馈速度与边界风险分层

```text
少量 E2E / deployed contract
  HTTP server、真实 DB/broker/provider sandbox（本 lab 未实现）

中量 boundary / integration contract
  adapters、error projection、Settings、serialization、event compatibility、examples

大量 pure unit
  value objects、validators、CoreSchema type、domain behavior、small factories
```

golden/schema 不完全属于传统 unit 或 E2E；它是 artifact review gate，应快速运行但必须配 semantic compatibility。不要用大量 snapshot 取代少量关键行为断言，也不要让所有测试都启动 FastAPI／数据库才获得“真实感”。

## 章节到现有 test 文件映射

| 文件 | 主要类别 | 防止的回归 |
|---|---|---|
| [`test_package_smoke.py`](lab/tests/test_package_smoke.py) | examples/import | package 无法 import、version 丢失 |
| [`test_value_objects.py`](lab/tests/test_value_objects.py) | 行为／序列化 | Currency normalize、ID strictness、Money float/int policy 与 JSON string |
| [`test_create_order.py`](lab/tests/test_create_order.py) | 行为／错误 | string quantity coercion、extra、重复 SKU、tuple immutability |
| [`test_webhook.py`](lab/tests/test_webhook.py) | 行为／错误／兼容性 | discriminator、aware datetime、strict version、签名先于 parse、wire shape |
| [`test_adapters.py`](lab/tests/test_adapters.py) | 行为／错误 | raw JSON parse、invalid JSON type/loc、显式 request → command mapper |
| [`test_domain_order.py`](lab/tests/test_domain_order.py) | 行为 | total/status 与单币种领域不变量 |
| [`test_serialization.py`](lab/tests/test_serialization.py) | 序列化 | customer allowlist、subclass 默认隐藏、`serialize_as_any` 泄漏风险 |
| [`test_event_compatibility.py`](lab/tests/test_event_compatibility.py) | 兼容性／序列化 | V1/V2 union、extra policy、version errors、projection、wire、immutability |
| [`test_errors.py`](lab/tests/test_errors.py) | 错误 | input 不回显、MQ failure classification、unknown bug propagation |
| [`test_settings.py`](lab/tests/test_settings.py) | Settings | source precedence、CSV/strict parse、ambient isolation、secret、fail-fast、cache |
| [`test_json_schema.py`](lab/tests/test_json_schema.py) | schema | 三份 validation schema 偏离 reviewed golden |
| [`test_advanced_types.py`](lab/tests/test_advanced_types.py) | 行为／schema／序列化 | custom CoreSchema normalization、subclass、JSON Schema 与 writer parity |
| [`test_performance_observations.py`](lab/tests/test_performance_observations.py) | 性能 | measurement path 失效、非正 iterations 被接受；不锁机器阈值 |
| [`test_examples.py`](lab/tests/test_examples.py) | examples/import／错误 | 教程脚本腐化、FastAPI route/OpenAPI/error redaction、Settings secret 泄漏 |
| [`test_integrations.py`](lab/tests/test_integrations.py) | integration smoke | `from_attributes` 属性 projection 形状漂移，且不假装测试 ORM session |

映射不是文件只能属于一类；它强迫 review 问“某次变化同时需要哪些层”。例如 event 新增字段至少触及 serialization、schema、compatibility，可能还触及 error 和 example。

## property-based testing：适合扩大输入空间，但本 lab 不引入

property-based testing 很适合：

- Unicode、空白、极长 string、Decimal 边界和 ID pattern；
- nested list 长度、duplicate SKU 组合、discriminator/version 组合；
- `validate(canonical_dump(x)) == x` 这类有意成立的 invariant；
- 确保任意内部字段都不会出现在 public projection 的安全 property。

它的价值是生成手写 case 没想到的组合，并通过 shrinking 给出最小反例。代价是 strategy 设计、运行时间、失败重放和团队学习成本；错误 strategy 还会生成大量业务上无意义输入。

本 lab **不增加 Hypothesis dependency**。当前 explicit examples 是可读的架构教程与 regression anchors；未来若引入 property-based tests，应作为补充，保留发现 bug 后的最小普通 pytest case，并对 seed／deadline／CI profile 做明确政策。

## Java／Go 对照

### Java：JUnit parameterized 与 Spring contract tests

JUnit 5 的 `@ParameterizedTest` + `@MethodSource`／`@CsvSource` 对应 pytest 参数表；每个 `Arguments` 同样应包含 input、expected 或 exception code/path，并用可读 display name。Bean Validation 测试锁 constraint code/property path，不锁整句 localized message。

Spring `MockMvc`／WebTestClient contract tests 验证 status、公开 error DTO、response absence 和 OpenAPI artifact；domain unit tests 不必启动 Spring context。JSON golden 更新也要 generate → diff → review，不能用 snapshot auto-accept 掩盖 DTO 漂移。

### Go：table-driven tests 与 golden files

Go 常用：

```go
tests := []struct {
    name     string
    input    any
    want     any
    wantKind string
    wantPath []any
}{ /* explicit cases */ }

for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) { /* act + assert */ })
}
```

它与 `pytest.mark.parametrize` 同构：case name、input、canonical expected／error kind/path 都应显式。`t.Setenv` 和 `t.TempDir` 隔离 Settings；修改 process env 的 tests 不应随意 `t.Parallel()`。Go golden 常用 `-update` flag，但 CI 不得自动开启；更新后仍要人工看 diff 和跑 old/new fixture compatibility。

Go decoder／validator unit tests、HTTP handler contract、broker consumer fixtures 和少量 E2E 也应组成金字塔；table-driven 并不意味着把所有层塞进一个循环。

## 面试场景

### “一个合法 payload 测试够不够？”

不够。它看不到 strict coercion、unknown field、边界外一位、bad discriminator 或输出泄漏。每条政策至少有代表性正例与反例，范围约束测 min/max 及两侧。

### “为什么不 snapshot 整个 ValidationError？”

msg/url/version 噪声大，input/ctx 可能敏感。锁机器可读 type/loc，再单测安全 public projection；只有自有 error DTO 才适合公开 golden。

### “round-trip 失败说明 serializer 有 bug吗？”

不一定。normalize、alias、Decimal string、computed field、SecretStr mask 都可能有意有损。先定义 invariant 是 model equality、canonical JSON stability 还是 raw byte identity，再写对应断言。

### “schema golden 通过为何还要 compatibility test？”

golden 只告诉你 artifact 是否变化；old reader 对 new enum/required/extra 的真实行为、单位语义和 rollout 不在相等断言里。必须用 V1/V2 fixtures 交叉验证。

### “CI 中能否断言 direct JSON 至少快两倍？”

不能把一次 machine-specific observation 当 correctness。correctness suite 只验证测量可产生正数；倍率回归放受控 benchmark 环境，用分布与基线政策判断。

### “何时值得引入 property-based testing？”

当输入空间大、边界组合多、存在明确 invariant，并且团队愿意维护 strategy/replay 时。它补充而不替代具名 regression、golden 和兼容矩阵；本 lab 当前刻意不引入 Hypothesis。

## 最终评审清单

1. 每条 coercion／normalize 政策是否同时有 input、expected 或 error type/loc？
2. min/max 有合法边界与刚好非法值吗？unknown/string/float/naive/bad tag 都覆盖了吗？
3. 错误断言是否避开 msg/url/input，并单测公开 projection 不泄漏？
4. round-trip 的 invariant 是 canonical model、JSON shape 还是原始 bytes？
5. output test 是否断言敏感字段不存在，而不只检查一个 happy field？
6. schema golden 更新是否经过 diff 和语义审查，且有 V1/V2 compatibility matrix？
7. Settings 是否清 ambient env/cache，使用 monkeypatch/tmp_path，不读取真实 secret？
8. examples/import 是否由 pytest 执行且无 import-time I/O？
9. performance test 是否只做 observation smoke，硬阈值留给受控 benchmark？
10. factory/fixture 是否独立、最小、无隐藏 mutable state？

最终原则：**测试契约的允许、拒绝、canonical output 与演进方向；不要测试偶然文案、机器速度或开发机环境。**
