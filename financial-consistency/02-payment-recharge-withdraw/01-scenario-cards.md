# 01 场景卡

## 目的

本文件先定义业务边界，再讨论一致性方案。每张场景卡都回答：链路从哪里开始，成功目标是什么，哪些事实必须持久化，哪些失败最危险。

## 充值

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户发起充值；系统创建充值单并调用支付渠道；渠道确认成功后，本地给账户入账并生成会计分录；充值最终进入成功、失败、未知或人工处理状态。 |
| 参与方 | 用户、payment-service、channel-adapter、account-service、ledger-service、reconciliation-service、message-broker。 |
| 核心状态机 | 成功路径：`CREATED -> CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED -> ACCOUNT_CREDITED -> LEDGER_POSTED -> SUCCEEDED`；失败或差错分支：`CHANNEL_FAILED -> FAILED`，`CHANNEL_UNKNOWN -> MANUAL_REVIEW`，`CHANNEL_SUCCEEDED -> RECONCILIATION_REQUIRED`。 |
| 正确性不变量 | 同一充值单不能重复入账；成功充值必须同时有渠道成功事实、账户入账流水和贷记分录。 |
| 关键命令和事件 | `RechargeRequested`、`ChannelPaymentInitiated`、`ChannelPaymentSucceeded`、`RechargeAccountCredited`、`RechargeLedgerPosted`。 |
| 耐久事实 | 充值单、渠道请求号、渠道交易号、账户流水、会计分录、Outbox 事件。 |
| 最危险失败点 | 渠道成功但本地入账失败；回调重复导致重复入账；查询成功和回调成功同时到达；本地状态成功但渠道账单不存在。 |
| 补偿方式 | 未入账时补入账；已重复入账时冲正；渠道缺失时进入差错处理；无法自动判断时进入人工复核。 |
| 对账来源 | 渠道账单、本地充值单、账户流水、会计分录、Outbox 消费记录。 |
| 验证方式 | 幂等测试、重复回调测试、渠道超时故障注入、渠道账单差错构造、账户和账本交叉对账。 |

## 提现

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 用户发起提现；系统冻结用户可用余额；系统提交出款请求到银行或出款渠道；渠道成功后消耗冻结并记账；渠道失败后释放冻结。 |
| 参与方 | 用户、payment-service、risk-service、channel-adapter、account-service、ledger-service、reconciliation-service、message-broker。 |
| 核心状态机 | 成功路径：`CREATED -> RISK_APPROVED -> FUNDS_RESERVED -> PAYOUT_SUBMITTED -> PAYOUT_UNKNOWN -> PAYOUT_SUCCEEDED -> FREEZE_CONSUMED -> LEDGER_POSTED -> SUCCEEDED`；失败或释放分支：`PAYOUT_FAILED -> FUNDS_RELEASED -> FAILED`，`PAYOUT_UNKNOWN -> MANUAL_REVIEW`。 |
| 正确性不变量 | 同一提现单不能重复出款；提现成功必须消耗冻结；提现失败必须释放冻结；不能既释放冻结又确认出款成功。 |
| 关键命令和事件 | `WithdrawRequested`、`WithdrawRiskApproved`、`WithdrawFundsReserved`、`PayoutSubmitted`、`PayoutSucceeded`、`WithdrawFreezeConsumed`、`WithdrawLedgerPosted`。 |
| 耐久事实 | 提现单、风控结果、冻结记录、渠道出款请求号、渠道出款流水、冻结消耗流水、借记分录、Outbox 事件。 |
| 最危险失败点 | 出款请求超时但渠道实际成功；重试造成重复出款；冻结金额长期悬挂；银行成功但本地状态未推进。 |
| 补偿方式 | 渠道失败释放冻结；渠道成功但本地未推进时补消耗冻结和分录；重复出款进入人工追回或反向入账；长期未知进入人工复核。 |
| 对账来源 | 银行出款文件、提现单、冻结流水、账户流水、会计分录、差错单。 |
| 验证方式 | 重复提交测试、渠道未知状态模型检查、冻结最终态扫描、出款账单对账。 |

