# Python 测试工程 track —— 设计 spec

> 日期：2026-07-15
> 目录：`python-testing/`
> 分支：`codex/python-testing-tutorial`
> 状态：设计已确认，待书面 spec 复核
> 读者：有扎实后端经验、希望把 Python 测试能力提升到资深工程师或架构师层级的开发者

## 1. 背景

仓库已有 [`python/12-testing.md`](../../../python/12-testing.md)，约 178 行，覆盖 pytest 基础、fixture、parametrize、mock、coverage、Hypothesis 与 tox/nox 的概念入口。它适合作为 Python 主教程中的测试导引，但不足以承载以下资深级主题：

- 如何依据风险与系统边界设计测试组合，而非机械追求覆盖率或测试金字塔比例；
- 如何通过 ports、依赖注入、clock/ID generator 等 seam 形成可测架构；
- 如何在真 Postgres、外部 HTTP、asyncio、背景任务与并发条件下建立可信测试；
- 如何理解 pytest collection、assert rewriting、fixture graph、plugin/hook 与 xdist 等会影响工程决策的机制；
- 如何使用 property-based/stateful testing、契约测试、mutation testing 与 CI matrix；
- 如何诊断并治理 flaky、顺序依赖、资源泄漏、错误 patch、timeout 与测试套件膨胀；
- 如何在棕地系统中先建立 characterization tests，再安全修复和重构。

因此新建独立 `python-testing/` track；原第 12 章改为 10–15 分钟的框架选型和快速入门，并链接到本 track。

## 2. 目标与学习成果

本 track 以真实工程为主线，面试内容由工程实践反向提炼。读完后，读者应能：

1. 根据业务风险、反馈速度、隔离程度与环境失真，选择 unit、component、integration、contract、property/stateful 与 E2E 测试；
2. 设计可替换的边界，在不污染领域模型的前提下隔离时间、随机、数据库与外部服务；
3. 解释 pytest 的关键执行机制，并用这些机制定位 collection、fixture、async 与并行执行问题；
4. 为 FastAPI + SQLAlchemy + Postgres 服务建立快速层和真实整合层；
5. 验证事务、约束、迁移、锁、幂等、重试、重复投递、HTTP 相容性与状态机不变量；
6. 评估 mock、fake、真实依赖、覆盖率与 mutation testing 的证据强度和失真风险；
7. 诊断 flaky tests、顺序依赖、共享状态污染、timeout、资源泄漏与 worker 隔离问题；
8. 建立 Python 3.11–3.14 的可重现测试矩阵与分层 CI；
9. 面对遗留代码时，先补 characterization tests 和失败证据，再实施安全修复与重构；
10. 在面试中用问题、风险、证据和取舍回答测试设计题，而不是背 pytest API。

## 3. 核心设计决策

| 维度 | 决策 |
|---|---|
| 教程形态 | 独立 `python-testing/` track，原 `python/12-testing.md` 降为桥接入口 |
| 组织主线 | 测试边界逐层扩张：domain → component → DB → HTTP → async/background → system → suite governance |
| 主框架 | pytest；unittest 与 doctest 只在入口章讲定位、迁移和互操作 |
| 贯穿案例 | 迷你订单／支付服务，使用 FastAPI、SQLAlchemy、Postgres 和可控支付渠道 |
| 架构形态 | 模块化单体；用 ports 隔离 repository、payment gateway、clock 与 ID generator |
| lab 环境 | 双层：默认 `uv + pytest`、无 Docker；整合章用 Testcontainers 启动真 Postgres |
| 开发情境 | 混合：前半绿地 test-first，后半棕地 characterization + bugfix + refactor |
| 范围 | 完整后端测试工程；包含 API E2E，不包含浏览器 UI |
| Python 基线 | CPython 3.11+；实现时验证 3.11、3.12、3.13、3.14 |
| 原理深度 | 深入 collection/import、assert rewriting、fixture graph、hook/plugin、event-loop ownership 和 xdist 进程模型；不做完整源码导读 |
| 验收形式 | 每章可执行任务 + 故障工单 + 面试卡；最后完成综合 capstone |
| 篇幅 | 12 章（00–11）+ `99-interview-cards/` + 一套可执行 lab |

