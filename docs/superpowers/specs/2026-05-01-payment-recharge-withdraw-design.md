# 02 支付、充值、提现与外部渠道一致性设计

日期：2026-05-01

## 目标

创建 `financial-consistency/02-payment-recharge-withdraw/`，把学习主线从内部转账推进到外部支付渠道。

这个阶段的核心不是“接一个支付 API”，而是理解外部系统不参与我们的数据库事务时，系统如何处理充值、提现、支付回调、渠道超时、未知状态、查询补偿、渠道对账和人工修复。

完成后，学习者应该能解释：

- 为什么接口超时不能直接当失败。
- 为什么回调不是唯一事实来源。
- 为什么查询补偿和渠道对账是状态收敛手段。
- 为什么充值成功必须最终落到账户流水和会计分录。
- 为什么提现必须先冻结资金，再等待外部出款事实。
- 为什么渠道成功、本地失败和本地成功、渠道失败是两类不同差错。

## 背景

`01-transfer` 已经建立了内部资金系统的基础：

- 账户余额、冻结、扣减、入账。
- 会计分录和资金守恒。
- 幂等、状态机、Outbox、补偿和对账。
- 用不变量、故障注入和对账验证正确性。

`02-payment-recharge-withdraw` 在此基础上新增一个关键变量：外部渠道。

外部渠道包括支付机构、银行、出款通道或模拟第三方系统。它们默认不可控：

- 不参与我们的本地事务。
- 请求可能成功但响应超时。
- 请求可能失败但稍后回调成功。
- 回调可能重复、乱序、伪造或延迟。
- 渠道账单可能和本地状态不一致。

## 范围

第一版覆盖 5 个核心场景：

1. 充值。
2. 提现。
3. 支付回调。
4. 外部渠道超时或未知状态。
5. 渠道对账。

这 5 个场景构成外部渠道一致性的最小闭环：

```text
本地订单
-> 外部渠道请求
-> 回调或查询补偿
-> 账户流水
-> 会计分录
-> Outbox 事件
-> 渠道对账
-> 差错修复
```

## 非目标

第一版不覆盖：

- 预授权、Capture、Void。
- ACH、Direct Debit、银行代扣。
- 订阅扣费和自动续费。
- 商户分账、佣金和日终批量出款。
- 贷款还款和利息计提。
- 真实第三方支付渠道 SDK 集成。
- 真实密钥、签名证书和监管报送。

这些场景已经放入 `00-scenario-matrix.md` 的高价值扩展区，后续可单独展开。

## 目录设计

新增目录：

```text
financial-consistency/02-payment-recharge-withdraw/
```

新增文件：

```text
README.md
01-scenario-cards.md
02-invariants.md
03-state-machine.md
04-service-boundaries.md
05-event-flow.md
06-failure-matrix.md
07-reconciliation.md
08-verification-plan.md
09-interview-synthesis.md
```

文件职责：

- `README.md`：模块入口、学习目标、学习顺序和核心问题。
- `01-scenario-cards.md`：充值、提现、支付回调、渠道未知状态、渠道对账的场景卡。
- `02-invariants.md`：外部渠道资金链路必须满足的不变量。
- `03-state-machine.md`：充值单、提现单、渠道请求、回调处理和差错单状态机。
- `04-service-boundaries.md`：payment-service、account-service、ledger-service、channel-adapter、reconciliation-service 的职责边界。
- `05-event-flow.md`：本地命令、渠道事实、Outbox 事件和消费依赖。
- `06-failure-matrix.md`：超时、重复、乱序、部分成功、渠道差错和人工修复路径。
- `07-reconciliation.md`：渠道账单、本地订单、账户流水和会计分录如何对账。
- `08-verification-plan.md`：模型验证、属性测试、集成测试、故障注入和历史检查。
- `09-interview-synthesis.md`：面试和架构评审表达。

## 场景卡

第一版必须包含 5 张场景卡。

### 充值

场景边界：

- 用户发起充值。
- 系统创建充值单并调用支付渠道。
- 渠道确认成功后，本地给账户入账并生成会计分录。
- 充值最终进入成功、失败、未知或人工处理状态。

核心风险：

- 渠道成功但本地入账失败。
- 回调重复导致重复入账。
- 查询成功和回调成功同时到达。
- 本地状态成功但渠道账单不存在。

