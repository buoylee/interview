[toc]



redis 事务, 有2种方式:

**MULTI** 和  **lua**

## multi 

multi 执行原理; 发送到 server 中的事务队列, `exec`后一并执行

事务回滚场景(命令不完整会导致回滚, 例如: incr )

watch 只能在 multi 前开启, 在 multi 内开启会报错, 但不会造成整个事务失败.

watch 的变量, 不会有ABA问题(只要出现过修改, 就会回滚)

Redis 事务保证了其中的一致性（C）(这里的一致性如果遇到例如 incr str, 就不会回滚)和隔离性（I），但并不保证原子性（A）和持久性（D）。

Refer: [redis 事务 事务机制详解 MULTI、EXEC、DISCARD、WATCH](https://www.cnblogs.com/myseries/p/11924733.html)  这个作者的其他文章也值得看

## lua

Lua 可以执行代码片段, 更好控制, 
多条命令一次性打包,有效地减少网络开销

执行的 lua 脚本, 并**不具有 ACID的原子性**, 
**redis lua脚本的原子性**, 只保证脚本作为一个整体执行且**不被其他事务打断/插入**.

### 可以利用的场景: 

分布式锁, 解锁:

```
if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("del",KEYS[1])
else
    return 0
end
```



检查剩余库存并扣减: 

```
// stock > num
// incrby key[item] -num
```





refer: [Redis 执行 Lua，能保证原子性吗](https://cloud.tencent.com/developer/article/2391645)

