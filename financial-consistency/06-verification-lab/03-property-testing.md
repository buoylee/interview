# 03 属性测试

## 目标

属性测试的重点不是随机生成字段值，而是随机生成异常 History。金融级属性测试要让重复请求、重复消息、回调乱序、外部超时、宕机恢复、TCC 乱序、Activity 重试、CDC 重放、补偿失败、对账差错和人工修复组合出现，然后检查不变量是否仍然成立。

换句话说，属性测试不是问“金额字段随机成 17.31 会不会报错”，而是问“一段异常 History 结束后，留下的 Fact 是否还能被状态机、幂等、账本、外部事实、对账和人工修复解释”。

属性测试不能穷尽所有异常历史，也不能证明系统绝对正确。它的价值是用系统化生成器扩大异常 History 覆盖范围，在已生成的 History 和已定义的不变量范围内降低不可解释事实出现的风险。

## 生成器模型

| 生成器 | 输入 | 可能制造的风险 | 主要不变量 |
| --- | --- | --- | --- |
| Command duplication | 相同业务幂等键、业务单号或 request id 重复提交 | 重复扣款、重复退款、重复出票、重复冻结或重复记账 | 幂等、账本、状态机 |
| Message duplication | 相同 event id 或业务事件重复投递 | 消费者重复处理，下游副作用重复 | 消费者、幂等、账本 |
| Callback reordering | 成功、失败、处理中、unknown 回调按非真实业务顺序到达 | 成功被迟到失败覆盖，终态被倒退 | 状态机、外部未知 |
| Timeout then success | 请求超时后外部系统实际成功，成功回调或查询结果迟到 | 本地失败和外部成功分叉，重试造成重复外部副作用 | 外部事实、对账、幂等 |
| Crash after commit | 本地事务提交后、Outbox 发布前或消费者处理记录写入前进程宕机 | 本地 Fact 存在但传播中断，或副作用成功但幂等记录缺失 | Outbox、消费者、账本 |
| TCC disorder | Cancel 先于 Try，Confirm/Cancel 并发，Confirm 或 Cancel 重复 | 空回滚、悬挂、Confirm/Cancel 双终态 | TCC、状态机 |
| Activity retry | 外部副作用成功但 Activity completion 未记录，工作流引擎重试 Activity | Temporal retry 或任务重试重复调用外部系统 | 幂等、外部事实、账本 |
| CDC replay | CDC offset 回退、重复捕获、旧事件重放或投影重建 | 读模型重复、倒退，消费者重复副作用 | CDC、消费者、状态机 |
| Manual repair replay | 人工修复命令、审批或冲正重复提交 | 重复冲正、重复补分录、修复 Fact 不可解释 | 人工修复、账本、对账 |

生成器输出的不是单个随机对象，而是一段由 Command、Event、Fact、Fault 和人工动作组成的 History。每个生成器都应该能说明它主要挑战哪类不变量，以及失败时应该由哪个 oracle 定位边界缺口。

## History 生成步骤

```text
1. 选择场景：internal transfer / payment / ecommerce order / travel booking
2. 生成初始 Fact：账户、余额、冻结、订单、库存、支付请求、供应商请求、对账批次
3. 生成正常 Command 序列：创建、确认、取消、查询、补偿、修复
4. 插入异常 History 片段：重复、乱序、超时、宕机、迟到回调、重放、人工修复
5. 执行业务状态迁移模型，记录每一步产生的 Fact
6. 用状态机 oracle、资金 oracle 和外部事实 oracle 检查不变量
7. 如果发现反例，输出可复现的失败种子、被破坏的不变量和缩小后的失败 History
```

生成时要刻意提高危险组合的出现概率，例如“Timeout then success + Command duplication”、“Crash after commit + Message duplication”、“TCC disorder + Callback reordering”、“Activity retry + 外部成功但本地 unknown”、“CDC replay + 已关闭对账批次”。这些组合比随机金额、随机字符串或随机枚举值更接近真实一致性事故。

如果一轮属性测试没有发现反例，输出不应该伪造失败 History，而应该报告生成器范围、seed 区间或 seed 数量、History 长度上下界、覆盖的 Invariant 和 oracle。这样的通过结果只说明在这组生成范围内没有发现不可解释事实。

## Shrinking 思路

Shrinking 的目标是把失败 History 缩小到更小、更容易解释、仍能触发同类不变量破坏的 reduced History。它通常只能给出局部最小或足够小的反例，不保证找到全局最短 History。它不应该只删除字段，而应该删除无关的 Command、Event、Fact、Fault 和人工动作，直到剩下的 History 足以解释问题。

