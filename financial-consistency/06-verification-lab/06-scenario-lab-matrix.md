# 06 场景实验矩阵

## 目标

场景实验矩阵把验证模型落回真实业务。每个场景都必须说明事实来源、关键不变量、异常 History 样例、故障注入点、history replay 样例和不合格判定。

矩阵不是按工具组织，而是按业务事实边界组织。一次实验合格，只能说明在这段 History、这些 Fact 和这些 Invariant 范围内没有发现不可解释事实；它不能证明所有生产异常绝对安全。

## 总览

| 场景 | 重点验证 | 主要 Oracle |
| --- | --- | --- |
| 内部转账 | 幂等、冻结、扣减、入账、account movement、ledger posting、冲正、调整、人工复核 | 状态机 oracle、资金 oracle |
| 充值提现 | 渠道超时、重复回调、主动查询、渠道账单、本地 unknown、退款、提现和对账 | 状态机 oracle、外部事实 oracle、资金 oracle |
| 电商下单 | 库存预留、支付成功后取消、重复消息、退款、发货、售后和商户结算 | 状态机 oracle、资金 oracle、外部事实 oracle |
| 旅行组合预订 | 核心项和附加项、供应商未知、已出票、已生效保险、付款策略、罚金、补差和人工处理 | 外部事实 oracle、资金 oracle、状态机 oracle |

## Oracle 映射

| Oracle | 读取的 Fact | 负责判定 | 不负责替代 |
| --- | --- | --- | --- |
| 状态机 oracle | 业务单状态、状态变更记录、版本号、事件时间、处理时间、幂等记录 | 状态迁移是否合法、终态是否单调、迟到事件是否被拒绝或解释、unknown 是否有收敛路径 | 渠道流水、供应商订单、账本分录和人工审批 |
| 资金 oracle | 账户余额、冻结、account movement、ledger posting、渠道流水、退款、冲正、调整分录、对账差错 | 余额变化是否可追溯、借贷是否平衡、同一业务效果是否最多一次、已 capture 资金是否通过 refund 或调整处理 | 只凭接口返回或 workflow history 判定资金成功 |
| 外部事实 oracle | 渠道请求号、渠道流水、查询结果、回调、渠道账单、供应商请求号、供应商订单、出票、酒店确认、保险生效、供应商账单 | 本地 Fact 与外部 Fact 是否互相解释，unknown 是否通过查询、回调、账单、对账或人工处理推进 | 用本地失败覆盖外部成功，或用供应商 unknown 直接判失败 |

## 全局边界

- account-service 和 ledger-service 不能共享本地事务；验证必须允许两边短暂分叉，但最终要能用 Outbox、重试、对账、冲正、调整或人工处理解释。
- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 和 `SUPPLIER_UNKNOWN` 不是直接失败；它们必须通过查询、回调、对账、长期对账终态或人工挂起终态继续解释。
- 已 capture 资金不能 void；只能 refund、reversal、adjustment posting、对账差错或人工修复。
- 已出票机票、已确认供应商订单和已生效保险不能被删除，也不能被本地取消字段覆盖。
- workflow history 不是事实来源。它只能解释编排过程，不能替代支付事实、供应商事实、退款事实、账本事实、对账事实或人工审批事实。
- broker offset 和 consumer offset 只能证明读取进度或处理进度，不能证明支付、退款、库存、供应商确认、ledger posting 或人工修复已经完成。

## 内部转账

### 事实来源

- 转账请求、业务幂等键和 transfer_request_id。
- 借方余额、贷方余额、冻结金额和释放记录。
- account movement，包括冻结、扣减、入账、释放、冲正和调整。
- ledger posting，包括借方分录、贷方分录、冲正分录和调整分录。
- Outbox 事件、消费者处理记录和重试记录。
- 对账差错、人工处理工单、maker-checker 审批和复核结果。

### 关键不变量

