# Scenario 01: 计划内切换不是零断线

## 我想验证的问题

计划内切换后，新旧 Primary 是否唯一；既有连接是否可能断开，以及写入何时恢复。

## 预期

新旧 Primary 唯一、既有连接可断、写入恢复、量出 RTO。

## 环境与命令

```bash
make scenario SCENARIO=planned-switchover
```
