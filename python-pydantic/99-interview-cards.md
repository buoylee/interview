# 99 · Pydantic v2 架构师面试卡

每张卡先给可在半分钟内说清的结论，再准备追问、常见误区和真实落点。重点不是背 API，而是说明边界、取舍和失败模式。

## 01 · Pydantic、类型注解与 mypy 是什么关系？

**30 秒回答**：类型注解是共同的描述语言；mypy/pyright 在运行前检查源码可见的类型关系，Pydantic 在运行时把外部数据验证、转换为符合注解与约束的值。注解本身不执行任何校验。

**深挖**：静态检查器看不到线上收到的 JSON；Pydantic 也不会替你证明所有内部调用的静态类型正确。边界先运行时验证，边界内再依靠类型检查和领域不变量。

**误区**：给函数参数写 `x: int` 就以为解释器会拒绝字符串，或者上了 Pydantic 就取消 CI 的静态检查。

**生产例子**：HTTP body 先由 `CreateOrderRequest.model_validate()` 收口，随后 service 接收已标注的 command，CI 用 mypy 检查内部调用。

## 02 · Pydantic v2 的 CoreSchema / pydantic-core 流水线怎样工作？

**30 秒回答**：模型定义阶段由 Python 侧读取注解、配置和 validators，生成 CoreSchema；运行时由 Rust 实现的 `pydantic-core` 按 schema 执行验证与序列化，JSON Schema 也从这份核心描述生成。

**深挖**：CoreSchema 是 Python 与 core 引擎的协议。模型类、dataclass、`TypeAdapter` 和自定义类型最终都进入相同引擎；高层 hook 应组合 handler 结果，而不是复制内部 schema。

**误区**：把 `pydantic-core` 当作业务代码应直接依赖的模型 API，或认为每次验证都会重新分析整个类定义。

**生产例子**：服务启动时构造并缓存 `TypeAdapter(list[OrderEvent])`，消费时只让已编译验证器处理批量 payload。

## 03 · 为什么 strict 不是全局一刀切？

**30 秒回答**：严格度是边界策略。安全敏感标识、金额和内部事件通常拒绝隐式转换；兼容历史表单或环境变量时可允许明确、可测试的转换。全局 strict 会牺牲可用性，全局 coercion 会掩盖脏数据。

**深挖**：可在类型、字段、模型或单次调用层指定 strict；应记录输入来源、允许的转换表和失败处理，而不是只开一个总开关。

**误区**：认为 strict 越多越“生产级”，或者相信 lax 模式能安全猜出任意业务语义。

**生产例子**：订单数量使用 `StrictInt` 拒绝 `"2"`，而 `APP_PORT="8080"` 由 settings 显式转换为整数。

## 04 · required、optional、nullable 怎样区分？

**30 秒回答**：required 表示字段是否必须出现；nullable 表示值能否为 `None`；有默认值才是可省略。`str | None` 只表达可空，若没有默认值，它仍是 required。

**深挖**：`field: str | None`、`field: str | None = None`、`field: str = "x"` 分别是“必传可空”“可省略可空”“可省略非空”。PATCH 还要区分未提供与显式 null。

**误区**：把 `Optional[T]` 理解为“字段可以不传”，导致 OpenAPI、更新语义和数据库映射错误。

**生产例子**：更新昵称时，未提供表示不修改，显式 `null` 表示清空；用 `model_fields_set` 保留这一区别。

## 05 · validator 的执行顺序是什么？

**30 秒回答**：wrap/before 先面对原始输入，core 验证生成目标类型，after 再处理已验证值；多个 `Annotated` validator 的方向与声明顺序有关，字段按定义顺序可见。

**深挖**：before 必须接受任意原始值；after 可依赖目标类型；wrap 可选择调用 handler。跨字段规则不要依赖尚未验证的后置字段，应放到 model validator。

**误区**：把所有 validator 当成按源码从上到下执行，或在 before 阶段假定拿到的已经是 `int`。

**生产例子**：先 trim SKU 字符串，再由 core 检查 pattern，最后 after 把它规范成大写库存键。

## 06 · field validator 与 model validator 怎么选？

