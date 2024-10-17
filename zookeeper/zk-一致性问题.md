[toc]

## 一致性问题概述

写请求时, leader 会向 `所有follower`  提交 proposal, 
收到 proposal 的 follower 会 返回成功给 leader,
当超过半数node成功时, leader会广播 follower 执行 commit操作.

所以, 由上可知, zookeeper 并不能保证读操作**在任何节点/任何时候**的强制一致性, 但保证了最终一致性。

严格说【Zookeeper如果只有写请求时，是线性一致性的；如果从读和写的角度来说是顺序一致性的】

总结一下：**Zookeeper并不保证读取的是最新数据：实现了CAP中的A-可用性、P-分区容错性、C-写入强一致性，丧失了C-读取一致性**。

## 参考:

[深入理解Zookeeper数据一致性问题](https://www.cnblogs.com/jelly12345/p/15603515.html)

[Zookeeper一致性级别](https://juejin.cn/post/6844903922843287559)

[ZooKeeper的顺序一致性属于强一致性?](https://cloud.tencent.com/developer/article/1911234) Consistency(一致性)、Consensus(共识). 一致性解释

[Apache ZooKeeper - 集群中 Observer 的作用以及 与 Follow 的区别](https://cloud.tencent.com/developer/article/1863322)  **observer 不参与写请求**

