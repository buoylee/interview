# Pydantic 数据契约教程设计

日期：2026-07-15

状态：已批准，进入实施计划阶段

目标分支：`codex/pydantic-contracts-tutorial`

## 1. 背景

仓库已经有系统化的 Python、并发、数据访问和 FastAPI 运维教程，但 Pydantic 目前只作为 FastAPI、类型提示或生产骨架中的零散知识出现。学习者能看到 `BaseModel`，却缺少一条从信任边界、运行时验证、数据建模一路走到契约演进、配置治理和生产故障分析的完整路径。

本教程将 Pydantic v2 定位为“服务边界的数据契约与运行时验证引擎”，而不是 FastAPI 的附属工具。主线保持框架无关，使用订单／支付服务作为连续案例；FastAPI、消息事件、ORM 映射和 LLM 结构化输出仅作为末尾的边界集成场景。

## 2. 目标读者与教学目标

### 2.1 目标读者

- 已能使用 Python 编写 Web 服务，了解类型提示、JSON、HTTP 和 pytest。
- 用过 Pydantic 或 FastAPI，但知识停留在声明字段、调用 `model_dump()` 的阶段。
- 正在准备高级 Python／后端面试，或需要制定团队的数据契约规范。
- 希望理解 Pydantic v2 的机制、边界和取舍，而不是只查 API 用法。

### 2.2 完成教程后的能力

学习者应能够：

1. 解释 Python 类型注解如何生成 CoreSchema，以及 `pydantic-core` 如何执行验证和序列化。
2. 按 HTTP、Webhook、MQ、配置和内部调用的信任边界制定 coercion／strict 策略。
3. 区分输入 DTO、应用命令、领域对象、输出视图和事件契约，避免一个模型贯穿所有层。
4. 正确组织字段验证、模型验证、规范化和显式映射，不在 validator 中执行 I/O。
5. 防止敏感字段、内部字段和子类字段通过序列化意外泄漏。
6. 使用 JSON Schema、版本化事件和兼容性测试管理契约演进。
7. 将 `ValidationError` 转换为稳定、可观测且不泄密的服务错误契约。
8. 使用 pytest 验证契约行为，而不是只测试几个 happy path 示例。
9. 在确有必要时扩展自定义类型／CoreSchema，并能判断其维护与性能成本。
10. 使用 `pydantic-settings` 管理生产配置的来源、优先级、密钥、缓存和测试隔离。
11. 回答高级面试中关于 Pydantic 与 dataclass、静态类型、领域模型、性能和演进策略的问题。

## 3. 核心定位与边界

### 3.1 Pydantic 负责什么

- 描述边界数据的结构、类型和局部不变量。
- 将受支持的外部表示解析为应用接受的规范形式。
- 产生具有字段位置和机器可读类型的验证错误。
- 控制边界对象的序列化结果。
- 生成可供文档、代码生成和契约审查使用的 JSON Schema。

### 3.2 Pydantic 不负责什么

- 库存是否足够、订单能否退款、状态能否迁移等领域决策。
- 数据库查询、外部 API 调用、Webhook 签名验证和消息确认。
- 事务、重试、幂等、超时、熔断或死信队列策略本身。
- 静态类型检查；Pydantic 在运行时验证数据，mypy／Pyright 在开发阶段分析代码。

### 3.3 边界原则

验证逻辑按生命周期放置：

```text
原始 bytes / dict
  -> 边界 schema 选择
  -> 解析与受控 coercion
  -> 字段／模型不变量
  -> 规范化
  -> 显式映射为应用命令
  -> 领域行为
  -> 显式投影为响应／事件
  -> 序列化与契约输出
```

- Pydantic 模型在协议边界最有价值；领域核心不被强制依赖 Pydantic。
- HTTP request、HTTP response、Webhook、MQ event 和 Settings 在语义或版本不同时使用不同模型。
- `OrderId`、`CurrencyCode` 等稳定值对象可以跨边界复用，但复用必须来自相同语义，而不是字段形状相同。
- validator 必须是确定、无 I/O、可快速执行的局部计算；需要外部状态的检查交给应用服务或领域服务。
- 不采用“全局严格”或“全局宽松”。字符串化数字等协议允许的输入可受控转换；金额、标识符、状态和容易歧义的字段默认从严。

