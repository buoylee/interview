# 10 真实工程原型设计

日期：2026-05-03

## 目标

创建 `financial-consistency/10-service-prototype/`，把第 09 章纯 Java 内存验证实验室推进到第一版真实工程原型。

这一阶段只实现内部转账资金内核服务。它要让学习者看到：当模型进入 MySQL 和应用服务边界后，幂等、本地事务、双分录账本、Outbox、状态机和独立一致性判定器如何组合在一起。

完成后，学习者应该能回答：

- MySQL 本地事务能保护什么，不能保护什么？
- 为什么内部转账必须有转账单、幂等记录、双分录账本和 Outbox？
- 为什么账户余额不能只看 `account.balance`，还要能被账本分录解释？
- 为什么业务服务提交成功以后，还要由独立 verifier 或对账检查事实？
- 第 09 章的 `Fact / History / ConsistencyVerifier` 如何映射到真实数据库行？

## 背景

前面阶段已经完成：

- `01-transfer`：内部转账的不变量、状态机、事件流和失败矩阵。
- `05-patterns`：Outbox、本地消息表、TCC、Saga、Temporal、CDC 和组合方式。
- `06-verification-lab`：不变量、属性测试、故障注入和历史回放规格。
- `07-reconciliation`：对账、差错分类、修复和审计。
- `09-code-lab`：纯 Java 内存版模型、异常历史、判定器、runner 和失败报告。

第 10 章的职责是从“内存事实”前进到“MySQL 事实”。它仍然不是完整金融生产系统，但必须贴近真实服务的关键边界：数据库事务、唯一约束、行锁、幂等键、账本分录、Outbox 和独立验证。

## 方案选择

采用方案 A：Funds Core Service。

这是一个资金内核服务原型，而不是业务大单体。它拥有自己的 MySQL schema 和明确服务边界，先只处理内部转账：

```text
POST /transfers
  -> idempotency key
  -> transfer_order
  -> ledger_entry debit/credit
  -> account balance update
  -> outbox_message
```

后续支付、订单、旅行 Saga 可以通过 Outbox 事件或适配器接入，但不进入本阶段。

## 范围

第一版覆盖：

- Spring Boot 应用骨架。
- MySQL schema 和迁移脚本。
- 内部转账 API。
- 幂等键和请求摘要检查。
- 账户表、转账单表、账本分录表、Outbox 表。
- MySQL 本地事务内的转账提交。
- 成功和失败状态机。
- Outbox 记录写入和 pending 状态。
- 从 MySQL 行抽取 `Fact / History`。
- 独立一致性判定器检查数据库事实。
- 自包含测试或脚本验证正常转账、重复请求、余额不足和坏数据检测。

## 非目标

第一版不做这些事情：

- 不接入 Kafka、RabbitMQ 或真实 broker。
- 不接入 Temporal、Camunda、Seata 或真实工作流引擎。
- 不实现支付渠道、订单库存、旅行预订或退款。
- 不实现人工修复工作台。
- 不实现真实日终对账文件导入。
- 不做多币种、汇率、跨境清结算或监管报送。
- 不把数据库约束当成唯一验证方式。
- 不宣称该原型已经达到生产金融系统安全等级。

## 目录设计

新增目录：

```text
financial-consistency/10-service-prototype/
```

建议结构：

```text
financial-consistency/10-service-prototype/
  README.md
  docs/
    01-domain-model.md
    02-transaction-boundary.md
    03-outbox-flow.md
    04-verification-from-mysql.md
    05-failure-cases.md
  service/
    README.md
    src/
      main/java/.../account/
      main/java/.../transfer/
      main/java/.../ledger/
      main/java/.../idempotency/
      main/java/.../outbox/
      main/java/.../verification/
      main/resources/db/migration/
      test/java/.../
```

计划阶段再决定具体构建工具、Spring Boot 版本、MySQL 驱动、迁移工具和测试容器方式。设计阶段只定义模块边界、事实模型和验证目标。

## 服务边界

`10-service-prototype` 只有一个服务：资金内核服务。

它负责：

- 账户余额读写。
- 内部转账单状态。
- 幂等记录。
- 双分录账本。
- Outbox 事件事实。
- 从数据库事实生成验证 History。

它不负责：

- 用户身份系统。
- 支付渠道接入。
- 订单交易流程。
- 供应商预订流程。
- 消息 broker 投递。
- 人工修复审批。

这个边界很重要：本阶段学习的是“一个服务内部如何把本地事务做到可审计、可验证”，不是一开始拆成多个服务制造分布式复杂度。

## 数据模型

### account