## 支付回调

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 渠道异步通知支付、充值或提现结果；系统验签、幂等识别、状态推进和事件发布；回调只能推进到合法状态，不能覆盖更可信的终态。 |
| 参与方 | channel-adapter、payment-service、account-service、ledger-service、message-broker。 |
| 核心状态机 | `RECEIVED -> VERIFIED -> DEDUPED -> APPLIED`，异常进入 `SIGNATURE_INVALID`、`DUPLICATE`、`STALE`、`CONFLICT`、`IGNORED` 或 `MANUAL_REVIEW`。 |
| 正确性不变量 | 重复回调只有一次业务效果；验签失败不能改变业务状态；失败回调不能覆盖已经确认的成功终态。 |
| 关键命令和事件 | `PaymentCallbackReceived`、`PaymentCallbackVerified`、`PaymentCallbackApplied`。 |
| 耐久事实 | 回调原文、验签结果、回调幂等记录、状态推进记录、Outbox 事件。 |
| 最危险失败点 | 回调重复、乱序、伪造、延迟；查询结果和回调结果冲突。 |
| 补偿方式 | 重复回调直接返回已处理结果；乱序回调按状态机忽略或进入冲突处理；伪造回调拒绝并审计；冲突事实进入人工复核。 |
| 对账来源 | 回调记录、渠道查询结果、渠道账单、本地订单状态、账户流水、会计分录。 |
| 验证方式 | 重复回调故障注入、乱序回调模型测试、验签失败测试、终态覆盖保护测试。 |

## 外部渠道超时或未知状态

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 本地向渠道发起请求；请求没有返回确定结果；系统进入 `UNKNOWN` 或等价状态；后续通过查询、回调、渠道账单或人工处理收敛。 |
| 参与方 | payment-service、channel-adapter、reconciliation-service、运营人员。 |
| 核心状态机 | `CHANNEL_PENDING -> CHANNEL_UNKNOWN -> CHANNEL_SUCCEEDED` 或 `CHANNEL_FAILED`，长时间无法收敛进入 `MANUAL_REVIEW`。 |
| 正确性不变量 | `UNKNOWN` 不是失败；未知状态不能直接释放、退款或重复提交外部动作；重复查询不能产生新的渠道交易。 |
| 关键命令和事件 | `ChannelPaymentUnknown`、`PayoutUnknown`、渠道查询命令、查询结果事实、人工复核事件。 |
| 耐久事实 | 渠道请求号、本地请求状态、查询请求、查询结果、回调事实、人工处理记录。 |
| 最危险失败点 | 把超时当失败；未知状态下重复提交外部请求；未知状态长期悬挂；查询结果和回调结果冲突。 |
| 补偿方式 | 定时查询补偿；根据渠道事实推进状态；长期未知升级人工复核；冲突事实进入差错单。 |
| 对账来源 | 渠道查询结果、渠道账单、本地订单、回调记录、差错单。 |
| 验证方式 | 超时故障注入、重复查询测试、未知状态 aging 扫描、查询回调冲突测试。 |

## 渠道对账

| 字段 | 内容 |
| --- | --- |
| 场景边界 | 系统导入渠道账单；对比本地订单、账户流水、会计分录和渠道流水；识别本地多记、本地少记、渠道多记、渠道少记、金额不一致和状态不一致；生成差错单和修复路径。 |
| 参与方 | reconciliation-service、payment-service、account-service、ledger-service、channel-adapter、运营人员。 |
| 核心状态机 | `STATEMENT_IMPORTED -> MATCHED` 或 `MISMATCH_DETECTED -> REPAIR_REQUESTED -> REPAIRED -> VERIFIED`。 |
| 正确性不变量 | 对账差异必须有分类、owner、修复动作和审计记录；修复不能直接覆盖历史事实。 |
| 关键命令和事件 | `ChannelStatementImported`、`ChannelMismatchDetected`、`ChannelRepairRequested`、`ManualRepairCompleted`。 |
| 耐久事实 | 渠道账单、匹配结果、差错单、修复动作、复核记录。 |
| 最危险失败点 | 只比较订单状态，不比较账户流水和分录；差错修复直接改历史记录；发现问题但没有 owner、状态和审计链。 |
| 补偿方式 | 补流水、补分录、冲正、补事件、人工复核和客户赔付。 |
| 对账来源 | 渠道账单、本地订单、账户流水、会计分录、Outbox 消费记录。 |
| 验证方式 | 构造差异账单、分类准确性测试、修复后不变量检查、审计记录检查。 |
