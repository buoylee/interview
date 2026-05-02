# 01 验证模型

## 目标

验证实验室需要一套统一语言。金融一致性验证不是检查某个接口是否返回成功，而是检查一段 History 结束后，所有 Fact 是否能被状态机、幂等、账本、外部事实、对账和人工修复解释。

这个模型的核心问题是：系统经历重复请求、乱序消息、迟到回调、外部超时、宕机恢复或人工修复后，最终留下的事实集合是否仍然自洽。

## 核心对象

| 对象 | 含义 | 示例 | 验证重点 |
| --- | --- | --- | --- |
| Command | 外部或内部发起的意图 | `CreateTransfer`、`CapturePayment`、`CancelBooking` | 是否幂等，是否有合法前置状态 |
| Event | 系统发布或接收的变化通知 | `PaymentCaptured`、`InventoryReserved`、`SupplierCallbackReceived` | 是否重复、乱序、迟到，消费者是否幂等 |
| Fact | 已经落库、可审计、不能随意删除的事实 | 账本分录、渠道流水、供应商订单、人工审批 | 是否可追溯，是否能和其他事实互相解释 |
| History | Command、Event、Fact、故障和人工动作组成的时序 | 支付请求超时后迟到成功回调 | 终态是否可解释 |
| Invariant | 系统永远不能违反的承诺 | 同一幂等键最多一个业务效果 | 是否被任意异常 History 破坏 |
| Oracle | 判断 History 是否合格的检查器 | 状态机 oracle、资金 oracle、外部事实 oracle | 是否能指出具体破坏的边界 |

## Fact 优先

验证必须 Fact-first。接口返回、日志、broker offset、workflow history 和页面状态都只是执行线索，不是最终业务事实来源。它们能帮助定位流程走到哪里、消息是否被拉取、工作流是否调度过某个步骤，但不能替代领域事实、渠道事实、供应商事实、账本事实、Outbox 事件、消费者处理记录、对账差错和人工审批记录。

典型判断方式：

- 接口返回成功，只说明调用方观察到了成功响应，不等于资金已过账。
- 日志打印 `PaymentCaptured`，只说明某段代码执行过，不等于渠道流水和账本分录都存在。
- broker offset 已提交，只说明消费者推进了消息位置，不等于业务副作用已经成功且幂等记录已落库。
- workflow history 记录 Activity 完成，只说明编排引擎看到了执行结果，不等于外部资金、供应商订单或人工审批事实已经可被业务账本解释。
- 页面展示成功，只是读模型或投影结果，不能覆盖底层 Fact 的缺失或冲突。

因此，验证的主语不是“某个接口返回了什么”，而是“一段 History 留下了哪些 Fact，这些 Fact 是否能互相解释”。

## 三类 Oracle

| Oracle | 检查内容 | 失败示例 |
| --- | --- | --- |
| 状态机 oracle | 状态迁移是否合法，终态是否单调，迟到事件是否被拒绝 | `PAYMENT_SUCCEEDED` 被迟到失败覆盖 |
| 资金 oracle | 余额、冻结、流水、账本分录、退款和调整是否可解释 | 借贷不平，重复扣款，已 capture 后 void |
| 外部事实 oracle | 渠道、供应商、人工修复和本地事实是否互相解释 | 本地成功但供应商无单且没有差错记录 |

Oracle 不代表生产系统里的单个服务。它是测试视角的判定模型，用来把状态、资金和外部事实放在同一段 History 中检查。

## History 形态

```text
Command
  -> Local Fact
  -> Outbox Event
  -> Consumer Command
  -> External Fact
  -> Callback / Query Result
  -> Ledger Fact
  -> Reconciliation Fact
  -> Manual Repair Fact
```

更具体的 History 可以写成：

```text
1. Command: CapturePayment(payment_request_id=P100, idempotency_key=K1)
2. Fact: PaymentRequestCreated(P100, PROCESSING)
3. Fact: OutboxEventCreated(PaymentCaptureRequested, event_id=E1)
4. Event: PaymentCaptureRequested(E1) delivered twice
5. Command: CallPaymentChannel(P100, channel_request_id=C1)
6. Fault: channel response timeout
7. Fact: PaymentMarkedUnknown(P100, PAYMENT_UNKNOWN)
8. Event: ChannelCallbackReceived(C1, SUCCEEDED) arrives late
9. Fact: ChannelTransactionRecorded(C1, CAPTURED, amount=100)
10. Fact: LedgerPostingCreated(P100, debit=100, credit=100)
11. Fact: ReconciliationMatched(P100, C1)
```

真实 History 可以重复、乱序、丢响应、迟到、被人工修复打断，也可能长期停留在 unknown 或人工挂起状态。验证模型必须允许这些异常历史存在，并检查它们是否仍然可解释。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只断言接口返回成功 | 无法发现迟到回调、重复消息和账本差异 | 断言 History 结束后的 Fact 集合 |
| 把日志当作 Fact | 日志丢失、重复或格式变化会掩盖业务事实缺口 | 日志只能辅助定位，业务判断读取可审计 Fact |
| 把 workflow history 当 Fact | 编排历史被误当成资金事实、供应商事实或人工审批事实 | workflow history 只能解释执行过程，最终仍要检查领域 Fact |
| 把 broker offset 当业务完成 | 消费者处理失败、外部副作用失败或幂等记录缺失不可见 | 消费者必须有业务处理记录、幂等键和可解释副作用 |
| 把 Outbox 发送成功当终态成功 | 事件传播成功被误认为支付、退款、库存或供应商动作成功 | Outbox 只能证明本地事实有传播路径，还要检查下游 Fact |
| Oracle 只检查最终状态 | 资金、供应商、人工修复事实可能不可解释 | 同时检查状态机 oracle、资金 oracle 和外部事实 oracle |
| 用本地失败覆盖外部未知 | 超时后迟到成功会被误判失败，可能重复扣款、重复退款或重复预订 | unknown 必须通过查询、回调、对账或人工处理收敛 |

## 输出结论

验证模型的输出不是“测试全部证明系统正确”，而是“在这组异常 History 和 Invariant 覆盖范围内，没有发现不可解释 Fact”。如果 oracle 能构造出不可解释事实，说明系统的状态机、幂等、账本、事件传播、补偿、对账或人工修复边界存在缺口。

测试、属性生成、故障注入和历史回放只能降低风险，不能证明所有可能的执行历史绝对正确。金融级验证真正要交付的是可解释的事实闭环，以及发现不可解释事实时能定位边界缺口的证据。
