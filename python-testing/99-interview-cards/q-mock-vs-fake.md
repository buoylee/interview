# Mock、stub、fake、spy：该选哪一种，为什么？

## 30 秒回答

先问风险是最终状态还是外部交互。stub 提供预设输入，spy 记录发生过的调用，mock 预先约束交互，fake 则运行一个简化但可工作的状态模型。订单与 outbox 的原子发布适合有事务语义的 fake 加 state verification；支付请求的稳定幂等 header 适合 interaction/contract evidence。名称是当前角色，不是类或库的永久类型。

## 机制

应用拥有 consumer-defined ports，并通过构造器注入 clock、ID、UoW 和 payment gateway。`spec_set`/autospec 能约束属性与签名，`AsyncMock` 能证明 await，但都不能执行远端协议或数据库语义。patch 必须命中被测代码实际 lookup 的绑定；若模块使用 `from x import y`，改 `x.y` 不会替换已经绑定的本地名字。

## lab 生产案例

[`MemoryUnitOfWork`](../lab/src/order_service/adapters/memory.py) 用 copy-on-enter、commit 发布、rollback 隔离与 outbox lease 保留应用级事务契约，因此 component tests 可断言真实状态。支付 port 由 [`payment.py`](../lab/src/order_service/ports/payment.py) 定义，HTTP adapter 的路径、header、JSON 与 timeout 则交给可控 ASGI/MockTransport 的 contract tests，而不是 mock adapter 自己。

## 取舍／反例

mock SQLAlchemy 的 `execute().scalars().first()` 会锁死 ORM 调用形状，却仍不证明 constraint、transaction 或 lock。fake 若用共享 dict 覆盖重复键，也可能替 production 提供不存在的原子性。真实依赖 fidelity 最高但更慢、更难隔离；选择不是“尽量真”或“尽量 mock”，而是让拥有语义的组件作证，并用更窄的 double 控制其余变量。

## 追问

- 同一个对象何时既是 stub 又是 spy？
- 哪些 interaction 属于公共协议，哪些只是内部实现？
- 如何证明 handwritten fake 与真实 adapter 没有语义漂移？
- patch lookup site 正确后，为什么仍需要 contract test？

## 证据链接

- 章节：[double taxonomy](../04-test-doubles-and-seams.md#meszaros-taxonomy-是角色不是库名称)、[state 与 interaction](../04-test-doubles-and-seams.md#state-verification-与-interaction-verification)、[fake fidelity](../04-test-doubles-and-seams.md#fake-fidelity-是明确的事务契约)
- Production：[`uow.py`](../lab/src/order_service/ports/uow.py)、[`memory.py`](../lab/src/order_service/adapters/memory.py)、[`payment_http.py`](../lab/src/order_service/adapters/payment_http.py)
- Tests：[`test_memory_adapter.py`](../lab/tests/unit/test_memory_adapter.py)、[`test_create_order.py`](../lab/tests/component/test_create_order.py)、[`test_payment_contract.py`](../lab/tests/contract/test_payment_contract.py)

[返回速答索引](README.md)