账户表表示当前账户状态。

关键字段：

- `account_id`
- `currency`
- `available_balance`
- `frozen_balance`
- `version`
- `created_at`
- `updated_at`

约束：

- `account_id` 唯一。
- 金额使用定点数，不使用浮点数。
- 余额不能小于零。
- 更新账户时必须有并发控制：行锁或版本号。

### transfer_order

转账单表表示业务状态机。

关键字段：

- `transfer_id`
- `request_id`
- `from_account_id`
- `to_account_id`
- `currency`
- `amount`
- `status`
- `failure_reason`
- `created_at`
- `updated_at`

状态：

```text
INITIATED
SUCCEEDED
FAILED
```

第一版不引入 `UNKNOWN`，因为内部转账不依赖外部渠道。后续接入外部支付时再引入 unknown。

### idempotency_record

幂等表防止同一请求重复产生业务效果。

关键字段：

- `idempotency_key`
- `request_hash`
- `business_type`
- `business_id`
- `status`
- `response_code`
- `response_body`
- `created_at`
- `updated_at`

约束：

- `idempotency_key` 唯一。
- 同一个幂等键重复请求必须返回同一个业务结果。
- 同一个幂等键但请求摘要不同必须拒绝。

### ledger_entry

账本分录表是资金事实的核心。

关键字段：

- `entry_id`
- `transfer_id`
- `account_id`
- `direction`
- `currency`
- `amount`
- `entry_type`
- `created_at`

约束：

- 每个成功转账必须有一借一贷两条分录。
- `direction` 只能是 `DEBIT` 或 `CREDIT`。
- 同一 `transfer_id + account_id + direction + entry_type` 不得重复。
- 任意成功转账的借贷金额合计必须平衡。

### outbox_message

Outbox 表记录本地事务提交后需要传播的事实。

关键字段：

- `message_id`
- `aggregate_type`
- `aggregate_id`
- `event_type`
- `payload`
- `status`
- `created_at`
- `updated_at`
- `published_at`
- `attempt_count`

状态：

```text
PENDING
PUBLISHED
FAILED_RETRYABLE
```

第一版只要求写入 `PENDING`。真实 broker 发布放到后续阶段。

## 核心事务流程

### 正常转账

```text
POST /transfers
  1. 校验 idempotency key 和请求摘要。
  2. 开启 MySQL 本地事务。
  3. 创建或读取 idempotency_record。
  4. 锁定付款账户和收款账户。
  5. 校验余额。
  6. 创建 transfer_order。
  7. 写两条 ledger_entry：付款账户 DEBIT，收款账户 CREDIT。
  8. 更新 account.available_balance。
  9. 写 outbox_message，状态为 PENDING。
  10. 更新 idempotency_record 为 SUCCEEDED。
  11. 提交事务。
```

事务提交后，数据库中应该同时出现：

- 转账单成功事实。
- 幂等完成事实。
- 两条平衡账本事实。
- 两个账户余额变化事实。
- 一个待发布 Outbox 事实。

### 重复请求

同一 `idempotency_key` 和同一 `request_hash` 再次请求时：

- 不能再次写账本分录。
- 不能再次更新账户余额。
- 可以返回第一次的业务结果。
- verifier 应能检查当前数据库事实没有重复业务效果。

同一 `idempotency_key` 但不同 `request_hash` 时：

- 必须拒绝。
- 不能创建新的转账单。
- 不能写账本分录。
- 不能写 Outbox。

### 余额不足

余额不足时：

- 可以创建失败转账单，也可以只记录幂等失败结果，具体实现计划阶段选择。
- 不能写资金变动账本分录。
- 不能更新账户余额。
- 不应该写转账成功 Outbox。

## Outbox 设计

第一版只实现本地事务内写 Outbox，不实现真实发布器。

Outbox 的作用是让系统有一个可审计事实：

```text
转账已经成功
-> 数据库事务内产生 TransferSucceeded event
-> outbox_message PENDING
-> 后续发布器可重试发送
```

第 10 章可以提供一个伪 publisher 或命令行扫描器，但它只修改 `outbox_message.status`，不连接真实 broker。

关键不变量：

- 成功转账必须有 Outbox。
- 失败转账不能产生成功事件。
- Outbox PENDING 不能被删除来表示已处理。
- 重复扫描不能重复生成 Outbox。

## 验证设计

第 10 章必须复用第 09 章思想，但不能直接相信业务服务状态。

验证链路：

```text
MySQL rows
  -> MysqlFactExtractor
  -> History
  -> ConsistencyVerifier
  -> InvariantViolation report
```

