[toc]

## 概述



## 问题解决

### 情况1：时钟回拨，雪花算法强依赖机器时钟，如果机器上时钟回拨，会造成发号重复。

我们可以维护一个上次生产ID的时间戳lastTimestamp，每次发号后更新lastTimestamp，
发号前则对比当前时间戳和lastTimestamp，当前时间戳比lastTimestamp小，就强制等待两者时间差后再发号，但这会造成发号服务处于不可用的状态。

### 情况2：在某一毫秒内，某些节点上的机器标识一致，并且产生了同一个序列号。

如果时间戳和序列号我们无法保证不重复，那就从机器标识下手。只要机器标识不重复，生成的ID自然也不会重复了。
如果我们的项目部署是机器级别，即一台机器上部署一套服务，那以机器MAC地址作为机器标识就可以。
如果是进程级别，即一台机器上部署多套相同的服务，仅仅是PID不同，这种情况下可以通过引入Redis、Zookeeper或者MySQL来保证机器标识位的唯一性。



## 参考

[还在用数据库自增ID做主键？建议了解一下雪花算法生成的分布式ID](https://juejin.cn/post/7170231638835036190)

[9种分布式ID生成方式，总有一款适合你](https://github.com/SoWhat1412/backend-learning/blob/master/tools/9%E7%A7%8D%E5%88%86%E5%B8%83%E5%BC%8FID%E7%94%9F%E6%88%90%E6%96%B9%E5%BC%8F%EF%BC%8C%E6%80%BB%E6%9C%89%E4%B8%80%E6%AC%BE%E9%80%82%E5%90%88%E4%BD%A0.md)

[分布式ID生成方案总结整理 ](https://www.cnblogs.com/mzq123/p/16840232.html) [常见分布式ID生成方案](https://blog.csdn.net/ThinkWon/article/details/123932818) **优缺点讲更多**

[一口气说出 9种 分布式ID生成方式，面试官有点懵了](https://cloud.tencent.com/developer/article/1584115)

[Mist 薄雾算法](https://pdai.tech/md/arch/arch-z-id.html#mist-%E8%96%84%E9%9B%BE%E7%AE%97%E6%B3%95)





