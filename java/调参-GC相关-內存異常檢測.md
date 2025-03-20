

[toc]

## 堆

```
-Xms450m -Xmx450m -Xmn128m -Xss512k
初始堆 
最大堆
年轻代堆
每个线程的栈内存
```



堆初始 和 堆最大值 一样, 避免频繁扩缩容造成性能影响. -Xms50M 和 -Xmx50M, 这样记, ms == memory small(刚开始最小的时候); mx == memory max.



## 元空间

-XX:Metaspacesize=256M -XX:MaxMetaspacesize=256M
**触发GC**时的元空间大小, 最大的元空间大小.





## 估算GC时间/空间

通过工具统计 minor/full GC 频率, 
得知当前 eden + 1个survivor 空间, older 区 空间, 来计算平均多长时间产生多少内存垃圾.



## 思路

减少full GC, 使更少对象进入older, 可以尝试调大 年轻代, 或调大 cms的触发older  GC时的 **older区占用比**



## Native Memory Tracking

可以檢測內存泄露, 和相關堆棧信息



## 參考

[【JVM进阶之路】十：JVM调优总结](https://www.cnblogs.com/three-fighter/p/14644152.html)

https://www.cnblogs.com/three-fighter/p/14644152.html

[阿里面试100%问到，JVM性能调优篇](https://cloud.tencent.com/developer/article/1478420)





