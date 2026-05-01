# 07 对账设计

## 为什么本阶段必须讲对账

外部渠道场景里，接口返回、回调、查询结果和账单可能互相不一致。对账不是后期补丁，而是发现渠道事实和本地事实分叉的核心链路。

## 渠道对账和账本对账

| 类型 | 关注点 | 主要输入 |
| --- | --- | --- |
| 渠道对账 | 渠道有没有这笔交易，状态、金额、币种、手续费和时间是否一致 | 渠道账单、本地支付单、渠道请求号、渠道交易号 |
| 账本对账 | 本地资金事实是否完整，账户流水和会计分录能否解释业务状态 | 本地支付单、账户流水、会计分录、Outbox 消费记录 |

## 差错分类

| 差错 | 含义 | owner | 修复方向 |
| --- | --- | --- | --- |
| 渠道成功，本地失败 | 渠道账单成功，本地未成功或缺少流水 | payment-service、account-service、ledger-service、event repair | 补状态、补账户流水、补分录、补事件 |
| 本地成功，渠道缺失 | 本地成功但渠道账单没有交易 | reconciliation-service、manual review | 进入人工复核，必要时冲正或客户沟通 |
| 渠道失败，本地成功 | 渠道失败但本地已入账或确认出款 | payment-service、account-service、ledger-service、manual review | 冲正、释放或人工修复 |
| 金额不一致 | 渠道金额、手续费、币种和本地不一致 | account-service、ledger-service、manual review | 差额分录、手续费调整、人工复核 |
| 重复入账 | 同一渠道事实产生多次账户入账 | account-service、ledger-service | 冲正重复流水，检查幂等缺陷 |
| 重复出款 | 同一提现产生多次渠道出款 | payment-service、account-service、manual review | 人工追回、反向入账、风险升级 |
| 分录缺失 | 账户流水存在但会计分录缺失 | ledger-service | 补分录 |
| 长时间未知状态 | 本地状态无法自动收敛 | reconciliation-service、payment-service、manual review | 查询、账单核验、人工复核 |
| 本地多记 | 本地账户流水或分录多于渠道事实 | account-service、ledger-service | 通过冲正或调整命令撤销多记事实 |
| 本地少记 | 渠道事实存在但本地账户流水或分录不足 | account-service、ledger-service、event repair | 补账户流水、补分录、补缺失事件 |
| 渠道多记 | 渠道账单存在重复扣款、重复入款或额外交易 | reconciliation-service、manual review | 生成差错单，发起渠道核验、退款或人工处理 |
| 渠道少记 | 本地请求存在但渠道账单缺少对应交易 | reconciliation-service、payment-service、manual review | 查询渠道，确认失败后冲正或进入客户沟通 |
| 状态不一致 | 渠道状态、支付单状态、账户流水状态或分录状态不一致 | payment-service、account-service、ledger-service | 按状态机补状态、补流水、补分录或冲正 |
| 渠道有交易但本地无订单 | 渠道账单有交易，但本地没有支付单、充值单或提现单 | reconciliation-service、manual review | 建立 unmatched 差错单，人工核验来源后补单或退款 |

## 修复路由

`reconciliation-service` 只负责分类、记录差错状态、创建修复命令或工单，并写入审计记录；它不直接修改账户余额、账户流水或会计分录。

- `payment-service`：修复支付单、充值单、提现单状态，或执行渠道查询和状态收敛。
- `account-service`：通过幂等命令补账户流水、冲正重复流水或做账户调整。
- `ledger-service`：追加会计分录、补缺失分录或追加冲正分录。
- `event repair`：补发缺失的 Outbox 事实，保证下游消费记录可追溯。
- `manual review`：处理高风险、金额不一致、重复出款、渠道缺单和无法自动判定的差错。

## 对账输入

- 渠道账单。
- 本地支付单、充值单、提现单。
- 渠道请求号和渠道交易号。
- 账户流水。
- 会计分录。
- Outbox 事件和消费记录。
- 回调记录和查询记录。

## 修复原则

- 不直接覆盖历史事实。
- 修复动作必须有幂等键。
- 自动修复必须留下审计记录。
- 高风险修复需要 maker-checker 或人工复核。
- 修复完成后必须重新对账。

## 对账输出

- `MATCHED`：渠道和本地事实一致。
- `MISMATCH_DETECTED`：发现差错。
- `REPAIR_REQUESTED`：已生成修复动作。
- `REPAIRED`：修复动作完成。
- `VERIFIED`：修复后复核通过。
