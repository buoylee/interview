## 概述

binlog是mysql提供的日志，**所有存储引擎都可用**。



## binlog选择

### binlog_format=STATEMENT（默认）：

**记录sql语句**到binlog中。

优点: **不需要记录每一行的数据变化**，**减少binlog日志量**，节约IO，提高性能。

缺点: 是在某些情况下会导致 master-slave中的数据不一致( 如sleep()函数， last_insert_id()，以及user-defined functions(udf)等会 出 现 问题).

LOAD_FILE(), UUID(), USER(), FOUND_ROWS(), SYSDATE() (除非启动时启用了 --sysdate-is-now 选项) **不会复制**.

**READ-COMMITTED、READ-UNCOMMITTED隔离级别**或者参数innodb_locks_unsafe_for_binlog为ON时，**禁止binlog_format=statement下的写入**.



### binlog_format=ROW：

**仅记录哪条数据修改成什么样**。

优点: 不会出现某些特定情况下的**存储过程、或function、或trigger**的调用和触发**无法被正确复制**的 问题。

缺点: 产生大量的日志，尤其是alter table的时候会让日志暴涨。

### binlog_format=MIXED：

是以上两种level的混合使用，有函数用ROW，没函数用STATEMENT，但是无法识别系统变量



## 总结

对于线上业务，InnoDB等事务引擎，**RR以下隔离**级别的写入，**一定不要**设置为binlog_format为**`STATEMENT`**，否则业务就**无法写入**了。
而对于binlog_format为**`Mixed`**模式，**RR**隔离级别**以下**这些事务引擎也一定写入的**是ROW event**。



## 参考

[MySQL中使用binlog时binlog格式的选择](https://juejin.cn/user/377887733324024/posts)