## 4. 范围

### 4.1 纳入范围

- CPython 3.11+ 与 Pydantic v2 主线；不为 Pydantic v1 编写双轨示例。
- Pydantic v2 的 validation、serialization、JSON Schema 和模型生命周期。
- 边界驱动的模型拆分、映射、错误契约、可观测性和版本演进。
- `TypeAdapter`、`RootModel`、泛型、可辨识联合类型和自定义类型。
- pytest 契约测试、golden schema 测试与低噪声性能实验。
- 一章完整的 `pydantic-settings` 生产配置治理。
- 小型 FastAPI adapter、MQ 事件解析、`from_attributes` 和 LLM structured output 的集成说明。
- Pydantic v1 到 v2 的集中迁移地图。

### 4.2 不纳入范围

- FastAPI 路由体系、认证授权、部署和运维教程。
- SQLAlchemy session、查询、事务或仓储实现。
- Kafka／RocketMQ 客户端安装、broker 或消费组运行环境。
- Pydantic AI 的 agent、model provider、tool calling、运行时和 API key。
- Rust 源码逐行讲解或 `pydantic-core` 内部实现考古。
- mypy、Pyright 或 Pylance 的安装配置。

Pydantic AI 是一个完整的生成式 AI agent 框架，不与本教程的“数据契约”主线混写。末章只用一小节说明 Pydantic 模型如何作为 LLM structured output 的契约，不安装 `pydantic-ai`，不调用模型。

## 5. 交付结构

教程采用独立深度专题，避免把既有 Python 主线膨胀为单一巨型章节：

```text
python/
└── 25-runtime-data-contracts-bridge.md

python-pydantic/
├── README.md
├── 00-data-contracts-and-trust-boundaries.md
├── 01-pydantic-v2-validation-engine.md
├── 02-field-semantics-types-and-coercion.md
├── 03-validation-pipeline-and-normalization.md
├── 04-composition-polymorphism-and-batches.md
├── 05-model-behavior-and-lifecycle.md
├── 06-contract-layering-and-domain-boundaries.md
├── 07-serialization-and-data-leak-defense.md
├── 08-json-schema-and-contract-evolution.md
├── 09-error-contracts-and-observability.md
├── 10-contract-testing-with-pytest.md
├── 11-custom-types-core-schema-and-performance.md
├── 12-pydantic-settings-in-production.md
├── 13-integrations-and-v1-migration.md
├── 99-interview-cards.md
└── lab/
```

`python/25-runtime-data-contracts-bridge.md` 只承担概念桥接、学习入口和与静态类型／FastAPI 章节的导航，不复制深度专题内容。

## 6. 学习路线

教程按数据生命周期组织，而不是按 Pydantic API 字母表组织：

1. `00`—`04`：理解外部数据如何进入信任边界。
2. `05`—`06`：理解模型生命周期、分层和领域边界。
3. `07`—`08`：理解数据如何安全离开服务及如何演进。
4. `09`—`10`：建立错误治理和契约测试体系。
5. `11`：进入扩展机制与性能判断。
6. `12`：将同一套边界思维用于生产配置。
7. `13`：连接框架、消息系统、ORM 对象和 v1 遗留代码。
8. `99`：用面试卡与故障清单完成复习。

每章固定采用以下结构，保证阅读节奏一致：

1. 生产事故或高级面试题开场。
2. 一句话心智模型。
3. 最小可运行示例。
4. 机制与必要的底层原理。
5. 订单／支付案例演进。
6. 常见错误实现与失败模式。
7. 架构边界和决策规则。
8. pytest 验证。
9. Java／Go 对照。
10. API／决策速查。
11. 面试卡。

## 7. 章节设计

### 7.1 00：数据契约与信任边界

