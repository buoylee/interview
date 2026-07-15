# Pydantic v2 · 运行时数据契约

这是一套面向资深 Python 后端工程师的 **服务边界的数据契约与运行时验证引擎** 教程。它讨论不可信数据如何进入系统、可信对象如何离开系统，以及契约怎样被测试和演进；它不是 FastAPI 的附录。

## 环境与验证

示例以 **CPython 3.11+ / Pydantic v2** 为准。可执行事实统一放在 [`lab/`](lab/)；先跑完整基线：

```bash
cd lab
uv sync
uv run pytest
```

## 三种阅读方式

- **线性通读**：按 00 → 13 阅读，从信任边界走到设置与集成。
- **按事故或边界跳读**：输入被意外转换看 02–03，DTO 污染领域看 05–06，字段泄漏或事件兼容看 07–08，错误、测试和性能看 09–11，配置事故看 12。
- **面试突击**：直接读 [99 · 架构师面试卡](99-interview-cards.md)，再回到卡壳章节。

## 四阶段路线

1. **00–04 · inbound trust**：识别信任边界，理解 v2 引擎、字段语义、验证流水线与组合输入。
2. **05–06 · architecture**：控制模型生命周期，并把 DTO、命令、领域对象和视图分层。
3. **07–08 · outbound / evolution**：守住序列化边界，用 JSON Schema 和版本策略演进契约。
4. **09–13 · operations**：稳定错误、测试、内部机制与性能、配置、集成和 v1 迁移。

## 章节目录

| # | 章节 | 读完能产出什么 |
|---|------|----------------|
| 00 | [数据契约与信任边界](00-data-contracts-and-trust-boundaries.md) | 画出 HTTP、消息、配置和存储入口的信任边界，并为每个边界选择策略。 |
| 01 | [Pydantic v2 验证引擎](01-pydantic-v2-validation-engine.md) | 解释 Python 注解、CoreSchema 与 `pydantic-core` 如何组成验证/序列化流水线。 |
| 02 | [字段语义、类型与转换](02-field-semantics-types-and-coercion.md) | 准确设计 required/optional/nullable、strict/coercion 与额外字段策略。 |
| 03 | [验证流水线与归一化](03-validation-pipeline-and-normalization.md) | 安排 before/after/wrap、field/model validator 的顺序并保持验证器纯净。 |
| 04 | [组合、多态与批量输入](04-composition-polymorphism-and-batches.md) | 用嵌套模型、discriminated union、泛型和 `TypeAdapter` 表达复杂输入。 |
| 05 | [模型行为与生命周期](05-model-behavior-and-lifecycle.md) | 控制复制、赋值验证、冻结、泛型和 `model_construct()` 的使用边界。 |
| 06 | [契约分层与领域边界](06-contract-layering-and-domain-boundaries.md) | 将 transport DTO、application command、domain object、view model 拆成可演进层。 |
| 07 | [序列化与数据泄漏防线](07-serialization-and-data-leak-defense.md) | 设计显式输出模型、上下文序列化和子类字段泄漏防线。 |
| 08 | [JSON Schema 与契约演进](08-json-schema-and-contract-evolution.md) | 导出 schema、判断兼容性，并规划 API/事件 V1→V2 演进。 |
| 09 | [错误契约与可观测性](09-error-contracts-and-observability.md) | 把 `ValidationError` 映射为稳定错误码，同时保留可观测性且不泄密。 |
| 10 | [用 pytest 测试契约](10-contract-testing-with-pytest.md) | 建立表驱动、边界、schema golden 与跨版本兼容测试。 |
| 11 | [自定义类型、CoreSchema 与性能](11-custom-types-core-schema-and-performance.md) | 在测量后选择约束类型、自定义 schema hook、适配器复用或 JSON 快路径。 |
| 12 | [生产级 pydantic-settings](12-pydantic-settings-in-production.md) | 定义来源优先级、缓存/刷新、测试隔离、密钥与多 worker 配置策略。 |
| 13 | [集成边界与 v1 迁移](13-integrations-and-v1-migration.md) | 用薄适配器接 HTTP/MQ/LLM，并按清单从 v1 迁到 v2。 |
| 99 | [架构师面试卡](99-interview-cards.md) | 用 20 组短答、深挖、误区和生产案例复盘整套决策。 |

## Lab：可执行事实源

文档讲决策，`lab/` 固化可复现事实：

```text
lab/
├── src/order_contracts/  # inbound、domain、events、outbound、settings 与适配器
├── examples/             # 四个边界入口示例
├── tests/                # 行为、兼容性、schema、设置和集成测试
├── schemas/              # 可审查的 JSON Schema golden files
└── scripts/              # schema 再生成工具
```

从 `lab/` 运行四个示例：

```bash
uv run python examples/validate_http_payload.py
uv run python examples/consume_event.py
uv run python examples/load_settings.py
uv run python -c "from examples.fastapi_adapter import app; print(app.title)"
```

完整命令、环境变量策略与测试文件映射见 [`lab/README.md`](lab/README.md)。

## 明确不覆盖

- FastAPI 部署、指标、追踪、日志与压测等运维细节；
- SQLAlchemy、Session、事务和数据访问实现；
- Kafka/RabbitMQ 等 broker 客户端选型与运行参数；
- Pydantic AI 的 agent/model runtime；
- mypy、pyright 等静态类型检查工具的配置与治理。

## 官方资料

- [Pydantic latest concepts: models](https://pydantic.dev/docs/validation/latest/concepts/models/)
- [Pydantic latest internals: architecture](https://pydantic.dev/docs/validation/latest/internals/architecture/)
- [Pydantic latest migration guide](https://pydantic.dev/docs/validation/latest/get-started/migration/)
- [pydantic-settings latest documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
