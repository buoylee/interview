# 07 HTTP 与契约测试：把未知结果当作一等状态

## 核心问题

支付调用跨越进程与网络。一次 `ReadTimeout` 只说明客户端没有及时读到响应，不能说明 provider 没扣款。这里的测试目标是证明三件事：我们发送的 wire contract 正确；已知响应能稳定映射到领域语义；结果未知时不会把订单错误地标成失败并用新幂等键重试。

## 直觉模型

HTTP adapter 是反腐层：外侧拥有 URL、header、JSON、状态码与 timeout，内侧只暴露 `PaymentResult`、`PaymentDeclined` 和 `PaymentUncertain`。transport fake 在 HTTP 边界接收真实序列化请求，比 monkeypatch `client.post()` 更能发现路径、header、Decimal 或 UUID 编码错误。

契约测试不是“provider 可用性测试”。它证明 consumer 当前理解的协议；若没有 provider verification 或双方共享的版本化 schema，它无法证明部署中的 provider 仍遵守协议。

## 机制深入

HTTPX 的 `ASGITransport` 在进程内执行可控 ASGI provider，却仍经过 request build、header、JSON encode/decode 和 response mapping。`MockTransport` 适合注入网络层异常与无法由正常路由表达的响应。直接 monkeypatch adapter 方法会跳过这些风险，通常只适合验证上层 orchestration 是否调用某个 port。

timeout 必须按阶段分类：connect timeout 通常尚未送达 provider；write、read、pool timeout 的事实不同。即使异常类型提供线索，涉及扣款时也应把无法证明结果的情况归为 unknown outcome，使用同一个 idempotency key 查询或重试，而不是推断失败。

请求 schema 由 consumer 负责序列化证据，响应 schema 由 adapter 负责防御性解析。200 仍可能缺字段、类型错误、返回半截 JSON 或业务状态不一致；因此“200-only mock”只能证明快乐路径分支存在，不能证明边界稳健。

## 设计取舍

- 手写 ASGI fake 快、确定、适合本仓库；代价是它可能和真实 provider 一起漂移。
- consumer-driven contract 能发布 consumer 期望，但必须由 provider CI 验证才形成闭环。
- OpenAPI schema diff 能发现删除字段、收紧类型等结构变化，却不能证明幂等、扣款时机等行为语义。
- retry eligibility 应由操作语义与失败阶段决定；支付写操作必须携带稳定幂等键。
- 测试失败输出、HTTP 日志和 snapshot 必须脱敏 Authorization、cookie、API key 与支付资料。

## 贯穿 lab

`PaymentGateway` 把 charge/refund 固定成领域 port。`ProcessPayment` 在调用 provider 前先提交 `payment_in_progress`，provider 返回 approved/declined 后再开新 UoW 提交终态。timeout 则保留中间态供 reconciliation；重放同一订单继续使用 `charge:{order_id}`。

contract suite 使用可控 provider 验证 UUID、字符串 Decimal、大写币种及 `Idempotency-Key`，并覆盖 approved、402 declined、malformed 200、5xx 和 timeout。refund 在本章固定同一接口形状，完整业务流程留给 capstone。

```bash
cd python-testing/lab
uv run pytest tests/component/test_process_payment.py tests/contract/test_payment_contract.py -q
```

## 故障工单

**症状：** `timeout 后自动重试导致重复扣款`。

先保存 timeout 类型、请求是否开始发送、provider 是否有按幂等键查询的能力，以及两次请求的 header。不要先增加 retry。最小复现让 transport 第一次在 provider 接收请求后抛 `ReadTimeout`，第二次返回成功；若代码生成新 key，fake provider 会观察到两次独立扣款意图。

修复是把幂等键绑定到业务操作而非尝试次数，并将 unknown outcome 留在 `payment_in_progress`。最终 regression oracle 不是“调用了两次”，而是两次请求都满足；以下断言逐字摘自 [`lab/tests/component/test_process_payment.py`](lab/tests/component/test_process_payment.py)：

```python
assert gateway.charge_calls[0]["idempotency_key"] == f"charge:{order.id}"
```

## Java / Go 对照

Java 常用 WireMock/MockWebServer，Go 常用 `httptest.Server` 或自定义 `RoundTripper`；它们对应 ASGITransport 与 MockTransport 的不同层次。无论语言，mock service method 都不能替代 wire-level contract，OpenAPI 兼容也不能替代 unknown-outcome 与幂等行为测试。

## 验收与面试卡

- 快速 suite 不访问公网或 Docker，且覆盖 approved、declined、malformed、5xx、timeout。
- timeout 后订单保持 `payment_in_progress`，只发生第一次状态提交。
- approved/declined 各有两次事务提交，已支付重放不调用 provider。
- charge/refund 都使用明确的稳定幂等 header 与字符串金额。

一句话：契约测试验证边界翻译，状态机测试验证 unknown outcome；只有二者同时成立，支付重试才有可信证据。