## 4. 教程与 lab 架构

### 4.1 服务边界

```text
FastAPI API
    ↓
Application use cases
    ↓
Order domain model / state machine
    ↓
Ports
 ┌──┴─────────────────┐
Repository         Payment gateway
    ↓                    ↓
SQLAlchemy/PG         HTTP adapter
    ↓
Outbox/background worker
```

- `domain`：订单状态、Money value object、不变量和状态转移；不依赖框架或 I/O。
- `application`：下单、支付、重试、退款与幂等策略；只依赖 ports。
- `ports`：repository、payment gateway、clock、ID generator 的稳定接口。
- `adapters`：SQLAlchemy/Postgres repository、HTTP 支付 adapter、outbox worker。
- `api`：FastAPI 路由、输入验证、错误映射、依赖组装和 lifespan。

lab 不承担 FastAPI、SQLAlchemy 或 asyncio 基础教学；这些内容链接到仓库既有教程。本 track 只解释它们如何改变测试边界和失败模式。

### 4.2 测试边界

| 边界 | 真实对象 | 替代对象 | 主要证明 |
|---|---|---|---|
| unit | domain | 无 | 状态转移、金额规则、异常和不变量 |
| component | domain + application | handwritten repository/payment/clock fakes | use-case 政策、协作和错误映射 |
| API component | FastAPI + application | adapters 由明确 override 替换 | HTTP 输入输出、lifespan、依赖组装和错误响应 |
| integration | SQLAlchemy + psycopg + Postgres | 外部支付仍为 fake | schema、约束、事务、锁、迁移和查询行为 |
| contract | HTTP adapter + 可控 provider | 仅 provider 为独立 fake server | 请求格式、响应映射、相容性、timeout/retry |
| E2E | API + application + Postgres + HTTP adapter | 支付 provider 为可控 fake server | 关键用户流程跨层接线正确 |
| property/stateful | domain 或受控 component | 参考模型 | 大输入空间、操作序列和全程不变量 |

这里不规定固定的测试金字塔比例。测试组合由风险、反馈速度、维护成本和环境失真共同决定。

## 5. 章节地图

| 章节 | 主题 | 核心内容与 lab 演进 |
|---|---|---|
| `00-testing-strategy.md` | 测试策略与风险模型 | 测试能证明什么、oracle、边界分类、反馈速度、失真与成本；为订单服务建立风险—测试矩阵 |
| `01-pytest-execution-model.md` | pytest 执行模型 | discovery/collection、rootdir/import mode、node ID、marker、plugin/hook、assert rewriting；建立项目测试骨架 |
| `02-test-design-and-tdd.md` | 好测试与 TDD | 行为而非实现、AAA/Given-When-Then、边界与反例、命名、coverage 限制、mutation 概念；test-first 建立订单 domain |
| `03-fixtures-and-parametrization.md` | fixture 依赖图 | fixture DAG、scope/cache、yield/finalizer、teardown 顺序、factory fixture、parametrize、conftest；建立不泄漏状态的 test data |
| `04-test-doubles-and-seams.md` | Test doubles 与可测架构 | dummy/stub/spy/mock/fake、ports/DI、autospec/spec_set、patch lookup、clock/UUID 隔离；建立 repository/payment fakes |
| `05-component-and-api-tests.md` | Component 与 API 测试 | application use case、FastAPI/HTTPX、dependency override、lifespan、验证、错误映射和日志断言；完成无 Docker 服务层测试 |
| `06-database-integration.md` | 真数据库整合 | Testcontainers/Postgres、事务 fixture、commit/rollback、constraint、migration、lock/isolation、SQL 数量契约；替换 fake repository |
| `07-http-and-contract-testing.md` | 外部 HTTP 与契约 | controllable fake server、timeout/retry/error mapping、consumer/provider contract、OpenAPI 相容性；接入支付 adapter |
| `08-async-concurrency-background.md` | async、并发与背景工作 | pytest-asyncio、event-loop ownership、task cleanup、timeout、竞态、可控调度、outbox worker；验证重复投递和并行支付 |
| `09-property-and-stateful-testing.md` | Hypothesis 与状态机 | strategy、shrinking、example database、property 设计、RuleBasedStateMachine；验证订单状态与金额不变量 |
| `10-suite-reliability-and-scale.md` | 测试套件治理 | flaky 分类、order dependency、状态污染、随机化、xdist、测试分层、速度预算、coverage/mutation；安全并行化 |
| `11-ci-legacy-and-capstone.md` | CI、棕地演进与综合实战 | Nox、Python 3.11–3.14 matrix、cache/artifact、characterization tests；完成退款流程 bugfix 与安全重构 |
| `99-interview-cards/` | 面试速答与深题 | 每章速答索引、架构取舍题、pytest 机制题、故障诊断题和完整答案 |