- 同一 transfer_request_id 最多产生一个转账业务效果。
- 借方扣减、贷方入账、account movement 和 ledger posting 必须能通过同一业务单号互相解释。
- account-service 和 ledger-service 不能共享本地事务，但任一侧提交后的事实分叉必须有可恢复传播、对账或人工处理路径。
- ledger posting 必须借贷平衡；冲正和调整必须追加新 Fact，不能删除原始分录。
- 冻结只能被确认扣减或释放一次，重复 Command、重复消息和重复人工修复不能产生第二次资金效果。

### 异常 History 样例

```text
1. Command: CreateTransfer(T1, idempotency_key=K1)
2. Fact: DebitAccountMovementCreated(T1, debit=100)
3. Fault: ProcessCrashBeforeLedgerPosting(T1)
4. Command: RetryTransfer(T1, idempotency_key=K1)
5. Fact: TransferIdempotencyHit(T1)
6. Fact: LedgerPostingCreated(T1, debit=100, credit=100)
7. Fact: CreditAccountMovementCreated(T1, credit=100)
8. Fact: ReconciliationMatched(T1)
```

### 故障注入点

- 借方冻结提交前失败：不得留下业务 Fact、Outbox 事件或 ledger posting。
- 借方 account movement 提交后、Outbox sent 前失败：publisher 只能重投事件，不能重新扣款。
- ledger-service 写入单边 posting 后失败：必须拒绝不平分录提交，或生成可审计差错和修复命令。
- 贷方入账成功但消费者处理记录缺失：重复消息必须通过 event id、transfer_request_id 和业务唯一约束幂等处理。
- consumer offset 已提交但贷方入账或 ledger posting 缺失：不能把 offset 当作业务完成，必须补处理记录、重放事件或进入对账差错。
- 人工冲正审批通过后响应丢失：重试只能返回同一修复结果，不能重复冲正。

### History Replay 样例

```text
1. Replay: LedgerPostingCreated(T1) arrives before CreditAccountMovementCreated(T1)
2. Replay: DuplicateTransferRequested(T1, idempotency_key=K1)
3. Replay: OutboxEventDeliveredTwice(T1)
4. Replay: ConsumerOffsetCommittedBeforeLedgerPosting(T1)
5. Replay: ManualAdjustmentRetried(T1, repair_request_id=R1)
6. Oracle: 状态机 oracle checks legal transfer states
7. Oracle: 资金 oracle checks account movement and ledger posting balance
```

合格结果：重复转账、重复事件和重复人工修复都只能解释为同一业务效果；账本借贷平衡；如果 account movement 与 ledger posting 短暂分叉，必须存在 Outbox、对账差错、修复命令或人工复核记录。

### 不合格判定

- 重复扣款、重复入账或重复冻结释放。
- 有 account movement 但无 ledger posting、Outbox、对账差错或人工处理记录。
- ledger posting 借贷不平，或分录缺少业务来源。
- account-service 与 ledger-service 分叉后没有恢复、对账或人工处理路径。
- 用 broker offset 或 consumer offset 证明贷方入账、ledger posting 或人工冲正已经完成。
- 人工冲正没有 maker-checker 审批、证据快照和复核结果。

## 充值提现

### 事实来源

- 本地支付单、充值单、提现单和退款单。
- payment_request_id、withdraw_request_id、refund_request_id、渠道 request id 和业务幂等键。
- 渠道请求记录、渠道流水、回调、主动查询结果和渠道账单。
- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 状态变更记录。
- 账户流水、冻结、入账、出账、退款、ledger posting 和调整分录。
- 对账批次、对账差错、修复命令、人工工单、审批和复核。

### 关键不变量

- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN` 和 `REFUND_UNKNOWN` 不能直接当失败；必须通过查询、回调、渠道账单、对账或人工处理收敛。
- 同一渠道 request id 不能产生多次充值入账、提现出账或退款业务效果。
- 成功回调、成功查询或渠道账单成功不能被迟到失败覆盖。
- 渠道成功但本地未推进时，必须进入账本补记、对账差错或人工处理。
- 已 capture 资金不能 void；充值撤销、订单取消或补偿只能走 refund、冲正、调整或人工处理。

### 异常 History 样例

```text
1. Command: CreateRecharge(R1, idempotency_key=K2)
2. Fact: ChannelRequestSent(R1, channel_request_id=C1)
3. Fault: ChannelTimeout(R1)
4. Fact: PaymentMarkedUnknown(R1, PAYMENT_UNKNOWN)
5. Event: ChannelSuccessCallback(R1, channel_txn=C1) arrives late
6. Event: DuplicateCallback(R1, channel_txn=C1)
7. Fact: ChannelTransactionRecorded(C1, CAPTURED)
8. Fact: LedgerPostingCreated(R1, debit=100, credit=100)
9. Fact: ChannelBillMatched(R1, C1)
```

### 故障注入点

- 渠道请求发出后响应超时：本地只能进入 unknown、查询、等待回调或对账，不能直接发起无关联二次扣款。
- 成功回调处理后、账户入账前失败：恢复时必须基于 channel_request_id 幂等补记，不能重复入账。
- 提现渠道受理后本地宕机：`WITHDRAW_UNKNOWN` 必须通过查询、账单或人工挂起解释，不能直接释放资金并重新提现。
- 退款请求超时：`REFUND_UNKNOWN` 必须通过同一 refund_request_id 查询、回调或对账推进，不能重复退款。
- 回调消费者提交 consumer offset 后入账或退款 ledger posting 缺失：必须按渠道 request id、event id 和业务单号幂等补记，不能把 offset 当资金事实。
- 渠道账单下载后对账任务中断：重跑应稳定生成同一差错或匹配结果。

### History Replay 样例

```text
1. Replay: ChannelFailureCallback(R1) arrives before ChannelSuccessCallback(R1)
2. Replay: QueryResultProcessing(R1) arrives after ChannelBillSuccess(R1)
3. Replay: DuplicateRefundCallback(RF1, REFUND_UNKNOWN)
4. Replay: WithdrawBillSuccess(W1) arrives after local WITHDRAW_UNKNOWN
5. Replay: BrokerOffsetAdvancedBeforeAccountMovement(R1)
6. Oracle: 状态机 oracle rejects terminal success rollback
7. Oracle: 外部事实 oracle matches callbacks, query results and bills
8. Oracle: 资金 oracle checks account movement and ledger posting
```

合格结果：本地 unknown 不被直接裁决；迟到成功、重复回调和账单成功都能关联到同一渠道 request id；账户流水和账本只产生一次业务效果；无法自动解释的差异进入对账或人工处理。

### 不合格判定

- 超时后发起无关联二次扣款、二次提现或二次退款。
- 重复回调造成重复入账、重复出账、重复退款或重复 ledger posting。
- 渠道账单成功但本地失败，且没有对账差错、修复命令或人工处理记录。
- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN` 或 `REFUND_UNKNOWN` 被直接判失败，导致迟到成功不可解释。
- 退款成功但账本无分录，或已 capture 资金被 void。
- 用 broker offset 或 consumer offset 证明充值入账、提现出账、退款或 ledger posting 已完成。

## 电商下单

### 事实来源

- 订单、订单状态变更、订单明细、支付请求和支付结果。
- 库存预留、确认、释放记录和库存流水。
- 退款请求、退款结果、退款 unknown、售后单和取消记录。
- 发货、签收、退货、商户结算和佣金依据。
- Outbox 事件、消费者处理记录、消息 event id 和 CDC 变更。
- account movement、ledger posting、渠道流水、对账差错和人工处理记录。

### 关键不变量

- 同一订单支付幂等键最多产生一次 capture；同一退款幂等键最多产生一次 refund。
- 库存预留只能确认或释放一次，Confirm 和 Release 不能双终态。
- 支付成功后取消必须进入退款、账本和对账路径，不能删除订单或支付事实。
- 重复消息不能重复确认库存、重复释放库存、重复退款、重复发货或重复结算。
- 已发货订单不能被普通取消流程覆盖；迟到失败不能覆盖已支付、已发货或已退款成功 Fact。

### 异常 History 样例

