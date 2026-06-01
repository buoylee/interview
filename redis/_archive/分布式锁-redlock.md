

[toc]





## 讨论: 

java环境有 [Redisson](https://github.com/mrniko/redisson) 可用于**生产环境**，但是分布式锁还是Zookeeper会比较好一些（可以看Martin Kleppmann 和 RedLock的分析）。Martin Kleppmann对RedLock的分析：http://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
RedLock 作者 antirez的回应：http://antirez.com/news/101

## 总结:

**作者承认**：Redlock 存在锁过期后互斥性可能被破坏的风险，但这是所有自动释放锁的共性问题。

**作者的观点**：只要合理设计，例如通过 **时间检查** 和 **随机 token**，Redlock 依然能在大多数场景中可靠地工作。

**作者的结论**：Redlock 不是完美的，但它的设计已经尽可能在**复杂性和性能**之间取得了平衡。

所以，Redlock 的确存在互斥性破坏的风险，但作者认为这个问题在可接受范围内，并且通过设计和使用策略可以在绝大多数场景下规避。



## 关于强一致性:

https://stackoverflow.com/questions/60573175/is-redisson-getlock-safe-for-distributed-lock-usage

https://github.com/redisson/redisson/issues/2669
上述issue, 使用WAIT命令来达到强一致性.
https://xie.infoq.cn/article/627c894e38277b17fea31027d
这里也解释了, 新的 rlock, 同步到所有slave, 进一步降低并发现象.

```
WAIT <numslaves> <timeout>
```

​	•	numslaves：指定你希望至少有多少个 **副本节点**（replicas）确认接收到数据。

​	•	timeout：指定最大等待时间（单位：毫秒）。即使没有达到预期的副本数量，等待会在超时时间后结束。



## 出现并发问题情况

- 假死, 无法续期, 导致锁提前释放
- 

## refer: 

[redis 分布式锁 ](https://www.cnblogs.com/myseries/p/11720508.html)
[Is Redlock safe?](http://antirez.com/news/101)