**30 秒回答**：单字段的解析和约束放 field validator；涉及多个字段、整个输入形状或模型最终不变量放 model validator。优先用内置类型/`Field`，validator 只承载表达不了的规则。

**深挖**：model before 适合旧格式迁移，model after 适合起止时间、互斥字段等关系；返回值必须遵守对应模式的契约。

**误区**：为复用方便把所有逻辑塞进 model validator，导致错误位置模糊、顺序脆弱。

**生产例子**：`quantity > 0` 用 `Field(gt=0)`，`discount <= subtotal` 用 model after validator。

## 07 · 为什么 validator 里不应做 I/O？

**30 秒回答**：验证器应确定、快速、可重复。数据库、HTTP、文件或 broker I/O 会让模型构造拥有隐藏延迟、失败和重试语义，也无法自然支持 async 与事务边界。

**深挖**：结构校验与外部事实校验应分层：Pydantic 生成 command，application service 再查库存/权限，并在明确超时、缓存和事务策略下返回业务错误。

**误区**：认为“校验用户名是否存在”名字里有校验，就应该写进 validator。

**生产例子**：`CreateOrderRequest` 只验证 UUID 和数量；`CreateOrderService` 批量查询 SKU 并处理缺货，而不是每个 item validator 发一次 SQL。

## 08 · TypeAdapter 与 BaseModel 如何选择？

**30 秒回答**：需要具名字段、模型方法和稳定 DTO 时用 `BaseModel`；只验证 `list[T]`、union、scalar、dataclass 等任意类型时用 `TypeAdapter`，避免造无意义 wrapper model。

**深挖**：`TypeAdapter` 同样支持 validate Python/JSON、dump 和 JSON Schema；热路径要复用实例，因为构造会生成验证器和序列化器。

**误区**：每次消息处理都临时 `TypeAdapter(...)`，或者为了验证列表创建 `class Items(BaseModel): root: ...`。

**生产例子**：模块级缓存 `TypeAdapter(list[OrderCreatedV2])`，一次验证 broker 拉取的一批消息。

## 09 · discriminated union 为什么优于普通 Union？

**30 秒回答**：它用稳定 discriminator 直接选择分支，验证更快、错误更聚焦、生成的 JSON Schema 更适合消费者；普通 union 需要逐分支尝试且容易产生歧义。

**深挖**：每个分支使用互斥的 `Literal` 标签，标签属于协议，不能随 Python 类重命名。演进时新增标签通常比改变旧标签安全。

**误区**：用可选字段是否存在来猜事件类型，或让两个分支共享同一 discriminator 值。

**生产例子**：支付 webhook 以 `event_type: Literal["captured", "refunded"]` 路由到两个 payload 模型。

## 10 · 为什么拆 DTO、command、domain、view？

**30 秒回答**：四者服务不同变化轴：DTO 适配外部协议，command 表达用例输入，domain 维护业务不变量，view 控制对外输出。共用一个模型会把接口兼容、持久化和业务演进绑死。

**深挖**：边界处做显式映射是防腐层；不是每层都必须是 Pydantic。领域对象可用普通类/dataclass，输出模型应白名单字段。

**误区**：把“少写转换代码”等同于低复杂度，最终在领域对象上堆 alias、序列化和数据库字段。

**生产例子**：API 的 `CreateOrderRequest` 接受 camelCase，转换为 `CreateOrderCommand`；`Order` 领域对象不认识 HTTP alias，`OrderResponse` 不含风控备注。

## 11 · `model_construct()` 有什么风险？

**30 秒回答**：它绕过正常验证来构造模型，只能用于数据已由等价或更强机制验证的受控路径。它不是通用性能开关，简单模型上甚至未必比验证快。

**深挖**：validator、副作用和某些嵌套转换不会运行；调用点必须能证明信任来源，并用 benchmark 证明收益。

**误区**：从数据库、缓存或内部服务来的数据就天然可信，因而全部 `model_construct()`。

**生产例子**：同一进程内从刚刚 `model_dump()` 的冻结快照恢复可评估 construct；跨版本 Redis blob 仍必须正常验证。

## 12 · `extra` 应怎样按边界配置？

