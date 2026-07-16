# 08 · JSON Schema 与契约演进：diff 是审查入口，不是兼容证明

> **本章目标**：能区分 Pydantic CoreSchema、JSON Schema、运行时行为与跨版本兼容性；能用 deterministic golden workflow 发现 schema 变化，再用 producer／consumer 矩阵判断它是否 breaking。可执行事实来自 [schema exporter](lab/scripts/export_schemas.py)、[create-order golden](lab/schemas/create-order.schema.json)、[OrderCreated V1 golden](lab/schemas/order-created-v1.schema.json)、[OrderCreated V2 golden](lab/schemas/order-created-v2.schema.json) 和 [event compatibility tests](lab/tests/test_event_compatibility.py)。

先重生 schema 并运行聚焦测试：

```bash
cd python-pydantic/lab
uv run python scripts/export_schemas.py
uv run pytest tests/test_json_schema.py tests/test_event_compatibility.py -v
```

当前 lab 收集 19 个测试：3 个 golden 对照和 16 个版本／wire 行为用例。exporter 重跑后不应出现 schema diff。若出现变化，正确动作不是立即接受快照，而是先判断 model、生成器版本或输出政策发生了什么。

## 事故开场：schema diff 只有一行，为什么旧消费者全挂了？

订单事件给 `status` enum 增加了 `refunded`。从新 reader 的视角，这是“允许值变多”，schema 约束似乎更宽松；新 producer 一旦真正发送该值，所有只认识旧 enum 的消费者却开始反序列化失败。

问题在于 schema diff 只描述**一份 schema 怎么变**，兼容性讨论必须同时指出 writer、reader、部署顺序和历史数据：

- 谁在生产哪一个版本？
- 谁正在读取哪一个版本？
- reader 对 unknown field／unknown enum／unknown version 的政策是什么？
- broker 中还保留多久的旧数据？
- 这次变化只改结构，还是悄悄改了单位、时区或字段含义？

因此本章采用四层判断：

```text
Python annotations / validators / serializers
                │ compile
                ▼
CoreSchema：运行时 validation + serialization 机制
                │ generate
                ▼
JSON Schema：可交换的结构描述与 metadata
                │ diff + tests + deployment analysis
                ▼
Compatibility decision：具体 producer 与 consumer 能否共存
```

前一层只能为后一层提供输入，不能自动替它完成证明；schema 相等也不会自动证明语义相等。

## CoreSchema 与 JSON Schema 解决不同问题

### CoreSchema：Pydantic runtime 的执行结构

Pydantic 根据注解、`Field`、validator、serializer 和 model 配置生成 CoreSchema，并由 `pydantic-core` 编译 runtime validator／serializer。它可以表达 before／after／wrap 调用、Python 函数、union 路由和类型转换等执行细节。

CoreSchema 是框架内部执行协议，不是应发布给客户端的 wire contract：

- 它可能包含 Python callable，其他语言无法执行；
- `__pydantic_core_schema__` 等内部形状不是公共版本化 API；
- 它描述“当前进程怎么验证／序列化”，不包含 caller 权限、库存、幂等或事件部署政策；
- 即使两个进程的 CoreSchema 相似，也不表示它们对单位、时区和业务含义达成一致。

应用应通过 `model_validate*`、`model_dump*` 等公共 API 使用它，不要把 CoreSchema JSON 化后充当 schema registry 产物。

### JSON Schema：可交换但有损的描述

`model_json_schema()` 把 Pydantic schema 投影成标准化 JSON 文档，供文档、OpenAPI、codegen、diff 和人工审查使用。它能表达 object properties、required、type、pattern、range、`additionalProperties`、discriminator 等，但无法忠实翻译任意 Python validator 或领域行为。

```python
reader_schema = CreateOrderRequest.model_json_schema(mode="validation")
writer_schema = CustomerOrderView.model_json_schema(mode="serialization")
```

