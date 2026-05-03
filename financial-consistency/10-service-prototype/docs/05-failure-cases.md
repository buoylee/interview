# 05 失败场景

本章用正常路径和坏历史 fixture 一起说明验证边界。服务路径证明本地事务如何写事实，fixture 路径证明验证器不会只相信服务代码。

## 正常转账

请求 A-001 向 B-001 转账，幂等键首次出现且余额充足。

预期事实：

- `idempotency_record` 从 `PROCESSING` 完成为 `SUCCEEDED`，保存业务 ID 和响应体。
- `transfer_order` 为 `SUCCEEDED`。
- `ledger_entry` 有两行，一条 `DEBIT`，一条 `CREDIT`。
- `account` 中 A-001 余额减少，B-001 余额增加。
- `outbox_message` 有一行 `PENDING` 的 `TransferSucceeded`，`aggregate_type` 为 `TRANSFER`。

预期验证结果：没有 `DbInvariantViolation`。

## 重复请求

同一个幂等键、相同 payload 再次提交。

预期事实：

- 不新增第二笔 `transfer_order`。
- 不新增第二组 `ledger_entry`。
- 不新增第二条成功 Outbox。
- 返回第一次请求保存的响应。

这个场景保护客户端超时重试。幂等表是入口处的业务锁，不让重试变成重复扣款。

## 同幂等键不同 payload

同一个幂等键携带不同账户、金额或币种再次提交。

预期事实：

- 服务返回拒绝响应。
- 不创建新的成功转账单。
- 不写新的账本或成功 Outbox。

这个场景防止调用方错误复用幂等键。相同 key 只能代表同一个业务意图，不能被后来的 payload 改写。

## 余额不足

转出账户可用余额小于转账金额。

预期事实：

- `transfer_order` 写为 `FAILED`，失败原因可解释为余额不足。
- `idempotency_record` 写为 `FAILED`，保存响应。
- 不写 `ledger_entry`。
- 不写 `TransferSucceeded` Outbox。

Task 6 的验证器要求失败转账不能有账本。如果人为给失败转账补入账本，会同时触发 `FAILED_TRANSFER_HAS_NO_LEDGER` 和 `LEDGER_REQUIRES_SUCCEEDED_TRANSFER`。

## 单边账本 fixture

测试或脚本直接插入一笔 `SUCCEEDED` 转账，但只插入一条 `ledger_entry`。

预期验证结果：

- `TransferMysqlVerifier` 报告 `LEDGER_DOUBLE_ENTRY_REQUIRED`。

这个 fixture 证明验证器要求双分录，而不是只检查“有账本就行”。

## 缺失 Outbox fixture

测试或脚本直接插入一笔 `SUCCEEDED` 转账和完整双分录，但不插入 `outbox_message`。

预期验证结果：

- `TransferMysqlVerifier` 报告 `TRANSFER_OUTBOX_REQUIRED`。

这个 fixture 证明成功业务事实必须带着可恢复的事件事实提交。否则服务崩溃后，后续发布器没有任何 `PENDING` 行可恢复，外部系统也无法可靠得知这笔成功转账。
