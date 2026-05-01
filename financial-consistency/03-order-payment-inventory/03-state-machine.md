# 03 状态机

## 设计原则

状态机的任务是防止订单、库存、支付和退款事实互相覆盖。所有状态推进都必须基于耐久事实和合法转换，不能只基于一次 RPC 返回值、回调或消息消费结果。

## 订单状态

正常履约路径：

```text
CREATED
-> STOCK_RESERVED
-> PENDING_PAYMENT
-> PAID
-> STOCK_CONFIRMED
-> FULFILLABLE
```

取消和退款路径：

```text
CANCEL_REQUESTED
-> CANCELLED
```

可信支付失败取消路径：

```text
PAYMENT_UNKNOWN -> PAYMENT_FAILED -> CANCEL_REQUESTED -> CANCELLED
```

```text
PAID
-> REFUND_REQUIRED
-> REFUNDING
-> REFUNDED
-> CLOSED
```

异常和人工状态：

```text
PAYMENT_UNKNOWN
PAYMENT_FAILED
STOCK_CONFIRM_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `PENDING_PAYMENT` 可以取消并释放库存。
- `PAID` 不能直接取消成 `CANCELLED`，必须进入退款、履约前取消或人工处理路径。
- `PAYMENT_UNKNOWN` 不能直接释放库存或取消成终态。
- `PAYMENT_UNKNOWN` 只有拿到可信支付失败事实后，才能进入 `PAYMENT_FAILED`，再走取消和库存释放路径。
- `CANCELLED` 后收到支付成功必须进入退款或人工处理。
- `FULFILLABLE` 表示本阶段可履约，第一版不展开发货和退货。

## 库存预留状态

成功确认路径：

```text
RESERVED
-> CONFIRMED
```

取消释放路径：

```text
RESERVED
-> RELEASED
```

异常状态：

```text
RESERVE_FAILED
CONFIRM_FAILED
RELEASE_FAILED
MANUAL_REVIEW
```

关键规则：

- `CONFIRMED` 和 `RELEASED` 是互斥终态。
- `RELEASED` 后不能确认同一预留。
- `CONFIRMED` 后不能释放同一预留。
- 重复确认或重复释放必须幂等返回既有结果。

## 支付单状态

```text
CREATED
-> CHANNEL_PENDING
-> CHANNEL_UNKNOWN
-> CHANNEL_SUCCEEDED
-> APPLIED_TO_ORDER
-> SUCCEEDED
```

可信失败路径：

```text
CHANNEL_PENDING -> CHANNEL_FAILED -> FAILED
CHANNEL_UNKNOWN -> CHANNEL_FAILED -> FAILED
```

失败和人工状态：

```text
CHANNEL_FAILED
FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `CHANNEL_UNKNOWN` 不能被当作失败。
- `CHANNEL_FAILED` 必须基于可信渠道失败、查询或对账事实；失败事实不能覆盖已经确认的成功事实。
- `CHANNEL_SUCCEEDED` 之后必须推进订单；如果订单已经取消，必须进入退款或人工处理。
- `SUCCEEDED` 不能被失败回调覆盖。
- 支付单成功不自动代表库存已确认。

## 退款单状态

```text
CREATED
-> REFUND_SUBMITTED
-> REFUND_UNKNOWN
-> REFUND_SUCCEEDED
-> ORDER_REFUNDED
-> LEDGER_POSTED
-> SUCCEEDED
```

失败和人工状态：

```text
REFUND_FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

关键规则：

- `REFUND_UNKNOWN` 不能重复提交外部退款。
- `REFUND_SUCCEEDED` 后必须推进订单和分录。
- `REFUND_FAILED` 不能覆盖已经确认的退款成功事实。
- 退款成功不删除原支付事实，只追加退款事实和分录。

## 非法转换示例

| 非法转换 | 原因 |
| --- | --- |
| `PAYMENT_UNKNOWN -> CANCELLED` | 支付未知不是失败，不能直接取消并释放库存。 |
| `PAID -> CANCELLED` | 已支付订单取消必须进入退款或人工处理路径。 |
| `RELEASED -> CONFIRMED` | 库存已释放后不能确认同一预留。 |
| `CONFIRMED -> RELEASED` | 库存已确认后不能释放同一预留。 |
| `REFUND_UNKNOWN -> REFUND_SUBMITTED` | 退款未知不能重复提交外部退款。 |
| `支付单：SUCCEEDED -> CHANNEL_FAILED` | 失败回调不能覆盖已确认成功终态。 |
