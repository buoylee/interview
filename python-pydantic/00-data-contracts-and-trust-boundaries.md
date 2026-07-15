# 00 · 数据契约与信任边界

> **本章目标**：先建立整套教程的架构坐标。Pydantic 负责把不可信输入收敛成可信的局部事实；应用层和领域层再决定“这件事能不能做”。可运行事实以 [Order Contracts Lab](lab/README.md) 为准。

## 事故开场：模型构造成功，为什么订单仍然不能下？

一次大促中，请求体里的 `customer_id`、幂等键、SKU、数量和金额都符合格式，`CreateOrderRequest` 也构造成功，但下单仍然必须失败：最后一件库存已被另一个请求售出。

这不是 Pydantic 漏检。它只能根据当前输入回答“数据是否满足契约”：数量是不是 1～100 的整数、SKU 是否重复、金额能否表示、币种能否规范化。库存则是请求之外、随并发变化的业务状态；要回答“现在是否允许创建订单”，必须读取库存并执行领域或应用规则。

把两个问题混在一起，是生产事故和架构面试里都很常见的误区：

- **契约有效（valid）**：这份数据结构完整，局部值合法，可以进入系统。
- **业务允许（allowed）**：当前操作者有权限，库存和额度足够，订单状态允许迁移，可以执行动作。

本 lab 故意不连接库存、数据库或支付平台。因此“售罄”是现实场景，不是假装已经实现的接口；lab 负责展示的是售罄检查之前和之后，数据应如何跨层流动。

## 一句话心智：Pydantic 守边界，不替领域做决定

**Pydantic 是运行时数据契约引擎：它在信任边界上 parse、validate、normalize；应用与领域代码继续 authorize、act；出站适配器再 project、serialize。**

这七个动词是本教程的统一语言：

| 动词 | 问题 | 本 lab 中的落点 |
|---|---|---|
| `parse` | bytes / JSON 能否被读成候选值？ | `CreateOrderRequest.model_validate_json(raw)` |
| `validate` | 结构、类型和局部不变量是否成立？ | `StrictInt`、范围、正则、`extra="forbid"`、重复 SKU 校验 |
| `normalize` | 契约允许的等价值是否收敛成标准表示？ | `"usd"` → `"USD"` |
| `authorize` | 谁能对什么资源发起这个动作？ | 应用层职责；lab 未接身份与权限系统 |
| `act` | 业务状态能否变化，变化结果是什么？ | `Order.create(...)` 校验单币种并创建订单 |
| `project` | 当前消费者允许看到哪些字段？ | `project_customer_order(...)` 显式白名单映射 |
| `serialize` | 结果如何稳定地变成 JSON 形状？ | `CustomerOrderView.model_dump(mode="json")` |

`model_validate_json` 可能在一次调用里同时完成 parse、validate 和 normalize，但架构讨论仍应把三个概念拆开：解析成功不代表字段有效，字段有效也不代表业务允许。

## 从 raw bytes 到领域行为的完整流水线

```text
raw bytes
   │
   ▼
外部 schema（CreateOrderRequest）
   │  parse / 明确允许的 coerce
   ▼
类型与局部不变量（validate + normalize）
   │
   ▼  显式 mapper：to_create_order_command
内部 command（CreateOrderCommand）
   │  authorize（真实服务的应用层；本 lab 未实现身份系统）
   ▼
domain（Order.create / act）
   │
   ├──► view（CustomerOrderView）
   └──► event（OrderCreatedEnvelopeV2）
              │  project / serialize
              ▼
             JSON
```

这条流水线有意使用不同的模型，而不是把一个 `BaseModel` 传到底：

1. [inbound/create_order.py](lab/src/order_contracts/inbound/create_order.py) 的 `CreateOrderRequest` 面向 HTTP 输入，拒绝未知字段和字符串数量，并把币种规范成大写。
2. [adapters.py](lab/src/order_contracts/adapters.py) 的 `to_create_order_command` 逐字段映射，形成内部 `CreateOrderCommand`；信任在这里提升，但不是无限提升。
3. [domain/order.py](lab/src/order_contracts/domain/order.py) 的 `Order.create` 执行领域规则。混合币种只有聚合整张订单时才能判断，所以不塞进单个金额字段的校验器。
4. 同一适配器把领域对象 project 成 `CustomerOrderView` 或事件，再由 Pydantic serialize 成消费者需要的 JSON。

一个重要的工程结论是：**验证不是“清洗后永远安全”的一次性仪式，而是每跨过一个不同信任边界，就按该边界的契约重新建立信任。**

## 五类信任边界

下表中的“失败政策”是服务适配器应做的决定。lab 只通过异常和测试固定契约，不伪装已经实现 HTTP 状态码、broker ack 或 DLQ。

