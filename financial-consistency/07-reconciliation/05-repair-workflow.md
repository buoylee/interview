# 05 修复闭环

## 目标

修复闭环的核心原则是：对账不能直接改平数据。所有修复都必须通过 Case、Repair Command、Repair Fact、Review 和 Close 留下证据。

## 标准流程

```text
DifferenceDetected
  -> CaseOpened
  -> EvidenceCaptured
  -> Classified
  -> RepairCommandCreated
  -> MakerApproved
  -> CheckerReviewed
  -> RepairExecuted
  -> RepairFactRecorded
  -> ReviewCompleted
  -> CaseClosed
```

## 自动修复

自动修复只适用于低风险、规则明确、幂等键完整的差异：

- 补记缺失的传播记录。
- 对重复 Case 做幂等合并。
- 对已确认重复消息生成重复处理记录。
- 对汇总报表缺失只能重新生成派生报表产物，不能把再生成结果当成 canonical fact。

自动修复必须输出 `repair_command_id`、幂等键、输入证据、执行结果和 Repair Fact。

报表再生成必须保留原始缺失或失败证据，只能基于已经对齐的不可变 source/domain/ledger/external facts 生成。再生成报表本身不能关闭 Case；只有源事实、领域事实、账本事实和外部事实已经互相解释，且 review 通过后，Case 才能按关闭原因关闭。

## 人工修复

人工修复适用于资金、账本、供应商不可逆事实、清结算和高风险状态差异：

- maker 提交修复建议和证据快照。
- checker 审核金额、事实来源、风险等级和修复命令。
- 执行修复后必须复核领域事实、账本事实、外部事实和人工事实。
- 复核失败必须重新打开 Case，不能关闭后再私下修数据。

## 禁止行为

- 对账 SQL 直接 update 业务状态。
- 删除原始账本分录来让报表平衡。
- 对已 capture 资金执行 void。
- 删除已出票、已确认供应商订单或已生效保险。
- 用人工备注替代 maker-checker、证据快照和复核结果。
- 修复命令没有幂等键，重复执行产生第二次资金效果。
- 关闭 Case 但没有关闭原因。

## 关闭原因

| 关闭原因 | 含义 | 必备证据 |
| --- | --- | --- |
| repaired | 已执行修复且复核通过 | Repair Fact、审批、复核结果 |
| external_late_fact_matched | 迟到外部事实到达并解释差异 | 外部 Statement、匹配记录 |
| no_repair_needed | 差异经 checker/review 批准后确认无需修复 | materiality、financial-impact 评估、reason code、owner、证据快照、data-quality defect 或 accepted-risk 记录链接 |
| long_term_suspended | 自动和人工都无法短期收敛 | 暴露金额、责任人、复核周期 |
| reopened | 关闭后被新事实推翻 | 新事实、重新打开原因 |

`no_repair_needed` 不可用于资金 movement，不可用于账本差异，不可用于清结算差异、供应商不可逆事实或仍未解决的 source mismatch。它只能关闭已经完成影响评估、责任归属和复核批准的低风险数据质量或接受风险差异。

## 输出结论

合格修复不是“状态改好了”，而是每个差异都能追溯到证据、命令、审批、执行、复核和关闭原因。对账系统本身必须比业务系统更重视可审计性。
