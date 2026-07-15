# 12 · 生产级 pydantic-settings：启动即验证，来源可解释，更新有政策

> **本章目标**：把 Settings 当成进程启动边界，而不是散落的 `os.environ` 读取；能明确默认与定制来源优先级，安全处理 nested 配置、dotenv、file secrets、缓存和多 worker 更新。可运行事实来自 [`config.py`](lab/src/order_contracts/config.py)、[Settings 测试](lab/tests/test_settings.py) 和 [安全示例](lab/examples/load_settings.py)；版本语义以当前 [pydantic-settings 官方文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 为核验基准。

先运行本章基线：

```bash
cd python-pydantic/lab
uv run pytest tests/test_settings.py \
  tests/test_examples.py::test_settings_example_never_returns_raw_secret -v
```

当前仓库在 lockfile 环境 `pydantic-settings 2.14.2` 下实际收集并通过 18 个测试。若旧任务说明仍写 6，应以测试收集结果为准，而不是删减覆盖去迎合旧数字。这组测试锁住 source precedence、CSV、strict timeout、prefix/case、dotenv、file secrets、nested extra、secret repr、startup fail-fast 与 cache lifecycle。

## 事故开场：第一个支付请求才发现 secret 缺失

服务部署后 worker 健康检查通过。十分钟后第一笔支付到来，代码才在 handler 中读取 `ORDER_PAYMENT__WEBHOOK_SECRET`；环境变量缺失，调用 provider 前抛异常。部分 worker 已处理普通流量，部分 worker 第一次遇到支付才失败，rollback 和告警都变得混乱。

Settings 校验不应由“第一个碰巧走到该功能的请求”触发。它属于 composition root：

```text
process / worker starts
        ↓
composition root loads AppSettings once
        ↓
all sources resolved + types validated + required secrets present?
  ├─ no  → startup fails; instance never becomes ready
  └─ yes → construct adapters/services → readiness on → serve traffic
```

[`get_settings()`](lab/src/order_contracts/config.py) 在缺少 required `payment` 时立即产生 `ValidationError`，[`test_startup_factory_fails_fast_without_required_settings`](lab/tests/test_settings.py) 锁定 error location `("payment",)`。框架的 startup hook、CLI `main()` 或 worker bootstrap 应调用它；不要在 route、repository 或 SDK wrapper 中延迟创建 Settings。

**fail fast 不等于打印整个异常后继续运行。** 启动层可以记录安全的 error type/location 并退出 non-zero；原始 input、dotenv 内容和 secret source 值仍不能进普通日志。

## `BaseSettings` 是配置边界，不是业务 DTO 基类

`BaseSettings` 的特殊责任是从多个外部来源组装 field values，然后执行 Pydantic validation。它适合 process-level configuration，例如环境、日志级别、provider endpoint、timeout 和 credential。

| 类型 | 数据来自哪里 | 生命周期 | 应否继承 `BaseSettings` |
|---|---|---|---|
| `AppSettings` | init、CLI/env/dotenv/secrets/defaults | 通常每进程一个 snapshot | 是 |
| HTTP request／response DTO | 每次请求 body/query/header | 每请求 | 否，用 `BaseModel` |
| MQ event | broker message | 每消息 | 否，用版本化 `BaseModel`／adapter |
| domain entity/value object | 已验证 application intent | 业务生命周期 | 否，保持 domain 独立 |

如果把所有 DTO 都继承 `BaseSettings`，普通 model construction 会意外读取 process environment，测试也会受开发机污染。反过来，完全手写 `os.environ` 解析通常会把这些错误散到各处：

```python
# 分散、无统一边界：缺失、空串、类型、范围和 secret 日志政策各自为政
timeout = int(os.environ.get("ORDER_TIMEOUT", "3"))
debug = os.environ.get("ORDER_DEBUG", "false").lower() == "true"
```

集中后的价值不是“少写几个 `getenv`”，而是有一份可审查的 schema、一个 source order、一套 error policy 和一个启动时刻。

## 两套优先级必须分开记

### 官方默认顺序

当前[官方 field priority 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority)的 descending priority 是：

```text
CLI arguments（仅启用 cli_parse_args 时）
> init kwargs
> environment variables
> dotenv variables
> file secrets
> field defaults
```

首项优先级最高。CLI 并非所有 `BaseSettings` 自动读取；只有启用 `cli_parse_args`／显式 CLI source 才进入该顺序。不能把“CLI 默认最高”误写成“任何 Web worker 都会解析 `sys.argv`”。

### 本 lab 的定制顺序

`AppSettings.settings_customise_sources()` 返回：

```python
return (
    init_settings,
    CommaSeparatedEnvSource(settings_cls),
    CommaSeparatedDotEnvSource(...),
    file_secret_settings,
)
```

因此 lab 的实际顺序是：

```text
init kwargs
> CommaSeparatedEnvSource（process environment）
> CommaSeparatedDotEnvSource（显式 dotenv）
> file secrets
> field defaults
```

lab 没有启用 `cli_parse_args`，所以这里没有 CLI source。defaults 也不需要出现在 returned tuple 中；source 都没有值时，model field default 才生效。

[`test_init_overrides_environment`](lab/tests/test_settings.py)、[`test_env_overrides_explicit_dotenv`](lab/tests/test_settings.py) 与 [`test_explicit_dotenv_overrides_file_secrets`](lab/tests/test_settings.py) 分别锁住相邻层级。source tuple 的第一项最高；调整返回顺序就是配置 API 变更，必须带 precedence matrix test。

### 同一 nested object 可能由多来源合成

“高优先级 source 获胜”不等于它必须独占整个 nested dict。当前 settings 会 deep-merge source 结果：高层同名 leaf 覆盖低层 leaf，低层仍可能补充缺失 sub-key。例如 dotenv 只给 `log_level`，file secrets 仍可提供完整 `payment`。

这使组合更实用，也增加审查责任：关键 credential 若来自哪个 source 必须一眼可知，最好由单一高优先级 source 完整提供，或为预期混合写精确测试。不要依赖“某个顶层 payment 出现后低层一定完全失效”的想象。

## `AppSettings`：把命名、嵌套和不可变性写进模型

lab 的核心配置是：

```python
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        env_nested_delimiter="__",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_currencies: tuple[CurrencyCode, ...] = ("USD",)
    payment: PaymentProviderSettings
```

对应的主要 environment names：

| field path | environment name | 输入语义 |
|---|---|---|
| `environment` | `ORDER_ENVIRONMENT` | literal |
| `log_level` | `ORDER_LOG_LEVEL` | literal |
| `allowed_currencies` | `ORDER_ALLOWED_CURRENCIES` | lab 定制 CSV，例如 `usd, eur` |
| `payment.base_url` | `ORDER_PAYMENT__BASE_URL` | nested URL |
| `payment.webhook_secret` | `ORDER_PAYMENT__WEBHOOK_SECRET` | nested secret string |
| `payment.timeout_seconds` | `ORDER_PAYMENT__TIMEOUT_SECONDS` | ASCII integer string → strict positive int，最大 30 |

`frozen=True` 把 validated snapshot 设为 faux-immutable，减少请求中途被任意 mutation；它不让 secret 加密，也不自动刷新来源。

### prefix 是 namespace，不是安全边界

`env_prefix="ORDER_"` 避免与同进程其他库的 `LOG_LEVEL`、`TIMEOUT` 冲突。它同样用于 dotenv、file secrets 等 settings sources 的 field lookup。未加前缀的 `PAYMENT__BASE_URL` 不能满足 `AppSettings.payment`，测试已经锁住这一点。

prefix 只解决命名；能读取 process environment 的代码仍可读取这些值。secret 的权限由 orchestrator、filesystem/process boundary 和日志政策负责。

### alias 与 `validation_alias` 改变 source lookup

对单字段可以使用：

- `Field(validation_alias="LEGACY_API_KEY")`：输入 source 使用别名，正常 output field name 仍可保持 Python 名；
- `Field(alias="API_KEY")`：同时定义 validation 与 serialization alias；输出时是否使用它仍由 `by_alias` 等 writer 选项决定；
- `AliasChoices(...)`：迁移期接受有限旧／新名称，按声明顺序选择找到的第一个。

在默认 prefix-target 语义下，alias 通常是完整 source name，不能想当然再拼 `env_prefix`。最新版还提供 prefix-target 配置，但这属于版本化政策；使用前应按锁定 `pydantic-settings` 版本写 lookup test。lab 没有字段 alias，因此表中的 `ORDER_...` 全由 prefix + field path 推导。

### case sensitivity 要与平台和测试一起设计

环境变量匹配默认 case-insensitive；lab 也显式 `case_sensitive=False`，所以 lowercase `order_payment__base_url` 能被读取。nested model 同样继承该匹配政策。

这不代表所有 source／OS 对大小写都同质：Windows 的 process environment 本身不保留可区分的 case，dotenv 文件仍可有大小写差异。生产命名仍应统一 uppercase；case-insensitive 是兼容政策，不是允许部署随意混用的理由。

## nested model、JSON 与 CSV 是三种不同解析

`PaymentProviderSettings` 是普通 `BaseModel`：

```python
class PaymentProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: AnyHttpUrl
    webhook_secret: SecretStr
    timeout_seconds: Annotated[
        StrictInt,
        BeforeValidator(_parse_timeout_seconds),
        Field(gt=0, le=30),
    ] = 3
```

复杂 environment value 默认按 JSON 解析。因此顶层 `ORDER_PAYMENT` 可以是：

```text
{"base_url":"https://pay.example","webhook_secret":"secret","timeout_seconds":4}
```

配置了 `env_nested_delimiter="__"` 后，也可分别提供 `ORDER_PAYMENT__BASE_URL` 等 leaf。若同时存在顶层 JSON 和 exploded nested value，nested leaf 覆盖 JSON 中同 leaf；这应被视为明确 source-within-source precedence。

JSON 适合结构化 dict/list/submodel；`usd, eur` 不是 JSON array。lab 有意把 `allowed_currencies` 定义成运维友好的 CSV，并在 custom source 中转成 list，之后 `CurrencyCode` 再 normalize 为 `("USD", "EUR")`。不要用一个含糊的 before validator 同时猜 JSON、CSV、空字符串和多种 delimiter；外部格式应固定。

`PaymentProviderSettings.extra="forbid"` 会拒绝 init／nested JSON 中未知 payment key，防止 credential 名拼错后静默忽略。`AppSettings.extra="ignore"` 则让共享 dotenv 中无关项与 prefixed unknown 项不阻塞 lab；root 与 nested 的 extra policy 是两个独立选择。

## custom source：必须完整委托非定制字段

lab 的关键实现不是只有 `split(",")`，而是一个完整 `prepare_field_value()`：

```python
class _CommaSeparatedCurrencySource:
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "allowed_currencies" and isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return super().prepare_field_value(
            field_name,
            field,
            value,
            value_is_complex,
        )
```

四个参数分别告诉 source 当前 field、annotation metadata、raw value，以及 framework 是否认为它复杂。只对已声明 CSV field 拦截；所有其他 field 交给 `EnvSettingsSource`／`DotEnvSettingsSource` 的 `super()`，保留默认 JSON、nested 和普通 string 处理。

如果 default branch 直接 `return value`，复杂 JSON 可能不再解码；如果对所有 string 都 split，URL、secret 与 JSON 会被误改。完整委托是 custom source 的正确性边界。

lab 同时定义 `CommaSeparatedEnvSource` 与 `CommaSeparatedDotEnvSource`。只替换 environment source 会导致同一个字段在 environment 接受 CSV、在 dotenv 却要求 JSON，形成难以解释的 source-dependent grammar。dotenv subclass 还保留 framework 提供的 `env_file` 与 encoding；显式文件路径不能在 customize 时丢失。

每次修改 `settings_customise_sources` 至少要测试：source order、定制 field、普通 simple field、普通 complex field、dotenv 对等行为、missing/invalid error。不要只测 CSV happy path。

## nested default partial update：不要拿隐式 merge 承载关键 secret

当前 `pydantic-settings` 提供 [`nested_model_default_partial_update`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#nested-model-default-partial-updates)：

- `False`：nested override 会构建新的 nested model；未提供 field 使用 nested model class 自身 default；
- `True`：以 outer Settings 上已有的 nested default object 为基础，局部更新它。

例如 outer default 是 `Provider(timeout=5, endpoint="...")`，环境只给 `PROVIDER__TIMEOUT=8`。开启 partial update 会保留 outer object 上的 endpoint；关闭时，新对象的 endpoint 来自 `Provider` class default，而不保证保留 outer object 的定制值。

lab 当前锁定版本运行时解析为 `False`，而且 `payment` 本身是 required、没有 outer default，所以不依赖这项隐式行为。若生产模型要使用它：

1. 在 `SettingsConfigDict` 中显式写 True/False，不依赖 package default；
2. pin `pydantic-settings` 并在升级时重跑 nested source matrix；
3. 对 endpoint、timeout 和 credential 分别测试缺失、单 leaf override、完整 object override；
4. 关键 secret 最好 required 或完整来自一个受控 source，不靠 partial merge 从默认对象“补回来”。

该配置与 deep merge 的细节随 settings 版本演进，属于版本敏感契约，不应只凭团队成员记忆。

## dotenv：相对路径跟 cwd，不跟 Python 文件

官方行为是：相对 `env_file` 从 current working directory 解释；指定文件名时只检查 cwd，不向 parent directories 搜索。这在 IDE、pytest、systemd、Docker `WORKDIR` 和命令行从不同目录启动时会产生差异。

lab 选择两层防护：

```python
model_config = SettingsConfigDict(env_file=None, ...)


def load_settings(
    *,
    env_file: Path | None = None,
    secrets_dir: Path | None = None,
) -> AppSettings:
    return AppSettings(_env_file=env_file, _secrets_dir=secrets_dir)
```

- default `env_file=None` 禁止 ambient `.env` 自动发现／读取；
- 只有调用 `load_settings(env_file=explicit_path)` 才加载该文件；
- `_env_file=None` 是有意义的 disable 值，不等于“回退到随便找 `.env`”。

[`test_default_loader_does_not_read_ambient_dotenv`](lab/tests/test_settings.py) 在 `tmp_path` 创建 `.env`、`chdir` 进去，仍断言 default `INFO`。这个 negative test 比只测显式文件更重要：它证明运行目录里偶然出现 `.env` 不会改生产配置。

相对路径仍受 cwd 影响。composition root 应从 deployment config／application root 构造已知路径，必要时 `resolve()`，而不是让 deep module 猜 `../../.env`。`.env.example` 是 reviewed 示例，不应包含真实 secret。

## file secrets 与 `SecretStr`：减少误泄漏，不提供加密

`_secrets_dir` 让每个文件名对应一个 setting key，文件内容就是 value。lab 测试用 `ORDER_LOG_LEVEL` 文件和包含 JSON 的 `ORDER_PAYMENT` 文件建立 nested settings。

必须明确两个限制：

1. **file secrets 是读取明文。** Pydantic 不加密文件，不设置 filesystem ACL，也不负责 secret manager 的 at-rest protection；目录挂载、owner/mode、备份与节点权限属于平台责任。
2. **`SecretStr` 只是表现层掩码。** `repr()`／`str()` 默认显示掩码，但 `get_secret_value()` 会返回明文，业务调用 provider 必然需要它；任何显式日志、exception context、dump customization 或调试器仍可泄漏。

[`test_file_secret_source_can_be_explicit`](lab/tests/test_settings.py) 与 [`test_settings_repr_redacts_payment_secret`](lab/tests/test_settings.py) 断言 raw secret 不在 repr。[安全示例](lab/examples/load_settings.py) 返回 `str(settings.payment.webhook_secret)`，对应测试确保公开结果没有原文。它们证明的是默认表现层防护，不是“secret 已加密”或“内存中不存在明文”。

### Settings source debug 是高危开关

当前官方 debug 能按优先级记录每个 source 收集的 dictionary。这正适合定位“为什么 env 没覆盖 dotenv”，也可能直接记录 environment、dotenv 或 secrets directory 中的 secret value。

> **警告**：`PYDANTIC_SETTINGS_DEBUG` 只应在可信、受控环境短时开启；不要在生产常驻，不要把输出上传到不受控 ticket/chat/APM。关闭后还要按日志保留策略处理已经产生的明文。

更安全的日常诊断是记录 source class、配置版本、非敏感 field 是否存在和 validation error type/loc；不要记录完整 source dict 或 Settings dump。

## 缓存属于 composition root，也必须能 reset

lab 明确暴露：

```python
@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
```

好处是：一个进程内 schema/source 解析一次，所有 service 获得同一 immutable snapshot；测试和受控 reload 又能清理。禁止这种 import-time singleton：

```python
# 不要：导入模块就读取真实 environment，失败时甚至还没进入 composition root
settings = AppSettings()
```

import-time construction 会让 import order 决定配置读取时刻，测试 monkeypatch 来不及，CLI/help/migration script 单纯 import 也可能失败。正确方式是在 startup 明确调用 `get_settings()`，再以参数注入 service；业务模块不应到处调用 global getter。

[`test_cache_is_explicit_and_clearable`](lab/tests/test_settings.py) 证明两次读取是同一对象，clear 后构建新对象。注意 clear 只删除 cache reference，不撤回已经注入到其他 service 的旧对象；reload policy 必须处理整个 object graph。

## 多 worker：每个进程都有自己的 snapshot

Gunicorn/Uvicorn worker、Celery worker 或多进程 job runner 不共享 Python `lru_cache`：

```text
master / orchestrator
  ├─ worker A → AppSettings snapshot A + cache A
  ├─ worker B → AppSettings snapshot B + cache B
  └─ worker C → AppSettings snapshot C + cache C
```

每个进程在自己的加载时刻读取 environment／files。之后修改 environment、dotenv 或 secret file，不会神奇地修改已有 frozen Settings object；调用 `clear_settings_cache()` 也只影响当前进程。

生产必须选一种更新政策并写进 runbook：

- **restart/rollout（推荐默认）**：新 worker 先 validate 新 snapshot、ready 后替换旧 worker；失败不接流量。简单、原子边界清楚。
- **受控 reload**：每个 worker 收到同一版本信号，在锁外构建并 validate fresh Settings／依赖 graph，成功后原子替换 reference，失败继续使用旧 snapshot并告警。需要版本、并发和 rollback 设计。
- **request-time reread**：通常拒绝；每请求 I/O、worker 间不一致、失败时机后移，也破坏 startup fail fast。

官方文档展示过对现有 object 再调用 `__init__()` 的 in-place reload，但并发 reader 可能看到 mutation 中间态。lab 的 Settings 是 frozen snapshot，也没有实现 reload；本教程不把 in-place mutation 当默认方案。若确需动态更新，更稳妥的是构建完整新对象再 swap，或直接滚动重启。

## 容器／Kubernetes secret rotation：文件更新不等于对象更新

不增加任何 Kubernetes integration，也可以定义正确概念：

- Secret 作为 environment variable 注入后，running container 不会因 Secret object 更新而获得新环境值；[Kubernetes 官方说明](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/)要求 restart 才能看到新值。
- Secret 作为 volume 文件时，Kubernetes 通常以 eventually-consistent 方式更新挂载内容；[`subPath` mount 不接收更新](https://kubernetes.io/docs/concepts/storage/volumes/#secret)。
- 即使文件已变化，已构造的 `AppSettings` 仍是旧 Python snapshot；应用必须 reload/restart 才会 reread。
- rotation 要同时处理 provider 两把 key 的 overlap window、readiness、失败回滚和多 worker 一致版本，不能只验证“文件 mtime 变了”。

因此最简单可靠的政策通常是：secret manager／Kubernetes 更新 → deployment rollout → 新 worker startup validation → readiness → drain 旧 worker。若业务必须无重启 rotation，先设计双 credential／版本号、watch signal、fresh object graph 与 atomic swap，再实现；Pydantic 不替应用完成这些协调。

file secret 也不能因为由 Kubernetes 提供就当作加密后的 Python value。挂载后应用读取的仍是明文，日志和内存防护政策不变。

## 测试隔离：逐项切断 ambient state

[`isolate_order_environment`](lab/tests/test_settings.py) 是 autouse fixture：

```python
@pytest.fixture(autouse=True)
def isolate_order_environment(monkeypatch):
    order_keys = set(ENV_KEYS)
    order_keys.update(
        key for key in os.environ if key.upper().startswith("ORDER_")
    )
    for key in order_keys:
        monkeypatch.delenv(key, raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()
```

每一步都有原因：

| 技术 | 隔离什么 | 为什么还需要其他步骤 |
|---|---|---|
| `monkeypatch.setenv/delenv` | 单测试 process environment，结束后自动恢复 | cached Settings 可能在修改前已经读取 |
| 动态删除所有 `key.upper().startswith("ORDER_")` | 开发机／CI 注入的 unknown key，以及 lowercase/mixed-case variant | 只删固定 uppercase 列表不足以隔离 case-insensitive lookup |
| `tmp_path` | dotenv／secrets directory，不接触仓库或用户文件 | 路径仍要显式传给 `load_settings` |
| `monkeypatch.chdir(tmp_path)` | 重现 cwd lookup 陷阱 | `env_file=None` negative assertion 才证明 ambient 文件不被读 |
| test 前后 `clear_settings_cache()` | 前例 snapshot 和本例新 snapshot | 只在 setup clear，失败／yield 后仍可能污染下一例 |

不要依赖测试机“应该没有 ORDER_ 变量”；CI secret injection 正是最容易制造假通过的 ambient state。也不要用真实项目 `.env` 做 test fixture，它可能含开发者 secret、随工作目录变化，且不能并行隔离。

安全示例额外使用 `patch.dict(os.environ, {}, clear=True)`，确保显式 `.env.example` 是唯一来源。普通 tests 则精准删 namespace，避免无意影响 pytest／系统所需的其他 env。

需要测试的矩阵至少包括：

- required missing 在 startup factory 失败；
- init > env > dotenv > file secrets > defaults；
- prefixed 接受、unprefixed 拒绝、case variants 按政策工作；
- nested JSON 与 exploded leaf precedence；
- CSV 在 env 和 dotenv 一致解析；
- invalid strict/range 值保持准确 type/loc；
- secret 不出现在 repr／公开 example；
- cache reuse、clear 后新 snapshot；
- ambient cwd `.env` 不被 default loader 读取。

## 一份生产 composition root

下面只展示 ownership，不绑定 Web framework：

```python
def build_application() -> Application:
    settings = get_settings()  # startup: sources + validation + fail fast
    payment_client = PaymentClient(
        base_url=str(settings.payment.base_url),
        webhook_secret=settings.payment.webhook_secret.get_secret_value(),
        timeout_seconds=settings.payment.timeout_seconds,
    )
    return Application(payment_client=payment_client)
```

secret 明文只在构造需要它的 adapter 时提取，不把整个 Settings 传遍 domain，不提供 `settings` debug endpoint。readiness 应在 `build_application()` 全部成功后开启；provider connectivity 是否也做 startup check，要按外部依赖可用性与启动耦合政策另行决定，不能与字段 validation 混为一谈。

## Java 与 Go：配置也是进程边界

### Java：Spring ConfigData 与 `@ConfigurationProperties`

Spring Boot 通常用 ConfigData 聚合 properties/YAML/environment/command line 等来源，再以 `@ConfigurationProperties` 绑定成 typed object，并结合 validation 在 application context startup 失败。它对应 `BaseSettings` + composition root，而不是让每个 bean 调 `System.getenv()`。

两点不能机械类比：Spring 的 property source precedence 与 profile/import 规则由 Spring 版本和 bootstrap 配置决定，不能照搬 Pydantic 顺序；Actuator／debug property reports 也可能暴露敏感来源，必须 sanitise 和限权。immutable configuration bean、constructor injection 与明确 refresh/restart policy，和本章原则相同。

### Go：Viper／envconfig 只负责加载，不自动定义团队政策

Go 常用 Viper、envconfig 或小型显式 loader 把 flags/env/files 解码到 struct，再调用 validation。不同库的 key normalization、prefix、file search 和 precedence 不同；应该在 composition root 固定顺序并写 table-driven tests，而不是到 handler 里 `os.Getenv()`。

Go process 读取后的 struct 同样是 snapshot。修改 Kubernetes env 不会改变 running process；文件变化也只有 watcher/reload code 主动重读才生效。推荐构建新 immutable-ish config/service graph 后 atomic swap，或 rollout；不要让 goroutine 并发 mutation 同一 config struct。secret redaction 需要专门 wrapper／logger policy，普通 `string` 没有 `SecretStr` 的默认 repr 掩码。

三种生态的共同模型是：

```text
explicit sources + reviewed precedence
→ typed binding and validation at startup
→ immutable process snapshot
→ dependency injection
→ explicit restart/reload protocol
```

## 面试追问

### 1. “Pydantic Settings 的默认优先级是什么？”

启用 CLI parsing 时：CLI > init kwargs > environment > dotenv > file secrets > defaults；未启用 CLI 时从 init 开始。还要继续问项目是否 override `settings_customise_sources`，因为 lab 的 custom env/dotenv sources 才是实际契约。

### 2. “为什么 `BaseSettings` 不该成为 request DTO 的基类？”

它会从 process-wide sources 补 field，生命周期和责任都与每请求 payload 不同。request DTO 用 `BaseModel`，Settings 只在 composition root 绑定部署配置，再向 service 注入窄依赖。

### 3. “dotenv 为什么在本地能读，容器里却读不到？”

相对 `env_file` 基于 cwd，且只查当前目录、不向 parent 搜索；IDE、shell 和 Docker `WORKDIR` 可能不同。使用显式路径，并用 `env_file=None` 禁止 default loader 读取 ambient `.env`。

### 4. “`SecretStr` 是否保证 secret 安全？”

不保证。它只默认掩码 repr/str；明文仍在 source、process memory 和 `get_secret_value()` 中。file secrets 也只是明文文件读取，权限、加密、rotation 和日志仍由应用／平台负责。

### 5. “为什么 custom source 要调用 `super().prepare_field_value()`？”

只定制 CSV field，其他 field 必须保留 framework 的 JSON、nested 和普通值处理。否则 custom source 会悄悄改变所有配置 grammar。env 与 dotenv 也要使用对等 custom source。

### 6. “更新 Secret 后，为什么 worker 仍用旧值？”

environment、file 和 Settings object 是三层 snapshot。Kubernetes env 不会原地更新；volume file 即使更新，已有 object 也不会重读；多 worker cache 又彼此独立。需要 rollout，或有版本与 atomic swap 的全进程 reload protocol。

### 7. “何时清 `get_settings()` cache？”

测试 setup/teardown，或应用已经设计并协调好的 reload。clear 只影响当前进程和未来 getter；已注入 service 的旧 object 不会被撤回，所以它本身不是完整 reload。

### 8. “nested partial update 为什么危险？”

它决定局部 nested override 是保留 outer default object 的其他值，还是以 nested class defaults 构建新对象；依赖隐式 default 会使 endpoint/secret 来源难以解释。显式配置、pin 版本、写 matrix test，关键 secret 保持 required。

## 本章检查清单

- [ ] composition root 在 readiness 前加载并验证 Settings
- [ ] `BaseSettings` 只用于配置边界，业务 DTO/domain 不继承
- [ ] 官方默认与项目 `settings_customise_sources` 顺序分别记录并测试
- [ ] CLI 只有启用 `cli_parse_args` 时才进入 precedence
- [ ] prefix、nested delimiter、alias、case 和 JSON/CSV grammar 明确
- [ ] custom `prepare_field_value()` 对非定制 field 完整委托 `super()`
- [ ] nested partial update 显式配置；关键 secret 不靠隐式 merge
- [ ] default `env_file=None`，生产／测试 dotenv 路径显式
- [ ] file secret 与 `SecretStr` 的明文／掩码边界已写入威胁模型
- [ ] source debug 只在可信环境短期开启，输出按 secret 处理
- [ ] cache 位于 composition root，可 reset；没有 import-time singleton
- [ ] 多 worker snapshot 和 restart/reload/rollback 政策已定义
- [ ] ambient env 的 unknown key 与大小写 variant 都在测试中隔离

## 小结

生产级 Settings 不是“把环境变量放进 class”，而是一项进程边界治理：来源有完整且可测试的优先级，复杂值有单一 grammar，required secret 在启动阶段验证，snapshot 在 composition root 缓存并注入。

lab 的价值恰在于把默认与定制分开：官方默认可含 CLI，lab 实际是 init > custom env > custom dotenv > file secrets > defaults；CSV source 保留其他字段的标准解析，dotenv 默认关闭，cache 可清理。多 worker 和 Kubernetes 不会自动更新已有对象，因此 rotation 最终必须落到明确的 rollout 或原子 reload protocol，而不是期待 `BaseSettings` 自己变成动态配置中心。
