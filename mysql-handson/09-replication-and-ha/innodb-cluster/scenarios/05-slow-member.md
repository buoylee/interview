# Scenario 05: 慢成员如何触发 backlog 与 flow control

## 我想验证的问题

慢成员是否会使 applier queue 跨过生效中的 QUOTA threshold，并在恢复后追平。

## 预期

core Performance Schema 的 applier queue 跨过生效中的 QUOTA threshold；记录前后 p95 写延迟但不把易受环境噪声影响的延迟升高设为硬断言；成员最终追平。

## 环境与命令

```bash
make scenario SCENARIO=slow-member
```