- `mode="validation"` 描述输入到 validator 的形状；
- `mode="serialization"` 描述 serializer 写出的形状；
- field/model serializer、alias 和自定义 schema hook 可能令两种模式不同；
- 两种模式仍只描述各自模型，不会把 inbound request 自动变成安全 outbound view。

本 lab 的 exporter 有意生成 **validation mode** goldens，因为三份产物当前用于审查 request/event reader 契约。若以后发布 response 或 event writer schema，必须明确增加 serialization-mode artifact 和测试，不能悄悄复用 validation golden。

## metadata 帮助人和工具，不执行验证

常见 JSON Schema metadata／组织机制各有明确边界：

| 机制 | 用途 | 不能证明什么 |
|---|---|---|
| `title` | UI／文档中可读名称；Pydantic 默认从字段／类名生成 | 不限制值，也不是稳定业务 identifier |
| `description` | 解释单位、语义、弃用或隐私政策 | 文字写“UTC”不会拒绝 naive datetime |
| `examples` | 文档和测试设计参考 | 示例不是 allowlist，没覆盖的值不因此非法 |
| `$defs` + `$ref` | 去重、复用 nested schema；三份 golden 都引用 `Money` | 不是独立发布版本、运行时对象身份或跨文档 registry |
| `json_schema_extra` | 添加标准／vendor extension 或补充 metadata | 手工写入关键字不会自动给 runtime validator 增加同等行为 |

例如：

```python
class MetadataOnly(BaseModel):
    quantity: int = Field(
        description="必须大于零",
        examples=[1, 2],
        json_schema_extra={"minimum": 1},
    )


assert MetadataOnly(quantity=0).quantity == 0
```

生成 schema 会展示 `minimum: 1`，但模型没有 `Field(gt=0)` 或 validator，runtime 仍接受 0。这会制造比“缺少文档”更危险的假承诺。约束应先由真实类型／validator 执行，再让生成 schema 反映它；必须自定义 JSON Schema 时，也要有 runtime parity test。

`$defs` 名称和 `$ref` 布局也不应被业务代码解析。它们是当前生成器组织文档的方式；消费者应基于发布的契约和标准 resolver 工作，而不是依赖 properties 顺序、definition 名称拼接或文件格式化细节。

## 修复实例：让 `Money` schema 与 runtime 对齐

[Money](lab/src/order_contracts/value_objects.py) 的 runtime before validator 只接受 `Decimal` 或 `str`：

```python
def _validate_money_input(value: Any) -> Any:
    if not isinstance(value, (Decimal, str)):
        raise ValueError("money amount must be a Decimal or decimal string")
    return value
```

若不补充 schema 输入类型，Pydantic 会生成 `anyOf: number | decimal-string`；但 JSON number 先成为 `int`／`float`，随后会被上述 validator 拒绝。Pydantic 无法从任意 Python 函数推导精确输入集合，因此 lab 显式声明 JSON 输入类型。

Money serializer 也标注返回 `str`，因此 validation 与 serialization mode 都只发布 string：

```python
validation_amount = Money.model_json_schema(mode="validation")["properties"]["amount"]
serialization_amount = Money.model_json_schema(mode="serialization")["properties"]["amount"]

assert validation_amount["type"] == "string"
assert serialization_amount["type"] == "string"
```

这个修复揭示了三条治理原则：

1. golden 只能证明“生成结果没有意外变化”，不能证明生成结果与 runtime 完全一致；
2. custom validator 需要 positive／negative runtime tests 和 schema parity 审查；
3. 修复前先选择政策：允许 JSON number，或让 validation JSON Schema 只声明 string；随后同时提交 model、测试、golden 和兼容性判断。

## deterministic golden workflow

[export_schemas.py](lab/scripts/export_schemas.py) 固定了可重现输出：

```python
MODELS: dict[str, type[BaseModel]] = {
    "create-order.schema.json": CreateOrderRequest,
    "order-created-v1.schema.json": OrderCreatedEnvelopeV1,
    "order-created-v2.schema.json": OrderCreatedEnvelopeV2,
}


def render_schema(model: type[BaseModel]) -> str:
    schema = model.model_json_schema(mode="validation")
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
```

