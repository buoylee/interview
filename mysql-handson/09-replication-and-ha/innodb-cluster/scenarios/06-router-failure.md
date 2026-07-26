# Scenario 06: 双 Router 解决入口单点

## 我想验证的问题

Router A 失败时，Router B 是否仍能在故障窗口继续完成写入。

## 预期

Router A worker 失败或未知，Router B worker 在故障窗仍有 SUCCESS。

## 环境与命令

```bash
make scenario SCENARIO=router-failure
```
