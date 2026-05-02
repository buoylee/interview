# 03 状态机

## 设计原则

状态机的任务是防止组合订单、报价、子订单、供应商事实和资金事实互相覆盖。所有状态推进都必须基于耐久事实和合法转换，不能只基于一次 RPC 返回值、回调或消息消费结果。

核心原则：

- 事实优先于派生状态：供应商确认、支付扣款、退款完成、人工决策都必须作为不可篡改事实记录，再由状态机推进派生状态。
- 未知状态不是失败：`SUPPLIER_UNKNOWN`、`PAYMENT_UNKNOWN`、`VOID_UNKNOWN`、`REFUND_UNKNOWN`、`RECONCILIATION_UNKNOWN` 必须进入查询、等待、对账或人工处理，不能直接转成失败终态。
- 成功事实不可被失败覆盖：已经确认的供应商成功、核心项成功、扣款成功或退款成功，不能被迟到失败回调、重复消息或人工误操作覆盖。
- 核心项和附加项分层处理：核心项决定组合订单能否成立，附加项失败只能降级为部分体验或补偿，不能把核心成功订单改成失败。
- 资金动作按生命周期转换：预授权、扣款、释放授权和退款分别建模，`CAPTURED` 后不能 `VOIDED`，只能退款、冲正、对账或人工处理。
- 人工修复必须留痕：人工处理只能追加修复事实、审批事实和对账事实，不能直接改写历史供应商事实或资金事实。

## 组合订单状态机

组合订单聚合核心项、附加项、支付和补偿状态，只表达用户订单的业务可见状态，不替代子订单、供应商和资金事实。

正常核心成功路径：

```text
QUOTE_SELECTED
-> BOOKING_CREATED
-> PAYMENT_AUTHORIZED
-> CORE_BOOKING_IN_PROGRESS
-> CORE_CONFIRMED
-> CONFIRMED
```

附加项成功路径：

```text
CORE_CONFIRMED
-> ADDON_BOOKING_IN_PROGRESS
-> ADDON_CONFIRMED
-> CONFIRMED
```

附加项失败路径：

```text
CORE_CONFIRMED
-> ADDON_BOOKING_IN_PROGRESS
-> CONFIRMED_WITH_ADDON_FAILURES
```

部分成功和补偿路径：

```text
CORE_BOOKING_IN_PROGRESS
-> PARTIALLY_CONFIRMED
-> COMPENSATING
-> REFUNDING
-> MANUAL_REVIEW
```

取消路径：

```text
COMPENSATING
-> CANCELLED
```

关键规则：

- 核心项没有全部成功时，组合订单不能进入 `CONFIRMED`。
- 附加项失败不能把核心成功订单改成 `FAILED`。
- `PARTIALLY_CONFIRMED` 必须能解释每个核心子订单、附加子订单、支付和退款状态。
- `CORE_CONFIRMED` 是核心成功事实的派生结果，不能被附加项失败、迟到失败回调或重复补偿消息覆盖。
- `MANUAL_REVIEW` 不能直接覆盖供应商事实或资金事实，只能引用人工工单和修复事实。

## 报价状态机

报价状态机保证价格、库存、取消规则和付款策略在下单时有可追溯快照。

报价锁定路径：

```text
QUOTE_CREATED
-> QUOTE_PRICED
-> QUOTE_LOCK_REQUESTED
-> QUOTE_LOCKED
-> QUOTE_SELECTED
```

报价失效路径：

```text
QUOTE_CREATED
-> QUOTE_PRICED
-> QUOTE_EXPIRED
```

报价变更路径：

```text
QUOTE_LOCK_REQUESTED
-> QUOTE_CHANGED
-> REQUOTE_REQUIRED
```

未知和人工路径：

```text
QUOTE_LOCK_UNKNOWN
-> QUOTE_RECONCILING
-> MANUAL_REVIEW
```

关键规则：

- `QUOTE_SELECTED` 必须引用锁价快照，包括币种、总价、税费、供应商取消规则、核心项/附加项标记和付款策略。
- 报价失效或价格变化不能复用旧报价创建子订单，必须重新报价或让用户确认差价。
- `QUOTE_LOCK_UNKNOWN` 不是报价失败，不能直接取消订单或释放授权，必须查询供应商、等待回调、对账或转人工。
- 报价快照一旦被订单引用，后续报价变化只能生成新版本，不能原地覆盖。

## 子订单状态机

子订单按核心项和附加项分别建模。核心子订单失败会影响组合订单成立；附加子订单失败只影响附加服务交付和补偿。

供应商成功路径：

