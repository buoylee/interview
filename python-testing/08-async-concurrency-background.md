# Async、并发与背景任务：测试调度，而不测试运气

## 1. 核心问题

异步代码最危险的缺陷通常不在返回值，而在所有权与时间：谁创建 task、谁等待它、取消后谁清理资源、失败消息何时可重试，以及两个 worker 是否会处理同一行。测试的目标不是“跑过一次”，而是让这些调度契约可控、可重复地失败。

本章的订单服务采用 outbox worker。它先在短事务中 claim 消息并提交租约，再调用支付用例，最后用另一个短事务标记成功或安排重试。这是 at-least-once，而不是 exactly-once：进程可能在支付成功后、`mark_done` 前崩溃，因此下游支付必须接受稳定的 idempotency key。

## 2. 直觉模型：资源、时间、竞争者

审查 async 测试时依次问三件事：

1. **资源所有权**：test、fixture、应用 lifespan 与 background task 各自创建和关闭什么？
2. **时间来源**：业务时间来自可注入 clock，还是测试真的在等墙上时间？
3. **竞争关系**：测试是否真的建立两个独立 transaction/session，还是只在一个 event loop 中顺序调用两次？

`async def` 不等于并行。pytest 默认逐个执行 test item；单个测试里的 coroutine 也只会在遇到 await 时协作切换。需要并发竞争时要显式创建 task；需要进程级并行时才使用 xdist。两者验证的风险不同。

## 3. 机制深入

### 3.1 pytest-asyncio 的 strict 与 auto

本 lab 使用 `asyncio_mode = "strict"`。async 测试必须显式标记，async fixture 必须使用 `pytest_asyncio.fixture`；这能尽早暴露由错误插件或 fixture 声明造成的隐式行为。`auto` 模式迁移较轻松，但在同时安装 AnyIO、pytest-asyncio 或自定义 loop 插件时，所有权更难判断。

pytest collector 有 session、package、module、class、function 层级，event loop scope 也属于测试契约。session-scope async engine 若跨多个 function-scope loop 使用，可能出现“attached to a different loop”。因此本 lab 的 Postgres engine 与 Docker integration 测试显式共享 session loop，而普通 component test 保持 function scope。扩大 loop scope 不是性能开关；它扩大了可泄漏状态的生命周期。

### 3.2 teardown 与取消

async fixture 应当只有一个清晰的 `yield` 所有权边界，并在 `finally` 中关闭 client、session、engine 或 task group。测试取消 coroutine 时，`CancelledError` 必须继续传播。worker 只捕获 `Exception`，不捕获 `BaseException`，因此不会把取消误判为业务失败并安排重试。

取消发生在 claim 已提交、业务处理尚未完成时，消息会保留 `claimed_at`。这是租约，不是永久锁；30 秒后另一个 worker 可恢复。测试通过 `ManualClock.advance` 跨过边界，不调用 sleep，也不会让 suite 真实等待 31 秒。

泄漏 task 的典型信号包括测试结束后的 pending-task warning、偶发的 connection closed，以及下一个测试收到前一个测试的事件。测试若调用 `create_task`，就必须 await 正常结束或在 teardown 中 cancel 后再次 await，确认取消完成。

### 3.3 deadline 不是 sleep

`sleep(0.1)` 既不是同步原语，也不是可靠断言：慢 CI 可能尚未到达目标状态，快机器则浪费时间。正确选择是：

- 用 `Event` 表示“已经到达某阶段”；
- 用 barrier 同时释放竞争者；
- 用注入 clock 表示业务时间；
- 用 timeout/deadline 给等待设失败上界，而不是用 sleep 猜完成时间。

本章的并发测试先让两个 task 分别设置 ready event，主测试观察双方 ready 后再设置 release event。这样被验证的是同一窗口内两个独立 UoW 的竞争，而不是 scheduler 碰巧交错。

### 3.4 SKIP LOCKED 与数据库事实

`SELECT ... FOR UPDATE SKIP LOCKED` 的价值必须用真实 Postgres 证明。SQLite、memory fake 或 mock 无法忠实模拟行锁、statement snapshot 与 transaction visibility。claim transaction 应尽量短：选行、更新 `claimed_at`、commit；绝不能在持锁期间调用外部支付 API。

测试至少需要证明：

- 两个 session 各 claim 一条时 ID 不重复；
- claim 已提交且 `claimed_at` 实际落库；
- 30 秒内不可重领，租约到期后可恢复；
- `limit`、due time、done 状态与排序规则仍成立。