| 边界 | 数据来源与威胁 | coercion / normalize 政策 | unknown-field 政策 | 失败政策 |
|---|---|---|---|---|
| HTTP 请求 | 公网客户端；可被篡改、过期或误用 | 默认严格；本例拒绝 `quantity="2"`，只显式允许币种大小写归一 | `CreateOrderRequest` 使用 `extra="forbid"`，阻断意外字段与 mass assignment | 转成稳定的 4xx 契约错误；不要进入领域动作 |
| Webhook | 第三方推送；既要验来源，也要验载荷 | 先基于原始 bytes 验 HMAC，再解析；版本号要求原始整数 | envelope 与具体 payload 均 `forbid` | 签名失败与 schema 失败分开观测；是否让提供方重试由 adapter 协议决定 |
| MQ 消息 | 上游服务和历史版本；可能重复、乱序或 poison message | 按 `schema_version` 选择明确版本，不做静默跨版本猜测 | 事件 envelope 使用 `forbid` | schema 永久错误通常进入隔离队列；暂时故障才重试；ack / nack 必须由消费 adapter 明确决定 |
| Settings | 环境变量、dotenv、file secrets；天然是文本且含敏感值 | 只为已知文本格式显式转换，例如 `"5"` → `5`、CSV → 币种元组 | 顶层忽略无关环境键；嵌套 `PaymentProviderSettings` 仍 `forbid` | 缺少必需配置时启动即失败，秘密用 `SecretStr` 避免 repr 泄漏 |
| 内部命令 | 已经过入口验证并由 mapper 生成的进程内数据 | 不再做方便性的隐式 coercion；保持精确类型和值对象语义 | dataclass 没有“额外 JSON 字段”概念，mapper 只列出允许字段 | 构造错误是编程错误；外部状态和状态迁移失败交给 application / domain |

HTTP 与 Settings 的策略不同并不矛盾。`"5"` 在 JSON 中是客户端主动发送的字符串，而环境变量从介质上只能是字符串；边界不同，允许的 coercion 就应不同。严格不是“所有地方一律不转换”，而是**转换必须有边界语义和测试依据**。

Webhook 的顺序尤其关键：[parse_payment_webhook](lab/src/order_contracts/adapters.py) 在解析 payload 之前验证签名。若先解析再重编码，空格、键顺序或数字表示的变化都可能让验签对象不再是提供方真正发送的 bytes。

## 类型注解、静态检查、运行时验证、业务规则不是一件事

完整的 Python 类型基础见 [09 · 类型系统与 typing](../python/09-typing.md)。本章只锁定四条边界：

| 机制 | 看到什么 | 何时工作 | 不能替代什么 |
|---|---|---|---|
| 类型注解 | 源码声明和 `__annotations__` | 本身不主动检查；供工具或框架消费 | 不能阻止解释器把错误类型传入普通函数 |
| mypy / Pyright | 静态可见的调用与类型关系 | 运行前、CI 中 | 看不到网络在运行时送来的真实 JSON，也不知道库存 |
| Pydantic | 运行时实际输入 | 边界解析或模型构造时 | 不负责用户权限、外部库存和状态迁移 |
| 业务规则 | 聚合状态、外部状态与用例语义 | application / domain 执行动作时 | 不应承担 JSON 语法和字段类型错误 |

本项目**没有安装 mypy 或 Pyright**；[pyproject.toml](lab/pyproject.toml) 的开发依赖只有 pytest。这里提到它们是为了划清职责，不是给出一个当前仓库无法运行的检查命令。

### Java、Go 与 Python 对照

- **Java**：Jackson DTO 负责 JSON 与对象映射，Bean Validation 用 `@NotNull`、`@Size` 等描述字段约束；`javac` 的静态类型检查仍不等于运行时输入验证，更不等于库存和权限规则。常见分层同样是 request DTO → command → domain → response DTO。
- **Go**：`json` struct tags 定义序列化名字，但 `json:"quantity"` 不会自动保证业务范围；团队通常调用显式 validator，或在构造函数中检查不变量。解码、validator 与领域行为仍是三步。
- **Python**：注解由 runtime annotation consumer 读取；Pydantic 正是这样的消费者，它把 `Annotated`、`Field`、validator 等编译成运行时契约。动态读取注解不意味着注解本身突然拥有执行业务规则的能力。

面试时若被问“用了 Pydantic 是否还需要分层”，可以直接回答：Pydantic 相当于把 Jackson DTO 与 Bean Validation、或 Go decoder 与 validator 的一部分组合得更紧；**组合的是边界机制，不是把边界、应用和领域合成一层。**

## 订单案例：一个模型贯穿所有层会怎样