例如，一个完整失败 History 可能包含创建订单、支付、库存确认、通知、对账和人工修复。但如果真正破坏的是外部 unknown 被本地失败覆盖，缩小后的失败 History 可能收敛为：

```text
1. Command: CapturePayment(payment_request_id=P100)
2. Fault: ChannelTimeout(P100)
3. Fact: PaymentMarkedFailed(P100)
4. Event: ChannelSuccessCallback(P100, channel_txn=C100) arrives late
5. Fact: ChannelTransactionRecorded(C100, CAPTURED)
```

这个缩小后的失败 History 暴露的问题是：系统把 `PAYMENT_UNKNOWN` 本地裁决成失败，导致迟到成功的渠道 Fact 无法被状态机和账本解释。它足以定位问题，但不声称自己是全局最短 History。

Shrinking 输出至少应该包含：

- 随机种子或可重放的生成参数。
- 缩小后的失败 History，或在工具支持时给出局部最小失败 History。
- 被破坏的不变量。
- 失败 oracle，例如状态机 oracle、资金 oracle 或外部事实 oracle。
- 哪个生成器片段最可能制造了缺口。

## 场景示例

### 内部转账

生成重复 `CreateTransfer`、重复 `PostLedger`、借方冻结成功但贷方入账超时、account movement 成功但 ledger posting 延迟、Crash after commit 后 Outbox 未发布、人工冲正重复提交。检查同一转账幂等键最多一个业务效果，余额变化必须有可追溯分录，借贷必须平衡，冲正必须追加新的修复 Fact。

### 支付

生成支付请求超时后渠道成功、重复 capture Command、重复渠道回调、成功失败 Callback reordering、Activity retry 重复调用渠道、渠道账单与本地状态不一致。检查 `PAYMENT_UNKNOWN` 不能直接失败，重复回调不能重复入账，成功 capture 必须有唯一渠道流水、账本分录、对账匹配或可审计差错。

### 电商下单

生成库存预留成功后支付失败、支付成功后库存确认失败、重复 `PaymentCaptured`、重复 `InventoryReleased`、Message duplication 导致订单事件重投、CDC replay 导致读模型重建。检查订单终态、库存预留、支付 capture、退款和释放库存之间的 Fact 是否可解释，避免已支付订单被迟到失败覆盖或库存释放重复执行。

### 旅行组合预订

生成机票出票成功但酒店失败、酒店成功但保险 Activity retry、供应商 unknown 后 Timeout then success、TCC disorder 导致 Cancel 先到、refund unknown 后人工处理。检查核心项和附加项策略是否明确，不可逆出票 Fact 不能被删除，罚金、补差、退款、供应商订单和人工处理必须形成可审计闭环。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只随机金额、字符串和枚举值 | 覆盖的是字段校验，不是金融一致性风险 | 随机生成异常 History，并让 oracle 检查 Fact 集合 |
| 把失败用例看成偶发随机失败 | 真正的状态机、幂等或账本缺口被忽略 | 输出可重放种子和最小失败 History |
| 只跑 happy path 属性 | 覆盖面和普通单元测试没有本质区别 | 强制生成重复、乱序、超时、宕机、重试和重放 |
| 断言框架或 workflow history 成功 | 漏掉资金、渠道、供应商或人工修复 Fact 不可解释 | 断言不变量和 Fact 集合，workflow history 只作为执行线索 |
| 把属性测试说成证明正确 | 过度承诺，掩盖生成器覆盖之外的风险 | 只声明它在已生成 History 和不变量范围内降低风险 |
| 不做 Shrinking | 失败 History 太长，无法定位设计缺口 | 收敛到更小、更容易解释的失败 History，并说明破坏了哪个边界 |
| 生成器不绑定不变量 | 随机序列很多，但不知道在验证什么 | 每个生成器都声明主要挑战的 Invariant 和 oracle |

## 输出结论

属性测试失败时的核心产物应该是一段可复现、缩小后的失败 History，以及被破坏的不变量和 oracle 判定。它不是证明系统正确，而是持续寻找会产生不可解释 Fact 的异常组合。

一次属性测试通过时，报告重点应该是生成器范围、seed 区间或数量、History 长度上下界、场景模型、不变量覆盖和 oracle 覆盖。通过只能说明在这批生成范围内没有发现不可解释事实。它降低风险，但不能替代故障注入、历史回放、对账验证、人工复核和生产审计。
