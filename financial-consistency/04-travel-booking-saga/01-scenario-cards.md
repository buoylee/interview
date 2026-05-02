# 01 场景卡

## 目的

本文件先定义旅行组合预订的业务边界，再讨论 Saga 和一致性方案。每张场景卡都回答：链路从哪里开始，核心成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 搜索报价、锁价和报价过期

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户搜索机票、酒店、租车和保险；系统展示组合报价；用户选择后尝试锁价或生成报价快照。 |
| 参与方 | 用户、booking-service、supplier-adapter-service、flight supplier、hotel supplier、car supplier、insurance supplier。 |
| 核心状态机 | 报价：`SEARCHED -> QUOTE_SELECTED -> QUOTE_LOCKED`，过期进入 `QUOTE_EXPIRED` 或 `PRICE_CHANGED`。 |
| 正确性不变量 | 搜索价不能直接当成交价；报价过期后不能按旧价扣款；价格变动必须被记录并等待用户确认或重新报价。 |
| 关键命令和事件 | `TravelSearchRequested`、`QuoteSelected`、`QuoteLockRequested`、`QuoteLocked`、`QuoteExpired`、`PriceChanged`。 |
| 耐久事实 | 报价快照、供应商报价号、价格、币种、有效期、可退改规则、付款策略。 |
| 最危险失败点 | 报价过期后继续扣款；供应商库存消失；价格上涨但没有用户确认；报价快照和供应商事实无法对账。 |
| 补偿方式 | 重新报价、用户确认差价、取消组合订单、释放授权或人工处理。 |
| 对账来源 | 报价快照、供应商报价响应、组合订单、支付授权记录、用户确认记录。 |
| 验证方式 | 报价过期故障注入、价格变动属性测试、用户确认审计检查。 |

## 创建组合订单和子订单

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户确认组合报价；booking-service 创建组合订单；为机票、酒店、租车和保险创建子订单。 |
| 参与方 | 用户、booking-service、payment-service、message-broker。 |
| 核心状态机 | 组合订单：`QUOTE_SELECTED -> BOOKING_CREATED`；子订单：`CREATED`。 |
| 正确性不变量 | 同一幂等键只能创建一个组合订单；组合订单必须能解释所有子订单；每个子订单必须记录供应商、报价、付款策略和可逆性。 |
| 关键命令和事件 | `BookingCreateRequested`、`BookingCreated`、`TravelItemCreated`、`PaymentPolicyRecorded`。 |
| 耐久事实 | 组合订单、子订单、幂等键、报价快照、付款策略、可逆性快照、Outbox 事件。 |
| 最危险失败点 | 组合订单存在但子订单缺失；重复创建组合订单；子订单没有独立状态机；付款策略没有快照。 |
| 补偿方式 | 幂等返回既有组合订单；补子订单和事件；无法补齐时进入人工处理。 |
| 对账来源 | 组合订单、子订单、报价快照、Outbox 消费记录。 |
| 验证方式 | 重复创建测试、子订单完整性检查、付款策略快照检查。 |

## 预授权、扣款、释放授权和退款

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统按子产品付款策略执行预授权、立即扣款、到供应商支付或不可退规则；资金动作和供应商动作解耦。 |
| 参与方 | 用户、booking-service、payment-service、refund-service、ledger-service、payment channel。 |
| 核心状态机 | 付款：`PAYMENT_CREATED -> AUTHORIZED -> CAPTURED`；释放：`AUTHORIZED -> VOIDED`；退款：`CAPTURED -> REFUNDING -> REFUNDED`。 |
| 正确性不变量 | 同一授权只能 capture 或 void 一次；已 capture 资金不能 void；退款、罚金和补差必须有分录。 |
| 关键命令和事件 | `PaymentAuthorized`、`PaymentCaptured`、`AuthorizationVoided`、`RefundRequired`、`RefundSucceeded`、`PenaltyPosted`、`AdjustmentPosted`。 |
| 耐久事实 | 支付单、授权号、capture 记录、void 记录、退款单、罚金、补差、会计分录。 |
| 最危险失败点 | 供应商失败后忘记释放授权；已扣款后供应商失败但没有退款；重复 capture；重复退款；罚金没有分录。 |
| 补偿方式 | void/release 授权、退款、冲正、罚金分录、补差分录或人工处理。 |
| 对账来源 | 支付单、退款单、渠道账单、会计分录、供应商规则。 |
| 验证方式 | capture/void 互斥属性测试、退款幂等测试、罚金补差对账。 |