**30 秒回答**：对命令、内部事件和安全敏感输入通常 `forbid`，让协议漂移尽早失败；对需要前向兼容的第三方 webhook 可 `ignore`，审计/代理场景才考虑 `allow`。选择必须与版本和观测策略配套。

**深挖**：未知字段是拼写错误、攻击面还是新版本信号，取决于边界。即使 ignore，也可记录抽样指标而不记录敏感原值。

**误区**：全项目统一 `extra="ignore"`，让客户端拼错字段仍收到成功响应。

**生产例子**：创建订单 API forbid 未知字段；支付供应商 webhook ignore 新增字段但对 schema drift 计数告警。

## 13 · 如何防止子类序列化泄漏？

**30 秒回答**：输出以声明的字段类型和专用 response model 为白名单，不要把持有更多内部字段的子类直接 duck-typed dump；敏感字段还应显式 exclude 或使用独立类型。

**深挖**：v2 默认按字段声明类型序列化能降低意外泄漏；`SerializeAsAny`/`serialize_as_any=True` 会恢复运行时子类字段，必须在明确协议下使用。

**误区**：认为字段名以下划线开头或 `repr=False` 就不会进入序列化结果。

**生产例子**：`UserPublic` 类型字段即使实际传入 `UserInternal(password_hash=...)`，响应也只输出 public 字段，并由泄漏回归测试锁定。

## 14 · JSON Schema golden 测试能证明兼容吗？

**30 秒回答**：不能。golden diff 能发现结构变化，是审查信号；兼容性还取决于消费者方向、required/default、约束收紧、格式语义和真实样本。必须结合语义规则与 V1/V2 交叉测试。

**深挖**：输入 schema 新增 optional 字段通常兼容，新增 required 字段通常破坏旧客户端；输出 schema 删除字段会破坏旧消费者。相同 diff 在 producer/consumer 方向结论不同。

**误区**：snapshot 没变就等于业务兼容，或 snapshot 一变就机械判定 breaking。

**生产例子**：PR 展示 schema golden diff，同时运行旧事件样本被 V2 consumer 接受、V1 consumer 对 V2 降级策略的测试。

## 15 · OrderCreated V1/V2 事件如何演进？

**30 秒回答**：版本放在 envelope/discriminator 中，旧版本模型保持不可变；新增 V2 模型和显式 upcaster，消费端在窗口期同时接受 V1/V2，确认消费者迁移后再停止生产 V1。

**深挖**：区分事件版本与 schema registry 版本；定义 additive/breaking 规则、重放策略、DLQ 修复和未知版本处理，不能就地修改历史事件语义。

**误区**：只给原模型加一堆 optional 字段并继续叫 V1，导致无法判断生产时语义。

**生产例子**：V2 增加 `currency`，V1 upcaster 用租户当时默认币种补齐；审计保存原 envelope，不篡改历史消息。

## 16 · 如何把 ValidationError 变成稳定 API 错误？

**30 秒回答**：边界层读取 `errors()` 的 `type`、`loc` 和安全上下文，映射为自有稳定 error code、字段路径和本地化消息；不要把 Pydantic 原始文本或输入值直接作为公共协议。

**深挖**：Pydantic 错误类型可随依赖升级变化，所以映射表和未知 fallback 要测试；日志保留 correlation id、模型和计数，敏感 `input` 需删除或脱敏。

**误区**：直接返回 `str(exc)`，让客户端依赖英文消息并把 token/PII 打进日志。

**生产例子**：`greater_than` 映射为 `ORDER_QUANTITY_INVALID`，响应只含 `items.0.quantity` 与稳定码，原 payload 不落日志。

## 17 · MQ 收到非法消息时怎样重试和进 DLQ？

**30 秒回答**：先区分永久契约错误和暂时基础设施错误。schema/版本/字段错误通常重试不会变好，应记录安全元数据后直接 DLQ；超时等瞬时错误才按上限退避重试。

**深挖**：DLQ 要保留消息 id、topic/partition/offset、producer/schema version 和错误码；修复工具需幂等并重新走完整验证，未知版本与坏业务数据可分流。

**误区**：所有异常统一重试，制造 poison message 热循环和分区阻塞。

