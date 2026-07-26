# Scenario 03: 少数派 Primary 必须被 fencing

## 我想验证的问题

Primary 被隔离为少数派时，是否会被 fencing，且多数派能否继续写入。

## 预期

隔离节点进入 `OFFLINE_MODE`／不可写，多数派继续写，重连后安全 rejoin。

## 环境与命令

```bash
make scenario SCENARIO=primary-partition
```
