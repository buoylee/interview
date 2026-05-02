# 06 场景矩阵

## 目标

场景矩阵把统一对账模型落回真实业务。每个场景都必须说明事实源、匹配键、差错分类、自动修复路径、人工处理边界和不合格修复。

## 总览

| 场景 | 对账重点 | 典型差错 |
| --- | --- | --- |
| 内部转账 | account movement、ledger posting、冻结、扣减、入账、冲正、调整 | 借贷不平、入账缺失、重复冲正、账本与账户流水不一致 |
| 充值提现 | 渠道流水、回调、查询、账单、退款、提现、手续费 | 渠道成功本地 unknown、重复回调、退款 unknown、提现受理后本地释放资金 |
| 电商下单 | 订单、支付、库存、退款、发货、售后、商户结算 | 已支付未发货、库存释放重复、退款缺账本、结算金额不一致 |
| 旅行组合预订 | 供应商订单、出票、酒店确认、保险生效、罚金、补差、退款 | 供应商迟到成功、已出票后本地失败、已生效保险被取消覆盖 |

## 通用安全边界

- broker offset、consumer offset、workflow history、日志和任务运行记录只能作为排查线索，不能作为支付成功、ledger posting 完成、供应商确认或人工修复完成的证明。
- 对账修复只能追加事实、Repair Fact、冲正分录、调整分录、审批和关闭原因，不能删除不可逆事实或覆盖历史事实。
- `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN`、`REFUND_UNKNOWN` 和 `SUPPLIER_UNKNOWN` 不能被直接判失败；必须经过查询、账单、T+N 证据或长期挂起路径。
- 已 capture 资金不能 void；需要退款、应收、claim、补差或 fresh user-authorized payment flow 时，必须通过幂等命令和 maker-checker。
- 高风险资金、账本、清结算、供应商不可逆事实和外部可见修复必须进入 maker-checker，并保留证据快照、执行回执、复核和关闭原因。

## 内部转账

- 事实源：账户流水、account movement、ledger posting、冻结记录、扣减记录、入账记录、Outbox 事件、消费者处理记录、冲正和调整分录、人工审批。
- 匹配键：`transfer_id`、`ledger_source_id`、`source_id`、`account_id`、`idempotency_key`、`repair_command_id`。
- 差错分类：账本不平、本地少记、本地多记、重复业务效果、状态不一致、人工修复缺证据。
- 自动修复路径：对缺失传播记录重投 Outbox；对重复消息生成幂等处理记录；对可确认的读模型缺失执行重建；对无法自动闭合的差异生成 Case。
- 人工处理边界：补账、冲正、调整、关闭账本 Case、释放冻结资金、处理借贷不平和高风险金额差异必须 maker-checker。
- 不合格修复示例：删除原始账本分录；用 broker offset 证明入账完成；用 workflow history completion 证明转账成功；重复执行冲正；直接 update 账户余额让报表平衡。

## 充值提现

- 事实源：支付请求、提现请求、退款请求、渠道流水、渠道回调、渠道查询结果、渠道账单、手续费、清算文件、ledger posting、人工 Case。
- 匹配键：`payment_request_id`、`withdraw_request_id`、`refund_request_id`、`channel_request_id`、`channel_txn_id`、`settlement_id`、`ledger_source_id`。
- 差错分类：本地少记、本地多记、外部多扣、外部少扣、unknown 未收敛、重复业务效果、清结算差异、人工修复缺证据。
- 自动修复路径：渠道成功本地 unknown 或本地少记时，先固化渠道 Statement 和查询证据，再补记可审计领域事实和账本；重复回调只生成幂等处理记录；手续费低风险差异可生成结算差异 Case。
- 人工处理边界：退款 unknown、提现受理后本地释放资金、外部多扣、手续费差异、大额资金差异、清算文件与本地账本不一致必须人工复核；退款、结算调整和 ledger correction 必须 maker-checker。
- 不合格修复示例：把 `PAYMENT_UNKNOWN`、`WITHDRAW_UNKNOWN` 或 `REFUND_UNKNOWN` 直接判失败；重复退款；对已 capture 资金执行 void；无外部扣款或应付负债证据时发起退款；用渠道日志替代渠道账单或查询结果。

## 电商下单

- 事实源：订单、支付、退款、库存预留、库存确认、库存释放、发货、售后、商户结算、平台手续费、ledger posting、人工 Case。
- 匹配键：`order_id`、`payment_request_id`、`refund_request_id`、`reservation_id`、`shipment_id`、`settlement_id`、`sku_id`、`ledger_source_id`。
- 差错分类：状态不一致、外部少扣、外部多扣、退款缺账本、库存与订单不一致、重复业务效果、清结算差异、人工修复缺证据。
- 自动修复路径：幂等合并重复消息；重建订单、库存或结算读模型；对重复库存释放生成重复处理记录；对退款缺账本、商户结算差异或支付库存双边不一致生成 Case。
- 人工处理边界：已发货后取消、退款缺账本、库存释放重复且影响可售库存、商户结算差异、库存与资金双边不一致、售后和履约状态冲突必须人工复核；涉及退款、结算调整、库存赔付或 ledger correction 必须 maker-checker。
- 不合格修复示例：删除已发货事实；重复释放库存；用汇总报表覆盖明细差异；自动补扣用户资金；在没有退款回执和账本事实时关闭退款 Case；迟到失败覆盖已支付或已发货事实。

## 旅行组合预订

- 事实源：组合订单、子订单、供应商 request id、供应商订单、出票、酒店确认、保险生效、供应商账单、支付 capture、refund、罚金、补差、claim、人工审批。
- 匹配键：`trip_id`、`sub_item_id`、`supplier_request_id`、`supplier_order_id`、`payment_request_id`、`refund_request_id`、`confirmation_no`、`bill_id`。
- 差错分类：供应商迟到、unknown 未收敛、外部多扣、外部少扣、状态不一致、清结算差异、人工修复缺证据。
- 自动修复路径：记录迟到供应商事实；把供应商账单、出票、酒店确认或已生效保险关联到本地子订单；生成 Case；重建组合订单读模型；对低风险重复通知生成幂等处理记录。
- 人工处理边界：已出票后酒店失败、保险已生效后取消、供应商迟到成功与本地失败冲突、罚金补差、供应商账单与本地策略冲突、外部少扣但存在不可逆履约事实时必须人工复核；退款、补差、claim、应收核销和高风险供应商修复必须 maker-checker。
- 不合格修复示例：删除已出票事实；删除已生效保险；用 workflow history completion 证明供应商确认；把 `SUPPLIER_UNKNOWN` 直接判失败；用本地取消覆盖供应商已确认订单；在已出票或已生效保险后直接 void 已 capture 资金。

## 输出结论

统一对账矩阵的价值是让每个业务场景都能回答同一组问题：事实从哪里来、用什么键匹配、差错属于哪类、能否自动修复、何时必须人工审批、哪些修复方式绝对不允许。
