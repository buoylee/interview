# 05 Temporal

## 解决的问题

Temporal 解决可靠长流程执行和编排问题。它提供 durable execution，让 Workflow 在 worker 重启、进程崩溃、网络抖动、timer 到期、Activity 超时和重试之后仍然可以从 workflow history 恢复并继续执行。

Temporal 适合承接 Saga 编排、定时查询、超时等待、重试、人工等待和恢复执行。它把“流程下一步该做什么、什么时候重试、什么时候等待回调、什么时候触发补偿”从单个进程内存中移到可恢复的执行模型里。

Temporal 不替代业务事实、状态机、幂等、Outbox、账本、对账或领域服务所有权。它能让流程可靠运行，但不能决定支付是否真实成功、退款是否真实到账、供应商是否真实出票，也不能把多个服务数据库变成一个分布式事务。

## 在本教程中的位置

推荐把 Temporal 用作长流程编排主线，尤其适合：

- 旅行组合预订：机票、酒店、保险、接送机和附加服务分步骤执行。
- 支付渠道查询和超时轮询：支付请求超时后定时查询渠道结果。
- 退款未知后的周期查询：退款请求返回 `REFUND_UNKNOWN` 后等待回调、轮询或转人工。
- 人工处理等待：供应商订单、支付单或退款单进入人工审核期间保持流程可恢复。
- 跨服务补偿流程：按业务顺序释放库存、void 授权、退款、取消供应商保留或创建人工工单。

## 与 Saga 的关系

Temporal 可以承载 Saga 编排。Workflow 负责保存流程进度和补偿顺序，Activity 负责调用领域服务或外部适配器。每个成功 Activity 都应该对应一个领域事实、外部请求记录或后续补偿动作；失败时，Workflow 可以按业务顺序触发补偿。

补偿必须按业务可逆性设计：

- 库存预留可以释放。
- 支付授权可以 void。
- 已 capture 资金只能 refund。
- 已出票机票可能只能退票、收罚金、补差、替代供应商或人工处理。
- 已生效保险不能通过删除本地字段回滚。

Temporal 让 Saga 的等待、重试和恢复更可靠，但 Saga 的正确性仍然来自每一步的状态机、幂等、审计记录、补偿语义和对账。

## Activity 幂等和请求 ID

Activity 可能因为 worker 崩溃、超时、心跳丢失、网络失败或重试策略被重复执行。所有 Activity 都必须幂等，尤其是扣款、退款、供应商预订、取消供应商订单和创建人工工单。

Activity 调用外部系统或领域服务时必须携带业务 request id，例如 `payment_request_id`、`refund_request_id`、`supplier_booking_request_id` 或 `compensation_request_id`。下游服务必须用这个 request id 做唯一约束和幂等返回：

- 重复支付 Activity 只能返回同一笔支付请求结果，不能重复扣款。
- 重复退款 Activity 只能返回同一笔退款请求结果，不能重复退款。
- 重复供应商预订 Activity 只能返回同一笔供应商订单或未知状态，不能创建多个供应商订单。
- 重复补偿 Activity 只能推进同一个补偿状态，不能释放两次库存或重复创建工单。

Temporal 的 retry 行为取决于 retry policy、timeout、cancellation、non-retryable error、maximum attempts 和 Workflow 本身是否仍然继续等待这个 Activity。它不能保证所有失败都会无限重试，也不能保证“外部动作天然只发生一次”。Exactly-once 的业务效果来自 request id、幂等键、状态机和唯一约束。

## Workflow history 不是账本

workflow history 记录的是 Workflow 执行事件，例如 Activity 调度、Activity 完成、timer、signal 和失败恢复。它是 Temporal 恢复执行的依据，不是订单、支付、退款、供应商账单或会计账本的事实来源。

不能把 workflow history 当 ledger 或 accounting source of truth：

- 账本必须记录资金方向、科目、借贷平衡、币种、金额、手续费和不可变流水。
- 支付服务必须记录支付请求、渠道流水、查询结果、回调和最终状态。
- 退款服务必须记录退款请求、退款渠道状态、失败原因和人工处理结果。
- 供应商服务必须记录供应商订单号、出票、取消、罚金、补差和结算状态。

Workflow 成功只代表编排流程走到了某个终态，不代表供应商账单、支付渠道、退款渠道和内部账本全部一致。最终一致性必须通过领域事实、渠道事实、账本事实和对账来确认。

## 典型场景

### 旅行组合预订

Workflow 可以按顺序调用 Activity：创建行程、预留机票、预留酒店、创建支付授权、确认机票、确认酒店、capture 支付、生成订单。任何一步失败时，Workflow 根据已成功步骤触发补偿。

如果机票已经出票但酒店失败，不能把本地订单直接改失败并删除机票事实。正确处理是进入补偿流程：尝试退票、记录罚金、改订酒店、补差或创建人工工单。Temporal 负责可靠执行这些步骤，业务系统负责记录每个事实和状态。