`MysqlFactExtractor` 应从这些表抽取事实：

- `account`
- `transfer_order`
- `idempotency_record`
- `ledger_entry`
- `outbox_message`

第一版可以先实现独立的转账 verifier，不强制复用第 09 章 Java 包。关键是判定器必须独立于写入转账的业务服务逻辑。

需要检查的不变量：

- 成功转账必须有且只有一借一贷两条账本分录。
- 成功转账的借贷金额必须平衡。
- 账户余额必须能由初始余额和账本分录解释。
- 同一幂等键不能对应多个不同成功业务效果。
- 幂等键相同但请求摘要不同不能成功复用。
- 成功转账必须有一条 Outbox PENDING 或 PUBLISHED 事实。
- 失败转账不能有资金变动分录。

## 测试设计

第一批测试或脚本必须覆盖：

1. 正常转账成功。
2. 重复请求返回同一结果，不重复扣款。
3. 同一幂等键不同请求摘要被拒绝。
4. 余额不足不产生资金变动。
5. 成功转账必须写双分录。
6. 成功转账必须写 Outbox PENDING。
7. 手工插入单边账本时，verifier 能发现不平衡。
8. 手工删除 Outbox 时，verifier 能发现传播事实缺失。
9. 重复扫描 Outbox 不产生重复消息事实。

这些测试应该验证数据库事实，而不只验证 HTTP 返回。

## 技术边界

第 10 章允许：

- Spring Boot。
- MySQL。
- JDBC、JPA 或 MyBatis 中的一种数据访问方式。
- 数据库迁移工具。
- 本地开发数据库或测试数据库。
- 自包含测试脚本。

第 10 章暂不允许：

- Kafka、RabbitMQ 或真实消息 broker。
- Temporal、Camunda、Seata 或工作流引擎。
- 多服务部署。
- 支付渠道模拟器。
- 旅行供应商模拟器。

实现计划阶段需要再做一次技术选型，并使用当前官方文档确认 Spring Boot、MySQL 驱动、迁移工具和测试工具的实际配置方式。

## 学习顺序

1. 先读 schema，理解哪些数据库行是事实。
2. 再运行正常转账，看同一事务中产生哪些事实。
3. 再运行重复请求，看幂等如何避免重复业务效果。
4. 再运行余额不足，看失败路径不能产生资金分录。
5. 再运行 Outbox 检查，看成功转账如何留下传播事实。
6. 最后运行 verifier，看它如何从 MySQL 行重建 History 并输出 violation。

## 成功标准

第 10 章完成时应满足：

- 有可运行的内部转账工程原型。
- 能初始化 MySQL schema 和基础账户数据。
- 能执行正常转账、重复请求和余额不足场景。
- 成功转账在一个本地事务内写入转账单、账本、幂等记录和 Outbox。
- verifier 能从数据库读取事实并发现至少两类坏数据：单边账本和缺失 Outbox。
- 文档能解释 MySQL 是事实存储和事务边界，不是一致性判定器。
- 文档能说明为什么 Kafka、Temporal 和支付渠道放到后续阶段。

## 风险与约束

| 风险 | 后果 | 约束 |
| --- | --- | --- |
| 一开始拆多服务 | 学习重点变成网络和 Saga 调度 | 第 10 章只做一个资金内核服务 |
| 只看 HTTP 返回 | 无法检查数据库事实是否一致 | 测试必须检查 MySQL 行和 verifier 输出 |
| 只更新余额不写账本 | 无法审计和对账 | 成功转账必须写双分录 |
| 重复请求不检查请求摘要 | 同一幂等键可能复用到不同业务意图 | 幂等记录必须保存 request hash |
| 成功转账不写 Outbox | 后续事件传播没有可恢复事实 | 转账成功和 Outbox 写入必须在同一事务 |
| verifier 复用业务服务代码 | 业务 bug 可能被测试重复 | verifier 从数据库事实独立判定 |
| 过早引入 Kafka 或 Temporal | 基础设施复杂度遮蔽资金内核 | 第 10 章只写 Outbox PENDING，不接 broker |

## 输出结论

第 10 章应该实现一个单服务资金内核原型：Spring Boot + MySQL + 内部转账 + 幂等 + 双分录账本 + Outbox + 独立 verifier。

它的重点不是“把分布式事务一次性全部做完”，而是把真实金融系统最核心的一层做扎实：在一个服务的本地事务边界内，所有资金事实必须可审计、可重放、可验证。

只有这个边界跑通后，才适合进入后续阶段：真实消息发布、消费者幂等、支付渠道、订单库存和旅行 Saga。
