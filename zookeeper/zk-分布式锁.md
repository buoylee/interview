## 概述

注册临时node, 会生成一个后缀index递增的node 的 path(得到自己的锁的index), 
检查自己的创建的node, 检查是否是在 path下的 index == 0,
是, 则加锁成功,
不是, 则注册watch 监听 path 的 event. 触发时, 检查自己得所是否是index == 0.

## redis 分布式锁区别

**Redis分布式锁**：简单易用、**性能高**、适用于对性能要求较高的场景，但可能存在锁丢失或死锁的问题。

**ZooKeeper分布式锁**：**强一致性和顺序性**保证、可靠性高、适用于对可靠性和顺序性要求较高的场景，**不会死锁**, 但部署和维护较复杂，**性能较低**。

## 参考

[Zookeeper 分布式锁 （图解+秒懂+史上最全） ](https://www.cnblogs.com/crazymakercircle/p/14504520.html)  手写锁

[如何使用redis和zookeeper实现分布式锁?有什么区别优缺点?分别适用什么场景?](https://www.itheima.com/news/20230523/104210.html)