稳定文件名、UTF-8、两空格缩进、sorted keys 和一个结尾换行让 code review 聚焦语义，而不是字典顺序。测试读取 JSON 后比较对象：

```python
expected = json.loads(golden_path.read_text(encoding="utf-8"))
assert model.model_json_schema(mode="validation") == expected
```

标准流程只有四步：

1. **生成**：在固定依赖环境运行 `uv run python scripts/export_schemas.py`。
2. **diff**：检查三份 schema 的结构变化、生成器／Pydantic 版本和源模型 diff。
3. **人工判断**：按 producer／consumer 矩阵判断 additive、breaking、metadata-only 或 generator noise；补 runtime、compatibility 和 migration 测试。
4. **提交**：只有变化是有意且迁移方案完整时，才把 model／exporter／tests／golden 一起提交。

禁止把 CI 失败修复成无条件运行 exporter、`git add schemas/` 或 snapshot `--update`。那只会把契约告警自动盖章。若变化不是本任务计划的一部分，应恢复／停止并调查，而不是把新 golden 带入无关 commit。

golden review 至少检查：

- `required` 增删、nullable/default 变化；
- `type`、format、pattern、range、enum／const；
- `additionalProperties` 与 nested `$ref` 指向；
- validation／serialization mode、alias 和 discriminator；
- title／description／examples 等 metadata 是否改变 codegen 或文档；
- diff 背后的业务单位、时区、计算口径和 PII 分类。

## V1 `ignore` 与 V2 `forbid` 并不矛盾

[OrderCreatedV1](lab/src/order_contracts/events/v1.py) 是旧 payload reader，使用 `extra="ignore"`；[OrderCreatedV2](lab/src/order_contracts/events/v2.py) 是当前 V2 contract，使用 `extra="forbid"`。两者优化的失败方向不同：

| 角色 | unknown-field 政策 | 想保护什么 | 代价 |
|---|---|---|---|
| V1 payload reader | `ignore` | 新 producer 添加 `item_count` 时，旧业务逻辑仍能读取认识的 V1 字段 | 拼写错误和未使用新字段也会被静默丢弃 |
| V2 producer/current model | `forbid` | typo、未审查字段、`internal_note` 泄漏在发布前失败 | additive V2 字段必须显式修改 schema 和协同发布 |
| V1/V2 envelope | `forbid` | `schema_version`、`event_type` 等路由 header 不容漂移 | header 扩展必须版本化或明确演进 |

golden 也能看到该政策：V2 payload 和 envelope 有 `additionalProperties: false`；V1 payload 没有该关键字，JSON Schema 默认允许额外属性；V1 envelope 仍是 `false`。

[`test_v1_payload_reader_ignores_additive_v2_field`](lab/tests/test_event_compatibility.py) 直接把带 `item_count` 的 V2 payload 交给 `OrderCreatedV1`，验证字段被接受并丢弃。`test_v2_producer_rejects_unknown_payload_field` 则给 V2 加 `internal_note`，验证 `extra_forbidden`。reader tolerance 与 writer correctness 可以同时成立。

但不要过度外推：整个 V2 envelope 的 `schema_version=2` 不会被 V1 envelope 当成 V1。payload additive compatibility 是一项能力；envelope discriminator 仍要求明确版本路由。

## 先定义 compatibility 的方向

“向后兼容”若没有主语很容易误导。本章使用两个可部署问题：

- **producer compatibility**：部署新 writer 后，当前已部署 readers 是否还能处理它真正发出的数据？
- **consumer compatibility**：部署新 reader 后，它是否还能处理 broker／存储中的旧数据和仍未升级的 writers？

基于 lab 的完整 envelope：