- 区分类型注解、静态检查、运行时验证、业务规则和协议契约。
- 用 HTTP JSON、Webhook、MQ event、环境变量和数据库对象展示不同信任等级。
- 引入 parse／validate／normalize／authorize／act 的职责边界。
- 解释为什么“能构造模型”不等于“业务操作被允许”。
- 建立后续统一使用的订单／支付服务上下文。

### 7.2 01：Pydantic v2 验证引擎心智模型

- 从 Python annotation 和模型定义到 CoreSchema 的构建过程。
- 解释 Python 层负责 schema 构建，Rust `pydantic-core` 负责高性能验证与序列化。
- 说明 CoreSchema、validator、serializer 的关系，以及 schema 复用／缓存的性能意义。
- 比较 `__init__`、`model_validate()`、`model_validate_json()` 和 `model_construct()` 的语义。
- 强调 `model_construct()` 是可信数据的逃生舱，不是跳过边界验证的优化捷径。

### 7.3 02：字段语义、类型与 coercion

- required、optional、nullable、default、default factory 是不同维度。
- 数值、布尔、日期时间、UUID、Decimal、Enum、Literal 和 constrained types 的边界行为。
- `Annotated`、`Field`、alias、validation alias 和 serialization alias。
- JSON mode 与 Python mode 的差异，以及 strict mode 并非单一全局开关。
- 为金额、数量、标识符、状态和客户端表单输入建立逐字段政策矩阵。
- 解释二进制浮点不适合作为货币契约的原因，并示范 Decimal 的输入与输出政策。

### 7.4 03：验证管线与规范化

- field validator 的 before／plain／wrap／after 模式及执行顺序。
- model validator 的前后置校验与跨字段不变量。
- default 是否被验证、失败后哪些 validator 会继续、错误如何聚合。
- `ValidationInfo`、context 和数据依赖的可见范围。
- 规范化与验证的边界：大小写、空白、时区、货币代码等可做纯函数转换；库存和支付状态不可。
- 避免 validator 中网络调用、数据库查询、日志泄密和隐藏副作用。

### 7.5 04：组合、多态与批量数据

- 嵌套模型、递归模型、泛型模型和 `RootModel`。
- 使用 discriminator 建模支付成功／失败事件，避免模糊 union 依赖试错顺序。
- 使用 `TypeAdapter` 验证模型外的 `list`、union、TypedDict 或批量事件。
- 讨论超大批次验证的内存与错误聚合成本，以及何时流式拆批。
- 明确“可接受多个版本”与“内部统一成一个领域命令”的分层方法。

### 7.6 05：模型行为与生命周期

- `ConfigDict` 中 `extra`、`frozen`、`validate_assignment`、revalidation 等关键策略。
- 输入边界对未知字段的 forbid／ignore／allow 选择及向前兼容取舍。
- `model_copy()`、浅拷贝与深拷贝、更新数据是否重新验证。
- private attribute、computed field 和缓存值的边界。
- `create_model()` 的适用范围和动态 schema 带来的可发现性／类型分析成本。
- 解释“不可变 DTO”不等同于“不可变领域实体”。

### 7.7 06：契约分层与领域边界

- 分离 `CreateOrderRequest`、`CreateOrderCommand`、领域 `Order`、`CustomerOrderView` 和 `OrderCreatedV1`。
- 使用显式映射，避免把 `model_dump()` 直接作为领域构造器／数据库更新参数。
- 防范 mass assignment、过度发布内部字段和协议字段渗透到领域层。
- 稳定值对象可共享；生命周期、权限、版本或可见性不同的对象必须分离。
- 比较 Pydantic model、dataclass、普通类和 TypedDict 在各层的角色。

### 7.8 07：序列化与数据泄漏防御

- `model_dump()`／`model_dump_json()` 的 mode、include、exclude、exclude_unset 等语义。
- field／model serializer、computed field 和 context-aware serialization。
- 子类序列化、duck typing 和意外输出敏感字段的风险。
- Secret 类型只保护展示，不代表密钥已加密或不会被主动取出。
- 用客户视图与内部运营视图证明“输出白名单模型”优于到处拼 exclude。
- 将日志、错误响应、事件和 API response 视为不同的出站契约。