`SKIP LOCKED` 解决的是 claim 阶段的重复选择，不解决外部副作用 exactly-once。若 worker 在支付成功后崩溃，消息会再次执行；本 lab 的 `ProcessPayment` 使用 `charge:{order_id}` 作为稳定 idempotency key，把重复执行风险交给可验证的支付契约。

## 4. 设计取舍

worker 每批先统一 claim，再逐条处理，吞吐量高且锁很短；代价是进程退出时整批消息都要等 lease 到期。逐条 claim 缩小恢复窗口，但增加 transaction 开销。生产系统还应考虑 heartbeat、最大 attempts、dead-letter 与可观测性；这些不是用更长 lease 替代的。

retry 采用 `min(2 ** attempts, 60)` 秒。确定性 backoff 便于教学与测试，真实系统通常加 jitter 避免惊群。jitter 应由可注入 random source 产生，否则测试只能断言范围，难以重放失败 seed。

AsyncMock 适合验证“是否 await、参数是什么、抛出何种协议异常”，但不能证明真实 httpx transport、SQLAlchemy transaction 或 Postgres locking。越靠近协议与并发语义，越应使用可控 fake server 或真实基础设施。

## 5. 贯穿 lab

`PaymentWorker.run_once(limit=10)` 的生命周期是：

1. 拒绝非正 limit，避免为无效输入打开 UoW；
2. 读取 clock，在第一个 UoW claim 并 commit；
3. 对每条消息 await `ProcessPayment.execute`；
4. 成功时在新 UoW `mark_done`；
5. 普通异常时增加 attempts，清空 claim，并用确定性 backoff 设置 `available_at`；
6. 取消时不捕获，让 task 结束，靠租约恢复。

component tests 用 memory adapter 精确验证状态与时间边界；integration tests 用两个真实 SQLAlchemy session 验证锁；E2E 从 FastAPI `POST /orders` 开始，经 outbox、HTTP payment adapter 和 fake provider，最后从 fresh SQL UoW 读到 `PAID` 与 `pay-001`。

## 6. 故障工单

**症状**：CI 偶发出现同一订单被支付两次。

**证据**：两个 worker log 有相同 message ID，且 claim 时间重叠；provider 收到相同 idempotency key。

**假设**：claim 查询缺少行锁，或锁在外部调用前未提交。

**实验**：用两个独立 session，在 event barrier 后同时 `claim_batch(limit=1)`；断言 ID 不重复并查询持久化的 `claimed_at`。再锁住排序第一行，确认另一个 transaction 能跳过它，而不是阻塞。

**修复**：在短 transaction 中使用 `FOR UPDATE SKIP LOCKED`，更新 lease 后 commit；外部调用移到 transaction 外。

**regression test**：保留并发 integration test 与完整 E2E，同时验证 provider idempotency key。不要把“重复跑 100 次没失败”当作竞态证明。

## 7. Java / Go 对照

Java 的 `CompletableFuture`、virtual thread 或 Reactor，Go 的 goroutine/channel，与 asyncio 的语法不同，但所有权问题相同：启动的工作必须有 join/cancel 边界。Go 的 `t.Parallel()` 是测试级并行；pytest-asyncio 不会因为测试是 async 就并行 test item。Java Testcontainers 与本 lab 一样适合验证数据库锁，但 transaction 必须来自两个真正独立 connection。

asyncio 更深入的 scheduler、TaskGroup、GIL 与 structured concurrency 材料见 [`python-concurrency/`](../python-concurrency/)。本章只展开会改变测试边界的部分。

## 8. 验收与面试卡

```bash
cd python-testing/lab
uv run pytest tests/component/test_payment_worker.py -q
uv run pytest tests/integration/test_outbox.py -m docker -q
uv run pytest tests/e2e/test_order_flow.py -m docker -q
uv run pytest -q
```

一句话回答：“我把业务时间注入、用 Event 建立 happens-before、用两个真实 transaction 验证 `SKIP LOCKED`，并明确 worker 是依赖幂等下游的 at-least-once。”

深答时继续说明：为何 cancellation 不应被普通失败处理吞掉；为何 claim 与外部 API 必须拆成短事务；为何 xdist、async task concurrency 与数据库并发是三种不同的测试维度；以及系统在哪个 crash window 会重复执行。