| writer 数据 | V1-only reader | V2-only reader | union reader `OrderCreatedMessage` |
|---|---:|---:|---:|
| V1 envelope | 接受 | 拒绝：版本／required payload 不同 | 接受并选择 V1 |
| V2 envelope | 拒绝：`schema_version=2` | 接受 | 接受并选择 V2 |
| unknown version 3 | 拒绝 | 拒绝 | `union_tag_invalid`，明确 incompatible |
| 缺少 version | 拒绝 | 拒绝 | `union_tag_not_found`，不猜 payload 版本 |

另有一条更窄的 payload 事实：V1 payload reader 能忽略 V2 的 additive `item_count`。不能把它写成“V1 consumer 能读整个 V2 event”，因为 envelope 路由有意拒绝错误 version。

所以从 V1 writer 直接切到 V2 writer，不具备对 V1-only envelope consumer 的 producer compatibility；把 reader 直接从 V1-only 换成 V2-only，也不具备对历史 V1 数据的 consumer compatibility。迁移期需要 union dual-read，或者经过设计的 topic／endpoint 版本隔离。

## discriminator 与 envelope version 是协议路由

lab 将 `OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2` 组成 discriminated union，以 `schema_version` 选择分支：

```python
OrderCreatedMessage = Annotated[
    Annotated[
        OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2,
        Field(discriminator="schema_version"),
    ],
    BeforeValidator(_validate_discriminator_header),
]
```

version 不是 payload 中“有没有 `item_count`”的猜测：

- V1/V2 用 `Literal[1]`／`Literal[2]` 固定 schema；
- missing version 得到原生 `union_tag_not_found`；
- unknown version 得到 `union_tag_invalid`，consumer 可以分类为 incompatible，而非 transient 无限重试；
- header before validator 要求原始 `type(value) is int`，拒绝 Python 中可冒充整数的 `True` 和 JSON `1.0`／`2.0`；
- `event_type` 决定事件族，`schema_version` 决定该事件族的 schema，两者都属于 envelope 协议。

版本号应随 breaking schema／语义变化有意推进，而不是每次部署自增。反过来，schema version 不变也不能为语义变化开后门。

## additive 与 breaking 必须相对 reader／writer 判断

| 变化 | 常见影响 | 订单例子／迁移要求 |
|---|---|---|
| 新增 optional 字段 | tolerant old reader 常可继续；strict reader 可能拒绝 | 添加 `promotion_code` 前先确认 old reader 的 extra policy |
| 新增 required 字段 | 新 reader 无法读取旧数据；old producer 无法满足新 contract | V2 `item_count` required，因此保留 V1 分支读取历史数据 |
| 删除字段 | 仍使用该字段的 reader 失败或业务降级 | 先证明 consumer 不再依赖，再停止 writer，最后删 schema |
| 字段重命名 | 等价于旧字段删除 + 新字段添加 | `customer_id` → `buyer_id` 需双读 alias／双字段窗口或新 version |
| 新增 enum value | schema 对新 reader 变宽，但 old reader 收到新值可能失败 | `status=refunded` 必须按 producer compatibility 审查 |
| 缩窄 type／range／pattern | 旧合法数据可能不再合法 | `item_count` max 100 → 50 前扫描历史与所有 producers |
| 扩宽 type | 新 reader 可接受更多，但新 producer 一旦发送新形态会破坏 old reader | amount 从 string 扩到 number 不能只看新 schema |
| 单位／计算口径改变 | JSON Schema 可能完全不变，通常仍是 breaking semantic change | amount dollars → cents；`item_count` 行数 → quantity 总和 |
| 时区语义改变 | `format: date-time` 可能不变 | `occurred_at` 从 UTC instant 改成本地墙上时间会破坏排序／窗口 |
| `ignore` → `forbid` | 新 reader 拒绝曾经接受的 payload | 必须确认所有 stored data／producers 都无 extra |
| `forbid` → `ignore` | 接受面变宽；可能隐藏 typo 或安全字段漂移 | 这是风险政策变化，不是“只会更兼容” |

required／optional、producer／consumer 是两条轴。给新 writer 增加一个 required 字段，可能不影响会 ignore extra 的 old reader；但让新 reader 要求该字段，会立即破坏旧数据。评审必须写清谁要求、谁发送、何时开始发送。