## 机票出票和酒店确认的核心 Saga

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 机票和酒店是核心项；系统锁座或出票、酒店保留或确认；核心项全部成功后组合订单进入核心成功。 |
| 参与方 | booking-service、supplier-adapter-service、flight supplier、hotel supplier、payment-service、refund-service、manual-review-service。 |
| 核心状态机 | 组合订单：`PAYMENT_AUTHORIZED -> CORE_BOOKING_IN_PROGRESS -> CORE_CONFIRMED`；子订单：`SUPPLIER_PENDING -> SUPPLIER_CONFIRMED`。 |
| 正确性不变量 | 核心项未全部成功时组合订单不能 `CONFIRMED`；供应商未知不是失败；供应商成功不能被失败回调覆盖。 |
| 关键命令和事件 | `FlightTicketRequested`、`FlightTicketed`、`HotelConfirmRequested`、`HotelConfirmed`、`CoreBookingConfirmed`、`CoreBookingFailed`。 |
| 耐久事实 | 机票子订单、酒店子订单、供应商请求号、PNR 或确认号、供应商状态历史、付款状态。 |
| 最危险失败点 | 机票已出票但酒店失败；酒店已确认但机票失败；一端未知；一端成功一端失败时直接把整单失败。 |
| 补偿方式 | 尝试取消或退款已成功核心项；计算罚金或补差；替代供应商；进入人工处理。 |
| 对账来源 | 组合订单、机票供应商订单、酒店供应商订单、支付单、退款单、会计分录。 |
| 验证方式 | 核心项部分成功故障注入、供应商未知测试、成功后失败回调测试。 |

## 租车和保险附加项处理

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 租车和保险是附加项；核心项成功后附加项继续确认；附加项失败不取消核心行程。 |
| 参与方 | booking-service、supplier-adapter-service、car supplier、insurance supplier、refund-service、manual-review-service。 |
| 核心状态机 | `CORE_CONFIRMED -> ADDON_BOOKING_IN_PROGRESS -> CONFIRMED` 或 `CONFIRMED_WITH_ADDON_FAILURES`。 |
| 正确性不变量 | 附加项失败不能覆盖核心成功事实；保险生效不能被本地删除掩盖；附加项退款必须能解释组合订单状态。 |
| 关键命令和事件 | `CarBookingRequested`、`CarBooked`、`InsuranceApplyRequested`、`InsuranceIssued`、`AddonFailed`、`AddonRefundRequired`。 |
| 耐久事实 | 租车子订单、保险子订单、供应商确认号、保险保单号、退款单、用户通知记录。 |
| 最危险失败点 | 租车失败却取消机票酒店；保险投保失败但订单显示已投保；保险已生效后收到失败回调；附加项退款和组合状态不一致。 |
| 补偿方式 | 保留核心成功；退款附加项；替代供应商；提示用户未投保；人工处理。 |
| 对账来源 | 组合订单、租车供应商订单、保险供应商订单、退款单、用户通知和账本。 |
| 验证方式 | 附加失败属性测试、核心保留测试、保险生效后失败回调测试。 |

## 核心失败、附加失败、部分成功和人工处理

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 组合订单可能进入部分成功、附加失败或人工处理；系统必须解释每个子订单最终状态。 |
| 参与方 | 用户、booking-service、manual-review-service、payment-service、refund-service、ledger-service。 |
| 核心状态机 | `PARTIALLY_CONFIRMED -> COMPENSATING -> REFUNDING -> MANUAL_REVIEW` 或 `CANCELLED`。 |
| 正确性不变量 | `PARTIALLY_CONFIRMED` 必须有 owner、下一步动作和审计记录；人工处理不能直接覆盖供应商或资金事实。 |
| 关键命令和事件 | `PartialBookingDetected`、`CompensationRequested`、`ManualReviewRequested`、`UserDecisionRecorded`、`ManualRepairCompleted`。 |
| 耐久事实 | 部分成功记录、补偿命令、用户决策、人工工单、审批记录、审计记录。 |
| 最危险失败点 | 只有总订单状态没有子订单事实；用户决策无审计；人工修复直接改历史；部分成功无法向客服和财务解释。 |
| 补偿方式 | 用户确认替代或补差；运营审批退款或罚金；追加修复事实；重新对账。 |
| 对账来源 | 组合订单、子订单、人工工单、用户确认记录、退款单、会计分录。 |
| 验证方式 | 人工修复重复提交测试、审计记录检查、部分成功历史检查。 |

## 供应商、支付、退款、罚金、补差和本地订单对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统对比本地组合订单、子订单、供应商订单、支付、退款、罚金、补差、会计分录和事件消费记录。 |
| 参与方 | reconciliation-service、booking-service、supplier-adapter-service、payment-service、refund-service、ledger-service、manual-review-service。 |
| 核心状态机 | `RECONCILIATION_STARTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 差错必须有分类、owner、状态、修复动作和审计记录；对账服务不直接修改领域事实。 |
| 关键命令和事件 | `TravelStatementImported`、`SupplierMismatchDetected`、`PaymentMismatchDetected`、`TravelRepairRequested`、`TravelRepairVerified`。 |
| 耐久事实 | 对账批次、供应商账单、支付账单、退款账单、差错单、修复命令、复核记录。 |
| 最危险失败点 | 本地确认但供应商无订单；供应商确认但本地未推进；已扣款但核心失败未退款；罚金或补差无分录。 |
| 补偿方式 | 补订单状态、补供应商事实、补退款、补罚金或补差分录、补事件、冲正或人工复核。 |
| 对账来源 | 组合订单、子订单、供应商订单、支付单、退款单、罚金、补差、会计分录、Outbox 消费记录。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