```text
CREATED
-> QUOTE_LOCKED
-> SUPPLIER_PENDING
-> SUPPLIER_CONFIRMED
-> APPLIED_TO_BOOKING
```

供应商失败路径：

```text
SUPPLIER_PENDING
-> SUPPLIER_FAILED
-> COMPENSATION_REQUIRED
```

供应商未知路径：

```text
SUPPLIER_PENDING
-> SUPPLIER_UNKNOWN
-> SUPPLIER_RECONCILING
-> MANUAL_REVIEW
```

取消和退款路径：

```text
SUPPLIER_CONFIRMED
-> CANCEL_REQUESTED
-> CANCELLED
-> REFUND_REQUIRED
```

取消未知路径：

```text
CANCEL_REQUESTED
-> CANCEL_UNKNOWN
-> SUPPLIER_RECONCILING
-> MANUAL_REVIEW
```

关键规则：

- `SUPPLIER_UNKNOWN` 不是失败，不能直接释放资金或取消成终态。
- `SUPPLIER_CONFIRMED` 不能被失败回调覆盖。
- 半不可逆或不可逆子订单失败后只能取消、退款、罚金、补差或人工处理。
- 每个子订单必须记录付款策略、可逆性快照、取消规则快照和核心项/附加项标记。
- 核心子订单进入 `SUPPLIER_FAILED` 时，组合订单只能进入补偿或人工处理，除非已有明确替代供应商成功事实。
- 附加子订单进入 `SUPPLIER_FAILED` 时，组合订单可以进入 `CONFIRMED_WITH_ADDON_FAILURES`，但不能覆盖核心子订单成功事实。

## 供应商状态机

供应商状态机记录外部供应商侧的事实，不直接代表组合订单状态。

预订路径：

```text
REQUEST_CREATED
-> SENT_TO_SUPPLIER
-> SUPPLIER_ACCEPTED
-> SUPPLIER_CONFIRMED
```

拒绝路径：

```text
SENT_TO_SUPPLIER
-> SUPPLIER_REJECTED
-> SUPPLIER_FAILED
```

未知路径：

```text
SENT_TO_SUPPLIER
-> SUPPLIER_UNKNOWN
-> SUPPLIER_QUERYING
-> SUPPLIER_RECONCILED
```

取消路径：

```text
SUPPLIER_CONFIRMED
-> CANCEL_SENT
-> CANCEL_ACCEPTED
-> CANCELLED
```

关键规则：

- 供应商幂等键、请求编号、确认号和回调编号必须与状态事实一起保存。
- `SUPPLIER_CONFIRMED` 是成功事实，迟到的 `SUPPLIER_REJECTED` 或失败回调只能进入冲突对账，不能覆盖成功事实。
- `SUPPLIER_UNKNOWN` 必须保留最后一次外部请求和查询证据，等待查询、回调、日终对账或人工修复。
- 供应商取消失败不等于退款失败，必须分别推进供应商取消状态和资金退款状态。

## 支付状态机

支付状态机区分预授权、扣款、释放授权和退款。资金状态只能由支付网关事实、账务流水、对账结果或人工修复事实推进。

预授权和扣款路径：

```text
PAYMENT_CREATED
-> AUTH_REQUESTED
-> AUTHORIZED
-> CAPTURE_REQUESTED
-> CAPTURED
```

释放授权路径：

```text
AUTHORIZED
-> VOID_REQUESTED
-> VOIDED
```

退款路径：

```text
CAPTURED
-> REFUND_REQUIRED
-> REFUND_REQUESTED
-> REFUNDING
-> REFUNDED
```

异常状态：

```text
PAYMENT_UNKNOWN
VOID_UNKNOWN
REFUND_UNKNOWN
CHARGEBACK_OPENED
MANUAL_REVIEW
```

关键规则：

- 预授权成功不等于扣款成功。
- `AUTHORIZED` 可以 `CAPTURE_REQUESTED` 或 `VOID_REQUESTED`，但同一授权不能同时完成 capture 和 void。
- `CAPTURED` 后不能 `VOIDED`，只能退款、冲正、拒付处理或人工处理。
- `VOIDED` 后不能 `CAPTURED`，除非创建新的支付授权。
- capture、void 和 refund 都必须幂等，并保存外部请求号、幂等键、金额、币种和网关结果。
- `REFUND_UNKNOWN` 不能重复提交外部退款，只能查询原退款请求、等待回调、对账或转人工。

## 退款状态机

退款状态机独立于组合订单和供应商取消状态，用于追踪应退、实退、未知和人工修复。

退款发起路径：