### 7.9 08：JSON Schema 与契约演进

- 解释 validation schema 与 serialization schema 可能不同。
- 标题、描述、examples、ref 和 schema customization 的作用与滥用风险。
- golden schema 文件用于审查契约变化，不将 schema 快照误当完整兼容性证明。
- `OrderCreatedV1`／`V2` 演示字段新增、重命名、语义变化和版本 envelope。
- 区分 producer compatibility、consumer compatibility 和内部迁移策略。
- 给出 breaking change 审查清单及何时必须新版本。

### 7.10 09：错误契约与可观测性

- 展开 `ValidationError.errors()` 的 `type`、`loc`、`input`、`ctx` 等结构。
- 服务错误响应使用稳定机器码和字段路径，不把本地化 `msg` 作为测试契约。
- 清理敏感 input／context，避免日志和 trace 泄漏 token 或支付数据。
- HTTP、Webhook、MQ、Settings 和内部命令采用不同的失败处理：
  - HTTP：稳定 4xx 错误契约。
  - Webhook：签名校验与 payload validation 分离。
  - MQ：区分不兼容、永久无效和暂时失败；仅永久错误进入 DLQ。
  - Settings：进程启动时 fail fast。
  - 内部命令：无效数据视为编程缺陷，而不是重新包装成客户端错误。
- 设计低基数 metrics，避免把完整错误路径或输入作为 label。

### 7.11 10：使用 pytest 进行契约测试

- 表格化测试 coercion／strict 决策矩阵。
- 测试字段不变量、跨字段不变量、错误 type／loc 和敏感字段不可见。
- round-trip 测试需明确对称性成立的前提，不能机械断言所有输入都能原样返回。
- JSON Schema golden、事件 v1／v2 兼容性和未知字段政策测试。
- Settings 来源优先级与测试隔离。
- 示例代码由测试实际执行，防止文档代码腐化。
- 说明 property-based testing 的适用点，但本教程不额外引入 Hypothesis 依赖。

### 7.12 11：自定义类型、CoreSchema 与性能

- 优先顺序：标准类型与 `Annotated` metadata → field／model validators → 自定义类型 → 直接 CoreSchema hook。
- 使用订单标识符或货币代码示范可复用自定义类型。
- 说明 `GetPydanticSchema`、自定义 validator／serializer 和 JSON Schema 配套责任。
- 直接使用 CoreSchema hook 属于高级扩展点，版本敏感且需要更强测试保护。
- 比较 `model_validate_json()` 与先 `json.loads()` 的数据路径，解释 adapter／schema 重用价值。
- 性能实验使用 `timeit` 或重复测量，只报告当前环境观察，不设脆弱的绝对耗时门槛。
- 优化前先确定验证是否真是瓶颈，不为微基准牺牲契约清晰度。

### 7.13 12：生产级 pydantic-settings

- `BaseSettings` 是配置边界模型，不是业务 DTO 的基类。
- 覆盖初始化参数、环境变量、dotenv、file secrets 和 default 的来源与优先级。
- nested settings、delimiter、alias、大小写政策和复杂值解析。
- Secret 类型、日志／repr 防泄漏和“secret file 仍是明文来源”的现实边界。
- 自定义 settings source 的适用场景、复杂度和可测试性成本。
- 启动 fail fast，避免业务请求到来后才发现配置缺失。
- 讨论缓存 settings 的位置、依赖注入、import-time singleton 的测试污染。
- 说明多 worker 进程各自加载配置；环境更新不会自动同步到已运行模型。
- 测试必须显式控制环境和 dotenv 路径，不读取开发者真实 `.env`。

### 7.14 13：集成矩阵与 v1 迁移

