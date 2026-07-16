# Python 测试工程面试卡

这份索引用于面试前快速校准表达，不替代章节和可执行 lab。回答顺序建议固定为：先说风险与 oracle，再说明最小可信边界，最后补上失真来源、取舍和可执行证据。

## 七张深题卡

| 主题 | 深题卡 |
|---|---|
| 支付流程的测试边界 | [如何为支付工作流选择测试边界？](q-test-strategy.md) |
| fixture DAG 与 teardown | [pytest 如何构建并执行 fixture DAG？](q-fixture-dag.md) |
| mock、stub、fake、spy | [该选哪一种 test double，为什么？](q-mock-vs-fake.md) |
| 真 Postgres 与事务 fixture | [为什么数据层要对真 Postgres 测试？](q-database-testing.md) |
| async flaky 与并行 | [event loop、task ownership 和 xdist 有何不同？](q-async-flaky.md) |
| property 与 stateful | [何时生成测试能发现样例遗漏的缺陷？](q-property-stateful.md) |
| 大型套件治理 | [如何治理 30 分钟且 flaky 的套件？](q-suite-governance.md) |

## 00 · 测试策略与风险模型

- 怎样决定一个支付风险该放在哪一层？— [先找能裁决业务损失的 oracle，再保留产生风险所必需的最小真实机制。](../00-testing-strategy.md#先问风险再问边界) ｜`test-boundary`
- 为什么 HTTP 200 不是充分的正确性证据？— [oracle 必须判断金额、状态或持久化事实，而不只是代码运行或请求成功。](../00-testing-strategy.md#核心问题) ｜`oracle`
- 为什么同一规则不应全部堆进 E2E？— [宽边界提高部分 fidelity，却降低隔离和诊断；应让互补的窄证据覆盖输入与分支。](../00-testing-strategy.md#五维决策模型) ｜`evidence-portfolio`
- 什么情况下必须把 fake 测试升级为 integration？— [当风险由真实约束、事务、锁或驱动语义裁决时，double 已经缺少关键机制。](../00-testing-strategy.md#何时升级何时下沉) ｜`integration`

## 01 · pytest 执行模型

- 为什么测试函数还没执行就会失败？— [pytest 先完成配置、plugin/conftest 加载、模块导入与 collection，任一阶段都可能红。](../01-pytest-execution-model.md#collection-不等于-execution) ｜`collection`
- 为什么 helper 内的 assert 没有 operands 展开？— [assert rewriting 默认覆盖测试和 plugin 模块，普通 helper 必须在首次 import 前注册。](../01-pytest-execution-model.md#assertion-import-hook-与-rewritten-pyc) ｜`assert-rewrite`
- rootdir 为什么不能修复包导入失败？— [rootdir 决定配置锚点、node ID 与缓存位置，不负责把源码加入 sys.path。](../01-pytest-execution-model.md#rootdir配置发现与-testpaths) ｜`import-mode`
- 两台机器同命令为何可能收集不同测试？— [安装的 plugin、自动加载和 conftest 作用域都会改变 collection 与 hook 行为。](../01-pytest-execution-model.md#conftestmarker-与-pluginhook) ｜`plugin`

## 02 · 好测试与 TDD

- 一个测试可以有多个 assert 吗？— [可以；同一状态转换的状态、引用和版本共同构成一个失败理由。](../02-test-design-and-tdd.md#一个测试只承担一个失败理由) ｜`test-design`
- 怎样证明一条测试真的经历过 RED？— [行为 API 已存在时，测试要因目标政策缺失而出现 assertion、DID NOT RAISE 或政策异常。](../02-test-design-and-tdd.md#redgreenrefactor-是证据链) ｜`tdd`
- 什么测试最能保护重构？— [通过公开 API 建立前提并断言可观察结果，不锁定私有 helper 或调用顺序。](../02-test-design-and-tdd.md#行为断言与实现断言) ｜`behavior`
- coverage 很高为何仍需要 mutation audit？— [执行过分支不代表 oracle 能区分错误；mutation 用行为变化检验断言敏感度。](../02-test-design-and-tdd.md#行为断言与实现断言) ｜`mutation`

## 03 · fixture 与参数化

- pytest 如何决定 fixture 的 setup 顺序？— [它按测试参数和 fixture 参数做 request-time 名字解析，构建依赖 DAG，而不是按源码顺序执行。](../03-fixtures-and-parametrization.md#fixture-是按名字解析的依赖-dag) ｜`fixture-dag`
- 为什么不能把昂贵 fixture 一律改成 session scope？— [scope 是共享所有权和释放时机，不是单纯的性能档位。](../03-fixtures-and-parametrization.md#session-scope-是所有权决策) ｜`scope`
- fixture setup 中途失败时哪些 cleanup 会运行？— [先前成功 setup 的依赖会按 LIFO 清理；未到 yield 的失败 fixture 不执行 yield 后代码。](../03-fixtures-and-parametrization.md#cachescope-mismatch-与-teardown) ｜`teardown`
- factory fixture 为什么比共享 object fixture 安全？— [共享无状态构造能力，每次调用产生新实体，避免跨测试共享可变领域状态。](../03-fixtures-and-parametrization.md#factory-fixture-与-object-fixture) ｜`factory-fixture`

## 04 · Test doubles 与 seams

- mock、stub、spy、fake 的名称由什么决定？— [由对象在当前测试中承担的角色决定，不由它来自哪个库或是否手写决定。](../04-test-doubles-and-seams.md#meszaros-taxonomy-是角色不是库名称) ｜`test-double`
- 为什么 patch 定义位置可能完全无效？— [被测模块可能早已建立本地绑定，必须 patch 运行时真正 lookup 的名字。](../04-test-doubles-and-seams.md#工单测试-patch-成功worker-却发出真实支付请求) ｜`patch-lookup`
- handwritten fake 何时会说谎？— [当它没有明确保留 commit、rollback、lease、错误与可见性等生产契约时。](../04-test-doubles-and-seams.md#fake-fidelity-是明确的事务契约) ｜`fake-fidelity`
- 什么时候应验证调用次数而非最终状态？— [只有外部副作用或协作协议本身就是风险时才使用 interaction verification。](../04-test-doubles-and-seams.md#state-verification-与-interaction-verification) ｜`interaction`

## 05 · Component 与 API 测试

- ASGITransport 的 component test 到底保留了什么？— [保留真实 HTTP/ASGI 解析、路由、use case 与序列化，但省掉网络进程和外部基础设施。](../05-component-and-api-tests.md#1-核心问题) ｜`component`
- AsyncClient 会自动运行 FastAPI lifespan 吗？— [不会；fixture 必须显式进入 lifespan context，并让 client 在其内部关闭。](../05-component-and-api-tests.md#3-机制深入) ｜`lifespan`
- dependency override 为什么会制造顺序依赖？— [override 是 app 上的可变状态，yield fixture 若不清空会泄漏给后续测试。](../05-component-and-api-tests.md#6-故障工单) ｜`dependency-override`
- 为什么不对所有响应做大型 snapshot？— [稳定公共字段适合精确断言；全量 snapshot 会把无关文案与结构变化变成噪声。](../05-component-and-api-tests.md#4-设计取舍) ｜`api-contract`

## 06 · 数据库整合测试

- 为什么每个测试都要拥有真实 session/transaction？— [只有显式 commit 才发布结果，退出时 rollback/close，才能观察真实事务可见性。](../06-database-integration.md#直觉模型) ｜`transaction-fixture`
- 为什么这里坚持 Testcontainers Postgres 16？— [唯一约束、JSONB、驱动映射、行锁和 SKIP LOCKED 都由 Postgres 自己裁决。](../06-database-integration.md#贯穿-lab) ｜`testcontainers`
- 外层 rollback fixture 为什么可能误导？— [它会隐藏真实 commit，使 fresh UoW 是否可见和跨事务行为产生假阳性。](../06-database-integration.md#设计取舍) ｜`commit-visibility`
- 乐观更新 rowcount 为零应如何解释？— [带 expected version 的 UPDATE 未命中表示观察版本已过期，应报告并发冲突而非普通未找到。](../06-database-integration.md#机制深入) ｜`optimistic-lock`

## 07 · HTTP 与契约测试

- contract test 能证明 provider 当前线上可用吗？— [不能；它证明 consumer 对版本化协议的理解，闭环仍需 provider verification。](../07-http-and-contract-testing.md#直觉模型) ｜`contract`
- ReadTimeout 为什么不能直接映射为支付失败？— [客户端只知道没及时读到响应，远端可能已完成扣款，因此结果必须保持 unknown。](../07-http-and-contract-testing.md#核心问题) ｜`timeout-unknown`
- 为什么 transport fake 优于 monkeypatch client.post？— [它让真实请求构建、header、JSON 编解码与响应映射仍参与测试。](../07-http-and-contract-testing.md#机制深入) ｜`wire-contract`
- 支付重试的幂等键为什么不能按 attempt 生成？— [幂等键必须绑定业务操作，使 unknown outcome 后的查询或重试仍代表同一扣款意图。](../07-http-and-contract-testing.md#故障工单) ｜`idempotency`

## 08 · Async、并发与背景任务

- async test 为何仍可能串行？— [coroutine 只在 await 时协作切换，pytest 默认也逐项执行；async 语法本身不产生竞争。](../08-async-concurrency-background.md#2-直觉模型资源时间竞争者) ｜`event-loop`
- xdist 和 asyncio task concurrency 有何区别？— [xdist 是多进程 test worker；async tasks 是单个 worker 的 event loop 内调度。](../08-async-concurrency-background.md#2-直觉模型资源时间竞争者) ｜`xdist`
- 为什么 CancelledError 不该转成 worker retry？— [取消表示 task 所有权终止，应继续传播；租约到期后由下一 worker 恢复。](../08-async-concurrency-background.md#32-teardown-与取消) ｜`cancellation`
- SKIP LOCKED 能提供 exactly-once 吗？— [不能；它只协调 claim，外部副作用仍需稳定幂等键应对 crash window。](../08-async-concurrency-background.md#34-skip-locked-与数据库事实) ｜`at-least-once`

## 09 · Property 与 stateful testing

- Hypothesis 的 shrinking 带来什么工程价值？— [它把复杂生成失败缩成可解释、可重播并可转成具名 regression 的最小反例。](../09-property-and-stateful-testing.md#机制深入) ｜`shrinking`
- state machine 与普通 property 的差异是什么？— [普通 property 探索输入空间；state machine 让模型与 SUT 沿操作序列逐步演进。](../09-property-and-stateful-testing.md#直觉模型) ｜`state-machine`
- reference model 为什么不能复制 production 条件？— [模型必须更小且独立，否则两边可能共享同一个错误并一起通过。](../09-property-and-stateful-testing.md#设计取舍) ｜`reference-model`
- 何时应保留具名样例而不是只靠生成测试？— [具名测试保存业务语言与已知故事，生成测试负责探索作者未枚举的输入和顺序。](../09-property-and-stateful-testing.md#核心问题) ｜`property`

## 10 · 测试套件可靠性与规模

- flaky test 的第一步是 rerun 吗？— [不是；先分类产品竞态、测试竞态、环境、时钟、依赖或资源耗尽，再最小化复现。](../10-suite-reliability-and-scale.md#核心问题) ｜`flaky`
- xdist 为何会暴露原本稳定的 fixture？— [每个 worker 是独立进程且各有 session fixture，共享端口、路径或外部名字仍会冲突。](../10-suite-reliability-and-scale.md#机制深入) ｜`xdist`
- mutation survivor 是否都要补精确断言？— [先看变更是否有业务语义；等价或纯文案 survivor 应记录理由，不为分数制造脆弱测试。](../10-suite-reliability-and-scale.md#贯穿-lab) ｜`mutation`
- quarantine 至少需要哪些治理字段？— [owner、issue、原因、expiry、退出条件与失败 artifact，不能成为永久 skip。](../10-suite-reliability-and-scale.md#设计取舍) ｜`quarantine`

## 11 · CI、遗留系统与 capstone

- 为什么棕地修复要先写 characterization test？— [先冻结调用方已依赖的可观察行为，才知道后续改变是缺陷修复还是兼容性破坏。](../11-ci-legacy-and-capstone.md#2-直觉模型先冻结边界再移动内部) ｜`characterization`
- 为什么 CI 不只是更大的 pytest？— [它还要固定 interpreter、lockfile、marker、cache、artifact 和基础设施契约。](../11-ci-legacy-and-capstone.md#1-核心问题ci-不是更大的-pytest) ｜`ci-matrix`
- 退款为什么需要两个本地事务？— [先持久化 refund_in_progress，再调用网络，最后以新事务记录终态，避免持锁等 I/O。](../11-ci-legacy-and-capstone.md#3-机制深入一次退款为什么需要两个本地事务) ｜`transaction-boundary`
- hermetic CI 怎样保留失败证据？— [锁定依赖与环境，并把 JUnit、coverage、日志、Hypothesis 反例和容器日志作为 artifact。](../11-ci-legacy-and-capstone.md#7-ci-契约hermeticcache-与-artifact) ｜`hermetic`

返回 [Python 测试工程 track](../README.md)。