```text
REFUND_REQUIRED
-> REFUND_REQUESTED
-> REFUNDING
-> REFUNDED
```

部分退款路径：

```text
REFUND_REQUIRED
-> PARTIAL_REFUND_REQUESTED
-> PARTIALLY_REFUNDED
-> REFUND_REMAINDER_REQUIRED
```

退款未知路径：

```text
REFUND_REQUESTED
-> REFUND_UNKNOWN
-> REFUND_RECONCILING
-> MANUAL_REVIEW
```

关键规则：

- 退款金额必须引用原扣款、罚金、供应商取消费和用户补偿决策。
- `REFUNDED` 是资金成功事实，不能被迟到失败回调覆盖。
- `PARTIALLY_REFUNDED` 必须说明剩余金额的责任方、下一步动作和人工审批状态。
- `REFUND_UNKNOWN` 下禁止创建新的外部退款请求，除非人工工单确认原请求不存在并留下审计记录。

## 对账状态机

对账状态机用于发现供应商事实、支付事实、内部账务和组合订单派生状态之间的不一致。

日常对账路径：

```text
RECONCILIATION_SCHEDULED
-> DATA_COLLECTED
-> MATCHING
-> MATCHED
-> CLOSED
```

差异处理路径：

```text
MATCHING
-> MISMATCH_FOUND
-> REPAIR_REQUIRED
-> REPAIR_REQUESTED
-> RECONCILED
-> CLOSED
```

未知处理路径：

```text
MATCHING
-> RECONCILIATION_UNKNOWN
-> INVESTIGATING
-> MANUAL_REVIEW
```

关键规则：

- 对账不能直接改供应商事实或资金事实，只能生成差异事实、修复请求和人工工单。
- `MATCHED` 只表示本轮数据一致，不表示未来不会被迟到回调或账单修正改变。
- `MISMATCH_FOUND` 必须定位差异来源：供应商确认号、支付流水、退款流水、内部账务分录或组合订单派生状态。
- 修复完成后必须重新进入 `MATCHING` 或记录新的 `RECONCILED` 事实，不能只关闭人工工单。

## 人工工单状态机

人工工单处理供应商未知、资金未知、对账差异、用户补偿和高风险修复。

```text
MANUAL_REVIEW_REQUESTED
-> ASSIGNED
-> EVIDENCE_COLLECTED
-> DECISION_RECORDED
-> REPAIR_REQUESTED
-> REPAIRED
-> VERIFIED
-> CLOSED
```

退回和升级路径：

```text
EVIDENCE_COLLECTED
-> ESCALATED
-> DECISION_RECORDED
```

关键规则：

- 人工处理不能直接改历史事实。
- 用户决策、运营审批、证据、外部沟通记录和 maker-checker 必须有审计记录。
- 修复动作必须追加修复事实，例如 `SUPPLIER_REPAIR_RECORDED`、`PAYMENT_REPAIR_RECORDED`、`REFUND_REPAIR_RECORDED` 或 `RECONCILIATION_REPAIR_RECORDED`。
- 修复完成后必须重新对账，`VERIFIED` 必须引用新的对账结果。
- 人工关闭必须说明未修复原因、用户影响、财务影响和后续监控项。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `SUPPLIER_UNKNOWN -> SUPPLIER_FAILED` | 供应商未知不是失败，必须查询、等待回调、对账或人工处理。 |
| `QUOTE_LOCK_UNKNOWN -> QUOTE_EXPIRED` | 报价锁定未知不是报价失效，必须查询供应商或转人工。 |
| `CORE_BOOKING_IN_PROGRESS -> CONFIRMED` | 核心项未全部成功时不能确认组合订单。 |
| `CORE_CONFIRMED -> FAILED` | 附加项失败不能覆盖核心成功事实。 |
| `SUPPLIER_CONFIRMED -> SUPPLIER_FAILED` | 失败回调不能覆盖已经确认的供应商成功事实。 |
| `CAPTURED -> VOIDED` | 已扣款资金不能释放授权，只能退款、冲正或人工处理。 |
| `VOIDED -> CAPTURED` | 已释放授权不能再扣款，必须重新创建授权。 |
| `REFUND_UNKNOWN -> REFUNDING` | 退款未知不能重复提交外部退款。 |
| `REFUNDED -> REFUND_FAILED` | 退款成功事实不能被迟到失败回调覆盖。 |
| `MATCHED -> CLOSED_WITHOUT_REPAIR` | 对账匹配不能替代需要修复的历史差异事实。 |
| `MANUAL_REVIEW -> FACT_OVERWRITTEN` | 人工处理不能改写历史事实，必须追加修复和审计记录。 |