**生产例子**：`literal_error` 标为 `contract.invalid_version` 直接 DLQ，库存服务 503 则指数退避三次后进入业务重试队列。

## 18 · settings 的优先级与缓存如何设计？

**30 秒回答**：显式定义来源优先级，常见是 init > env > dotenv > secrets > defaults；每进程在启动边界构造并注入一个 settings 快照。测试清缓存、隔离环境，多 worker 各自加载，动态配置用专门刷新机制。

**深挖**：dotenv 是本地便利，不应悄悄污染生产；缓存提升一致性但意味着变更不会自动生效。密钥显示、嵌套分隔符、大小写和自定义 source 都要测试。

**误区**：库模块 import 时创建全局 settings，测试修改环境变量后期待它自动刷新。

**生产例子**：应用工厂用 `lru_cache` 获取快照，pytest fixture 在 monkeypatch 前后 clear cache；Kubernetes secret 更新通过滚动重启生效。

## 19 · 什么时候值得写 CoreSchema hook？

**30 秒回答**：当一个组织级值对象需要跨模型复用验证、序列化与 JSON Schema，且 `Annotated`、`Field`、内置类型或普通 validator 无法一致表达时才值得。它是高耦合扩展点，要有契约测试和升级预算。

**深挖**：优先调用 handler 组合下游 schema，并同步考虑 `__get_pydantic_json_schema__`；避免依赖未公开内部结构。先做简单 adapter/validator 原型和 benchmark。

**误区**：为了少写几行 validator 就操作 CoreSchema，或复制一份当前版本内部 schema 字典。

**生产例子**：全公司 `SnowflakeId` 同时需要 strict int 输入、范围约束、字符串 JSON 输出和统一 schema format，因此封装成受测自定义类型。

## 20 · Pydantic 性能怎样测量和优化？

**30 秒回答**：先用代表性 payload 和端到端剖析定位占比，再做最小改动：复用模型/`TypeAdapter`，需要 JSON 时比较 `model_validate_json()`，避免 wrap validator 和重复 Python 转换；最后重新测正确性与吞吐。

**深挖**：报告分位延迟、吞吐、批大小、错误比例和环境；验证成本可能根本不是瓶颈。`model_construct()`、FailFast 或自定义 core hook 都要在真实数据上证明收益。

**误区**：引用框架 benchmark 当作自己系统结果，或者为微秒收益牺牲可读错误和边界安全。

**生产例子**：profiling 显示 worker 每条消息重建 adapter；移到模块级后 p99 降低，再用兼容性测试确认行为未变。

## 故障速查

| 症状 | 第一检查点 | 常见修复方向 |
|------|------------|--------------|
| 意外类型转换 | 02 的 strict/coercion 策略与 conversion table | 对标识/金额收紧字段；把允许转换写进边界测试 |
| 未知字段被接受或拒绝 | 模型 `extra` 与调用级 override | 按边界选择 forbid/ignore/allow，并监控漂移 |
| validator 延迟升高 | validator 中 I/O、wrap 模式、逐项 Python 循环 | 移出 I/O，优先 core 约束，profile 后批量化 |
| 内部字段泄漏 | 输出声明类型、`SerializeAsAny`、专用 view model | 白名单响应字段并加负向泄漏测试 |
| 事件版本不兼容 | discriminator/envelope、旧样本、upcaster | 保持旧模型不可变，双读 V1/V2，显式升级 |
| 错误日志泄漏 | `ValidationError.errors()` 中的 `input`/`ctx` | 结构化映射并删除或脱敏原值 |
| 多 worker 配置不一致 | 每进程初始化时间、来源优先级、刷新方式 | 启动时构造快照，版本化配置并滚动重启 |
| 环境被 `.env` 污染 | 当前工作目录、`env_file` 与生产镜像 | 生产禁用隐式 dotenv，测试传显式临时路径 |
| schema golden 漂移 | 生成命令、Pydantic 版本、语义 diff | 固定工具链，审查 diff，再跑兼容性测试 |
| 热路径反复重建 adapter | `TypeAdapter(...)` 的构造位置 | 提升到模块/应用生命周期并安全复用 |
