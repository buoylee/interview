

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

## refer: 

[redis 分布式锁 ](https://www.cnblogs.com/myseries/p/11720508.html)
[Is Redlock safe?](http://antirez.com/news/101)