假设为了“少写几个类”，HTTP 请求、内部命令、ORM 持久化对象和响应都复用 `OrderModel`，短期少了一段 mapper，长期会产生四类耦合：

1. **mass assignment**：客户端提交 `is_admin`、`status="paid"` 或内部备注，通用的 `model_dump()` / `**data` 更新路径可能把它们写入内部状态。本 lab 的 `extra="forbid"` 会拒绝 `is_admin`，显式 mapper 则进一步保证只有已审查字段进入 command。
2. **权限字段混入数据验证**：字段类型合法不代表调用者有权设置它。`status` 即使是合法枚举，也只能通过授权后的领域动作迁移，不能靠“DTO 校验通过”赋值。
3. **版本耦合**：数据库加一个列、事件发布 v2、HTTP 响应隐藏一个字段，本来是三个独立演进；共享模型会迫使它们同时发布，或者堆叠大量可选字段与条件 serializer。
4. **ORM 泄漏**：若直接从 ORM 属性生成响应，内部列、懒加载关系或后来新增的敏感字段可能悄悄进入外部 JSON；序列化还可能在请求结束时触发意外查询。

本 lab 给出了可审计的替代方案：`CreateOrderRequest` 只描述入口，`CreateOrderCommand` 只表达应用意图，`Order` 维护领域状态，`CustomerOrderView` 只暴露客户可见字段。[test_serialization.py](lab/tests/test_serialization.py) 还证明，改用 `serialize_as_any=True` 可能重新暴露内部子类字段；因此输出安全依赖显式 project 白名单，而不是“对象已经验证过”。

这也是资深工程实践里 mapper 值得保留的原因：它不是无意义搬运，而是一处可 code review 的权限与版本闸门。

## 决策表：规则应该放在哪一层

| 规则 / 例子 | 归属 | 判断依据 |
|---|---|---|
| JSON 可解析、必填字段、正则、数量 1～100 | Pydantic inbound schema | 只依赖当前输入的结构或单值 |
| 重复 SKU、金额格式、币种大写 normalize | Pydantic schema / 值对象 | 仍是当前 payload 内可确定的局部不变量 |
| 字段白名单、request → command 映射 | adapter | 跨越外部契约与内部意图，必须显式降维 |
| 当前用户能否替客户下单（authorize） | application | 依赖身份、资源和用例策略 |
| 库存是否足够、幂等记录是否已存在 | application / domain service | 依赖仓储或外部状态，不能由 DTO 独自回答 |
| 订单只能使用单一币种、合法状态迁移（act） | domain | 约束聚合一致性和业务行为 |
| HMAC 签名、重试、ack / nack、DLQ | adapter | 属于传输协议、交付语义和边界安全 |
| 客户响应字段、事件版本（project / serialize） | outbound adapter + Pydantic view/event | 取决于消费者契约，不等于领域对象全量状态 |

一个实用的判断法：若规则只看这份输入即可稳定回答，优先放 Pydantic；若必须问“谁、现在、之前发生了什么、外部系统怎么说”，它通常属于 application / domain；若问题是“消息从哪里来、如何确认、失败后谁重试”，它属于 adapter。

## 对应 pytest

先在 lab 目录运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_create_order.py tests/test_adapters.py tests/test_domain_order.py tests/test_serialization.py -v
```

四组测试按失败层次拆开，而不是按“都是订单”塞进一个文件：

- [test_adapters.py](lab/tests/test_adapters.py) 失败，说明边界解析或显式映射出了问题，例如 raw bytes 不是合法 JSON、币种未 normalize、request 字段没有正确进入 command。此时不应调用领域行为。
- [test_domain_order.py](lab/tests/test_domain_order.py) 失败，说明一个已经构造好的 `CreateOrderCommand` 触犯领域不变量，例如同一订单混用 USD 与 EUR。它刻意绕过 HTTP DTO，证明领域规则不会因入口验证通过而消失。
- [test_create_order.py](lab/tests/test_create_order.py) 固定入口契约：严格数量、未知字段、重复 SKU 和不可变集合。
- [test_serialization.py](lab/tests/test_serialization.py) 固定出站白名单，防止内部字段因继承或宽松 serialize 泄漏。

如果线上出现“422 增多”，先看 parse / validate 的 adapter 指标；如果是“合法请求却无法创建订单”，再看 authorize / act 的应用与领域指标。把测试和监控按信任边界分开，故障定位才不会停留在一句模糊的“Pydantic 报错了”。

读完本章后，可以从 [lab README](lab/README.md) 启动完整测试，再沿上述源码与测试链接逐层阅读；后续主题都应回到这条主线判断：数据正处于哪个边界，当前这层究竟有权回答什么问题。
