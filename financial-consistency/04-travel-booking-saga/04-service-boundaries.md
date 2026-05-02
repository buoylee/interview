# 04 服务边界

## 目标

本文件定义旅行组合预订中的服务职责。核心原则是：组合订单事实、供应商事实、支付事实、退款事实、账本事实、对账事实和人工决策事实分别由明确边界拥有，不能让一个服务偷偷完成所有事情。

任何跨服务协作都必须通过幂等命令、查询接口或事件完成。一个服务不能直接修改另一个服务的数据库，也不能把消息投递状态当成业务事实。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `booking-service` | 组合订单、子订单、组合状态机、用户决策、幂等键 | 不直接确认供应商事实，不直接扣款或退款 |
| `supplier-adapter-service` | 供应商请求、回调、查询、供应商请求号、供应商事实 | 不决定资金入账，不直接改账本 |
| `payment-service` | 预授权、capture、void/release、支付单、支付渠道事实 | 不决定供应商是否确认成功 |
| `refund-service` | 退款单、部分退款、退款查询、退款渠道事实 | 不删除原支付事实，不直接改供应商订单 |
| `ledger-service` | 支付、退款、罚金、补差、冲正和差错修复分录 | 不覆盖历史分录，不替代订单或供应商服务 |
| `reconciliation-service` | 本地订单/供应商/支付/退款/账本对账、差错分类、修复工单 | 不直接修改订单、供应商、支付、退款或分录 |
| `manual-review-service` | 用户决策、运营审批、maker-checker、人工修复审计 | 不绕过状态机，不直接删除历史事实 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 服务明细

### `booking-service`

- 拥有的数据：组合订单、子订单、行程项、订单状态机、用户选择、取消意图、订单级幂等键、命令执行记录。
- 可执行命令：`CreateBooking`、`StartSupplierBooking`、`RecordSupplierResult`、`ConfirmCoreTrip`、`MarkAddonFailed`、`RequestCancellation`、`RequestCompensation`、`RecordUserDecision`。
- 可发布事件：`BookingCreated`、`BookingStateChanged`、`CoreTripConfirmed`、`AddonBookingRequested`、`AddonFailed`、`CompensationRequested`、`ManualReviewRequested`。
- 不能做什么：不能直接写供应商、支付、退款、账本或人工审核数据库；不能本地伪造供应商确认；不能直接执行扣款、退款或账本分录；不能用单一总状态覆盖子订单事实。

### `supplier-adapter-service`

- 拥有的数据：供应商请求、供应商请求号、供应商回调、供应商查询结果、供应商订单状态、供应商错误码、供应商幂等映射。
- 可执行命令：`ReserveSupplierItem`、`CancelSupplierItem`、`QuerySupplierStatus`、`RecordSupplierCallback`、`NormalizeSupplierResult`。
- 可发布事件：`SupplierRequestSent`、`SupplierConfirmed`、`SupplierRejected`、`SupplierPending`、`SupplierCancelled`、`SupplierCallbackReceived`。
- 不能做什么：不能决定组合订单最终状态；不能直接扣款、退款或入账；不能改写 `booking-service` 的订单表；不能把超时直接等同于失败，必须保留 pending 或查询状态。

### `payment-service`

- 拥有的数据：预授权单、扣款单、void/release 记录、支付渠道请求和响应、支付渠道交易号、支付幂等键。
- 可执行命令：`AuthorizePayment`、`CapturePayment`、`VoidAuthorization`、`ReleaseAuthorization`、`QueryPaymentStatus`。
- 可发布事件：`PaymentAuthorized`、`PaymentCaptured`、`PaymentAuthorizationVoided`、`PaymentAuthorizationReleased`、`PaymentFailed`、`PaymentStatusUpdated`。
- 不能做什么：不能确认供应商是否预订成功；不能直接创建退款事实；不能直接写账本分录；不能删除失败或被撤销的支付事实。

### `refund-service`

- 拥有的数据：退款单、部分退款明细、退款渠道请求和响应、退款渠道交易号、退款状态、退款幂等键。
- 可执行命令：`CreateRefund`、`SubmitRefund`、`QueryRefundStatus`、`RecordPartialRefund`、`RetryRefund`。
- 可发布事件：`RefundCreated`、`RefundSubmitted`、`RefundSucceeded`、`RefundFailed`、`PartialRefundRecorded`、`RefundStatusUpdated`。
- 不能做什么：不能删除或覆盖原支付事实；不能直接取消供应商订单；不能直接改订单状态机；不能直接写账本，退款成功后应通过事件或命令驱动 `ledger-service` 追加分录。

### `ledger-service`

