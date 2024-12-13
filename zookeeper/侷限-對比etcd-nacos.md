[toc]



## 概述

**内存空间**：Zookeeper 的所有数据都存储在内存中，包括 DataNode、Key Path、Watcher 等，内存上限就是 Zookeeper Server 的数据存储上限，因此 Zookeeper 只能存储 GB 级别的数；另一方面过多的数据量也会增加 GC 的压力，降低哈希表查询的性能，都会请求响应速度；
Zookeeper为了保证高吞吐和低延迟，在**内存**中维护了这个**树状的目录结构**，这种特性使得Zookeeper**不能用于存放大量的数据**，每个节点的存放数据**上限为1M**。

**持久化**：Zookeeper 的持久化机制是基于文件系统的，每次写入操作都会同步操作日志到磁盘，同样会增加写入操作的延迟，降低写入性能；





## 對比nacos 

### 服務發現

目前還是只看到從AP來對比





## 參考



[谈谈 ZooKeeper 的局限性](https://wingsxdu.com/posts/database/zookeeper-limitations/#%E6%80%A7%E8%83%BD%E7%93%B6%E9%A2%88) 與etcd對比

[ZooKeeper读写性能不佳问题分析](https://developer.baidu.com/article/details/2898007)

[ZooKeeper的性能如何？在处理大量并发请求的情况下，如何优化ZooKeeper的性能？是否有任何局限性或常见的问题需要注意？](https://yifan-online.com/zh/km/article/detail/18002)



[为什么我们要把服务注册发现改为阿里巴巴的Nacos而不用 ZooKeeper？](https://blog.csdn.net/u012921921/article/details/106521181) 有點水?









