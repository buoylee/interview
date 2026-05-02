# 02 对账数据源

## 目标

对账首先要回答哪些东西可以作为事实源，哪些只能作为执行线索。事实源可以参与判定 Difference；执行线索只能帮助定位问题。

## 可判定事实源

| 来源 | 典型事实 | 关键字段 | 常见风险 |
| --- | --- | --- | --- |
| 领域事实 | 订单、支付请求、退款请求、提现请求、供应商请求、售后单 | business_id、request_id、idempotency_key、state、version | 状态推进但账本或外部事实缺失 |
| 账户事实 | account movement、freeze、unfreeze、balance snapshot | account_id、movement_id、freeze_id、amount、balance_version、source_id | 余额快照无法被资金流水解释，冻结和解冻不成对 |
| 账本事实 | journal、posting、reversal、adjustment、日切批次 | ledger_id、journal_id、debit、credit、posting_date、source_id | 借贷不平、缺业务来源、重复分录 |
| 事件传播事实 | Outbox event、Inbox/dedup 接收记录、消费处理结果 | event_id、aggregate_id、business_id、event_type、producer_version、consumer_service、consumed_at、handler_result、source_fact_id | 事件已持久化但未被消费，消费结果无法关联来源事实 |
| 渠道事实 | 支付流水、退款流水、提现结果、渠道账单、手续费 | channel_request_id、channel_txn_id、amount、currency、status、settle_date | 回调成功本地 unknown，账单迟到 |
| 供应商事实 | 供应商订单、出票、酒店确认、保险生效、供应商账单 | supplier_request_id、supplier_order_id、confirmation_no、bill_id | 迟到成功、迟到失败、罚金不可解释 |
| 库存和订单事实 | 预留、确认、释放、发货、取消、售后 | order_id、reservation_id、shipment_id、sku_id、quantity | 库存双终态，已发货被取消覆盖 |
| 清结算事实 | 商户结算、平台手续费、供应商结算、资金划拨 | settlement_id、merchant_id、supplier_id、fee、net_amount | 汇总平但明细不可解释 |
| 人工事实 | Case、证据快照、审批、修复命令、复核、关闭原因 | case_id、operator、reviewer、evidence_id、reason | 人工修复缺审批或复核 |

## 辅助线索

日志、trace、workflow history、broker offset、consumer offset、任务实例和报表生成记录只能说明系统执行过某些动作。它们不能单独证明支付成功、退款成功、供应商确认、库存释放、ledger posting 完成或人工修复完成。

Outbox event、Inbox/dedup 接收记录和消费处理结果属于已持久化的事件传播事实；broker offset、consumer offset 和任务实例只是执行位置或运行记录，仍然只能作为辅助线索。

## 匹配键

- 业务单号：`transfer_id`、`payment_request_id`、`refund_request_id`、`order_id`、`trip_id`。
- 幂等键：`idempotency_key`、`channel_request_id`、`supplier_request_id`、`repair_command_id`、`event_id`。
- 外部流水：`channel_txn_id`、`supplier_order_id`、`settlement_id`。
- 账本和事件来源：`source_type`、`source_id`、`source_fact_id`、`ledger_batch_id`。
- 时间窗口：业务发生时间、外部账单时间、入账时间、日切批次、清算日期。

## 数据质量要求

- 每个事实源必须有来源系统、statement/batch/file id、覆盖时间窗口、采集时间、解析版本，以及 checksum、signature、hash 或行级明细证据。
- 每条外部或内部 Statement 必须保留原始证据、可追溯文件或行级明细证据。
- 账户余额快照必须能被 account movement、freeze 和 unfreeze 解释，不能用快照直接覆盖流水。
- 汇总对账不能替代明细对账。
- 报表只能读取事实和 Case 状态，不能反向修改事实。
- 任何缺字段导致无法匹配的记录必须进入 Difference 或数据质量 Case。

## 输出结论

对账数据源的底线是 Fact-first。真正能关闭差错的是可审计事实、修复事实、审批复核和关闭原因，不是日志、offset、workflow history 或报表展示。
