# 01 场景卡

## 目的

本文件先定义业务边界，再讨论一致性方案。每张场景卡都回答：链路从哪里开始，成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 下单并预留库存

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户提交订单；系统创建订单；库存服务按订单明细预留库存；预留成功后订单进入待支付状态。 |
| 参与方 | 用户、order-service、inventory-service、message-broker。 |
| 核心状态机 | 订单：`CREATED -> STOCK_RESERVED -> PENDING_PAYMENT`；库存预留：`RESERVED`，失败进入 `RESERVE_FAILED` 或 `MANUAL_REVIEW`。 |
| 正确性不变量 | 库存可售量不能为负；同一订单明细只能预留一次库存；库存不足时订单不能进入可支付状态。 |
| 关键命令和事件 | `OrderCreateRequested`、`OrderCreated`、`StockReserveRequested`、`StockReserved`、`StockReserveFailed`。 |
| 耐久事实 | 订单、订单明细、库存预留记录、库存流水、Outbox 事件。 |
| 最危险失败点 | 订单创建成功但库存预留失败；库存预留成功但订单状态未推进；重复下单或重复预留；库存不足但订单可支付。 |
| 补偿方式 | 预留失败时订单进入创建失败或可重试状态；订单失败但库存已预留时释放预留；重复预留按订单明细幂等返回既有结果。 |
| 对账来源 | 订单、订单明细、库存预留记录、库存流水、Outbox 消费记录。 |
| 验证方式 | 库存非负属性测试、重复预留测试、订单创建失败故障注入、库存流水对账。 |

## 支付成功后确认订单和库存

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户完成支付；payment-service 提供可信支付成功事实；order-service 将订单推进到已支付；inventory-service 将预留库存确认；ledger-service 追加支付分录。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、ledger-service、message-broker。 |
| 核心状态机 | 订单：`PENDING_PAYMENT -> PAID -> STOCK_CONFIRMED -> FULFILLABLE`；库存：`RESERVED -> CONFIRMED`。 |
| 正确性不变量 | 支付成功订单必须有支付成功事实；同一订单只能确认一次库存；`CONFIRMED` 库存不能再释放；支付成功必须最终有订单终态和会计分录。 |
| 关键命令和事件 | `PaymentSucceeded`、`OrderPaid`、`StockConfirmRequested`、`StockConfirmed`、`PaymentLedgerPosted`、`OrderFulfillable`。 |
| 耐久事实 | 支付单、支付渠道事实、订单状态历史、库存确认流水、会计分录、Outbox 事件。 |
| 最危险失败点 | 支付成功但订单未推进；支付成功但库存未确认；库存确认失败；重复支付事件导致库存重复确认。 |
| 补偿方式 | 支付成功但订单未推进时补订单状态；库存未确认时补确认或进入人工处理；库存已释放时进入退款或人工处理。 |
| 对账来源 | 订单、支付单、库存预留和确认流水、会计分录、渠道账单、Outbox 消费记录。 |
| 验证方式 | 重复支付事件测试、支付成功后库存确认故障注入、订单库存账本交叉对账。 |

