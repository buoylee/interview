# 05 历史回放

## 目标

历史回放用同一批 Fact 构造不同顺序，检查系统是否仍能解释状态、资金、外部系统、事件传播、对账和人工修复。它特别适合验证重复、乱序、迟到成功、迟到失败、CDC offset 回退、对账后重放和人工修复交错。

历史回放不能替代对账。它验证系统如何解释已有事实和迟到事实；对账仍然负责发现生产中的渠道、供应商、账本和本地领域事实差异。换句话说，history replay 是验证解释能力，不是生产修复工具，也不是事实发现机制。

一次合格的历史回放应该回答：这段 History 以不同顺序出现时，留下的 Fact 是否仍能被 Invariant、状态机 oracle、资金 oracle 和外部事实 oracle 解释。

## 回放类型

| 回放类型 | 构造方式 | 风险 | 检查重点 |
| --- | --- | --- | --- |
| 原始顺序 | 按发生时间回放 | 基线 History 不可解释 | 每个状态都有前置 Fact，每个资金动作都有账本分录 |
| 回调先到 | 回调早于本地查询结果或本地状态初始化 | 本地状态未准备好，回调被丢弃 | 幂等、挂起记录和后续关联能力 |
| 成功先到、失败迟到 | 成功 Fact 之后收到失败回调或失败事件 | 成功被覆盖，终态倒退 | 状态机拒绝倒退，迟到失败被记录并解释 |
| 失败先到、成功迟到 | 本地失败或超时后收到外部成功 | 外部成功不可解释，重复扣款或重复预订 | `PAYMENT_UNKNOWN`、查询、回调、对账和人工处理路径 |
| 消息重复 | 同一 event id、业务单号或 request id 多次出现 | 重复业务效果，重复账本分录 | 消费者幂等和业务唯一约束 |
| CDC offset 回退 | 已投影变化再次被捕获，旧 offset 后的变更被重放 | 读模型重复、倒退或触发重复副作用 | 版本号、投影幂等和消费者处理记录 |
| 人工修复交错 | 自动补偿、对账修复和人工修复同时或乱序出现 | 重复冲正、重复补分录或覆盖历史 Fact | maker-checker、修复命令幂等和复核结果 |
| 对账后重放 | 差错生成、修复和复核后重新回放账单或事件 | 报表调平但事实仍不可解释 | 差错分类稳定、修复 Fact 唯一、关闭原因可追踪 |

## 回放输入

每段 replay history 至少包含：

- 原始 Command，包括业务单号、request id 和幂等键。
- 领域 Fact，例如 payment request、order sub item、supplier request、状态变更记录。
- Event 或 CDC 变化，包括 event id、版本号、offset 和 consumer group。
- 外部请求号、渠道流水、供应商请求号或供应商订单号。
- 查询结果、回调、账单记录和处理时间。
- 账本分录、账户流水、冻结、退款、冲正或调整分录。
- 对账批次、匹配结果、差错记录、修复命令和复核结果。
- 人工修复记录，包括证据快照、maker-checker 审批、修复 Fact 和关闭原因。

回放输入必须保留迟到事实，不能为了让终态好看而删除、过滤或改写 late fact。回放也不能用本地服务的当前判断直接裁决 unknown；`PAYMENT_UNKNOWN`、`REFUND_UNKNOWN` 和 `SUPPLIER_UNKNOWN` 必须通过查询、回调、对账或人工处理继续解释。

## 检查规则

- 状态机不能倒退，终态成功不能被迟到失败覆盖。
- 成功事实不能被迟到失败改写或删除。
- 失败事实不能删除迟到成功，迟到成功必须被记录、解释或转入对账和人工处理。
- unknown 不能被本地直接裁决为成功或失败。
- 每个资金动作都有原始请求、幂等键、业务单号和账本分录。
- 每个外部成功都有请求号、查询、回调、渠道账单或供应商账单证据。
- 每个人工修复都有证据快照、maker-checker 审批、修复命令、修复 Fact 和复核结果。
- 每个传播事实都能追溯到已经落库的领域 Fact。
- 每个重复消息都只能产生一次业务效果，重复处理必须能被 event id、request id 或业务唯一键解释。
- 每个 CDC offset 回退后的投影变化都不能造成读模型倒退或重复副作用。
- 每个对账后重放都必须保持差错分类、修复命令和复核结果可解释。