### schema diff 没变，但语义已经 breaking

假设 `item_count` 仍是 `integer, 1..100`，projection 从“订单行数”改成“所有 line.quantity 之和”。golden 完全不变，但下游若用它估算每单拣货批次、计费或容量，含义已经变化。应新增 `total_quantity` 或推进 version，并给出单位／口径说明和迁移测试，不能用“schema 无 diff”批准。

类似地，`Money.amount` 仍是 decimal string，却从主币单位改为 minor-unit cents；或 `occurred_at` 仍是 date-time string，却不再代表 UTC instant，都是结构不变的 breaking change。

### schema diff 变了，但旧 consumer 仍兼容

V2 payload schema 比 V1 多了 required `item_count`，diff 显著；将 V2 payload 单独交给 V1 payload reader 时，`extra="ignore"` 让旧 consumer 继续读取 `order_id`、`customer_id`、`total`。这说明“有 diff”不等于“所有方向都 breaking”。

限定条件同样重要：V1 envelope 不接受 `schema_version=2`，所以这只是 payload-level consumer compatibility。完整迁移仍要 union reader 或版本化路由。

## dual read／dual write 迁移顺序

推荐把扩大读取能力放在改变写入之前：

1. 盘点所有 consumer、离线任务、重放工具、schema cache 和数据保留期。
2. 部署 **dual-read** union reader，同时接受 V1/V2；对每个分支记录计数、失败分类和业务结果。
3. 确认所有关键 consumer 已能读 V2，再启用 V2 writer；用 canary／小流量观察真实 payload。
4. 如必须 **dual-write**，明确 topic／key／event id、顺序和去重政策，防止同一业务事实产生两次副作用。
5. 停止 V1 writer，但继续读取 V1，直到 broker retention、重放窗口和离线存量越过水位线。
6. 证明 V1 流量归零后再移除 V1 reader、golden 和代码；删除是独立 breaking review。

dual-write 不是默认安全方案。两个 event 可能乱序、部分发布、使用不同 id，consumer 也可能同时订阅后重复扣款／发货。若版本化 topic 或单一 V2 event + dual-read 足够，应避免双写。必须双写时，outbox transaction、幂等 key、可观测性和回滚都属于迁移设计，不由 Pydantic 自动提供。

## schema diff 审查清单

每次 golden 变化逐项记录：

1. 变的是 validation 还是 serialization mode？真实 reader／writer 使用哪个？
2. 哪个 producer 何时开始发送新形态？是否可回滚？
3. 当前和历史 consumers 对 required、extra、enum、null、default 的政策是什么？
4. discriminator／`schema_version` 是否明确选择新分支，unknown version 如何隔离？
5. required、rename、remove、type、range、format、unit、timezone、计算口径是否变化？
6. `additionalProperties` 从允许到拒绝，或反向变化了吗？
7. `$defs`／`$ref` diff 是真实 nested contract 变化，还是生成器组织噪声？
8. title、description、examples、deprecated、vendor extensions 是否影响文档／codegen？
9. custom validator／serializer 是否存在 schema/runtime mismatch，正反例是否跑真实 API？
10. 是否有 old writer × new reader、new writer × old reader 和历史 golden payload 测试？
11. rollout 是否按 dual-read → new-write → retention → old-read removal 排序？
12. diff 是否只包含这次计划内 artifact；是否有人无条件 update snapshots？

评审结果应明确写成：兼容方向、受影响 consumer、迁移阶段、观测指标、回滚点。单独一句“additive”或“测试通过”不够。

## OpenAPI 与 codegen 的边界

OpenAPI 可以把 request／response JSON Schema 与 HTTP operation、status、media type 组合起来，适合文档和 client generation；它仍不能完整表达或执行：

- 未提供 schema annotation 的任意 Python validator／serializer；
- authorize、库存、幂等、单币种和状态迁移；
- broker retry／ack／DLQ 与版本部署顺序；
- 字段单位、隐私等级和语义变化，除非人准确维护 description 并遵守它；
- 真实 server 是否按 published schema 工作。

