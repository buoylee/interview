# 03 状态机

## 设计原则

状态机的任务是防止外部渠道的不确定性污染本地资金事实。所有状态推进都必须基于耐久事实，不能只基于一次 RPC 返回值。

## 充值单状态

```text
CREATED
-> CHANNEL_PENDING
-> CHANNEL_UNKNOWN
-> CHANNEL_SUCCEEDED
-> ACCOUNT_CREDITED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
CHANNEL_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `CHANNEL_UNKNOWN` 只能通过查询、回调、账单或人工处理继续推进。
- `CHANNEL_SUCCEEDED` 之后必须补齐账户入账和分录。
- `SUCCEEDED` 不能被失败回调覆盖。
- `ACCOUNT_CREDITED` 但缺少 `LEDGER_POSTED` 时，修复方向是补分录，不是回滚入账。

## 提现单状态

```text
CREATED
-> RISK_APPROVED
-> FUNDS_RESERVED
-> PAYOUT_SUBMITTED
-> PAYOUT_UNKNOWN
-> PAYOUT_SUCCEEDED
-> FREEZE_CONSUMED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
RISK_REJECTED
PAYOUT_FAILED
FUNDS_RELEASED
FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `PAYOUT_SUBMITTED` 之后出现超时必须进入 `PAYOUT_UNKNOWN`，不能直接进入失败。
- `PAYOUT_UNKNOWN` 不能再次提交新的出款动作，只能查询、等待回调或人工处理。
- `PAYOUT_FAILED` 后必须释放冻结，进入 `FUNDS_RELEASED` 后才能失败终结。
- `PAYOUT_SUCCEEDED` 后必须消耗冻结和记分录。

## 回调处理状态

```text
RECEIVED
-> VERIFIED
-> DEDUPED
-> APPLIED
```

异常状态：

```text
SIGNATURE_INVALID
DUPLICATE
STALE
CONFLICT
IGNORED
MANUAL_REVIEW
```

关键规则：

- `SIGNATURE_INVALID` 不能推进业务状态。
- `DUPLICATE` 返回既有处理结果，不重复执行业务动作。
- `STALE` 表示回调事实落后于本地更可信终态。
- `CONFLICT` 表示回调和本地或查询事实冲突，必须进入差错处理。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `CHANNEL_UNKNOWN -> CHANNEL_FAILED` | 超时不是失败，必须查询事实或等待回调。 |
| `PAYOUT_UNKNOWN -> FUNDS_RELEASED` | 未知出款不能释放冻结，否则可能造成用户拿到钱且余额恢复。 |
| `SUCCEEDED -> CHANNEL_FAILED` | 失败回调不能覆盖已确认成功终态。 |
| `PAYOUT_SUCCEEDED -> PAYOUT_SUBMITTED` | 出款成功后不能重新提交出款。 |
| `ACCOUNT_CREDITED -> CHANNEL_FAILED` | 已入账后发现冲突必须走差错或冲正，不允许简单改失败。 |
