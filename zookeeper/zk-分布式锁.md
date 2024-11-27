## 概述

****

注册临时node, 会生成一个后缀index递增的node 的 path(得到自己的锁的index), 
检查自己的创建的node, 检查是否是在 path下的 index == 0,
是, 则加锁成功,
不是, 则注册watch 监听 path 的 event. 触发时, 检查自己得所是否是index == 0.



## 公平/非公平/读写锁 实现(curator)



### protection创建模式

在**网络抖动等**异常时, 用于**判断创建node是否成功**

#### 原理

**生成uuid, 用于创建node时, 带上唯一标识, client重试时, 用uuid来验证是否就是刚刚创建的node.**



### 非公平

``` 
create dir
get -w dir
delete dir
```



### 公平

临时顺序node



### 读写锁

<img src="Screenshot 2024-11-27 at 10.40.48.png" alt="Screenshot 2024-11-27 at 10.40.48" style="zoom:33%;" />

**curator 的 InternallnterProcessMutex 读写实现**

### 原理

**上读锁时**, 
先找到自己的node; 
然后往上找第一个readLock, 如果存在readLock, 监听这个readLock; 如果不存在, 上锁成功.

**上写锁时,**
先找自己node;
然后监听自己的上一个node即可.



### 选主

<img src="Screenshot 2024-11-27 at 11.02.25.png" alt="Screenshot 2024-11-27 at 11.02.25" style="zoom: 50%;" />






## redis 分布式锁区别

**Redis分布式锁**：简单易用、**性能高**、适用于对性能要求较高的场景，但可能存在锁丢失或死锁的问题。
**redis 也有wait 来保证副本数, 但是因为不是2阶段提交, 假如写未过半, 已成功的node无法回滚**.

**ZooKeeper分布式锁**：**关键! 强一致性(顺序一致性, 通过事务ID), 写过半策略**, 来保证**可靠性高(有最新的副本)**、适用于对可靠性和顺序性要求较高的场景，
**不会死锁**, 但部署和维护较复杂，**性能较低**。

## 参考

[Zookeeper 分布式锁 （图解+秒懂+史上最全） ](https://www.cnblogs.com/crazymakercircle/p/14504520.html)  手写锁

[如何使用redis和zookeeper实现分布式锁?有什么区别优缺点?分别适用什么场景?](https://www.itheima.com/news/20230523/104210.html)



