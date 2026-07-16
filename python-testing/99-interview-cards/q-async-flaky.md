# 为什么 async 测试会 flaky，event loop、task ownership 和 xdist 有何不同？

## 30 秒回答

async flaky 通常是所有权或 happens-before 没写清：task 谁创建、谁 join/cancel，client/session 属于哪个 loop，业务时间来自哪里，竞争者是否真的同时到达临界区。event loop 调度同一进程里的 coroutine；xdist 启动独立 worker 进程；数据库并发还要求独立 transaction/connection。三者不能互相替代。

## 机制

strict asyncio mode 要求 async test/fixture 显式声明，使 loop ownership 可见。测试若创建 task，正常路径要 await，异常或 teardown 要 cancel 后再次 await；`CancelledError` 不能被通用业务错误捕获。`sleep` 不建立可靠同步，应使用 Event/barrier 表达阶段、注入 clock 表达业务时间、deadline 只为等待设置失败上界。xdist 下每个 worker 有独立 interpreter 和 session fixtures，但仍可能争用固定端口、文件名和数据库 namespace。

## lab 生产案例

[`PaymentWorker`](../lab/src/order_service/adapters/outbox.py) 先短事务 claim/commit，再调用支付，最后用新 UoW mark done 或 backoff；取消会传播，已提交 lease 等到期恢复。component test 用 `ManualClock` 跨过 30 秒 lease，不 sleep；integration test 用两个真实 session 与 barrier 验证 claim 不重复；E2E 再证明 worker、HTTP adapter 与 Postgres 的 wiring。

## 取舍／反例

把 loop scope 扩为 session 可能减少 setup，却扩大 task、client 与 connection 泄漏的生命周期。连续重复运行一百次只能估计概率，不能证明竞态被触发；明确 barrier 和独立事务才是可重复证据。SKIP LOCKED 也只处理 claim 竞争，不提供外部副作用 exactly-once，仍需稳定 provider idempotency key。

## 追问

- pytest-asyncio auto 与 strict 对大型 plugin 环境有什么取舍？
- task 被取消在 provider 成功、mark_done 前会发生什么？
- 什么 artifact 能区分产品竞态与测试资源泄漏？
- xdist 通过为何不能证明两个数据库 transaction 的锁行为？

## 证据链接

- 章节：[资源、时间与竞争者](../08-async-concurrency-background.md#2-直觉模型资源时间竞争者)、[teardown 与取消](../08-async-concurrency-background.md#32-teardown-与取消)、[xdist 进程模型](../10-suite-reliability-and-scale.md#机制深入)
- Production：[`outbox.py`](../lab/src/order_service/adapters/outbox.py)、[`process_payment.py`](../lab/src/order_service/application/process_payment.py)
- Tests：[`test_payment_worker.py`](../lab/tests/component/test_payment_worker.py)、[`test_outbox.py`](../lab/tests/integration/test_outbox.py)、[`test_order_flow.py`](../lab/tests/e2e/test_order_flow.py)

[返回速答索引](README.md)
