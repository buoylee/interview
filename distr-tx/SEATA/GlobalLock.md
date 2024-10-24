[toc]

## 概述

@GlobalLock 避免脏读脏写



## 参考

https://seata.apache.org/zh-cn/blog/seata-at-lock/



从执行过程和提交过程可以看出，既然开启全局事务 `@GlobalTransactional`注解可以在事务提交前，查询全局锁是否存在，那为什么 Seata 还要设计多处一个 `@GlobalLock`注解呢？

因为并不是所有的数据库操作都需要开启全局事务，而开启全局事务是一个比较重的操作，需要向 TC 发起开启全局事务等 RPC 过程，而`@GlobalLock`注解只会在执行过程中查询全局锁是否存在，不会去开启全局事务，因此在不需要全局事务，而又需要检查全局锁避免脏读脏写时，使用`@GlobalLock`注解是一个更加轻量的操作。