- 拥有的数据：支付分录、退款分录、罚金分录、补差分录、冲正分录、差错修复分录、账户余额投影、分录幂等键。
- 可执行命令：`PostPaymentEntry`、`PostRefundEntry`、`PostPenaltyEntry`、`PostAdjustmentEntry`、`ReverseEntry`、`PostRepairEntry`。
- 可发布事件：`LedgerEntryPosted`、`LedgerEntryReversed`、`LedgerRepairPosted`、`LedgerBalanceChanged`。
- 不能做什么：不能覆盖或物理删除历史分录；不能替代订单、供应商、支付或退款服务作事实判断；不能直接读取并修改其他服务数据库；不能把账本投影当成供应商或渠道原始事实。

### `reconciliation-service`

- 拥有的数据：对账批次、对账快照、差异记录、差错分类、修复工单、自动修复决策、对账审计日志。
- 可执行命令：`StartReconciliationBatch`、`CompareBookingSupplierPaymentRefundLedger`、`ClassifyDiscrepancy`、`CreateRepairTicket`、`RequestAutoRepair`、`CloseReconciliationItem`。
- 可发布事件：`ReconciliationBatchStarted`、`DiscrepancyDetected`、`DiscrepancyClassified`、`RepairTicketCreated`、`AutoRepairRequested`、`ReconciliationItemClosed`。
- 不能做什么：不能直接修改订单、供应商、支付、退款或账本事实；不能直接改分录修平账；不能把对账结果写回业务库替代业务命令；自动修复也必须通过领域服务命令并留下审计证据。

### `manual-review-service`

- 拥有的数据：用户决策、运营审批单、maker-checker 记录、人工处理意见、审批附件、人工修复审计。
- 可执行命令：`CreateReviewCase`、`SubmitUserDecision`、`ApproveManualRepair`、`RejectManualRepair`、`RequestDomainCommand`、`CloseReviewCase`。
- 可发布事件：`ManualReviewCreated`、`UserDecisionSubmitted`、`ManualRepairApproved`、`ManualRepairRejected`、`DomainCommandRequested`、`ManualReviewClosed`。
- 不能做什么：不能绕过 `booking-service`、`refund-service` 或 `ledger-service` 的状态机；不能直接删除历史事实；不能用人工审批结果直接改其他服务数据库；不能跳过 maker-checker 执行高风险修复。

### `message-broker`

- 拥有的数据：待投递 outbox 事件、投递状态、消费位点、重试和死信记录、消息元数据。
- 可执行命令：`PublishOutboxEvent`、`DeliverMessage`、`RetryMessage`、`DeadLetterMessage`、`AcknowledgeMessage`。
- 可发布事件：`MessageDelivered`、`MessageDeliveryFailed`、`MessageDeadLettered`、`MessageRetried`。
- 不能做什么：不能代表业务事实本身；不能作为订单、供应商确认、付款、退款或补偿完成的事实来源；不能让消费者只依赖 offset 推导业务完成；不能替代领域服务的幂等和去重。

## 关键边界

- `booking-service` 是组合订单 owner，但不是供应商事实 owner 或资金事实 owner。
- `supplier-adapter-service` 只记录供应商事实，不直接推进资金账本。
- `payment-service` 和 `refund-service` 只记录资金渠道事实，不改写供应商历史。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单和修复命令，不能直接修改事实；自动修复也必须留下审计证据。
- `manual-review-service` 记录人工决策和审批，不绕过领域服务的幂等命令。
- `message-broker` 只负责投递和解耦，不是任何业务事实的来源。
- 所有服务只能拥有并修改自己的数据。跨服务不能直接改库，只能调用对方命令、查询对方只读接口，或消费对方发布的事件。

## 典型调用关系

### 创建组合订单

```text
booking-service
-> payment-service
-> message-broker
```

### 核心项预订

```text
booking-service
-> supplier-adapter-service
-> booking-service
-> payment-service
-> ledger-service
-> message-broker
```

### 附加项预订

```text
booking-service
-> supplier-adapter-service
-> refund-service or manual-review-service
-> message-broker
```

### 补偿和人工处理

```text
booking-service
-> refund-service
-> ledger-service
-> manual-review-service
-> message-broker
```

### 对账

```text
reconciliation-service
-> booking-service
-> supplier-adapter-service
-> payment-service
-> refund-service
-> ledger-service
-> manual-review-service
```

## 不接受的设计

- 一个 booking-service 直接调用供应商、扣款、退款并改账本。
- 只保存总订单状态，不保存子订单和供应商事实。
- 把搜索价当最终成交价。
- 供应商超时直接失败。
- 已出票、已确认或已生效动作被本地字段回滚。
- 附加项失败后取消核心成功行程。
- 对账脚本直接改订单、供应商、支付、退款或分录。
- 用消息 offset 作为供应商确认、付款、退款或补偿完成事实。
