# 02 不变量目录

## 目标

不变量是金融级系统永远不能违反的承诺。验证实验室的每个 property tests、fault injection、history replay 和 oracle 都必须落回不变量，而不是只检查流程是否跑完。

普通单元测试可以验证单个函数、单个分支或 happy path 的返回值，但它不足以证明一段异常 History 结束后的 Fact 集合可解释。真正有价值的不变量检查要覆盖重复请求、乱序消息、迟到回调、外部 unknown、宕机恢复、补偿失败、对账差错和人工修复。

## 不变量总表

| 类别 | 不变量 | 典型破坏方式 | 应该检查的 Fact |
| --- | --- | --- | --- |
| 幂等 | 同一业务幂等键最多产生一个业务效果 | 重复请求造成重复扣款、退款、出票或记账 | request id、业务单号、幂等处理记录、唯一约束、账本分录 |
| 状态机 | 非法状态转换必须被拒绝，终态不能被迟到事件覆盖 | `PAYMENT_SUCCEEDED` 被迟到失败覆盖，已取消订单又被确认 | 状态变更记录、前置状态、版本号、事件时间、处理时间 |
| 账本 | 借贷分录必须平衡、可追溯，并能解释账户余额变化 | 账户余额变化但无分录，分录无业务来源，借贷不平 | account movement、ledger posting、业务单号、渠道流水、调整分录 |
| 外部未知 | `PAYMENT_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 不能本地直接判失败，必须被查询、回调、对账或人工修复继续推进 | 超时后重复扣款，供应商成功被本地失败覆盖，退款 unknown 后重复退款 | 渠道流水、供应商请求号、查询结果、回调、对账账单、长期对账终态、人工挂起终态 |
| TCC | Try 后 Confirm 和 Cancel 不能同时成功，空回滚和悬挂必须可解释 | 同一预留资源既确认又释放，Cancel 先到导致后续 Try 悬挂 | 全局事务 ID、分支 ID、Try/Confirm/Cancel 状态、资源冻结记录 |
| 补偿 | 补偿必须追加新业务事实，不能删除或改写历史事实；void/release 只适用于 pre-capture authorization 或 cancelable reservation | 已出票、已 capture 后删除本地记录，已 capture 资金被误当成可 void，补偿失败后无差错记录 | refund、reversal/adjustment posting、void、release、罚金、补差、补偿命令、补偿结果、人工处理 |
| Outbox | 本地 Fact 提交后必须有可恢复的传播记录 | 业务提交后消息丢失，publisher 宕机后下游永远不可见 | Outbox 事件、publisher 状态、发送尝试、消费者处理记录 |
| 消费者 | 重复消息、乱序消息和重投不能产生第二次业务效果 | broker 重投造成重复库存确认、重复退款或重复记账 | event id、consumer group、处理表、业务唯一约束、下游 Fact |
| 对账 | 对账只能产生差错、匹配和修复命令，不能直接改写领域 Fact | 报表调平但业务事实不可解释，渠道有成功本地无记录 | 对账批次、差错记录、owner、修复命令、复核结果、关闭原因 |
| 人工修复 | 人工结论必须可审计、可复核，并留下新的修复 Fact | 人工直接改状态，无证据链，重复提交人工冲正 | 工单、maker-checker 审批、证据快照、修复命令、修复 Fact |

## 不变量写法

一个可用的不变量必须包含：

| 字段 | 含义 | 常见错误 |
| --- | --- | --- |
| scenario | 适用业务场景，例如支付、退款、订单支付、旅行预订、内部转账 | 只写“金额一致”，没有说明适用边界 |
| History range | 要检查的 History 范围，例如一次 payment request、一次 TCC 分支、一个对账批次 | 只看当前状态，漏掉迟到回调和重复事件 |
| Facts read | 需要读取哪些 Fact，例如账本、渠道流水、Outbox、消费者记录、人工工单 | 读取日志、页面状态或 broker offset 当作业务事实 |
| condition | 判断条件，例如数量上限、状态迁移合法性、借贷平衡、外部事实可解释 | 条件不可执行，无法被 oracle 自动判定 |
| failure meaning | 失败时说明哪类一致性边界被破坏 | 只报断言失败，不指出幂等、状态机、账本或外部事实缺口 |

示例：

```text
Invariant: 同一 payment_request_id 最多产生一次 capture 业务效果
scenario: 支付、旅行预订、订单支付
History range: 从 CapturePayment Command 到渠道回调、查询、对账、人工修复或可审计长期终态
Facts read: payment_request, channel_transaction, ledger_posting, reconciliation_item, manual_repair_ticket
condition: capture 成功 Fact 数量 <= 1，并且每个成功 capture 都有唯一渠道流水和账本分录
failure meaning: 支付幂等或账本一致性边界被破坏
```

## 分层使用

| 层次 | 主要表达方式 | 需要防住的破坏 |
| --- | --- | --- |
| 单服务内 | 状态机、唯一约束、本地事务、版本号 | 重复提交、非法迁移、并发覆盖 |
| 跨服务事件 | Outbox、消费者处理记录、业务唯一约束、重试记录 | 消息丢失、重复消费、下游副作用重复 |
| 外部系统 | request id、查询、回调、渠道账单、供应商账单 | `PAYMENT_UNKNOWN`、`REFUND_UNKNOWN`、`SUPPLIER_UNKNOWN` 被本地误裁决 |
| 资金事实 | 账户流水、冻结、借贷分录、调整分录、对账差错 | 余额不可解释、借贷不平、补偿缺失 |
| 长事务 | TCC 分支状态、Saga 步骤、补偿命令、外部副作用记录 | Confirm/Cancel 双终态、补偿覆盖历史、悬挂资源 |
| 人工修复 | maker-checker、证据快照、审批、复核、修复 Fact | 不可审计修复、重复修复、绕过对账闭环 |

## 检查方式

不变量不是普通单元测试清单。它们应该被以下验证方式反复检查：

- property tests：生成异常 History，组合重复、乱序、迟到、超时、补偿失败和人工修复。
- fault injection：在提交本地 Fact、写 Outbox、调用外部系统、记录消费者处理结果、写账本和跑对账时制造故障。
- history replay：改变事件顺序、重放历史消息、插入迟到回调，检查终态 Fact 是否仍可解释。
- oracles：用状态机 oracle、资金 oracle 和外部事实 oracle 读取 Fact 集合，判断不变量是否被破坏。

单元测试仍然有价值，但它只能覆盖局部逻辑。不变量必须面向一段 History 后的 Fact 集合，否则无法发现外部 unknown、消息重投、账本差异、对账差错和人工修复造成的事实分叉。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 只写“金额不能错” | 无法定位破坏边界，也无法实现 oracle | 写清金额来自哪些 Fact、如何汇总、允许哪些调整分录 |
| 只检查最终状态 | 账本、渠道、供应商或人工修复事实可能不可解释 | 同时检查状态机、资金和外部事实 |
| 把 unknown 当失败 | 覆盖迟到成功，造成重复扣款、重复退款或重复预订 | unknown 必须通过查询、回调、对账或人工修复推进；仍无法判定时，进入可审计的长期对账终态或人工挂起终态 |
| 用删除历史记录表达补偿 | 审计链断裂，历史回放无法解释资金或供应商事实 | 补偿必须追加 refund、reversal/adjustment posting、罚金、补差或修复 Fact；void/release 只用于 capture 前授权或可取消预留 |
| 把 Outbox 发送成功当业务成功 | 事件传播成功被误认为支付、退款、库存或供应商动作成功 | Outbox 只证明传播路径，下游 Fact 仍要被 oracle 检查 |
| 只断言消费者提交 broker offset | 业务副作用可能失败，重复消息也可能产生第二次效果 | 消费者必须有处理记录、幂等键和业务唯一约束 |
| 对账脚本直接修数据 | 修复不可审计，maker-checker 和证据链缺失 | 生成差错、修复命令、审批、复核和修复 Fact |
| 人工修复绕过不变量 | 人工动作成为新的不可解释事实来源 | 人工修复也要进入 History，并被 oracle 检查 |

## 输出结论

不变量目录是后续所有测试的共同词典。属性测试负责生成异常 History，故障注入负责制造事实分叉，历史回放负责改变时序，oracle 负责检查这些不变量是否被破坏。

一次检查通过只能说明“在这组 History 和 Fact 覆盖范围内，没有发现不可解释事实”。它不能证明所有执行历史绝对正确，但能让幂等、状态机、账本、外部 unknown、TCC、补偿、Outbox、消费者、对账和人工修复的边界缺口更早暴露。
