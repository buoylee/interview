# Scenario 02: Primary crash 后谁完成 failover

## 我想验证的问题

Primary crash 后，多数派、Router 与客户端如何完成 failover。

## 预期

多数派选新 Primary、Router 只迁移新连接、所有 SUCCESS 存在，并量出 detection／election／backlog fence／Router refresh／application reconnect 五段 RTO。

## 环境与命令

```bash
make scenario SCENARIO=primary-crash
```