- FastAPI：request／response model 的小型 adapter；不扩展为路由框架教程。
- MQ：对原始 bytes 使用 `model_validate_json()`／`TypeAdapter`，再分类验证失败；不依赖 Kafka／RocketMQ SDK。
- ORM：用 `from_attributes` 解释“读取对象属性”与“ORM session 管理”是两件事。
- LLM：只说明 structured output 可复用 Pydantic 契约，以及外部模型输出仍是不可信输入。
- 集中列出 v1 → v2 的主要迁移：方法更名、validator API、Config、ORM mode、RootModel、序列化和 strict 行为审计。
- 迁移不只做机械改名；必须回归输入 coercion、unknown fields、序列化和错误格式。

### 7.15 99：面试卡与故障速查

- 每张卡采用“30 秒回答 → 深挖 → 常见误区 → 生产例子”。
- 覆盖 Pydantic 与静态类型、dataclass、FastAPI、领域模型、JSON Schema、Settings 和性能。
- 故障速查从症状反推边界：意外 coercion、字段泄漏、事件不兼容、worker 配置不一致、validator 延迟、错误日志泄密。
- 给出设计评审清单，方便团队直接用于 code review。

## 8. 连续案例与模型目录

### 8.1 案例上下文

一个订单／支付服务接收下单 HTTP 请求，接收第三方支付 Webhook，消费订单事件，加载运行配置，并向客户和内部运营人员输出不同视图。案例只模拟协议边界和应用映射，不连接真实数据库、消息 broker 或支付平台。

### 8.2 主要模型

- 稳定值对象：`OrderId`、`CustomerId`、`CurrencyCode`、`Money`。
- 入站：`CreateOrderRequest`、`CreateOrderItem`。
- Webhook：`PaymentWebhookEnvelope`、`PaymentSucceeded`、`PaymentFailed`。
- 应用层：`CreateOrderCommand`。
- 领域层：普通 dataclass／Python class `Order`。
- 出站：`CustomerOrderView`、`InternalOrderView`。
- 事件：`EventEnvelope`、`OrderCreatedV1`、`OrderCreatedV2`。
- 配置：`AppSettings`、`PaymentProviderSettings`。

案例不得包含或模拟完整银行卡号、CVV、真实 token、API key 或用户隐私数据。支付相关字段只使用不敏感的 provider reference。

## 9. 可运行 Lab

### 9.1 目录

```text
python-pydantic/lab/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── schemas/
│   ├── create-order.schema.json
│   ├── order-created-v1.schema.json
│   └── order-created-v2.schema.json
├── src/order_contracts/
│   ├── __init__.py
│   ├── value_objects.py
│   ├── inbound/
│   │   ├── __init__.py
│   │   ├── create_order.py
│   │   └── payment_webhook.py
│   ├── application/
│   │   ├── __init__.py
│   │   └── commands.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── order.py
│   ├── outbound/
│   │   ├── __init__.py
│   │   └── views.py
│   ├── events/
│   │   ├── __init__.py
│   │   ├── envelope.py
│   │   ├── v1.py
│   │   └── v2.py
│   ├── config.py
│   ├── errors.py
│   └── adapters.py
├── examples/
│   ├── validate_http_payload.py
│   ├── consume_event.py
│   ├── load_settings.py
│   └── fastapi_adapter.py
└── tests/
    ├── test_value_objects.py
    ├── test_create_order.py
    ├── test_webhook.py
    ├── test_adapters.py
    ├── test_serialization.py
    ├── test_event_compatibility.py
    ├── test_json_schema.py
    ├── test_settings.py
    ├── test_errors.py
    ├── test_examples.py
    └── test_performance_observations.py
```

### 9.2 依赖

核心依赖：

```toml
pydantic = ">=2,<3"
pydantic-settings = ">=2,<3"
```

开发测试组只有 `pytest`；`fastapi` 放在独立的 integration dependency group，仅供末章 adapter 示例使用。`uv` 配置让标准开发同步默认安装这两个 group，因此 `uv sync` 后可以执行全部测试；只消费核心包的用户不必安装 FastAPI。Lab 不引入 SQLAlchemy、Kafka／RocketMQ SDK、Pydantic AI、Docker、数据库、网络服务或 API key。