学习阶段分为：

```text
00–04：测试思维、pytest 心智与可测设计
05–08：跨越 API、DB、HTTP、async 等真实边界
09：从 example-based 升级到不变量和状态空间
10–11：从会写测试升级到能治理大型测试套件
```

## 6. 每章教学模板

每章固定为八段：

1. **核心问题**：本章要消除的工程风险；
2. **直觉模型**：可记忆、可迁移的心智框架；
3. **机制深入**：只展开会影响行为、设计或除错的底层；
4. **设计取舍**：不同方案何时成立、何时失效；
5. **贯穿 lab**：在订单／支付服务增加一层测试能力；
6. **故障工单**：症状 → 证据 → 假设 → 修复 → regression test；
7. **Java/Go 对照**：只解释容易错用既有经验之处；
8. **验收与面试卡**：可执行任务、诊断题、一句话和深答版本。

每个 lab 任务必须写明：

- 执行目录、命令与预期成功或失败现象；
- 所属测试边界，以及为何不放到其他层；
- 正例、边界、失败路径和至少一个反例；
- 失败时需要保留的证据；
- 基于行为和风险的完成定义，而非单一 coverage 百分比。

正式代码块必须来自可执行 lab；纯示意代码明确标为 pseudocode。故障修复后必须保留 regression test。

## 7. 目录与产物

```text
python-testing/
├── README.md
├── 00-testing-strategy.md
├── 01-pytest-execution-model.md
├── 02-test-design-and-tdd.md
├── 03-fixtures-and-parametrization.md
├── 04-test-doubles-and-seams.md
├── 05-component-and-api-tests.md
├── 06-database-integration.md
├── 07-http-and-contract-testing.md
├── 08-async-concurrency-background.md
├── 09-property-and-stateful-testing.md
├── 10-suite-reliability-and-scale.md
├── 11-ci-legacy-and-capstone.md
├── 99-interview-cards/
│   ├── README.md
│   └── q-*.md
└── lab/
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── noxfile.py
    ├── migrations/
    ├── src/order_service/
    │   ├── domain/
    │   ├── application/
    │   ├── ports/
    │   ├── adapters/
    │   └── api/
    ├── tests/
    │   ├── unit/
    │   ├── component/
    │   ├── integration/
    │   ├── contract/
    │   ├── e2e/
    │   └── property/
    └── scenarios/
        └── pytest 机制和故障诊断的最小重现案例
```

`lab/` 只有一份累积演进的最终服务。只有 collection/import、fixture scope、async loop 等无法自然放进业务服务的机制问题，才建立最小重现案例；不按章节复制整套应用。

## 8. 工具栈

