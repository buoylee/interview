# Scenario 07: 离群成员不能直接恢复服务

## 我想验证的问题

离群成员是否必须经过显式恢复阶段，才回到 Cluster 服务。

## 预期

`rejoin_begin` 先于 `rejoin_online`，成员经恢复阶段回到 ONLINE，三成员 ID 集完全相同。

## 环境与命令

```bash
make scenario SCENARIO=member-rejoin
```
