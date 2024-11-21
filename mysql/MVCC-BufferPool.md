## 概述

**MVCC（Multi-Version Concurrency Control）多版本并发控制机制**, 在读已提交和可重复读隔离级别, **实现读写隔离性**, 

## undo日志版本链与read view机制详解

每张表都有 **两个隐藏字段trx_id和roll_pointer**, 把这些undo日志串联起来形成一个历史记录版本链, 新记录头插.

<img src="Screenshot 2024-11-22 at 01.11.29.png" alt="Screenshot 2024-11-22 at 01.11.29" style="zoom: 33%;" />