```text
1. Command: CreateOrder(O1, idempotency_key=K3)
2. Fact: InventoryReserved(O1, reservation_id=IR1)
3. Fact: PaymentCaptured(O1, payment_request_id=P1)
4. Event: InventoryConfirmMessageDuplicated(O1, event_id=E1)
5. Command: CancelOrderRequested(O1)
6. Fact: RefundRequested(O1, refund_request_id=RF1)
7. Fault: RefundTimeout(RF1)
8. Fact: RefundMarkedUnknown(RF1, REFUND_UNKNOWN)
9. Fact: ReconciliationPending(O1)
```

### 故障注入点

- 订单本地事务提交后、Outbox sent 前失败：Outbox 扫描只能重投事件，不能重建订单或重复扣款。
- 支付 capture 成功后库存确认消息重复：消费者必须按 event id 和 order_id 幂等确认。
- 库存预留成功但支付超时：订单不能直接失败并丢弃预留，必须释放、等待支付回调或进入补偿。
- 支付成功后取消，refund 请求超时：`REFUND_UNKNOWN` 不能直接失败，必须通过查询、账单、对账或人工处理解释。
- 库存、退款或结算消费者提交 consumer offset 后业务 Fact 缺失：必须重放或补偿，不能用 offset 证明库存确认、退款或结算完成。
- 发货 Fact 已存在后收到取消消息：状态机必须拒绝普通取消覆盖发货事实。

### History Replay 样例

```text
1. Replay: PaymentCaptured(O1) before InventoryReservedProjection(O1)
2. Replay: InventoryReleased(O1) duplicated after InventoryConfirmed(O1)
3. Replay: CancelOrderRequested(O1) after ShipmentCreated(O1)
4. Replay: RefundSuccessCallback(RF1) after REFUND_UNKNOWN
5. Replay: ConsumerOffsetCommittedBeforeRefundPosting(O1)
6. Oracle: 状态机 oracle checks order, inventory and shipment transitions
7. Oracle: 资金 oracle checks capture, refund and settlement postings
8. Oracle: 外部事实 oracle checks channel transaction and refund evidence
```

合格结果：支付、库存、发货、退款和结算 Fact 不因乱序或重复消息产生第二次业务效果；支付成功后的取消只追加 refund 或售后事实；已发货事实保留，后续差异进入售后、对账或人工处理。

### 不合格判定

- 支付成功后删除订单、支付单、渠道流水或账本分录。
- 库存预留失败仍扣款，且没有退款、差错或人工处理路径。
- 重复消息造成重复扣减库存、重复释放库存、重复退款或重复结算。
- `REFUND_UNKNOWN` 被直接判失败且无查询、对账或人工处理路径。
- 已发货订单被普通取消流程覆盖，或售后退款没有资金和库存依据。
- 用 broker offset 或 consumer offset 证明支付、库存确认、退款、发货或商户结算已经完成。

## 旅行组合预订

### 事实来源

- 报价快照、组合订单、子订单状态、核心项和附加项策略。
- 供应商 request id、供应商订单号、出票、酒店确认、保险生效和供应商账单。
- 支付授权、capture、void、refund、refund unknown、罚金和补差。
- `SUPPLIER_UNKNOWN`、供应商查询结果、回调、迟到成功和迟到失败记录。
- 外部请求记录、领域 Fact、支付事实、供应商事实和人工审批事实。
- ledger posting、account movement、对账差错、人工处理工单、审批和复核。
- 编排执行线索（非业务事实）：workflow history、Activity attempt、broker offset、consumer offset。业务事实必须来自领域记录、外部供应商或支付证据、ledger posting、对账差错或人工审批。

### 关键不变量

- 核心项和附加项必须分层处理；附加项失败不能直接取消核心行程。
- 已出票机票、已确认酒店和已生效保险不能被删除，也不能被本地失败、取消或 workflow completion 覆盖。
- `SUPPLIER_UNKNOWN` 不能直接失败；必须查询、等待回调、对账、补偿或进入人工挂起。
- 已 capture 资金不能 void；只能 refund、冲正、调整、罚金、补差、对账差错或人工处理。
- workflow history 不是供应商事实、支付事实、退款事实或账本事实；Activity 成功只说明编排过程推进过。

