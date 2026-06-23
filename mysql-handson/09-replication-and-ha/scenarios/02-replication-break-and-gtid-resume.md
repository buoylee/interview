# Scenario 02: 主从断裂 + 靠 GTID 自动续传恢复

> ⚠️ **实机状态**：lab 步骤就绪（`make chaos-replica-cut` / `chaos-restore`）。本次 session 因宿主 Docker 重启致从库网络损坏，未跑出真值；拓扑早段已验证可用。下方为强预期，请在稳定环境跑出真值替换。

## 我想验证的问题

主从网络断了几十秒（主库继续写），网络恢复后，从库能**自己**追上吗？还是要人工干预重新指位点？GTID `Auto_Position=1` 在这里起什么作用？

## 预期（基于 ch09 §3.1 / §3.3 推算）

- 断网时从库 **IO thread 报错并停**（拉不到 binlog），`Replica_IO_Running` 变 `Connecting`/`No`，`Last_IO_Error` 有连接错误。这期间主库照写，从库行数停住。
- 网络恢复后，因为 `SOURCE_AUTO_POSITION=1`，从库用 **GTID 自动定位**：它把自己 `gtid_executed` 告诉主库，主库从「缺的那个 GTID」开始补发——**不需要人工记位点**，从库自动续上、追平。
- 这正是 GTID 相对传统「binlog file + position」的最大好处：断点续传不用人算位点。

## 环境 / 步骤

```bash
cd 00-lab   # (已 make up-replica && make replica-setup)

make chaos-replica-cut                     # 切断主→从（toxiproxy timeout=0）
make mysql -> INSERT INTO repl_demo(v) SELECT 2 FROM information_schema.columns LIMIT 100;
make mysql-replica -> SHOW REPLICA STATUS\G        # IO thread 应停/报错

make chaos-restore                         # 恢复网络
make mysql-replica -> SHOW REPLICA STATUS\G        # 看是否自动 Yes/Yes、追平
```

## 实机告诉我（强预期，待跑真值替换）

```
# 断网期间从库：
Replica_IO_Running: Connecting        ← 拉不到 binlog
Replica_SQL_Running: Yes
Last_IO_Error: Error reconnecting to source ... (timeout / can't connect)
# 此时 primary repl_demo 行数=300，replica 行数=200（停住）

# make chaos-restore 后等几秒：
Replica_IO_Running: Yes               ← 自动重连
Replica_SQL_Running: Yes
Seconds_Behind_Source: 0
# replica repl_demo 行数=300          ← GTID 自动续传，无需人工干预就追平
```

## ⚠️ 预期 vs 实机落差（跑完补）

- 重点验证：恢复网络后从库**没有任何人工操作**就自己 Yes/Yes 并追平——这就是 `Auto_Position=1`（GTID）的价值。
- 对照面试题「GTID vs 位点切换」：位点模式断点续传要人工 `CHANGE ... SOURCE_LOG_FILE/POS`，算错就丢数据或重复；GTID 模式从库报上自己的集合、主库补差集，天然幂等（ch09 §3.3）。

## 连到的面试卡

- `99-interview-cards/q-gtid-auto-resume.md`