### 支付查询和超时

支付 Activity 调用渠道超时后，不能直接把订单判失败。Workflow 应该把支付子状态保持为 `PAYMENT_UNKNOWN`，启动 timer 周期查询，等待渠道回调，或者在超过业务窗口后转人工处理。

查询 Activity 也必须幂等。重复查询只能更新同一笔支付请求的状态，不能发起新的扣款请求。对查询结果的状态迁移必须由支付服务保护，成功事实不能被迟到失败回调覆盖。

### 退款未知

退款 Activity 返回 `REFUND_UNKNOWN` 时，Workflow 可以等待回调、按退避策略查询或创建人工处理任务。它不能在 Workflow 里直接裁决退款失败，因为渠道可能已经受理，后续可能成功入账。

退款最终状态必须由退款服务和账本共同解释。退款成功需要有渠道退款流水和对应账本分录；退款失败需要有可审计原因；长期未知需要进入对账或人工处理。

### 供应商未知和人工处理

供应商预订、取消或出票超时后，应记录 `SUPPLIER_UNKNOWN`，并让 Workflow 进入查询、等待回调、人工处理或对账流程。人工处理可以通过 signal 或领域服务状态变更唤醒 Workflow，但人工结论必须落在供应商服务或订单服务的业务事实中。

Temporal 可以可靠等待人处理三天、七天或更久；它不能替代人工处理记录、审批记录、供应商凭证或财务结算事实。

## 必须遵守的边界

- Activity 必须幂等，并使用业务 request id。
- Workflow 只能编排领域服务命令，不能直接修改多个服务数据库。
- Workflow 不能绕过支付、退款、供应商、库存或账本服务的状态机。
- workflow history 不是账本，也不是供应商、支付或退款的事实来源。
- `SUPPLIER_UNKNOWN`、`PAYMENT_UNKNOWN`、`REFUND_UNKNOWN` 不能在 Workflow 中被直接裁决为失败。
- Temporal retry 不能替代 Outbox、消费者幂等、唯一约束和对账。
- Temporal timer 不能替代业务超时规则、人工升级规则和清算周期。
- Workflow 完成不等于所有渠道、供应商和账本都一致。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 把 workflow history 当业务事实或账本 | 领域服务和账务不可解释，审计无法成立 | 业务事实落领域库，资金事实落账本，Workflow 只编排 |
| Activity 没有幂等键 | worker 重试造成重复扣款、重复退款或重复供应商订单 | 每个 Activity 使用业务 request id，并由下游唯一约束保护 |
| Workflow 内直接改多个库 | 绕过服务边界、状态机和审计 | 调用领域服务命令，让服务自己提交本地事务 |
| 超时直接失败 | 外部系统可能已经成功，后续回调无法解释 | 标记 unknown，查询、等待回调、对账或人工处理 |
| 把 Temporal 当分布式事务 | 部分成功、不可逆动作和资金事实被掩盖 | 用 Saga、状态机、补偿、Outbox、账本和对账组合保证一致性 |
| 在 Workflow 中写随机数、当前时间或不可重放逻辑 | replay 行为不确定，恢复执行失败 | 遵守 Temporal Workflow determinism，非确定性动作放到 Activity |

## 验证方法

- 外部副作用已经成功，但 Activity completion/result 尚未被持久记录到 workflow history 时故障注入，验证 Activity 可能被重试，且下游幂等、查询或对账能阻止重复业务效果。
- Activity 超时后重试，验证 request id 和幂等键阻止重复扣款、重复退款或重复供应商预订。
- timer 恢复后继续查询支付、退款或供应商状态，验证 `PAYMENT_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 能收敛到成功、失败、人工或长期对账状态。
- 人工等待期间重启 worker，验证 Workflow 能恢复等待状态，并能通过 signal 或领域状态继续流程。
- 补偿 Activity 失败后重试，验证不会重复释放、重复退款或重复创建人工工单。
- 对账 Workflow 结果和领域事实、渠道事实、供应商事实、账本事实，验证 Workflow 完成不被当成财务完成。
- 故障注入重复回调、乱序回调、迟到失败和迟到成功，验证领域服务状态机保护已知成功事实。

## 面试表达

Temporal 解决的是可靠长流程执行和编排，不是分布式事务数据库。它非常适合 durable execution、Saga、Activity retry、timer、恢复执行和人工等待，但业务事实必须由领域服务、支付服务、退款服务、供应商服务、账本、Outbox 和对账共同保证。

可以进一步强调：Workflow 负责“下一步做什么”，Activity 负责“调用一个有幂等保护的业务动作”。workflow history 用来恢复 Workflow，不是 ledger。支付、退款和供应商未知状态不能被流程框架直接判死，必须查询、回调、对账或人工处理。