codegen 产物通过编译也不是 wire compatibility 证明。生成器可能把 missing／null、Decimal、date-time、`oneOf` discriminator、`additionalProperties` 映射成不同语言语义；客户端也可能长期不重生。需要 contract tests、golden payload 和实际旧 client／consumer fixture，而不是只检查 OpenAPI 可解析。

不要把所有 Pydantic models 自动塞进一个 OpenAPI 并称为“契约目录”：只发布真正有 owner 的 request、response 和 versioned event schema，区分 validation／serialization mode，避免内部 model／secret view 被 codegen 扩散。

## Java／Go 与 Avro／Protobuf 对照

### Java

Java REST 常用 Bean Validation + Jackson 生成／维护 OpenAPI；静态 DTO 与 generated client 提高编译期反馈，但 custom validator、Jackson module、`@JsonView` 和业务语义仍可能超出 schema。专用 request／response DTO、golden diff 和 producer／consumer contract test 仍然必要。

事件系统常用 Avro 或 Protobuf：

- Avro 有 writer schema／reader schema resolution 与 default 规则，schema registry 可执行 backward／forward／full 等配置；配置只检查它理解的结构兼容，不能证明 `amount` 单位没变。
- Protobuf 依靠稳定 field number 演进；删除字段后应 reserve number/name，绝不能把旧 number 复用为新语义。unknown field preservation 取决于语言/runtime 和处理路径，不能假定 JSON 转换仍保留。
- generated Java class 能编译不代表 rollout 安全；enum unknown、required-like application invariants、dual write 重复副作用仍需测试和迁移。

### Go

Go `encoding/json` 的 struct tags 只描述字段名、`omitempty`、`-` 等编码选择，本身没有完整 JSON Schema、runtime range validation 或 compatibility checker。`Decoder.DisallowUnknownFields()` 是具体 decoder 的读取政策，不会自动应用到所有入口。

OpenAPI／Protobuf codegen 可以生成 Go types，但 `string` 仍不知道是 dollars 还是 cents，`time.Time` 也不能替协议决定 UTC 语义。手写或生成类型之后，仍要：固定 discriminator/version、显式 validate、维护 old/new fixtures、逐字段 project event，并测试 deployed consumer 的真实 decoder 行为。

跨 JSON、Avro、Protobuf 的共同原则是：schema 技术能让一部分结构规则机器可检验；**compatibility 永远相对于具体 writer、reader、语义和部署时间线。**

## 面试场景

### “新增 optional 字段一定兼容吗？”

不一定。old reader 若 `extra="forbid"` 会拒绝；codegen client 可能对 unknown field 严格；新 producer 也可能立刻依赖该字段改变行为。先查 deployed reader policy，再谈 producer compatibility。

### “golden test 通过说明什么？”

只说明当前生成 JSON Schema 与已评审 snapshot 相等。它不证明 arbitrary validator 被准确表达、old consumer 能读 new event、单位没变或 OpenAPI server 真正遵守 schema。

### “为什么 V1 ignore、V2 forbid？”

V1 是 tolerant old payload reader，目标是读取 additive 新字段；V2 是当前 writer contract，目标是阻断 typo 和未审查泄漏。角色不同，政策不矛盾；envelope header 始终严格。

### “什么时候提升 schema version？”

当结构或语义不能在既有兼容承诺下安全共存时提升，例如 required／rename、enum producer 扩展、单位或计算口径变化。不要按部署次数自增，也不要用版本不变隐藏 breaking semantics。

### “如何零停机从 V1 到 V2？”

先部署 union dual-reader，再启用 V2 writer，观察并保留 V1 读取直到 retention 水位过去，最后移除 V1。dual-write 只有在明确处理重复、顺序、部分失败和回滚后才采用。

最终原则：**生成 schema 是事实采样，golden diff 是审查触发器；只有 producer × consumer × 语义 × rollout 的完整分析，才能给出兼容结论。**
