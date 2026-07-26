# Scenario 04: 没有多数派宁可停止写

## 我想验证的问题

失去多数派时，故障窗口内是否停止接受新写入，并在 quorum 恢复后才继续。

## 预期

在 `fault_active` 后才开始、并于 `quorum_restore_begin` 前完成的请求零 SUCCESS，避免把故障前已跨过提交边界的 in-flight 请求误判为无 quorum 写入；默认 3 秒窗口保持在 Lab 的 5 秒 unreachable-majority timeout 内；恢复 quorum 后才继续。

## 环境与命令

```bash
make scenario SCENARIO=quorum-loss
```