提交 `uv.lock` 以保证示例可复现。标准运行入口为：

```bash
uv sync
uv run pytest
```

### 9.3 端到端数据流

```text
raw JSON bytes
  -> model_validate_json() / TypeAdapter
  -> inbound DTO
  -> 显式 mapper
  -> application command
  -> domain dataclass / Python class
  -> 显式 projection
  -> response model / event model
  -> model_dump_json()
```

每次跨层转换都必须可见、可测试。禁止用任意 `**model_dump()` 让新增协议字段自动进入应用命令、领域对象或持久化更新。

## 10. 测试策略

### 10.1 行为测试

- 字段级和模型级不变量。
- coercion／strict 决策矩阵。
- discriminator、批量事件和版本 envelope。
- 显式映射及未知字段政策。
- 序列化 round-trip 的适用场景。
- 客户视图不包含内部字段、Secret 或子类敏感字段。

### 10.2 契约测试

- JSON Schema 与仓库中的 golden 文件比较。
- `OrderCreatedV1`／`V2` producer 和 consumer 兼容性。
- 错误断言稳定的 `type` 和 `loc`，不锁死可能变化／本地化的完整 `msg`。
- 修改 golden schema 必须作为契约变化人工审查，不能无条件自动更新。

### 10.3 配置测试

- 明确验证 init、environment、dotenv、file secrets 和 default 的优先级。
- 每个测试使用隔离环境／临时文件，清理 settings 缓存。
- 不读取开发者机器上的真实 `.env`、home directory 或系统 secrets。

### 10.4 文档与性能测试

- 关键文档代码复用或调用 lab 中的可执行实现。
- `examples/` 全部由 pytest 执行。
- 性能用例只验证实验可以执行和结果量级合理，不设置依赖机器负载的硬阈值。

## 11. 错误和故障分类

| 边界 | Pydantic 的职责 | 后续处理 |
|---|---|---|
| HTTP request | 结构、局部不变量、规范化 | 转为稳定 4xx；业务冲突由应用层另行处理 |
| Payment Webhook | payload 契约 | 签名先由 I/O adapter 验证；错误响应不得回显敏感输入 |
| MQ event | envelope／版本／payload 契约 | 区分不兼容、永久无效、暂时失败；仅永久错误进入 DLQ |
| Settings | 启动配置契约 | 启动 fail fast，输出安全的字段路径，不输出 secret 值 |
| Internal command | 应用内部不变量 | 视为编程缺陷，告警并修复生产者，不伪装为客户端输入错误 |

教程会强调：Pydantic 能识别“数据不符合契约”，但不会自动知道错误是否可重试、是否应进入 DLQ 或应该映射成哪个 HTTP 状态码。这些是 adapter／应用层政策。

## 12. 仓库与 Git 卫生

### 12.1 应提交内容

- 教程 Markdown、桥接章节和导航更新。
- `pyproject.toml`、`uv.lock`、`.env.example`。
- `src/`、`tests/`、`examples/`。
- 经过审查的 JSON Schema golden 文件。

### 12.2 不应提交内容

- 虚拟环境、安装后的第三方依赖或 vendor 目录。
- Python bytecode、pytest／类型检查／lint 缓存。
- coverage、build、dist 和 egg-info 产物。
- `.env`、本地 secrets 和开发者专属配置。
- 临时 benchmark 输出、日志、数据库或 broker 数据。

