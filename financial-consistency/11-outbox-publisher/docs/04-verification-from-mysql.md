# 04 从 MySQL 事实验证

本章验证的重点是独立证据链。接口返回成功不等于系统一致，服务日志也不等于事实；真正的输入是 MySQL 已提交的行。

## 验证链路

验证链路固定为：

```text
MySQL rows -> DbFact -> DbHistory -> TransferMysqlVerifier -> DbInvariantViolation
```

- `MySQL rows`：`account`、`transfer_order`、`idempotency_record`、`ledger_entry`、`outbox_message`、`consumer_processed_event` 中已经提交的行。
- `DbFact`：把每一行抽象成表名、事实 ID、业务 ID 和属性集合。
- `DbHistory`：把一组数据库事实组成可验证历史。
- `TransferMysqlVerifier`：只读取 `DbHistory`，按资金不变量做判断。
- `DbInvariantViolation`：输出违反的不变量、原因和相关事实 ID。

验证器不复用 `TransferService`、Repository 写入逻辑或接口响应构造逻辑。它不问“服务认为自己做了什么”，只问“数据库事实能否支持这笔转账是一致的”。

## 当前检查的不变量

当前实现重点检查这些规则：

- 成功转账必须有且只有两条账本分录，一条 `DEBIT`，一条 `CREDIT`，否则报告 `LEDGER_DOUBLE_ENTRY_REQUIRED`。
- 两条账本分录必须金额一致、币种一致，并且与 `transfer_order` 的金额和币种一致，否则报告 `LEDGER_BALANCED`。
- 成功转账必须有 `aggregate_type = TRANSFER`、`event_type = TransferSucceeded` 的 Outbox，否则报告 `TRANSFER_OUTBOX_REQUIRED`。
- 同一笔成功转账只能有一条 `aggregate_type = TRANSFER`、`event_type = TransferSucceeded` 的 Outbox，否则报告 `TRANSFER_OUTBOX_SINGLE_SUCCEEDED_EVENT`。
- 失败转账不能有账本，否则报告 `FAILED_TRANSFER_HAS_NO_LEDGER`。
- 任意账本分录都必须引用已成功转账，否则报告 `LEDGER_REQUIRES_SUCCEEDED_TRANSFER`。
- 同一个幂等键不能对应多个成功业务 ID，否则报告 `IDEMPOTENCY_KEY_SINGLE_SUCCESSFUL_BUSINESS_ID`。
- `TransferSucceeded` Outbox 如果已经有发布尝试，并且仍停在 `FAILED_RETRYABLE` 或 `PUBLISHING`，报告 `OUTBOX_PUBLISH_REQUIRED`。
- `PUBLISHED` Outbox 必须有配置消费者组的 `consumer_processed_event(PROCESSED)`，否则报告 `CONSUMER_PROCESSED_PUBLISHED_EVENT`。
- 同一消费者组内，同一 `event_id` 不能有多条成功消费事实，否则报告 `CONSUMER_IDEMPOTENT_PROCESSING`。

这些规则会故意抓住 fixture 造出的坏历史，例如单边账本、缺失 Outbox、账本引用失败转账、已发布事件缺少配置消费者组的处理事实、同一消费者组重复处理同一事件。验证器的价值就在这里：它可以发现服务之外、脚本之外或人工修复造成的数据库事实不一致。

Kafka offset 不参与这些业务不变量。offset 只能说明消费者组对 broker 的读取进度，不能替代 `consumer_processed_event` 里的本地处理事实。