### 异常 History 样例

```text
1. Command: CreateTrip(TR1, idempotency_key=K4)
2. Fact: FlightTicketed(TR1, supplier_order_id=F1)
3. Fact: HotelFailed(TR1, supplier_order_id=H1)
4. Fact: PaymentCaptured(TR1, payment_request_id=P2)
5. Fact: CompensationStarted(TR1)
6. Fault: RefundTimeout(TR1, refund_request_id=RF2)
7. Fact: RefundMarkedUnknown(RF2, REFUND_UNKNOWN)
8. Fact: ManualReviewOpened(TR1)
9. Fact: SupplierBillReceived(TR1)
10. Fact: ReconciliationMismatch(TR1)
```

### 故障注入点

- Flight Activity 调用供应商后、completion 未写入 workflow history 前失败：重试必须使用同一 supplier request id 查询或幂等重试，不能重复出票。
- 酒店供应商响应超时：本地只能进入 `SUPPLIER_UNKNOWN`、查询、等待回调、对账或人工挂起，不能直接失败并删除外部请求。
- 机票已出票后酒店失败：不能删除出票 Fact；必须按产品策略处理保留、退款、改签、罚金、补差或人工审批。
- 支付 capture 成功后组合失败：不能 void 已 capture 资金，必须 refund、冲正、调整或人工处理。
- 供应商消息或支付回调的 consumer offset 已提交但供应商订单、退款或账本 Fact 缺失：必须查询、重放、对账或人工挂起，不能用 offset 证明完成。
- 保险已生效后取消：不能删除保险事实，必须追加退保、保留、罚金、补差或人工处理 Fact。

### History Replay 样例

```text
1. Replay: SupplierSuccessCallback(TR1, F1) after local SUPPLIER_UNKNOWN
2. Replay: SupplierFailureCallback(TR1, H1) after PaymentCaptured(TR1)
3. Replay: ActivityCompleted in workflow history before SupplierBillReceived(TR1)
4. Replay: RefundSuccessCallback(RF2) after ManualReviewOpened(TR1)
5. Replay: ConsumerOffsetCommittedBeforeSupplierFact(TR1)
6. Oracle: 外部事实 oracle checks ticket, hotel, insurance and supplier bills
7. Oracle: 资金 oracle checks capture, refund, penalty and adjustment postings
8. Oracle: 状态机 oracle checks package and sub-item transitions
```

合格结果：迟到供应商成功、迟到供应商失败、Activity 重试和退款 unknown 都被记录并解释；核心项和附加项策略明确；不可逆供应商 Fact 保留；资金通过 refund、罚金、补差、冲正、调整、对账或人工复核闭环。

### 不合格判定

- 附加项失败直接取消核心行程，且没有产品策略、补偿或人工审批依据。
- `SUPPLIER_UNKNOWN` 被直接判失败，导致迟到出票、酒店确认或保险生效不可解释。
- 已出票、已确认供应商订单或已生效保险被删除、覆盖或本地回滚。
- 已 capture 资金被 void，或退款 unknown 没有查询、对账或人工处理路径。
- workflow history completion 被当成账平、出票成功、供应商确认或人工审批完成。
- 用 broker offset 或 consumer offset 证明出票、酒店确认、保险生效、退款、ledger posting 或人工审批完成。

## 输出结论

场景实验矩阵的作用是防止验证方法脱离业务。每个实验都必须说清：事实从哪里来、什么不能违反、异常 History 如何构造、故障注入放在哪里、history replay 如何改变顺序、失败时说明哪条一致性边界有缺口。

合格报告应该输出场景、输入 History、读取的 Fact、执行的 oracle、被覆盖的不变量和剩余 unknown 的处理路径。不合格判定必须指向具体边界，例如幂等、状态机、资金账本、外部事实、对账或人工修复，而不是只写“测试失败”。
