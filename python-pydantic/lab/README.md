# Order Contracts Lab

本 lab 是 Pydantic v2 教程的**可执行事实源**，目标环境为 CPython 3.11+、Pydantic v2、pydantic-settings v2 与 pytest。它不连接数据库、broker、支付服务或 LLM，也不需要任何真实密钥。

## 安装与完整验证

```bash
uv sync
uv run pytest
```

## 目录树

```text
.
├── src/order_contracts/
│   ├── inbound/       # HTTP/webhook 输入契约
│   ├── application/   # 与 transport 解耦的 commands
│   ├── domain/        # 普通领域对象与不变量
│   ├── events/        # OrderCreated V1/V2 envelope 与解析
│   ├── outbound/      # 白名单 view models
│   ├── adapters.py    # 边界 DTO ↔ command/domain/view 映射
│   ├── config.py      # settings 来源、缓存与显式加载
│   └── errors.py      # 稳定错误契约
├── examples/          # 四个可直接运行的边界示例
├── tests/             # 行为、回归、兼容性和集成测试
├── schemas/           # 提交到仓库的 JSON Schema golden files
└── scripts/export_schemas.py
```

## 四个示例命令

```bash
uv run python examples/validate_http_payload.py
uv run python examples/consume_event.py
uv run python examples/load_settings.py
uv run python -c "from examples.fastapi_adapter import app; print(app.title)"
```

它们分别验证 HTTP bytes 并映射 command、解析版本化事件、安全加载配置，以及证明 FastAPI adapter 能导入且拥有应用标题。

## 再生成 JSON Schema

```bash
uv run python scripts/export_schemas.py
```

生成后检查 `git diff -- schemas/`；golden diff 是兼容性审查入口，不等于自动证明兼容。

## 环境变量策略

- `.env.example` 只含公开演示值；真实 `.env` 永不提交。
- `AppSettings` 默认 `env_file=None`，不会因当前工作目录里碰巧存在 `.env` 而污染测试或生产。
- 只有调用 `load_settings(env_file=...)` 时才显式读取 dotenv；当前来源顺序为 init > environment > explicit dotenv > secrets > defaults。
- `get_settings()` 提供每进程缓存；测试修改环境前后调用 `clear_settings_cache()`。多 worker 各自加载配置，不共享进程内缓存。
- `SecretStr` 只降低误打印风险，不替代生产 secret manager；任何真实 secret 都不得进入仓库、测试输出或日志。

## 测试文件地图

| 契约事实 | 测试文件 |
|----------|----------|
| inbound 字段语义、strict、validator、webhook | [`tests/test_create_order.py`](tests/test_create_order.py)、[`tests/test_webhook.py`](tests/test_webhook.py) |
| DTO → command/domain/view 与泄漏防线 | [`tests/test_adapters.py`](tests/test_adapters.py)、[`tests/test_domain_order.py`](tests/test_domain_order.py)、[`tests/test_serialization.py`](tests/test_serialization.py) |
| 事件 V1/V2 与兼容性 | [`tests/test_event_compatibility.py`](tests/test_event_compatibility.py) |
| 稳定错误映射 | [`tests/test_errors.py`](tests/test_errors.py) |
| JSON Schema golden | [`tests/test_json_schema.py`](tests/test_json_schema.py) |
| 自定义类型与性能观察 | [`tests/test_advanced_types.py`](tests/test_advanced_types.py)、[`tests/test_value_objects.py`](tests/test_value_objects.py)、[`tests/test_performance_observations.py`](tests/test_performance_observations.py) |
| settings 来源、缓存与隔离 | [`tests/test_settings.py`](tests/test_settings.py) |
| 示例、FastAPI 薄适配和包烟测 | [`tests/test_examples.py`](tests/test_examples.py)、[`tests/test_integrations.py`](tests/test_integrations.py)、[`tests/test_package_smoke.py`](tests/test_package_smoke.py) |