## 支付失败、超时或未知状态

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 支付请求提交后返回失败、超时或未知；可信失败事实可以释放库存或允许重新支付；未知状态必须查询、等待回调或对账。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、reconciliation-service、message-broker。 |
| 核心状态机 | 支付：`CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED` 或 `CHANNEL_FAILED`；订单：`PENDING_PAYMENT -> PAYMENT_UNKNOWN`，可信失败后进入 `PAYMENT_FAILED` 或 `CANCELLED`。 |
| 正确性不变量 | 支付超时不是失败；`PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态；未知状态不能重复提交新支付动作。 |
| 关键命令和事件 | `PaymentRequested`、`PaymentUnknown`、`PaymentQueryRequested`、`PaymentSucceeded`、`PaymentFailed`、`OrderPaymentUnknown`。 |
| 耐久事实 | 支付单、渠道请求号、查询结果、回调事实、订单状态历史、库存预留记录。 |
| 最危险失败点 | 把支付超时当失败并释放库存；未知状态下重复提交新支付；失败回调覆盖成功终态；库存长期悬挂。 |
| 补偿方式 | 查询补偿、等待回调、渠道账单核验、人工复核；可信失败后释放库存；可信成功后推进订单和库存确认。 |
| 对账来源 | 支付单、渠道账单、订单状态、库存预留记录、回调记录、查询记录。 |
| 验证方式 | 支付超时故障注入、未知状态重复动作测试、失败晚于成功测试、库存悬挂扫描。 |

## 订单取消与支付回调并发

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户或系统发起取消；支付成功、失败或未知回调可能同时到达；状态机必须裁决订单进入取消、已支付、退款中或人工处理。 |
| 参与方 | 用户、order-service、payment-service、inventory-service、refund-service、message-broker。 |
| 核心状态机 | 取消先成功：`PENDING_PAYMENT -> CANCEL_REQUESTED -> CANCELLED`；支付先成功：`PENDING_PAYMENT -> PAID -> REFUND_REQUIRED` 或 `FULFILLABLE`；冲突进入 `MANUAL_REVIEW`。 |
| 正确性不变量 | 订单终态不能互相覆盖；取消成功必须释放未确认库存；支付成功后不能普通取消，必须履约或退款；同一库存预留不能既确认又释放。 |
| 关键命令和事件 | `OrderCancelRequested`、`OrderCancelAccepted`、`StockReleased`、`OrderCancelled`、`PaymentSucceeded`、`OrderRefundRequired`。 |
| 耐久事实 | 订单状态历史、支付事实、库存释放流水、库存确认流水、退款需求记录、Outbox 事件。 |
| 最危险失败点 | 取消成功后收到支付成功；支付成功后库存已释放；取消和支付同时推进导致终态冲突；重复取消释放库存。 |
| 补偿方式 | 版本条件更新裁决并发；取消后支付成功进入退款或人工处理；支付后取消进入退款或履约前取消；重复取消幂等返回既有结果。 |
| 对账来源 | 订单状态历史、支付单、库存流水、退款单、Outbox 消费记录。 |
| 验证方式 | 并发模型验证、支付回调和取消竞态测试、重复取消测试、库存确认释放互斥属性测试。 |

## 已支付订单取消和退款

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 已支付但未履约订单被取消；系统创建退款单；退款渠道确认成功后订单进入已退款或关闭状态，并追加退款分录。 |
| 参与方 | 用户、order-service、refund-service、payment-service、ledger-service、reconciliation-service、message-broker。 |
| 核心状态机 | 订单：`PAID -> REFUND_REQUIRED -> REFUNDING -> REFUNDED -> CLOSED`；退款：`CREATED -> REFUND_SUBMITTED -> REFUND_UNKNOWN -> REFUND_SUCCEEDED -> SUCCEEDED`。 |
| 正确性不变量 | 已支付订单不能直接回滚为未支付；同一退款单只能产生一次退款业务效果；累计退款金额不能超过原支付金额；退款成功必须有渠道事实和退款分录。 |
| 关键命令和事件 | `RefundRequired`、`RefundCreated`、`RefundSubmitted`、`RefundSucceeded`、`OrderRefunded`、`RefundLedgerPosted`。 |
| 耐久事实 | 退款单、退款渠道请求号、退款渠道事实、订单状态历史、退款分录、Outbox 事件。 |
| 最危险失败点 | 重复退款；退款金额超过原支付金额；退款成功但订单未关闭；退款未知状态下重复提交外部退款。 |
| 补偿方式 | 退款请求幂等；未知退款查询补偿；退款成功本地未推进时补订单状态和分录；冲突进入人工复核。 |
| 对账来源 | 订单、支付单、退款单、退款渠道账单、会计分录、Outbox 消费记录。 |
| 验证方式 | 重复退款测试、退款金额上限属性测试、退款未知故障注入、退款账单对账。 |

## 订单、支付、库存、退款对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统对比订单、支付单、库存流水、退款单、会计分录、Outbox 和渠道账单；识别差错并生成修复路径。 |
| 参与方 | reconciliation-service、order-service、payment-service、inventory-service、refund-service、ledger-service、运营人员。 |
| 核心状态机 | `RECONCILIATION_STARTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 差错必须有分类、owner、状态、修复动作和审计记录；修复不能直接覆盖订单、库存、支付、退款或分录历史。 |
| 关键命令和事件 | `CommerceStatementImported`、`CommerceMismatchDetected`、`CommerceRepairRequested`、`ManualRepairCompleted`。 |
| 耐久事实 | 对账批次、匹配结果、差错单、修复命令、审批记录、复核记录。 |
| 最危险失败点 | 只对账订单状态；不检查库存流水和退款单；差错修复直接改历史；发现问题没有 owner 和审计链。 |
| 补偿方式 | 补订单状态、补库存流水、补退款状态、补分录、补事件、冲正、人工复核。 |
| 对账来源 | 订单、支付单、库存流水、退款单、会计分录、Outbox 消费记录、渠道账单。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
