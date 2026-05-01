# 05 事件流

## 目标

事件流用于区分订单命令、库存事实、支付事实、退款事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在取消、支付回调、库存确认、退款和重复消息交错时恢复。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 订单命令 | `OrderCreateRequested`、`OrderCancelRequested` | `order-service` |
| 订单事实 | `OrderCreated`、`OrderPaid`、`OrderCancelled`、`OrderRefundRequired` | `order-service` |
| 库存事实 | `StockReserved`、`StockConfirmed`、`StockReleased` | `inventory-service` |
| 支付事实 | `PaymentSucceeded`、`PaymentFailed`、`PaymentUnknown` | `payment-service` / 支付渠道 |
| 退款事实 | `RefundSubmitted`、`RefundSucceeded`、`RefundFailed`、`RefundUnknown` | `refund-service` / 支付渠道 |
| 账本事实 | `PaymentLedgerPosted`、`RefundLedgerPosted` | `ledger-service` |
| 对账事实 | `CommerceMismatchDetected`、`CommerceRepairRequested` | `reconciliation-service` |
| 修复事实 | `ManualRepairCompleted`、`RepairVerified` | `reconciliation-service` / 运营复核 |

## 下单事件流

```text
OrderCreateRequested
-> OrderCreated
-> StockReserveRequested
-> StockReserved
-> OrderPendingPayment
```

## 支付成功事件流

```text
PaymentSucceeded
-> OrderPaid
-> StockConfirmRequested
-> StockConfirmed
-> PaymentLedgerPosted
-> OrderFulfillable
```

异常分支：

```text
PaymentSucceeded
-> OrderAlreadyCancelled
-> OrderRefundRequired or ManualReviewRequired
```

## 取消事件流

```text
OrderCancelRequested
-> OrderCancelAccepted
-> StockReleaseRequested
-> StockReleased
-> OrderCancelled
```

异常分支：

```text
OrderCancelRequested
-> OrderAlreadyPaid
-> RefundRequired or ManualReviewRequired
```

## 退款事件流

```text
RefundRequired
-> RefundCreated
-> RefundSubmitted
-> RefundSucceeded
-> OrderRefunded
-> RefundLedgerPosted
-> OrderClosed
```

异常分支：

```text
RefundUnknown
-> refund query or callback
-> RefundSucceeded or RefundFailed or ManualReviewRequired
```

## 对账事件流

匹配终止：

```text
CommerceReconciliationStarted
-> order/payment/inventory/refund/ledger matched
-> Matched
```

差错修复：

```text
CommerceMismatchDetected
-> CommerceRepairRequested
-> ManualRepairCompleted
-> RepairVerified
```

## 顺序依赖

- `OrderPendingPayment` 依赖 `StockReserved`。
- `OrderPaid` 依赖可信的 `PaymentSucceeded`。
- `StockConfirmed` 依赖 `OrderPaid`。
- `PaymentLedgerPosted` 依赖 `OrderPaid`。
- `StockReleased` 依赖合法取消裁决。
- `RefundSubmitted` 依赖 `RefundRequired`。
- `OrderRefunded` 依赖可信的 `RefundSucceeded`。
- `RefundLedgerPosted` 依赖 `OrderRefunded`。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、库存流水、支付渠道事实、退款渠道事实、会计分录和对账记录，不能用 consumer offset 证明订单、库存、支付或退款已经完成。
