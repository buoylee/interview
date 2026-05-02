# 07 验证与审计

## 目标

对账系统也会产生风险。它可能重复生成 Case、重复执行 Repair、错误关闭差错、遗漏审批、让报表反向修改事实，或者在重跑时制造第二次资金效果。因此，对账系统本身也必须被验证和审计。

## 核心不变量

| 不变量 | 失败示例 | 验证方式 |
| --- | --- | --- |
| Difference 幂等 | 同一差异无限生成重复 Case | 固定匹配键和差异指纹 |
| CaseOpened 幂等 | 同一差异被多次打开成多个活跃 Case | 稳定 case_open_key 和 difference_fingerprint，唯一约束只允许一个打开结果 |
| CaseClosed 幂等 | 重复关闭导致多条关闭记录、重复通知或重复后续动作 | close_command_id 或 case_transition_id 去重，并校验 expected case version / state precondition |
| Repair 幂等 | 重复补账、重复退款、重复冲正 | repair_command_id 和业务唯一约束 |
| Close 可解释 | Case 关闭但无证据、修复或挂起原因 | Close 必须引用证据和 Review |
| 重跑安全 | 日终重跑或 T+N 重跑重复修复 | 重跑只能追加发现、重新分类或生成 reopen proposal，不得重新执行 Repair 或 Close 副作用 |
| 审计完整 | 人工修复缺操作者、审批或复核 | 审计链检查 |
| 报表只读 | 报表任务修改业务事实 | 报表权限和数据流验证 |

Case 状态迁移必须带前置条件：调用方提交 expected case version 和 state precondition，系统只在版本和状态同时匹配时写入 transition。重试或重跑遇到相同 close_command_id / case_transition_id 时只能返回既有结果，遇到旧版本或状态不匹配时只能产生可审计的拒绝记录。

## 异常 History

需要验证这些 History：

- 同一渠道账单重复导入。
- 同一 Difference 被准实时对账和日终对账同时发现。
- Repair Command 提交后进程宕机，然后重试。
- maker 审批通过后 checker 拒绝。
- Case 关闭后 T+N 迟到事实到达。
- 日终重跑覆盖已有 Case 状态。
- 报表生成任务读到未关闭 Case。
- 人工修复和自动修复并发。

## 审计字段

每个 Case 至少要能追踪：

- case_id、difference_fingerprint、classification、risk_level。
- evidence_snapshot、source_batch、statement_id、fact_ids。
- maker、checker、operator、review_result。
- repair_command_id、repair_fact_ids、idempotency_key。
- close_reason、closed_by、closed_at、reopen_reason。

每一次人工、自动、审批、修复、关闭和重开动作都要写入不可变 Action Record，不能只覆盖 Case 当前状态：

- run_id、batch_id、case_id、difference_fingerprint、case_open_key。
- maker_decision_id、maker_at、maker_result。
- checker_decision_id、checker_at、checker_result。
- operator_id、action、executed_at。
- repair_command_id、repair_created_at、repair_executed_at、repair_result。
- before_status、after_status、expected case version、state precondition。
- close_command_id、close_review_id、case_transition_id。
- reopened_by、reopened_at、reopen_evidence_id。

run_id / batch_id 用于把 Case、Difference、Repair、Close、Replay 和报表读取关联到一次对账运行或账单批次，支持审计时还原“谁在什么输入下做了什么动作”。

## 监控指标

- 新增 Case 数量和金额。
- P0/P1 暴露金额。
- unknown 年龄和长期挂起金额。
- 自动修复率、人工处理时长、复核失败率。
- 重开率、重复 Case 合并率、重跑差异数量。
- 渠道账单、供应商账单、清算文件延迟。
- 日终对账完成时间和失败批次。

## 与 06 验证实验室的连接

对账验证必须复用 06 的语言：History、Invariant、Oracle、Fault Injection 和 Replay。一次合格验证只能说明在已生成的对账 History 和不变量范围内没有发现不可解释事实，不能证明所有生产差异绝对安全。

## 输出结论

对账系统本身必须像资金系统一样被验证。它的成功标准不是 Case 数量归零，而是每个差异都能被事实、修复、审批、复核和关闭原因解释。
