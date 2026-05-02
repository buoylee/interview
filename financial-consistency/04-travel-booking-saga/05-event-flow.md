# 05 事件流

## 目标

事件流用于区分报价事实、组合订单事实、供应商事实、付款事实、退款事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在供应商超时、核心项部分成功、附加项失败、扣款退款和人工修复交错时恢复。

本文只描述已经发生的业务事实如何传播。命令可以被拒绝、重试或超时，事件不能被当作待执行动作；事件只能表示事实来源已经把结果落到了自己的本地记录中。

## 命令和事件

| 概念 | 命名示例 | 含义 | 处理要求 |
| --- | --- | --- | --- |
| 命令 | `QuoteLockRequested`、`BookingCreateRequested`、`FlightTicketRequested`、`SubmitRefund` | 请求某个 owner 尝试执行动作 | 可以失败、超时、重试；不能作为事实依据 |
| 事件 | `QuoteLocked`、`BookingCreated`、`FlightTicketed`、`RefundSubmitted`、`RefundSucceeded` | owner 已经确认并持久化的事实 | 只能追加发布；消费者按事实更新自己的投影或触发后续命令 |

命令由编排器或业务服务发出，事件由事实 owner 发布。比如 `FlightTicketRequested` 是对供应商适配层的命令，`FlightTicketed` 才是机票已出票的供应商事实；`BookingCreateRequested` 是创建组合订单的命令，`BookingCreated` 才是 `booking-service` 本地订单已经存在的事实；`SubmitRefund` 是提交退款的命令，`RefundSubmitted` 才是 `refund-service` 已经持久化退款请求和渠道请求号的事实。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 报价事实 | `QuoteSelected`、`QuoteLocked`、`QuoteExpired`、`PriceChanged` | `booking-service` / supplier |
| 组合订单事实 | `BookingCreated`、`CoreBookingConfirmed`、`AddonFailed`、`BookingPartiallyConfirmed` | `booking-service` |
| 供应商事实 | `FlightTicketed`、`HotelConfirmed`、`CarBooked`、`InsuranceIssued`、`SupplierUnknown` | `supplier-adapter-service` / supplier |
| 付款事实 | `PaymentAuthorized`、`PaymentCaptured`、`AuthorizationVoided`、`PaymentUnknown` | `payment-service` / payment channel |
| 退款事实 | `RefundRequired`、`RefundSubmitted`、`RefundSucceeded`、`RefundUnknown` | `refund-service` / payment channel |
| 账本事实 | `PaymentLedgerPosted`、`RefundLedgerPosted`、`PenaltyPosted`、`AdjustmentPosted` | `ledger-service` |
| 对账事实 | `TravelMismatchDetected`、`TravelRepairRequested` | `reconciliation-service` |
| 人工事实 | `ManualReviewRequested`、`UserDecisionRecorded`、`ManualRepairCompleted` | `manual-review-service` |

## Outbox 与本地事务

事实 owner 必须在同一个本地事务中写入业务表和 Outbox 记录，然后由 Outbox publisher 异步投递到 broker。这样可以保证事件发布与事实落库一致：

- `booking-service` 创建订单时，在同一事务中写入 booking 聚合和 `BookingCreated` Outbox 记录。
- `supplier-adapter-service` 确认出票或酒店成功时，在同一事务中写入 supplier result 和 `FlightTicketed` / `HotelConfirmed` Outbox 记录。
- `payment-service` 完成扣款时，在同一事务中写入 payment transaction 和 `PaymentCaptured` Outbox 记录。
- `refund-service` 确认退款成功时，在同一事务中写入 refund transaction 和 `RefundSucceeded` Outbox 记录。
- `reconciliation-service` 发现差错时，在同一事务中写入 mismatch case 和 `TravelMismatchDetected` Outbox 记录。

Outbox 只能证明某个服务已经提交了本地事实，不能证明下游消费者已经处理完成。下游完成情况必须由下游自己的事实事件表达，例如 `PaymentLedgerPosted` 或 `ManualRepairCompleted`。

## 报价和下单事件流

```text
TravelSearchRequested
-> QuoteSelected
-> QuoteLockRequested
-> QuoteLocked
-> BookingCreateRequested
-> BookingCreated
```

异常分支：

```text
QuoteLockRequested
-> QuoteExpired or PriceChanged
-> UserDecisionRequired or BookingCancelled
```

`QuoteLocked` 表示报价、库存和价格在锁定窗口内可用于下单。`BookingCreated` 依赖 `QuoteLocked`，或依赖用户对 `PriceChanged` 后新报价的明确确认；不能用用户曾经选择过报价来创建订单。

## 核心项预订事件流

```text
PaymentAuthorized
-> CoreBookingStarted
-> FlightTicketRequested
-> FlightTicketed
-> HotelConfirmRequested
-> HotelConfirmed
-> CoreBookingConfirmed
-> PaymentCaptured
-> PaymentLedgerPosted
```

异常分支：

```text
FlightTicketed
-> HotelConfirmFailed
-> CompensationRequired or ManualReviewRequested
```

机票和酒店是核心项。`FlightTicketed` 和 `HotelConfirmed` 都成功后，`booking-service` 才能发布 `CoreBookingConfirmed`。`PaymentCaptured` 依赖合法 capture 条件，通常包括核心项确认、授权仍有效、金额未变化以及幂等键未被重复使用；不能只因为收到单个供应商成功回调就扣款。

