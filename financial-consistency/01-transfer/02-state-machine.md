# 02 状态机

## 主状态

| 状态 | 含义 | 是否终态 |
|---|---|---|
| `REQUESTED` | 接收到转账请求，幂等记录已创建 | 否 |
| `RISK_CHECKED` | 风控检查通过 | 否 |
| `DEBIT_RESERVED` | 付款方资金已冻结 | 否 |
| `DEBIT_POSTED` | 账户侧已消耗付款方冻结资金（`FreezeConsumed`），账务侧付款方借记分录已入账（`DebitPosted`） | 否 |
| `CREDIT_POSTED` | 账户侧已入账收款方账户（`AccountCredited`），账务侧收款方贷记分录已入账（`CreditPosted`），等待最终确认 | 否 |
| `SUCCEEDED` | 转账完成 | 是 |
| `FAILED` | 转账失败，未产生需要补偿的资金影响 | 是 |
| `COMPENSATING` | 正在执行补偿 | 否 |
| `COMPENSATED` | 补偿完成 | 是 |
| `MANUAL_REVIEW` | 自动恢复失败，需要人工处理 | 是 |

## 正常路径

```text
REQUESTED
-> RISK_CHECKED
-> DEBIT_RESERVED
-> DEBIT_POSTED
-> CREDIT_POSTED
-> SUCCEEDED
```

## 失败路径

```text
REQUESTED -> FAILED
RISK_CHECKED -> FAILED
DEBIT_RESERVED -> COMPENSATING -> COMPENSATED
DEBIT_POSTED -> COMPENSATING -> COMPENSATED
COMPENSATING -> MANUAL_REVIEW
```

## 恢复路径

```text
DEBIT_POSTED -> CREDIT_POSTED -> SUCCEEDED
CREDIT_POSTED -> SUCCEEDED
```

- `DEBIT_POSTED -> CREDIT_POSTED -> SUCCEEDED` 表示在部分进度之后继续重试到成功，不属于失败路径。
- `CREDIT_POSTED` 表示账户侧收款方已入账且账务侧收款方贷记分录已入账；此时应重试最终确认直到进入 `SUCCEEDED`，不能执行资金补偿，也不能静默失败。

## 允许跳转

| 当前状态 | 允许目标状态 | 说明 |
|---|---|---|
| `REQUESTED` | `RISK_CHECKED`, `FAILED` | 风控通过或请求前置校验失败 |
| `RISK_CHECKED` | `DEBIT_RESERVED`, `FAILED` | 冻结资金或后续校验失败 |
| `DEBIT_RESERVED` | `DEBIT_POSTED`, `COMPENSATING` | 借记入账或释放冻结资金 |
| `DEBIT_POSTED` | `CREDIT_POSTED`, `COMPENSATING` | 收款方账户入账并生成贷记分录；仅在贷记未发生且无法继续时补偿，例如贷记前置条件不可恢复地失败、贷记发生前收到明确取消，或在补偿策略下贷记重试耗尽 |
| `CREDIT_POSTED` | `SUCCEEDED` | 收款方账户与贷记分录均已入账，只能重试最终确认 |
| `COMPENSATING` | `COMPENSATED`, `MANUAL_REVIEW` | 补偿完成或自动补偿失败 |
| `SUCCEEDED` | 无 | 终态 |
| `FAILED` | 无 | 终态 |
| `COMPENSATED` | 无 | 终态 |
| `MANUAL_REVIEW` | 无 | 终态，除非通过人工修复流程产生新的修复交易 |

除上表列出的跳转外，其他状态跳转均为非法跳转。

非法跳转必须被拒绝或作为 no-op 处理，保持当前状态不变，并记录 audit、metric 与明确的错误原因；非法跳转不得被当作幂等成功处理。

## 非法跳转

- `SUCCEEDED -> FAILED`
- `FAILED -> SUCCEEDED`
- `COMPENSATED -> SUCCEEDED`
- `MANUAL_REVIEW -> SUCCEEDED`，除非通过人工修复流程产生新的修复交易。
- `REQUESTED -> CREDIT_POSTED`
- `DEBIT_RESERVED -> CREDIT_POSTED`

## 状态更新规则

- 状态更新必须带 `version` 或等价乐观锁。
- 重复消息只能重放当前状态允许的幂等结果。
- 迟到消息如果对应状态已经终结，必须被记录为 ignored 或 duplicate，不能推动状态倒退。
