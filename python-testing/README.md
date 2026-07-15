# Python 测试工程 track

这是一条面向资深后端工程师的 Python 测试进阶路线。读者应已能开发 Python 服务；这里关心的不是 pytest API 清单，而是如何根据业务风险选择测试边界、建立可测架构、保留失败证据，并治理真实测试套件。

仓库中的规范入口是 [`python-testing/README.md`](../python-testing/README.md)，配套可执行项目位于 [`lab/`](lab/README.md)。

## 前置知识

- [Python 工具链、环境与打包](../python/11-tooling-envs-packaging.md)：先熟悉 `uv`、`pyproject.toml` 与 src layout。
- [Python 测试快速入门](../python/12-testing.md)：先掌握 pytest、fixture、parametrize，以及 unittest/doctest 的定位。
- [Python 类型系统](../python/09-typing.md)：读懂 ports、Protocol 和依赖边界。
- 环境要求：CPython 3.11+、[`uv`](https://docs.astral.sh/uv/)；只有 integration 与 E2E 层需要 Docker。

## 章节地图

| 章节 | 主题 | 本章交付 |
|---|---|---|
| 00 | [测试策略与风险模型](00-testing-strategy.md) | 为订单服务建立风险—证据矩阵 |
| 01 | [pytest 执行模型](01-pytest-execution-model.md) | 建立 collection、marker 与插件心智模型 |
| 02 | [好测试与 TDD](02-test-design-and-tdd.md) | test-first 建立订单领域模型 |
| 03 | [fixture 与参数化](03-fixtures-and-parametrization.md) | 建立无共享状态泄漏的测试数据 |
| 04 | [Test doubles 与 seams](04-test-doubles-and-seams.md) | 隔离 repository、payment、clock 与 ID |
| 05 | [Component 与 API 测试](05-component-and-api-tests.md) | 验证无 Docker 的应用与 HTTP 边界 |
| 06 | [数据库整合测试](06-database-integration.md) | 用真 Postgres 验证约束、事务与迁移 |
| 07 | [HTTP 与契约测试](07-http-and-contract-testing.md) | 验证支付 adapter 与版本化契约 |
| 08 | [Async、并发与背景任务](08-async-concurrency-background.md) | 验证 event loop、竞态与 outbox worker |
| 09 | [Property 与 stateful testing](09-property-and-stateful-testing.md) | 用生成数据和状态机验证不变量 |
| 10 | [测试套件可靠性与规模](10-suite-reliability-and-scale.md) | 治理 flaky、顺序依赖、xdist 与速度预算 |
| 11 | [CI、遗留系统与 capstone](11-ci-legacy-and-capstone.md) | 完成退款缺陷的 characterization、修复与矩阵验证 |

## 命令层级

所有命令都从 `python-testing/lab/` 执行。首次运行先执行 `uv sync --extra dev`。

| 层级 | 命令 | 环境契约 |
|---|---|---|
| fast（默认本地反馈） | `uv run pytest -m "not integration and not e2e and not docker" -q` | unit、component、contract 与轻量 property；不接触 Docker |
| integration | `uv run pytest -m "integration and docker" -q` | 真 Postgres、migration、事务、锁；需要 Docker |
| E2E | `uv run pytest -m "e2e and docker" -q` | HTTP 到 Postgres 与可控支付端的完整路径；需要 Docker |

未经明确选择 `docker` marker，不应启动容器。Task 3 的 bootstrap 快照可用 `uv run pytest -q` 验证包安装与 bridge 基础示例，当时结果为 `6 passed`；累计数量会随后续章节增长。

fixture ownership 规则：module/session scope 可以共享真正只读或有隔离协议的资源管理能力，但不得直接返回可变领域对象。需要多个订单或局部覆盖时，共享无状态 factory，并让每次调用创建新的 `Order`。

## 每章固定模板

每章使用相同的八段结构，保证理论、实验、故障证据与面试表达形成闭环：

1. **核心问题**：本章要消除的工程风险。
2. **直觉模型**：可记忆、可迁移的心智框架。
3. **机制深入**：只展开会影响行为、设计或除错的底层机制。
4. **设计取舍**：比较方案成立和失效的条件。
5. **贯穿 lab**：为订单／支付服务增加一层可执行测试能力。
6. **故障工单**：按症状 → 证据 → 假设 → 修复 → regression test 推进。
7. **Java/Go 对照**：指出迁移既有经验时最容易误判的地方。
8. **验收与面试卡**：给出命令、完成定义、一句话与深答版本。

## 进度

| 交付 | 状态 |
|---|---|
| Bootstrap：track、package、配置与 bridge | ✅ 完成 |
| 00 测试策略与风险模型 | ✅ 完成 |
| 01 pytest 执行模型 | ✅ 完成 |
| 02 好测试与 TDD | ✅ 完成 |
| 03 fixture 与参数化 | ✅ 完成 |
| 04 Test doubles 与 seams | ✅ 完成 |
| 05 Component 与 API 测试 | ✅ 完成 |
| 06 数据库整合测试 | ✅ 完成 |
| 07 HTTP 与契约测试 | ⬜ 待完成 |
| 08 Async、并发与背景任务 | ⬜ 待完成 |
| 09 Property 与 stateful testing | ⬜ 待完成 |
| 10 测试套件可靠性与规模 | ⬜ 待完成 |
| 11 CI、遗留系统与 capstone | ⬜ 待完成 |

## 与仓库其他路线的关系

本 track 只解释相关机制如何改变测试边界与失败模式，底层主题继续复用既有路线：

- [数据库、事务、隔离与迁移](../python-data/)
- [GIL、asyncio、AnyIO 与 worker](../python-concurrency/)
- [benchmark、profiling 与性能诊断](../performance-tuning-roadmap/)
- [幂等、状态机与一致性不变量](../financial-consistency/)
- [Go 测试工程对照](../golang/testing/)
- [FastAPI 运维与可观测性](../fastapi-ops/)