### 提现

场景边界：

- 用户发起提现。
- 系统冻结用户可用余额。
- 系统提交出款请求到银行或出款渠道。
- 渠道成功后消耗冻结并记账；渠道失败后释放冻结。

核心风险：

- 出款请求超时，但渠道实际成功。
- 重试造成重复出款。
- 冻结金额长期悬挂。
- 银行成功但本地状态未推进。

### 支付回调

场景边界：

- 渠道异步通知支付、充值或提现结果。
- 系统验签、幂等识别、状态推进和事件发布。
- 回调只能推进到合法状态，不能覆盖更可信的终态。

核心风险：

- 回调重复。
- 回调乱序。
- 伪造回调。
- 失败回调晚于成功事实。

### 外部渠道超时或未知状态

场景边界：

- 本地向渠道发起请求。
- 请求没有返回确定结果。
- 系统进入 `UNKNOWN` 或等价状态。
- 后续通过查询、回调、渠道账单或人工处理收敛。

核心风险：

- 把超时当失败。
- 在未知状态下重复提交外部请求。
- 未知状态长期悬挂。
- 查询结果和回调结果冲突。

### 渠道对账

场景边界：

- 系统导入渠道账单。
- 对比本地订单、账户流水、会计分录和渠道流水。
- 识别本地多记、本地少记、渠道多记、渠道少记、金额不一致和状态不一致。
- 生成差错单和修复路径。

核心风险：

- 对账只比较订单状态，不比较账户流水和分录。
- 差错修复直接改历史记录。
- 对账发现问题但没有 owner、状态和审计链。

## 服务边界

第一版采用这些逻辑服务：

- `payment-service`：充值单、提现单、支付单、渠道请求、回调幂等、渠道状态机。
- `channel-adapter`：封装外部渠道调用、验签、查询、账单导入和渠道幂等号。
- `account-service`：账户入账、提现冻结、冻结释放、冻结消耗和账户流水。
- `ledger-service`：充值、提现、退款式冲正和差错修复的会计分录。
- `reconciliation-service`：渠道账单对账、差错分类、修复工单。
- `message-broker`：Outbox 事件发布和下游消费。
- `risk-service`：提现前风险检查、限额和风控拒绝。

关键边界：

- `payment-service` 不直接改账户余额。
- `channel-adapter` 不拥有业务终态，只提供渠道事实。
- `account-service` 不决定渠道是否成功，只根据已确认命令处理账户变化。
- `ledger-service` 不覆盖历史分录，只追加分录或冲正分录。
- `reconciliation-service` 不静默修钱，必须生成差错记录、修复动作和审计证据。

## 正确性不变量

第一版至少定义这些不变量：

- 同一业务幂等键只能产生一次充值入账、一次提现出款或一次回调业务效果。
- 充值成功必须有渠道成功事实、账户入账流水和贷记分录。
- 提现成功必须有冻结消耗、渠道出款成功事实和借记分录。
- 提现失败必须释放冻结，不能既释放冻结又成功出款。
- `UNKNOWN` 不是失败，不能直接触发释放、退款或重复提交。
- 渠道回调不能把成功终态覆盖成失败终态。
- 渠道账单、本地支付单、账户流水和会计分录最终必须能对账。
- 差错修复必须通过补流水、补分录、冲正、补事件或人工工单完成，不能直接覆盖历史事实。

## 状态模型

### 充值单

核心状态：

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

### 提现单

核心状态：

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

### 回调处理

核心状态：

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

## 事件模型

第一版至少定义这些耐久事实和事件：

- `RechargeRequested`
- `ChannelPaymentInitiated`
- `ChannelPaymentUnknown`
- `ChannelPaymentSucceeded`
- `ChannelPaymentFailed`
- `RechargeAccountCredited`
- `RechargeLedgerPosted`
- `WithdrawRequested`
- `WithdrawRiskApproved`
- `WithdrawFundsReserved`
- `PayoutSubmitted`
- `PayoutUnknown`
- `PayoutSucceeded`
- `PayoutFailed`
- `WithdrawFreezeConsumed`
- `WithdrawFundsReleased`
- `WithdrawLedgerPosted`
- `PaymentCallbackReceived`
- `PaymentCallbackVerified`
- `PaymentCallbackApplied`
- `ChannelStatementImported`
- `ChannelMismatchDetected`
- `ChannelRepairRequested`
- `ManualRepairCompleted`