## 示例：支付迟到成功

```text
1. Command: CreatePayment(payment_request_id=P1, idempotency_key=K1)
2. Fact: PaymentRequestCreated(P1, PROCESSING)
3. Fault: ChannelTimeout(P1, channel_request_id=C1)
4. Fact: PaymentMarkedUnknown(P1, PAYMENT_UNKNOWN)
5. Fact: ManualReviewStarted(P1)
6. Event: ChannelSuccessCallback(P1, channel_txn=C1) arrives late
7. Fact: ChannelTransactionRecorded(C1, CAPTURED)
8. Fact: LedgerPostingCreated(P1, C1, debit=100, credit=100)
9. Fact: ReconciliationMatched(P1, C1)
```

合格结果：本地不能在第 3 步把支付判失败并发起无关联二次扣款。第 6 步迟到成功必须能推进到成功、补账、对账匹配或人工复核完成。若人工流程已经开始，人工修复记录也必须解释为什么接受迟到成功、如何关闭工单，以及账本和渠道流水如何匹配。

不合格结果包括：把 `PAYMENT_UNKNOWN` 本地直接判失败、删除迟到成功回调、用新 request id 重新扣款、账本缺少对应分录，或对账只调平报表但无法解释渠道成功 Fact。

## 示例：供应商迟到失败

```text
1. Command: SupplierBookingRequested(S1, idempotency_key=K2)
2. Event: SupplierSuccessCallback(S1, ticket_no=T1)
3. Fact: SupplierOrderRecorded(S1, T1, CONFIRMED)
4. Fact: OrderSubItemConfirmed(S1)
5. Event: SupplierFailureCallback(S1) arrives late
6. Fact: LateSupplierFailureRecorded(S1)
7. Fact: ReconciliationItemCreated(S1, conflict=success_then_failure)
```

合格结果：第 5 步不能覆盖第 2 步已确认成功 Fact，也不能删除供应商订单或本地子单确认记录。系统应记录迟到失败回调、拒绝状态倒退，并在必要时进入对账或人工处理，解释供应商成功单、迟到失败回调、罚金、补差或退款路径。

不合格结果包括：用迟到失败覆盖已确认出票、删除供应商订单 Fact、重复下单，或人工直接改状态但没有证据快照、审批、修复命令和复核结果。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只按原始顺序回放 | 无法发现乱序、回调先到和迟到事实问题 | 生成多种顺序，并覆盖成功先到、失败迟到和失败先到、成功迟到 |
| 回放只检查最终状态 | 账本、渠道、供应商和人工修复 Fact 可能不可解释 | 同时检查状态机、资金、外部事实、对账和人工修复 |
| 把 replay 当生产修复 | 测试动作污染真实事实，绕过审批和审计 | replay 只读或在隔离环境执行，生产修复必须走修复命令和 maker-checker |
| 迟到事实直接丢弃 | 外部成功或失败不可解释，审计链断裂 | 记录迟到事实，由状态机、对账或人工处理解释 |
| 本地直接裁决 unknown | 超时被误当失败，可能重复扣款、重复退款或重复预订 | unknown 必须通过查询、回调、对账或人工处理收敛 |
| 用 replay 结果改写历史 Fact | 历史回放变成不可审计的数据修补 | replay 只能输出发现和证据，不能删除或改写生产 Fact |
| 对账后重放只看报表是否平 | 差错关闭但领域事实、账本或外部事实仍冲突 | 检查差错分类、修复 Fact、复核结果和关闭原因 |

## 输出结论

历史回放的输出应该是一份 replay report，至少包含：输入 History、回放顺序、状态迁移、生成 Fact、被拒绝事件、重复消息处理结果、CDC offset 回退处理结果、对账后重放结果、不变量检查结果、oracle 判定和需要人工解释的差异。

replay report 的结论不应该写成“系统已经被证明正确”。它只能说明：在这段 History、这些回放顺序和这些 Invariant 范围内，没有发现不可解释 Fact；或者指出哪一个状态机、幂等、账本、外部事实、对账或人工修复边界存在缺口。
