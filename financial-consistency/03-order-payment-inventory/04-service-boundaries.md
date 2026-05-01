# 04 服务边界

## 目标

本文件定义电商交易闭环中的服务职责。核心原则是：订单事实、库存事实、支付事实、退款事实、账本事实和对账事实分别由明确边界拥有，不能让一个服务偷偷完成所有事情。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `order-service` | 订单、订单明细、订单状态机、取消请求、订单幂等键 | 不直接扣库存，不直接确认渠道支付或退款事实 |
| `inventory-service` | 库存可售量、库存预留、确认、释放、库存流水 | 不决定订单是否支付成功，不处理退款 |
| `payment-service` | 支付单、支付回调、支付查询、支付渠道事实 | 不决定库存是否确认，不直接改订单历史 |
| `refund-service` | 退款单、退款提交、退款回调、退款查询、退款状态机 | 不直接回滚订单，不删除支付事实 |
| `ledger-service` | 支付、退款、冲正和差错修复分录 | 不覆盖历史分录，不替代订单或库存服务 |
| `reconciliation-service` | 订单/支付/库存/退款/账本对账、差错分类、修复工单 | 不直接修改订单、库存、支付、退款或分录 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 关键边界

- `order-service` 是订单状态 owner，但不是库存 owner、支付事实 owner 或退款事实 owner。
- `inventory-service` 根据订单命令处理库存预留、确认和释放，并生成库存流水。
- `payment-service` 只提供支付渠道事实和支付单状态，不直接确认库存。
- `refund-service` 只提供退款渠道事实和退款单状态，不直接删除原支付事实。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单和修复命令，自动修复也必须留下审计证据。

## 典型调用关系

### 下单

```text
order-service
-> inventory-service
-> order-service
-> message-broker
```

### 支付成功

```text
payment-service
-> order-service
-> inventory-service
-> ledger-service
-> message-broker
```

### 取消和退款

```text
order-service
-> inventory-service or refund-service
-> ledger-service
-> message-broker
```

### 对账

```text
reconciliation-service
-> order-service
-> payment-service
-> inventory-service
-> refund-service
-> ledger-service
-> repair workflow
```

## 不接受的设计

- `order-service` 直接扣减库存。
- 支付回调绕过订单状态机。
- 支付超时直接取消订单并释放库存。
- 已支付订单取消时直接改订单为取消，不创建退款单。
- 对账脚本直接改订单、库存、支付、退款或分录。
- 用消息 offset 作为订单、库存、支付或退款完成事实。
