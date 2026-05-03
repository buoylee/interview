# 10 真实工程原型

这是内部转账资金内核服务原型，用来把第 09 章的内存事实验证推进到 Spring Boot、MySQL、本地事务、双分录账本和 Outbox。

## 目标

本章实现一个单体边界内的 Funds Core Service，而不是多个服务之间的分布式事务。核心目标是把 A 给 B 转账落到真实数据库事实里：

- `account` 保存账户余额。
- `transfer_order` 保存转账业务单。
- `idempotency_record` 保存幂等键、请求摘要和最终响应。
- `ledger_entry` 保存一借一贷的双分录账本。
- `outbox_message` 保存等待发布的业务事件。

MySQL 在这里承担事实存储和本地事务边界：服务写入的余额、账本、转账单、幂等记录和 Outbox 都必须在同一个 MySQL 事务里一起提交或一起回滚。MySQL 不是独立的一致性判定器；一致性判定来自单独的验证代码读取数据库事实后的推导，而不是服务自己的自述。

## 运行方式

从仓库根目录运行：

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

脚本会启动 Docker Compose 中的 MySQL，等待数据库就绪，然后执行 Spring Boot 集成测试。

需要手工启动服务时运行：

```bash
bash financial-consistency/10-service-prototype/scripts/run-service.sh
```

服务暴露内部转账 API 和数据库事实验证 API。当前阶段不接 Kafka、Temporal、支付渠道或其他外部系统。

## 核心事务

成功转账的本地事务按固定顺序写入事实：

```text
idempotency -> account locks -> transfer_order -> ledger_entry -> account update -> outbox_message -> idempotency completion -> commit
```

这个顺序先占住幂等键，再按账户号顺序加行锁，随后写转账单、双分录账本、余额变更、Outbox 事件和幂等最终响应。只要事务没有提交，外部观察者就不应看到半笔成功转账。

失败路径也要留下可解释事实。余额不足会写 `FAILED` 的 `transfer_order` 和 `FAILED` 的 `idempotency_record`，但不会写 `ledger_entry` 或 `TransferSucceeded` Outbox。校验拒绝和幂等冲突会返回明确响应，避免重复扣款。

## 验证方式

验证链路从 MySQL 行开始，而不是从 `TransferService` 的返回值开始：

```text
MySQL rows -> DbFact -> DbHistory -> TransferMysqlVerifier -> DbInvariantViolation
```

`MysqlFactExtractor` 把数据库行转成 `DbFact`，`DbHistory` 聚合这些事实，`TransferMysqlVerifier` 独立检查不变量并输出 `DbInvariantViolation`。验证器不复用转账服务代码，因此它检查的是数据库里已经发生的事实，而不是服务对自己行为的说明。

当前重点不变量包括：成功转账必须有一借一贷双分录，账本金额和币种必须与转账单一致，成功转账必须有 `TRANSFER` 聚合的 `TransferSucceeded` Outbox，失败转账不能有账本，账本必须引用已成功的转账。

## 关键边界

- 本章只覆盖单个资金内核服务的本地事务，不实现跨服务 Saga。
- MySQL 本地事务只保护本服务内部事实，不保护外部消息 broker、支付渠道或其他服务。
- Outbox 当前只写 `PENDING`，发布到 broker 延后到后续阶段。
- 验证是独立证据链：从数据库事实重新计算一致性，而不是信任接口响应或日志。
- 余额用于在线读写和风控判断，账本用于审计、追溯和重建。两者必须同时存在，互相校验。

## 延伸阅读

- [01-domain-model.md](./docs/01-domain-model.md)
- [02-transaction-boundary.md](./docs/02-transaction-boundary.md)
- [03-outbox-flow.md](./docs/03-outbox-flow.md)
- [04-verification-from-mysql.md](./docs/04-verification-from-mysql.md)
- [05-failure-cases.md](./docs/05-failure-cases.md)
