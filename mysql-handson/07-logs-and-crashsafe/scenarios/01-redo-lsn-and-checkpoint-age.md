# Scenario 01: 看 redo LSN 推进 + checkpoint 滞后 —— WAL 的「两条进度线」

## 我想验证的问题

WAL 说「先写 redo log，脏页晚点刷」。这句话能不能在 `SHOW ENGINE INNODB STATUS` 的 LOG 段里**亲眼看到两条进度线分叉**？写一批数据后：

- LSN（写到哪了）会涨多少？
- checkpoint（刷盘刷到哪了）会不会跟着涨，还是落在后面？
- 「checkpoint age」是什么、为什么重要？

## 预期（基于 ch07 §3.3 推算）

- **LSN（Log Sequence Number）** = redo 日志写到的字节位置，每次修改都立即推进。
- **Last checkpoint** = 脏页已经安全刷到数据文件的位置，**滞后于 LSN**（这正是 WAL 的价值：改完先记 redo 就返回，脏页攒着批量刷）。
- 二者之差 = **checkpoint age** = 「已写 redo 但对应脏页还没落盘」的量。它越大，崩溃恢复要重放的 redo 越多；逼近 redo 容量上限时，InnoDB 会强制刷脏、触发写停顿。

预期：灌一批更新后，LSN 大涨，checkpoint 基本不动 → 两线分叉，checkpoint age 变大。

## 环境

- `mvcc_demo` + 存储过程 `flood(n)`（对 id=1 连做 n 次 UPDATE）
- 测量：`SHOW ENGINE INNODB STATUS\G` 的 `LOG` 段

## 步骤

```sql
-- 1. 空闲时看一次 LOG 段
SHOW ENGINE INNODB STATUS\G   -- 记下 Log sequence number / Last checkpoint at

-- 2. 灌 1 万次更新
CALL flood(10000);

-- 3. 再看 LOG 段，对比两条线
SHOW ENGINE INNODB STATUS\G
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
====== flood 前（空闲）======
LOG
---
Log sequence number          73310249
Log flushed up to            73310249
Pages flushed up to          73310249
Last checkpoint at           73310249      ← 四条线齐平：没有未刷的脏页

====== flood(10000) 后 ======
LOG
---
Log sequence number          79155110      ← LSN 涨了 5,844,861 字节(约 5.6MB)
Log flushed up to            79155110      ← redo 已落盘(顺序写)
Added dirty pages up to      79155110
Pages flushed up to          73310249      ← 脏页还停在老位置！
Last checkpoint at           73310249      ← checkpoint 没动
```

观察到的关键事实：

- 1 万次更新让 **LSN 推进了 ≈ 5.84 MB**（≈ 584 字节/次更新的 redo 量，含 undo 也是 redo 保护的）。
- **`Log flushed up to` 紧跟 LSN**：redo 是顺序写、立即落盘（默认 `innodb_flush_log_at_trx_commit=1` 每次提交 fsync）。
- **`Pages flushed up to` 和 `Last checkpoint at` 纹丝不动，停在 73310249**：对应的脏页还躺在 Buffer Pool 里没刷。这就是 WAL——**改动靠 redo 保证持久，数据页可以慢慢刷**。
- 此刻 **checkpoint age = 79155110 − 73310249 ≈ 5.6 MB**。如果继续猛写，这个差会逼近 redo log 总容量；到阈值时 InnoDB 会强制刷脏推进 checkpoint，表现为突发的写延迟尖刺（ch07 §3.3 的 async/sync flush 水位）。

## ⚠️ 预期 vs 实机落差

- 预期完全对上，而且「四条线在空闲时齐平、写入后分叉」这个画面非常直观地解释了 WAL：**redo 线冲在前面，脏页/checkpoint 线在后面追**。
- 直接可用的运维判断：`SHOW ENGINE INNODB STATUS` 里 LSN 与 Last checkpoint 差得越来越大、且 `Pages flushed` 追不上，说明刷脏能力跟不上写入 → 该调 `innodb_io_capacity`/`innodb_io_capacity_max`，或排查是不是 redo log（`innodb_redo_log_capacity`）开太小导致频繁强制 checkpoint。

## 连到的面试卡

- `99-interview-cards/q-wal-redo-checkpoint.md`
