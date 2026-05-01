# 05 事件流

## 目标

事件流用于区分本地命令、渠道事实、账户事实、账本事实、对账事实和人工修复事实。只有明确事实来源，系统才能在超时、重复、乱序和部分成功之后恢复。

## 事件分类

| 类型 | 示例 | 事实 owner |
| --- | --- | --- |
| 本地命令 | `RechargeRequested`、`WithdrawRequested` | `payment-service` |
| 渠道事实 | `ChannelPaymentSucceeded`、`PayoutSucceeded` | `channel-adapter` / 渠道账单 |
| 账户事实 | `RechargeAccountCredited`、`WithdrawFreezeConsumed` | `account-service` |
| 账本事实 | `RechargeLedgerPosted`、`WithdrawLedgerPosted` | `ledger-service` |
| 回调事实 | `PaymentCallbackReceived`、`PaymentCallbackVerified`、`PaymentCallbackApplied` | `payment-service` |
| 对账事实 | `ChannelStatementImported`、`ChannelMismatchDetected` | `reconciliation-service` |
| 修复事实 | `ChannelRepairRequested`、`ManualRepairCompleted` | `reconciliation-service` / 运营复核 |

## 充值事件流

```text
RechargeRequested
-> ChannelPaymentInitiated
-> ChannelPaymentSucceeded
-> RechargeAccountCredited
-> RechargeLedgerPosted
-> RechargeSucceeded
```

异常分支：

```text
ChannelPaymentUnknown
-> channel query or callback
-> ChannelPaymentSucceeded or ChannelPaymentFailed or ManualReviewRequired
```

## 提现事件流

```text
WithdrawRequested
-> WithdrawRiskApproved
-> WithdrawFundsReserved
-> PayoutSubmitted
-> PayoutSucceeded
-> WithdrawFreezeConsumed
-> WithdrawLedgerPosted
-> WithdrawSucceeded
```

异常分支：

```text
PayoutUnknown
-> channel query or callback
-> PayoutSucceeded or PayoutFailed or ManualReviewRequired
```

## 回调事件流

```text
PaymentCallbackReceived
-> PaymentCallbackVerified
-> callback dedup check
-> PaymentCallbackApplied
-> downstream state transition
```

回调不能直接代表业务成功。它只是一个外部事实输入，必须经过验签、幂等和状态机判断。

## 对账事件流

```text
ChannelStatementImported
-> local order matched
-> account movement matched
-> ledger posting matched
-> matched or ChannelMismatchDetected
-> ChannelRepairRequested
-> ManualRepairCompleted
```

## 顺序依赖

- `RechargeAccountCredited` 依赖可信的 `ChannelPaymentSucceeded`。
- `RechargeLedgerPosted` 依赖 `RechargeAccountCredited`。
- `PayoutSubmitted` 依赖 `WithdrawFundsReserved`。
- `WithdrawFreezeConsumed` 依赖可信的 `PayoutSucceeded`。
- `WithdrawLedgerPosted` 依赖 `WithdrawFreezeConsumed`。
- `ManualRepairCompleted` 依赖差错分类和审批证据。

## Broker 不是事实来源

Kafka 或其他消息系统只负责投递语义。业务事实必须来自本地数据库记录、渠道事实、账户流水、会计分录和对账记录，不能用 consumer offset 证明入账、出款或对账已经完成。
