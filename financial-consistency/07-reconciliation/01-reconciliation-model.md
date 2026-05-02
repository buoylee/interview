# 01 对账模型

## 目标

统一对账语言。对账不是两张表相减，也不是发现差异后直接改数据；对账是一组从 Difference 到 Case、Repair、Review、Close 的事实闭环。

## 核心对象

| 对象 | 含义 | 示例 | 验证重点 |
| --- | --- | --- | --- |
| Fact | 已经持久化、可审计的业务或资金事实 | 支付单、账本分录、供应商订单、库存流水、人工审批 | 是否可信、可追溯、不可随意删除 |
| Statement | 外部或内部对账来源给出的陈述 | 渠道账单、供应商账单、清算文件、库存快照 | 是否有来源、批次、时间窗口和签名或校验 |
| Difference | Fact 与 Statement 或 Fact 之间的差异 | 渠道成功但本地 unknown、账本借贷不平 | 是否能定位业务单、金额、状态和责任边界 |
| Case | 差错工单 | `CASE_PAYMENT_LOCAL_MISSING` | 是否有分类、证据、风险等级和状态机 |
| Repair | 修复命令和修复事实 | 补记账本、退款、冲正、调整、补差、罚金 | 是否幂等，是否追加事实 |
| Review | 审批和复核 | maker-checker 审批、复核失败、重新打开 | 是否有人、时间、证据和意见 |
| Close | 关闭事实 | 已修复关闭、无需修复关闭、长期挂起 | 是否有关闭原因和可审计证据 |

## 状态流

```text
DifferenceDetected
  -> CaseOpened
  -> Classified
  -> RepairProposed
  -> RiskAssessed
  -> AutoRepairAllowed -> RepairExecuted -> RepairVerified
  -> ReviewRequired -> MakerApproved -> CheckerApproved -> RepairExecuted -> RepairVerified
  -> ReviewRejected -> RepairProposed / Reopened
  -> CloseProposed
  -> Closed / Reopened / LongTermSuspended
```

## 不可变边界

- 对账不能删除或覆盖历史 Fact。
- 对账不能用 Statement 直接覆盖本地事实，也不能用本地状态覆盖外部事实。
- 对账不能把 `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 或 `SUPPLIER_UNKNOWN` 直接判失败。
- 对账不能用日志、workflow history、broker offset、consumer offset 或任务运行记录替代业务事实。
- Repair 必须追加 Repair Fact，并能被 Review 和 Close 解释。
- 高风险资金修复必须经过 maker-checker。

## 合格输出

一次合格对账输出的不是“数据已改平”，而是：差异是什么、证据是什么、分类是什么、谁审批、执行了什么修复、生成了哪些新事实、复核结果是什么、为什么可以关闭。
