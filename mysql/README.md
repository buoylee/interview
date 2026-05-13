# mysql/ — 旧笔记归档

> 这个目录的零散笔记已经在 2026-05 重写并整合进 [`../mysql-handson/`](../mysql-handson/) 的 12 章系统文档。

旧文件全部移到 [`_archive/`](_archive/) 保留，没删。新内容请去：

- **入口**：[`../mysql-handson/README.md`](../mysql-handson/README.md)
- **面试速查**：[`../mysql-handson/12-interview-cheatsheet/`](../mysql-handson/12-interview-cheatsheet/)
- **lab**：[`../mysql-handson/00-lab/`](../mysql-handson/00-lab/)

## 旧笔记 → 新章节对照

| 旧文件 | 内容已合并到 |
|---|---|
| `base.md` | ch01-architecture |
| `MVCC-BufferPool.md` | ch02-innodb-storage §3.3-3.4 + ch05 §3.4 |
| `索引.md` | ch03-indexing（已扩展） |
| `执行原理-binlog.md` + `执行计划.md` | ch04-execution-and-explain + ch07 §3.6 |
| `事务-隔离级别-锁.md` | ch05-mvcc-and-transaction + ch06-locking |
| `deadlock.md` | ch06-locking §3.7 |
| `binlog.md` | ch07-logs-and-crashsafe §3.5 |
| `分库分表-迁移.md` | ch10-sharding-and-scaling |
| `高可用.md` + `部署-架构.md` | ch09-replication-and-ha |
| `面试.md` + `collections.md` | ch12-interview-cheatsheet |

设计文档：[`../docs/superpowers/specs/2026-05-13-mysql-handson-design.md`](../docs/superpowers/specs/2026-05-13-mysql-handson-design.md)