这些事件要区分：

- 本地命令。
- 渠道事实。
- 账户事实。
- 账本事实。
- 对账事实。
- 人工修复事实。

## 失败矩阵

第一版失败矩阵至少覆盖：

- 调用渠道前本地事务失败。
- 调用渠道成功但响应超时。
- 调用渠道失败但稍后收到成功回调。
- 回调重复。
- 回调乱序。
- 回调验签失败。
- 查询结果和回调结果冲突。
- 充值渠道成功但账户入账失败。
- 充值账户入账成功但分录失败。
- 提现冻结成功但出款提交失败。
- 提现出款成功但本地状态未推进。
- 提现出款失败但冻结未释放。
- Outbox 事件发布失败。
- 消费者重复消费。
- 渠道账单和本地订单不一致。
- 人工修复动作失败或重复提交。

## 对账设计

`07-reconciliation.md` 必须解释渠道对账和账本对账的区别。

渠道对账关注：

- 渠道流水是否存在。
- 渠道状态是否和本地订单一致。
- 渠道金额、币种、手续费是否一致。
- 渠道交易时间和本地交易时间如何匹配。

账本对账关注：

- 账户流水是否存在。
- 会计分录是否存在。
- 分录方向和金额是否正确。
- 本地状态是否能由流水和分录解释。

差错分类至少包括：

- 渠道成功，本地失败。
- 本地成功，渠道缺失。
- 渠道失败，本地成功。
- 金额不一致。
- 重复入账。
- 重复出款。
- 分录缺失。
- 长时间未知状态。

## 验证设计

验证路线必须覆盖：

- 状态机模型验证：`UNKNOWN` 不能直接变成失败补偿，成功终态不能被失败回调覆盖。
- 属性测试：随机生成回调重复、查询补偿、提现重试和渠道未知序列。
- 集成测试：真实数据库事务、Outbox、consumer dedup 和 channel-adapter fake。
- 故障注入：渠道超时、回调重复、回调乱序、DB 失败、Outbox 发布失败、消费者崩溃。
- 历史检查：检查最终充值、提现、渠道账单和分录是否满足不变量。
- 对账验证：用构造账单验证每类差错都能被分类。

## 面试表达

`09-interview-synthesis.md` 应该帮助学习者回答：

- 支付回调重复怎么办？
- 支付接口超时怎么办？
- 充值成功但本地没入账怎么办？
- 提现请求超时能不能重试？
- 渠道成功、本地失败如何处理？
- 本地成功、渠道失败如何处理？
- 为什么不能只看回调？
- 为什么对账不是补丁？
- Temporal 在这类场景里解决什么，不解决什么？

## README 更新

`financial-consistency/README.md` 中的 `02-payment-recharge-withdraw` 应该变成链接：

```markdown
- [02-payment-recharge-withdraw](./02-payment-recharge-withdraw/README.md)
  充值、提现、支付回调、渠道超时、渠道对账。
```

正式设计文档列表需要加入：

```markdown
- [2026-05-01-payment-recharge-withdraw-design.md](../docs/superpowers/specs/2026-05-01-payment-recharge-withdraw-design.md)
```

## 验收标准

完成后应满足：

- 新增 `financial-consistency/02-payment-recharge-withdraw/`。
- 新增 10 个模块文件。
- 每个文件都有清晰标题和职责。
- README 学习顺序能链接到 9 个子文档。
- 场景卡覆盖充值、提现、支付回调、外部渠道未知状态、渠道对账。
- 不变量、状态机、事件流、失败矩阵、对账和验证路线彼此一致。
- `financial-consistency/README.md` 链接到 `02-payment-recharge-withdraw/README.md`。
- 不修改 `01-transfer` 内容。
- 文档完整、无含糊要求、无空白格式问题。

## 后续工作

设计确认后，进入实施计划：

1. 创建 `02-payment-recharge-withdraw/README.md`。
2. 创建场景卡。
3. 创建不变量文档。
4. 创建状态机文档。
5. 创建服务边界文档。
6. 创建事件流文档。
7. 创建失败矩阵文档。
8. 创建对账文档。
9. 创建验证路线文档。
10. 创建面试表达文档。
11. 更新总 README。
12. 验证链接、完整性扫描和格式。