如果机票已出票但酒店失败，系统不能简单取消整个流程。机票可能存在退改规则、罚金或人工审批要求，因此需要进入补偿、退款或人工处理链路。

## 附加项事件流

```text
CoreBookingConfirmed
-> AddonBookingStarted
-> CarBookingRequested
-> CarBooked or CarBookingFailed
-> InsuranceApplyRequested
-> InsuranceIssued or InsuranceFailed
-> BookingConfirmed or BookingConfirmedWithAddonFailures
```

核心项和附加项的事件语义不同：

- 核心项失败会影响主订单是否可确认，通常触发补偿、退款或 `ManualReviewRequested`。
- 附加项失败不一定推翻主订单。`CarBooked` 和 `InsuranceIssued` 是附加服务成功事实；如果租车或保险失败，系统可以发布 `BookingConfirmedWithAddonFailures`，保留已成功的机票和酒店。
- 附加项的退款或补差只处理对应附加服务金额，不能误伤核心项账本。

## 补偿事件流

```text
CompensationRequired
-> SupplierCancelRequested
-> RefundRequired
-> SubmitRefund
-> RefundSubmitted
-> RefundSucceeded
-> RefundLedgerPosted
-> CompensationCompleted
```

异常分支：

```text
RefundUnknown
-> refund query or callback
-> RefundSucceeded or RefundFailed or ManualReviewRequested
```

`RefundSucceeded` 必须来自退款渠道或 `refund-service` 对渠道结果的可信查询，不能由 broker 投递成功、调用返回超时或用户投诉直接推导。`RefundLedgerPosted` 依赖 `RefundSucceeded`，账本只记录可信退款事实。

## 人工处理事件流

```text
ManualReviewRequested
-> UserDecisionRecorded
-> ManualRepairRequested
-> ManualRepairCompleted
-> RepairVerified
```

`ManualReviewRequested` 表示自动流程无法安全推进，例如供应商状态未知、核心项部分成功、退款长期未知、账本差异超过阈值或规则需要人工审批。人工处理服务记录处理人、原因、证据、修复动作和审批结果，再发布 `ManualRepairCompleted` 供对账和订单投影继续验证。

## 对账事件流

匹配终止：

```text
TravelReconciliationStarted
-> booking/supplier/payment/refund/ledger matched
-> Matched
```

差错修复：

```text
TravelMismatchDetected
-> TravelRepairRequested
-> ManualRepairCompleted or AutoRepairCompleted
-> RepairVerified
```

`TravelMismatchDetected` 是对账服务发现订单、供应商、支付、退款或账本之间存在不一致后的事实。它不直接修改业务状态，而是打开修复 case，并通过 `TravelRepairRequested` 触发自动修复或人工处理。修复完成后必须再次对账，只有 `RepairVerified` 后才能关闭 case。

## 事件消费者幂等

消费者必须按事件 owner、事件 ID 和业务幂等键处理重复投递：

- 投影消费者用 `event_id` 或 `(event_type, aggregate_id, version)` 去重，重复事件只确认消费，不重复改状态。
- 命令触发型消费者用业务幂等键调用下游，例如 `booking_id + supplier_item_id`、`booking_id + payment_attempt_id`、`refund_id`。
- 账本消费者使用唯一分录键，例如 `PaymentCaptured.payment_id` 或 `RefundSucceeded.refund_id`，保证不会重复记账。
- 人工和对账消费者保留 case ID，重复的 `ManualReviewRequested` 或 `TravelMismatchDetected` 只能补充证据，不能创建多个互相冲突的修复单。

幂等状态要落在消费者自己的数据库中，不能依赖 broker offset。offset 只能表示消息读取位置，不能表示业务动作是否已经提交。

## 顺序依赖

- `BookingCreated` 依赖 `QuoteLocked` 或用户确认后的新报价。
- `CoreBookingConfirmed` 依赖机票和酒店核心项成功。
- `PaymentCaptured` 依赖合法 capture 条件，不能只依赖供应商单个回调。
- `BookingConfirmedWithAddonFailures` 依赖核心成功和附加项失败事实。
- `RefundSubmitted` 依赖 `RefundRequired`，以及 `SubmitRefund` 命令被 `refund-service` 接收并持久化。
- `RefundLedgerPosted` 依赖可信的 `RefundSucceeded`。
- `PenaltyPosted` 和 `AdjustmentPosted` 依赖供应商规则、用户确认或人工审批。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、供应商事实、支付渠道事实、退款渠道事实、会计分录、人工审批和对账记录，不能用 consumer offset 证明供应商确认、付款、退款或补偿已经完成。

如果 broker 重放、乱序或重复投递，消费者应依据本地事实版本和幂等表决定是否处理。broker 可用于传播 `QuoteLocked`、`BookingCreated`、`FlightTicketed`、`HotelConfirmed`、`PaymentCaptured`、`CarBooked`、`InsuranceIssued`、`RefundSucceeded`、`ManualReviewRequested` 和 `TravelMismatchDetected`，但这些事件的真实性只来自各自 owner 的持久化记录。