| 责任 | 工具 | 使用原则 |
|---|---|---|
| 主测试框架 | pytest | 所有测试的统一 runner；演示 unittest 互操作但不以它为主线 |
| mock/patch | `unittest.mock` + `monkeypatch` | 只替换明确边界；handwritten fake 优先用于有行为的协作者 |
| async | pytest-asyncio | lab 使用 strict mode 和显式 marker，讲清 event-loop ownership |
| property/stateful | Hypothesis | domain properties 与订单 RuleBasedStateMachine |
| API/component | FastAPI + HTTPX ASGITransport | 不启动网络进程即可验证应用接线 |
| 数据库 | `testcontainers[postgres]` + SQLAlchemy + psycopg | 真实 Postgres；不使用 SQLite 模拟生产数据库语义 |
| coverage | coverage.py / pytest-cov | 找测试盲区，不设 100% KPI |
| 平行执行 | pytest-xdist | 隔离审计通过后才启用；讲清多进程 worker 边界 |
| mutation | mutmut | 只针对核心 domain，排程或手动运行；不阻塞每个 PR |
| 环境矩阵 | Nox | lab 采用 Nox + uv backend；正文比较 tox 与 Nox |
| 依赖 | uv + committed `uv.lock` | 固定实际使用版本，保证命令可重现 |

`pyproject.toml` 统一配置 marker、strict marker、`xfail_strict`、async mode、warning policy、test paths 和 coverage。不得把重要运行约定分散到隐含 shell 环境中。

## 9. 执行层级与 CI 契约

### 9.1 本地命令层级

- **fast**：unit + component + contract；默认命令，不需要 Docker；
- **integration**：真 Postgres、migration、锁和并发；需要 Docker；
- **e2e**：HTTP 入口到 Postgres 和 fake payment provider；需要 Docker；
- **property**：轻量 properties 可在 fast，较重 stateful tests 独立标记；
- **mutation**：针对 domain 的选择性任务，手动或排程运行。

具体命令在实现计划中固定为 Nox sessions，并由 `lab/README.md` 提供等价的直接 `uv run pytest ...` 命令。

### 9.2 CI 分层

```text
PR
├── fast matrix：Python 3.11、3.12、3.13、3.14
│   └── unit + component + contract
├── integration：Python 3.14
│   └── Postgres + migration + concurrency
├── e2e：Python 3.14
│   └── HTTP → application → Postgres → fake payment
└── quality
    ├── coverage report/artifact
    └── selective mutation（排程或手动）
```

CI 设计保持平台中立：教程给出 job 输入、命令、缓存和 artifact 契约，不维护某个供应商的完整 YAML 百科。Nox sessions 是本地和 CI 的共同入口。

## 10. 失败证据与 flaky test 治理

一次可诊断的失败至少记录：

- pytest node ID、marker、Python 和依赖版本；
- 随机 seed 或 Hypothesis 最小反例；
- request/correlation ID 和结构化日志；
- SQL/query count，以及必要的 Postgres/container log；
- setup、test body、teardown 中的失败阶段；
- 每阶段耗时和 timeout 所在边界。

治理规则：

1. 不用任意 `sleep` 等待 async 或背景任务；使用事件、可控时钟、polling deadline 或显式同步点；
2. timeout 放在明确边界，失败消息说明正在等待的条件；
3. 不用 rerun 插件把 flaky test 洗绿；rerun 只作为诊断证据；
4. quarantine 必须有原因、owner、到期条件和跟踪项；
5. `xfail` 使用 strict，未注册 marker 直接报错；
6. warning 不整体关闭，只为已理解的来源制定 policy；
7. cleanup 在被测代码失败时仍必须执行，teardown failure 独立可见；
8. xdist 只用于无共享可变状态、无固定端口和无数据库命名冲突的测试；
9. 任何线上或棕地缺陷修复必须留下能稳定复现原问题的 regression test。

## 11. Capstone：遗留退款流程

最终章不另建项目，而是在现有订单服务加入一个带缺陷的退款流程。初始状态包含：

