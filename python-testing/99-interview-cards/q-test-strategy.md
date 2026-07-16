# 如何为支付工作流选择测试边界？

## 30 秒回答

我不会从“unit 还是 E2E”开始，而会先列损失：金额或状态错误、重复扣款、timeout 后误判失败、数据库与 outbox 不原子、wire contract 漂移。为每项风险找能裁决它的 oracle，再选择保留该风险机制的最小边界：领域状态用 unit/property，应用决策用 component，Postgres 原子性用 integration，HTTP 翻译用 contract，少量 E2E 只验证关键 wiring。

## 机制

边界由参与产生结果的真实机制定义，不由目录或框架定义。选择时先淘汰 fidelity 不足的方案，再比较反馈速度、隔离、诊断性和维护成本。同一高风险不变量可以在不同 seam 各证明一次，但每层应有不同责任：component 证明 unknown outcome 决策，contract 证明 timeout/response mapping，E2E 证明真实装配没有绕开这些政策。

## lab 生产案例

[`ProcessPayment`](../lab/src/order_service/application/process_payment.py) 在调用 provider 前提交 `PAYMENT_IN_PROGRESS`，再用新 UoW 写已知终态；timeout 保留 unknown 状态。HTTP adapter 用稳定 `Idempotency-Key` 翻译 wire contract；Postgres adapter 则负责事务、版本和 outbox 的真实语义。最终订单 E2E 从 FastAPI 入口穿过 Postgres、worker 与可控 provider，但不拿它穷举所有错误响应。

## 取舍／反例

把 provider mock 成固定 approved 的 E2E 很快，却不会发现 Decimal/UUID 序列化、timeout 分类或 header 错误；把每种金额都跑完整 E2E 又会放大成本和 flaky。反过来，只在 fake repository 验证幂等也不足，因为并发唯一性由 Postgres constraint 裁决。边界升级必须能指出新增了哪项关键机制。

## 追问

- 若 provider 不参与 consumer contract verification，你会怎样量化剩余漂移风险？
- 哪个 crash window 仍可能重复扣款，系统靠什么恢复？
- 什么证据能证明 E2E 数量应增加，而不是把分支下沉？
- timeout、5xx 和 declined 的业务状态为何不能统一？

## 证据链接

- 章节：[风险与 oracle](../00-testing-strategy.md#核心问题)、[HTTP unknown outcome](../07-http-and-contract-testing.md#核心问题)、[capstone 事务边界](../11-ci-legacy-and-capstone.md#3-机制深入一次退款为什么需要两个本地事务)
- Production：[`process_payment.py`](../lab/src/order_service/application/process_payment.py)、[`payment_http.py`](../lab/src/order_service/adapters/payment_http.py)、[`sqlalchemy.py`](../lab/src/order_service/adapters/sqlalchemy.py)
- Tests：[`test_process_payment.py`](../lab/tests/component/test_process_payment.py)、[`test_payment_contract.py`](../lab/tests/contract/test_payment_contract.py)、[`test_order_flow.py`](../lab/tests/e2e/test_order_flow.py)

[返回速答索引](README.md)
