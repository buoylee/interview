# Scenario 03: 制造并检测 GTID errant（幽灵）事务

> ⚠️ **实机状态**：lab 步骤就绪。本次 session 因宿主 Docker 重启致从库网络损坏，未跑出真值；拓扑早段已验证可用。下方为强预期，请在稳定环境跑出真值替换。这条 scenario 是 [ch09 §3.11](../README.md) 的实证。

## 我想验证的问题

如果有人**直连从库写了一笔数据**（运维误操作），从库就多出一个主库没有的 GTID（errant 事务）。怎么用 `GTID_SUBTRACT` 把它揪出来？为什么它在故障切换时是定时炸弹？

## 预期（基于 ch09 §3.11 推算）

- 从库默认应开 `super_read_only=ON` 杜绝写入。一旦关掉它直连写，从库的 `gtid_executed` 里就多出一个 **server_uuid 是从库自己** 的 GTID（主库的复制流里没有）。
- 检测 = `GTID_SUBTRACT(从库的 gtid_executed, 主库的 gtid_executed)` —— 返回非空就是 errant 事务。
- 危害：故障切换让这个从库当新主时，其它从库会去拉这个幽灵事务，或因 GTID 集合对不上而复制中断。

## 环境 / 步骤

```bash
cd 00-lab   # (已 make up-replica && make replica-setup)

# 模拟误操作：关掉只读，直连从库写一笔
make mysql-replica
  -> SET GLOBAL super_read_only=0; SET GLOBAL read_only=0;
  -> CREATE TABLE sbtest.errant_demo(id INT PRIMARY KEY); INSERT INTO sbtest.errant_demo VALUES(99);

# 检测：从库有、主库没有的 GTID
make mysql          -> SELECT @@global.gtid_executed;     -- 记下主库的
make mysql-replica  -> SELECT GTID_SUBTRACT(@@global.gtid_executed, '<上面主库的字符串>');

# 复原
make mysql-replica
  -> DROP TABLE sbtest.errant_demo; SET GLOBAL super_read_only=1; SET GLOBAL read_only=1;
```

## 实机告诉我（强预期，待跑真值替换）

```
# 主库 gtid_executed:
fd8a0403-...:1-203          (server_uuid = 主库的)

# 从库 gtid_executed（多出一段从库自己 uuid 的 GTID）:
fd8a0403-...:1-203,
9c1f77aa-...:1              ← 从库 uuid，主库根本没有

# GTID_SUBTRACT(replica, primary) =
9c1f77aa-...:1              ← 这就是 errant 事务，一眼揪出
```

## ⚠️ 预期 vs 实机落差（跑完补）

- 重点验证：`GTID_SUBTRACT` 精确返回那个从库独有的 GTID。
- 处理（ch09 §3.11）：确认幽灵数据无业务价值后，在新主上为该 GTID **注入空事务**（`SET GTID_NEXT='9c1f77aa-...:1'; BEGIN; COMMIT; SET GTID_NEXT='AUTOMATIC';`）让新主 gtid 集合覆盖它；预防靠 `super_read_only=ON` + 运维只走只读账号。

## 连到的面试卡

- `99-interview-cards/q-gtid-auto-resume.md`（含 errant 检测追问）