- 行为已有调用方依赖，但缺少明确契约；
- 一个 transaction/commit 边界问题；
- 一个支付渠道 timeout 后状态不确定的问题；
- 重复请求下的幂等缺口；
- 一个会在并行或特定顺序下暴露的 flaky test；
- 需要保持向后相容的 API response。

读者必须依次：

1. 建立 characterization tests，记录现有可观察行为；
2. 收集失败证据并区分产品缺陷、测试缺陷与环境缺陷；
3. 用真 Postgres 和可控支付 provider 重现失败；
4. 补充 transaction、contract、stateful 或 concurrency 层的 regression test；
5. 修复缺陷并重构 seam；
6. 在 fast、integration、E2E 和版本矩阵中验证；
7. 形成一份面试可讲述的测试策略和取舍复盘。

## 12. 与仓库既有内容的关系

- Python 语言入口：[`python/12-testing.md`](../../../python/12-testing.md)；
- 数据库、Session、事务、隔离级别与迁移机制：[`python-data/`](../../../python-data/)；
- GIL、asyncio、AnyIO 和生产 worker：[`python-concurrency/`](../../../python-concurrency/)；
- benchmark、profiling 与性能诊断：[`performance-tuning-roadmap/`](../../../performance-tuning-roadmap/)；
- 幂等、状态机和一致性不变量：[`financial-consistency/`](../../../financial-consistency/)；
- Go 测试工程对照：[`golang/testing/`](../../../golang/testing/)；
- FastAPI 运维和可观测性：[`fastapi-ops/`](../../../fastapi-ops/)。

本 track 通过链接复用上述机制，不重写它们；正文聚焦这些机制如何影响测试策略、fixture 生命周期和失败模式。

## 13. 验收标准

- `python-testing/README.md`、12 章、`99-interview-cards/` 和 bridge chapter 全部完成且互链正确；
- `lab/` 采用 src layout，依赖锁定，README 从零可运行；
- fast 层不需要 Docker，能独立运行；
- integration 和 E2E 使用真 Postgres，不以 SQLite 替代；
- 所有正式代码块、pytest 命令和 Nox session 均实际执行验证；
- 每章至少有一个可重现故障工单，修复后保留 regression test；
- Python 3.11、3.12、3.13、3.14 的 fast matrix 通过；
- 数据库、契约、async、stateful、xdist 和 capstone 各有可运行证据；
- capstone 同时覆盖 characterization、DB、外部 HTTP、幂等、flaky 诊断和安全重构；
- coverage 和 mutation 结果能揭示至少一个实际断言盲区，但不要求 100% 指标；
- 面试卡能从问题定义、风险、证据、方案和取舍完整回答，而非只列 API。

## 14. 非目标

- 不重教 FastAPI、SQLAlchemy、Postgres、asyncio 或 Python 语法基础；
- 不包含浏览器 UI、移动端、压测、渗透测试或大型混沌平台；
- 不建立 Kafka、Redis、Kubernetes 或多服务 lab；
- 不做完整 pytest 源码导读或插件开发教程；
- 不做 mock framework、CI YAML、pytest 插件或命令参数百科；
- 不以 100% coverage、固定测试数量或固定金字塔比例作为成功标准；
- 不为了展示模式而引入 repository、service 或 interface 样板；每个 seam 必须对应真实测试边界。

## 15. 官方参考基线

- pytest：https://docs.pytest.org/en/stable/
- Python unittest：https://docs.python.org/3/library/unittest.html
- pytest-asyncio：https://pytest-asyncio.readthedocs.io/en/stable/concepts.html
- Hypothesis stateful testing：https://hypothesis.readthedocs.io/en/latest/stateful.html
- Testcontainers Python：https://testcontainers-python.readthedocs.io/en/latest/
- pytest-xdist：https://pytest-xdist.readthedocs.io/en/stable/
- mutmut：https://mutmut.readthedocs.io/en/latest/
- Nox：https://nox.thea.codes/en/latest/usage.html

实现时依赖版本以 `uv.lock` 为唯一可执行基线；教程描述稳定概念，并对版本敏感行为明确标注版本。
