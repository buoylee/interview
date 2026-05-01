# 04 服务边界

## 目标

本文件定义外部渠道场景下的服务职责。核心原则是：渠道事实、账户事实、账本事实和对账事实分别由不同边界拥有，不能让一个服务偷偷完成所有事情。

## 服务职责

| 服务 | 拥有什么 | 不拥有什么 |
| --- | --- | --- |
| `payment-service` | 充值单、提现单、支付单、渠道请求、回调幂等、业务状态机 | 不直接改账户余额，不直接写会计分录 |
| `channel-adapter` | 渠道调用、验签、查询、账单导入、渠道幂等号映射 | 不拥有业务终态，不决定用户余额 |
| `account-service` | 入账、冻结、释放冻结、消耗冻结、账户流水 | 不决定渠道是否成功 |
| `ledger-service` | 充值、提现、冲正和差错修复分录 | 不覆盖历史分录，不替代账户服务 |
| `reconciliation-service` | 渠道对账、账本对账、差错分类、修复工单 | 不静默修改资金 |
| `risk-service` | 提现风控、限额、风险拒绝 | 不处理渠道回调和出款结果 |
| `message-broker` | Outbox 事件投递和异步解耦 | 不代表业务事实本身 |

## 关键边界

- `payment-service` 是流程状态 owner，但不是资金 owner。
- `channel-adapter` 只提供渠道事实，不把渠道返回值直接变成本地成功。
- `account-service` 根据已确认命令修改账户，并生成账户流水。
- `ledger-service` 只追加分录或冲正分录，不删除历史。
- `reconciliation-service` 发现差异后生成差错单，自动修复也必须留下审计证据。

## 典型调用关系

### 充值

```text
payment-service
-> channel-adapter
-> payment-service
-> account-service
-> ledger-service
-> message-broker
```

### 提现

```text
payment-service
-> risk-service
-> account-service
-> channel-adapter
-> account-service
-> ledger-service
-> message-broker
```

### 渠道对账

```text
reconciliation-service
-> channel-adapter
-> payment-service
-> account-service
-> ledger-service
-> repair workflow
```

## 不接受的设计

- `payment-service` 直接更新余额。
- 回调处理绕过状态机。
- `channel-adapter` 决定本地成功或失败终态。
- 对账脚本直接改余额或改分录。
- 用消息 offset 作为入账、出款或对账完成事实。