实现阶段先检查根 `.gitignore`，只补充缺失规则，目标集合为：

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.pyright/
.ruff_cache/
.coverage
htmlcov/
.env
.env.*
!.env.example
build/
dist/
*.egg-info/
.DS_Store
```

虽然本教程不安装 mypy／Pyright／Ruff，仍忽略其常见本地产物，避免读者运行个人工具后误提交。不能忽略 `uv.lock`、`.env.example` 或 `schemas/*.json`。

## 13. 文档风格与一致性

- 正文使用简体中文，与仓库现有教程一致；保留必要英文术语和正式 API 名称。
- 第一次出现的重要术语同时给出英文，后续保持命名一致。
- 先给心智模型和场景，再展开 API；示例不能脱离订单／支付上下文堆砌。
- Java 对照侧重 Bean Validation、Jackson、record／DTO 和配置体系；Go 对照侧重 struct tags、显式解析、validator 生态和不可隐式表达的约束。
- 机制解释到 CoreSchema／validator／serializer 的层级，避免把不稳定内部细节写成长期契约。
- 所有性能结论说明 Python／Pydantic 版本、输入形状和测量条件，禁止无上下文的“快 N 倍”。

## 14. 质量门槛

在宣布实现完成前必须满足：

1. 在干净 worktree 中执行 `uv sync` 成功。
2. `uv run pytest` 全部通过。
3. 所有 example 可执行，且由测试覆盖。
4. 教程关键代码与 lab 实现一致，不存在明显不可运行片段。
5. JSON Schema 变化经过 diff 审查。
6. 测试不依赖真实 `.env`、网络、数据库、broker、API key、系统时区或调用者 cwd。
7. 示例和错误输出不包含 secrets 或真实支付数据。
8. `git diff --check` 无 whitespace 错误。
9. 检查内部链接、未跟踪文件和 `.gitignore`，确认没有依赖目录或生成垃圾进入提交。
10. 对高级扩展和性能章节进行事实核对，明确公共 API 与版本敏感实现细节。

## 15. 成功标准

本教程成功，不以章节数量或 API 覆盖率衡量，而以学习者能否完成以下任务衡量：

- 为新的服务边界写出明确的 coercion、strict、unknown-field 和 error policy。
- 画出输入 DTO 到领域对象再到响应／事件的模型边界，并解释每次映射为何存在。
- 诊断 validator I/O、mass assignment、序列化泄漏和事件不兼容等生产问题。
- 阅读 Pydantic v2 错误与 schema，解释 CoreSchema 验证管线而不神化底层实现。
- 为配置来源和优先级制定可测试、可审计的生产政策。
- 在面试或设计评审中说明何时应该使用 Pydantic，何时普通类／dataclass／TypedDict 更合适。

## 16. 风险与控制

### 16.1 范围过大

风险：教程滑向 FastAPI、MQ、ORM 或 AI 框架教程。

控制：集成集中在第 13 章，lab 只保留 adapter，不引入外部运行系统。

### 16.2 文档与代码漂移

风险：长教程中的代码无法运行或与 lab 行为不一致。

控制：核心示例引用同一模型，examples 由 pytest 执行，schema 由 golden tests 保护。

### 16.3 过度依赖内部实现

风险：直接教授 CoreSchema 细节导致小版本升级即过时。

控制：以公开高层 API 为默认路径，直接 hook 单独标记为高级／版本敏感，并配套测试。

### 16.4 把验证误当业务设计

风险：复杂领域规则进入 validator，形成隐藏 I/O、延迟和难以复用的模型。

控制：全教程重复使用边界职责表和显式 mapper，测试分别覆盖契约错误与业务错误。

### 16.5 配置示例污染真实环境

风险：测试误读本地 `.env` 或展示真实 secret。

控制：显式 settings source、临时目录、环境清理和 `.env.example`，禁止 ambient configuration。

## 17. 后续实施顺序

书面设计确认后，先编写逐文件实施计划，再按以下依赖顺序执行：

1. 建立教程导航、lab 包结构、依赖与测试骨架。
2. 实现稳定值对象、入站模型、应用／领域映射和基础测试。
3. 实现出站视图、事件版本、错误 adapter、Settings 和 schema golden。
4. 编写生命周期章节并让文档示例落到已测试代码。
5. 补充高级扩展、性能、集成、迁移和面试卡。
6. 执行完整质量门槛、自审教程连续性和仓库卫生。

本设计已于 2026-07-15 完成书面复核并获批准；后续实现必须按对应 implementation plan 的任务、测试和质量门槛执行。
