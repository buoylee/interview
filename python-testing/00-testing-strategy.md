# 测试策略与风险模型

测试策略不是“多写测试”，而是为每个重要风险选择足够可信、反馈尽可能快的证据。本章以订单／支付服务为例，建立后续章节共用的边界词汇、风险矩阵与取舍方法。配套命令遵循 [track 的命令层级](README.md#命令层级)，但本章只做策略设计，不新增应用代码或测试。

## 核心问题

一个全绿的测试套件只能证明“这些测试在这个环境里没有发现问题”。它不能自动回答三个更重要的问题：

1. 最贵的业务失败是什么，是否已经被测试覆盖？
2. 测试使用的 oracle，真的能识别那种失败吗？
3. 测试环境保留了触发失败所需的真实机制吗？

这里的 **oracle** 是判定实际结果是否正确的依据，例如金额不变量、状态转移表、数据库唯一约束、对方发布的契约或可观察的 HTTP 响应。测试边界则决定有多少生产机制参与产生这份证据。没有可信 oracle，E2E 也只是昂贵地执行代码；边界保留不了风险来源，再精确的断言也会产生虚假信心。

因此，策略从业务风险开始，而不是从目录、框架或 coverage 百分比开始。订单服务的核心问题可归纳为下面这张风险—证据矩阵。

| 业务风险 | 失败示例 | 最便宜且可信的 oracle | 必需测试边界 |
|---|---|---|---|
| 金额/币种 | 把 `USD 10.00` 与 `CNY 10.00` 相加；折扣后出现不允许的负金额或舍入误差 | 金额值对象的不变量与币种规则 | `unit`；用 `property/stateful` 扩展输入空间 |
| 非法状态转移 | 已取消订单又从 `CANCELLED` 进入 `PAID` | 领域状态转移表与最终领域状态 | `unit`；关键 HTTP 映射补 `component` |
| 幂等键重复 | 同一个 idempotency key 两次创建出两笔订单 | 同一 key 只对应一个持久化业务结果 | `integration`，因为竞争与唯一性由真数据库裁决 |
| 数据库约束与事务 | 订单已提交但 outbox 事件未提交；外键、`NOT NULL` 或唯一约束在 migration 中缺失 | Postgres schema、约束和事务提交／回滚结果 | `integration` |
| 支付 HTTP 相容性 | adapter 发送了错误字段名、认证头或枚举值，支付端拒绝请求 | 双方认可的版本化请求／响应契约 | `contract`；传输细节必要时使用真 HTTP |
| timeout 后结果未知 | 支付端已扣款，但客户端在响应返回前 timeout，重试导致二次扣款 | 查询／对账后的支付事实，而不是 timeout 异常本身 | `component` 验证决策；`contract` 验证查询协议；少量 `e2e` 验证完整闭环 |
| 重复投递 | outbox 消息或 webhook 重放后重复发货、重复退款 | 消费后的业务不变量与去重记录 | `integration` 验证持久化去重；`property/stateful` 验证事件序列 |
| API 向后相容 | 新版本把可选字段改为必填或删除旧响应字段 | 已发布的 consumer/provider API 契约 | `contract`；发布前保留少量 `e2e` smoke |

“最便宜”不是“最小”。例如幂等规则可以在 fake repository 上写得很快，但它不能证明 Postgres 中真的存在唯一约束；此时 `integration` 才是最便宜且**可信**的边界。反过来，金额运算若可由纯领域对象裁决，启动完整服务不会增加关键证据，只会降低反馈质量。

## 直觉模型

### 先问风险，再问边界

可以把每个测试设计压缩为一张证据链：

| 问题 | 要求 |
|---|---|
| 风险是什么？ | 用业务可观察的损失描述，而不是“某行代码没测” |
| 什么事实能证明它没有发生？ | 选一个能明确判定对错的 oracle |
| 哪种机制可能让它发生？ | 领域规则、序列化、数据库、网络、并发或部署 wiring |
| 最小可信边界是什么？ | 只纳入产生风险与执行 oracle 所必需的真实机制 |
| 失败后能否定位？ | 失败输出应指向输入、边界、实际结果与违反的不变量 |

这条链路能防止两个常见误区：按文件结构机械地分层，或把“更接近生产”误当作“对所有风险都更可信”。测试范围越大，fidelity 通常越高，但 isolation 和 diagnosability 往往下降；策略的目标是用一组互补证据覆盖风险，而不是让某一种测试包办一切。

### 五维决策模型

对候选边界逐项比较以下五个维度：

| 维度 | 要问的问题 | 倾向 |
|---|---|---|
| 反馈速度（feedback speed） | 开发者多久拿到结果，失败后多久能重跑？ | 越快越适合高频、本地反馈 |
| 保真度（fidelity） | 是否保留了触发该风险的真实机制与配置？ | 必须达到该风险的可信阈值 |
| 隔离性（isolation） | 失败是否只受被测行为影响，能否并行、能否确定地复现？ | 越高越容易控制变量 |
| 可诊断性（diagnosability） | 红灯是否能指出哪个不变量、adapter 或基础设施契约被破坏？ | 越高越缩短修复时间 |
| 维护成本（maintenance cost） | 数据准备、环境、版本升级和 flaky 治理成本是多少？ | 在证据等价时选择更低者 |

决策顺序是：先淘汰 fidelity 不足、无法识别目标风险的边界；再在剩余候选中选择反馈更快、隔离和可诊断性更好、维护成本更低者。如果一种边界无法同时满足，就拆成互补测试：快速测试穷举领域规则，窄 integration／contract 测试验证真实 seam，少量 E2E 验证关键 wiring。

## 机制深入

### 边界由“哪些机制是真的”定义

这些名称是本 track 的规范定义。它们描述测试保留的真实边界，不等同于文件夹、marker、函数数量或进程数量。

| 名称 | 本 track 的规范定义 | 典型真实机制 | 不负责证明 |
|---|---|---|---|
| `unit` | 围绕一个行为单元验证领域决策；unit 是稳定行为边界，不必等于一个函数或类 | 领域对象／应用策略；外部端口用可控 double | 数据库 schema、网络协议、部署 wiring |
| `component` | 在单进程内装配一个可独立调用的应用组件，跨越多个内部对象但替换进程外基础设施 | use case、路由、序列化、异常映射、依赖注入 | 真数据库语义和真实外部服务相容性 |
| `integration` | 让应用 adapter 与一个真实基础设施边界协作，验证双方语义 | Postgres、migration、事务、锁或真实 broker adapter | 整个用户旅程与所有部署组件 |
| `contract` | 验证 provider 与 consumer 在可版本化接口上的共同约定 | HTTP schema、状态码、headers、事件结构与兼容规则 | 对方内部业务正确性或完整部署 |
| `e2e` | 从公开入口穿过已部署／近生产装配到最终可观察结果，验证关键 wiring 与旅程 | HTTP、应用装配、数据库及可控外部边界 | 所有输入组合和每个底层分支 |
| `property/stateful` | 用生成输入或命令序列反复验证不变量；property 验证广泛输入空间，stateful 验证状态演化 | 领域模型，也可组合受控 adapter | 未纳入边界的基础设施语义 |

一个测试可以同时具有两个维度。例如，连接真 Postgres 并生成随机幂等键序列的测试既是 `integration`，也采用 `property/stateful` 技法。名称不是互斥分类，更不是质量等级；应在测试名、marker 和失败信息中明确它主要提供哪种证据。

### 测试结果也会失真

本章采用如下术语：

- **false positive（假阳性）**：系统行为正确，测试却报错。例如测试断言 JSON 对象的键顺序或自动生成的时间戳必须逐字符相同，重排或时钟变化就制造红灯。它伤害信任，并把维护时间浪费在非业务差异上。
- **false negative（假阴性）**：系统行为错误，测试却通过。例如 fake repository 用字典覆盖相同 idempotency key，于是重复请求测试全绿；真实 migration 却缺少 Postgres unique constraint，并发请求仍会插入两行。
- **环境保真度（environment fidelity）失配**：测试环境没有生产故障依赖的语义。例如用 SQLite 验证 Postgres 的隔离级别、锁和约束，或让自制支付 stub 接受真实 provider 会拒绝的字段。提高 fidelity 的理由应是补齐某项风险机制，不是笼统追求“更真实”。

oracle 也可能错误：若断言只检查 HTTP `200`，便无法发现金额写错；若只检查抛出 `TimeoutError`，便无法判断远端是否已经扣款。可靠测试要让 oracle 对准业务后果，并让环境保留产生该后果的机制。

### coverage 是地图，不是证明

coverage 回答“哪些语句或分支执行过”，不回答断言是否有识别力、输入空间是否充分、并发交错是否出现、契约是否真实，或高风险路径是否有独立证据。一个没有断言的 E2E 可以获得很高 coverage；一个只返回固定值的 mock 也能让错误实现全绿。

coverage 适合发现测试盲区和异常分支，不能替代风险矩阵。对金额、状态机这类巨大输入／序列空间，还应使用示例测试加 `property/stateful` 不变量；对数据库与协议风险，则要提高对应边界的 fidelity。必要时 mutation testing 可以检验断言是否能杀死行为变化，但它仍不告诉团队业务风险排序是否正确。

## 设计取舍

### 金字塔、钻石和蜂巢只是启发式

测试金字塔强调大量快速窄测试、较少宽测试；测试钻石提高 integration／component 的比重；测试蜂巢则把 integration 放在服务测试中心。这些图形提醒团队关注反馈和边界，但都不是固定比例。

不能从“70% unit、20% integration、10% E2E”推导质量，原因有三：

1. 分母不稳定：parametrize 的一百个 case、一个 stateful 测试和一条 E2E 旅程无法按数量等价比较。
2. 架构不同：纯计算库的可信证据集中在 unit/property；以 SQL 约束、消息和外部协议为核心的服务必须增加 integration/contract。
3. 风险不均匀：一次重复扣款的损失远高于后台文案错误，测试投资应随影响、发生概率和可探测性变化。

因此图形用于审查组合是否失衡，而不是考核比例。更有用的问题是：每项高风险是否有可信 oracle；同一规则是否在过多边界重复；宽测试失败时是否有窄测试帮助定位；最慢层是否只保留必须由它证明的事项。

### 何时升级，何时下沉

| 现象 | 策略动作 |
|---|---|
| double 无法表达真实约束、事务或锁 | 把该证据升级到 `integration`，领域规则仍留在 `unit` |
| HTTP schema 漂移但完整 E2E 太慢 | 用 `contract` 固定双方约定，E2E 只留发布 smoke |
| E2E 才能发现状态机错误 | 将规则下沉到 `unit`／`property/stateful`，E2E 只验证 wiring |
| 大量 component 测试重复相同分支 | 保留少量路由／装配证据，把输入组合下沉到 unit |
| 宽测试经常因非业务差异失败 | 收窄 oracle，固定时钟／随机源，移除与风险无关的断言 |

测试重复并非总是坏事：关键不变量可以在不同 seam 各出现一次，分别证明领域决策、持久化和公开行为。坏的重复是多个昂贵测试提供完全相同的证据，却没有增加 fidelity 或故障定位能力。

## 贯穿 lab

后续章节会在 [`lab/`](lab/README.md) 中逐步实现订单／支付服务。本章先给每类证据分配运行层级，避免未来把目录名误当成策略。

| 证据 | 默认层级 | 环境契约 | 本地反馈用途 |
|---|---|---|---|
| 金额、币种、状态转移与应用决策 | `unit` / 轻量 `property` | 无网络、无 Docker | 每次编辑后运行 |
| 路由、序列化、错误映射、timeout 决策 | `component` | 进程外端口可控；无 Docker | fast 套件运行 |
| 支付与 API schema | `contract` | 默认使用确定的本地契约边界；需要真服务时显式标记 | fast 或专门契约 job |
| Postgres 约束、事务、锁与持久化去重 | `integration` + `docker` | 真 Postgres；必须显式选择 Docker | 合并前／CI 运行 |
| 关键创建、支付确认与恢复旅程 | `e2e` + `docker` | 完整装配与可控支付端 | 少量发布门禁 |

默认反馈命令是 `cd python-testing/lab && uv run pytest -m "not integration and not e2e and not docker" -q`。它覆盖 unit、component、contract 与轻量 property，且不会启动容器。只有显式运行 integration 或 E2E 层级时才允许使用 Docker；这个运行契约与 [lab README](lab/README.md#命令层级) 保持一致。

策略落地时，为每个新增测试记录三件事即可：它防止的业务风险、使用的 oracle、为什么当前边界是最小可信边界。若无法回答其中任何一项，先不要用更大的测试掩盖设计不清。

## 故障工单

### 工单：测试全绿，重复请求仍创建两笔订单

**症状**

生产中两个携带相同 idempotency key 的并发 `POST /orders` 都成功，产生两笔订单。unit 与 component 套件全绿；它们使用 mocked repository。

**证据**

- 两条生产记录拥有相同 idempotency key 和不同 order ID，写入时间只差数毫秒。
- mocked repository 以 key 为字典索引，第二次保存会覆盖第一次，因此测试观察到的永远只有一个结果。
- 当前 Postgres migration 没有 idempotency key 的 unique constraint；测试环境也从未运行真实 migration。
- 应用层“先查询、再插入”分成两个操作，两个事务可以同时查询不到记录。

**假设**

mock 把“重复 key 时保持单一结果”实现成了自己的行为，既没有模拟并发，也没有执行 Postgres 的原子唯一性裁决。测试验证的是 fake 的保证，不是生产系统的保证，因而形成 false negative。

**修复**

在正确业务作用域内为 idempotency key 增加 Postgres unique constraint；repository 把唯一冲突映射为“读取并返回既有结果”或明确的领域结果，并让 migration 成为 integration 测试装配的一部分。应用层预检查可保留为优化，但不能承担并发正确性。

**regression test**

新增使用真 Postgres 的 integration 回归测试：先执行真实 migration，再并发提交相同 key，断言最终只有一个持久化业务结果，所有调用者收到同一订单身份或约定的重复结果。该测试的 oracle 是数据库最终状态与公开 repository 结果；unit 测试继续覆盖冲突映射的快速分支，但不再声称证明唯一约束。

**工单结论**

mock 适合隔离应用决策，却不能证明数据库约束存在。修复不仅是“多加一个测试”，而是把风险、oracle 与拥有裁决权的 Postgres 边界重新对齐。事务、隔离级别与 migration 的机制细节参见 [Python 数据路线](../python-data/README.md)。

## Java/Go 对照

| 目标 | Java / JUnit / Spring | Go | 本 track 的 Python 边界 |
|---|---|---|---|
| 验证领域行为 | JUnit 测普通对象，mock 外部 port；unit 不等于“一个 method” | 同 package 或 `_test` package 测稳定行为，常用 table-driven test | `unit` 围绕稳定行为单元，pytest 函数／类不决定边界 |
| 验证 Web 组件 | `@WebMvcTest` 只装配 MVC slice；mock service／port | `httptest` 在进程内调用 handler，外部依赖替换 | `component` 装配路由、序列化、use case 与错误映射 |
| 验证持久化 | `@DataJpaTest` 验证 JPA slice；若目标是 Postgres 语义，应配真 Postgres/Testcontainers | repository test 连接真数据库；常用 build tag、环境变量或独立 CI job 隔离 integration | `integration` 使用真 Postgres、migration 与事务；`docker` 必须显式选择 |
| 验证完整装配 | `@SpringBootTest` 只有在端口、数据库等真实边界参与时才接近 E2E；单凭注解不能判定层级 | 编译并启动服务，从公开 API 驱动关键旅程 | `e2e` 由公开入口、真实装配和最终可观察结果定义 |

最容易误判的是把框架机制直接翻译成测试层级。Spring slice 通常对应 component 或窄 integration，但 `@DataJpaTest` 若换成内存数据库，就不能证明 Postgres 特有语义；Go 的 package test 既可能是纯 unit，也可能启动数据库。Python 同理：pytest marker 和目录是运行／治理工具，真实依赖与 oracle 才定义证据边界。

迁移经验时保留原则，不照搬形式：JUnit 的 class/annotation 生命周期、Go 的 package/table-driven 组织和 pytest 的 fixture/parametrize 都能表达高质量测试；它们都无法替团队决定哪种生产风险值得哪种 fidelity。

## 验收与面试卡

### 验收

- 八类订单服务风险都能追溯到失败示例、可信 oracle 与必需边界。
- `unit`、`component`、`integration`、`contract`、`e2e`、`property/stateful` 均按真实机制定义，而非按目录或框架定义。
- fast 命令保持 Docker-free；integration 与 E2E 只有显式选择 `docker` 才启动基础设施。
- 故障工单能够解释 mocked repository 为什么产生虚假信心，以及真 Postgres regression test 补充了什么证据。

检查本章的关键概念：

```bash
rg -n "反馈速度|失真|oracle|unit|component|integration|contract|e2e|property|幂等|timeout|coverage|python-data" python-testing/00-testing-strategy.md
```

运行当前 fast 套件：

```bash
cd python-testing/lab
uv run pytest -m "not integration and not e2e and not docker" -q
```

### 面试卡 1：单元测试的 unit 到底是什么？

**一句话：** unit 是一个可独立验证的稳定行为边界，不必等于一个函数、类或文件。

**深答：** 我先确定要证明的领域决策，再把不会影响该决策的进程外协作者替换为可控端口。只要测试能通过公开行为观察结果、失败能定位到该决策，并且不依赖数据库或网络，它就可以是 unit；一个 use case 可能跨多个对象，一个很小的 repository method 反而可能是 integration。边界由真实机制和 oracle 定义，不由代码行数定义。

### 面试卡 2：为什么不能只看 coverage？

**一句话：** coverage 只说明代码被执行，不说明断言能发现错误，也不说明高风险行为获得了可信证据。

**深答：** 高 coverage 仍可能遗漏边界输入、状态序列、并发交错、数据库约束和外部契约；无断言执行或过度宽松的 mock 都能让数字很好看。我把 coverage 当作盲区地图，再按风险补充示例、property/stateful、integration 或 contract 证据，并用失败质量检验 oracle，而不是把覆盖率阈值当作质量结论。

### 面试卡 3：如何选择 E2E 数量？

**一句话：** 不按固定比例选 E2E，而按必须由完整 wiring 才能证明的高价值用户旅程来选。

**深答：** 我先列出高影响旅程及其不可替代的跨边界风险，例如创建订单、支付结果未知后的恢复、重复投递后的单一业务结果。能由 unit、component、integration 或 contract 更快证明的分支下沉；E2E 只保留公开入口、真实装配、关键依赖和最终结果之间的连通性证据。数量增长的条件是出现新的独立 wiring 风险，而不是代码量增加或追求某个金字塔比例。

完成本章后，返回 [Python 测试工程 track](README.md)；后续章节会把本章的风险矩阵逐项变成可执行证据。
