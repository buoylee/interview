# 02 状态机

## 主状态

| 状态 | 含义 | 是否终态 |
|---|---|---|
| `REQUESTED` | 接收到转账请求，幂等记录已创建 | 否 |
| `RISK_CHECKED` | 风控检查通过 | 否 |
| `DEBIT_RESERVED` | 付款方资金已冻结 | 否 |
| `DEBIT_POSTED` | 付款方借记分录已入账 | 否 |
| `CREDIT_POSTED` | 收款方贷记分录已入账 | 否 |
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
DEBIT_POSTED -> CREDIT_POSTED -> SUCCEEDED
COMPENSATING -> MANUAL_REVIEW
```

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
