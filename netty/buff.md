## 数据结构

和NIO不同
有 读/写指针, 元素容量, 还有字节len等.



## bytebuf

3纬度
pool/Unpool,
 Heap/Direct
...Strong/Weak/Soft/Phantom?



## 回收

**UnpooledHeap**ByteBuf 底下的byte[]能够**依赖JVM GC自然回收**

**UnpooledDirect**ByteBuf底下是DirectByteBuffer, 除了等JVM GC，**最好也能主动进行回收**

**Pooled**HeapByteBuf 和 PooledDirectByteBuf，则必须要主动将用完的byte[]/ByteBuffer放回池里.
所以，Netty **ByteBuf**需要在JVM的GC机制之外，有自己的**引用计数器和回收过程**。



## 谁来Release

因为Handler链的存在，ByteBuf经常要传递到下一个Hanlder去而不复还，所以规则变成了谁是**最后使用者，谁负责释放**。



## 引用

Strong Reference : **没有**任何对象指向它时,  **GC** 执行后将会**被回收**

WeakReference & WeakHashMap : **所引用的对象**在JVM 内**不再有强引用**时, GC 后 weak reference 将会被自动回收
WeakHashMap 使用 WeakReference 作为 key， 一旦没有指向 key 的强引用, WeakHashMap 在 GC 后将自动删除相关的 entry 

SoftReference: **和 WeakReference 基本一样**, 直到 JVM **内存不足**时才会**被回收(虚拟机保证)**, 这一特性使得 SoftReference 非常适合缓存应用 

PhantomReference : 它的 get() 方法永远返回 null, 唯一的用处就是**跟踪 referent** 何时被 **enqueue 到 ReferenceQueue** 中. 优点: 准确地知道**对象何时**被从内存中删除; **避免**某个对象重载了 finalize, 导致**GC 无法回收**这个对象并有可能 **引起**任意次 GC.
RererenceQueue : 对象**被回收时**， **虚拟机**会自动将这个对象**插入到 ReferenceQueue** 



## 正確處理(釋放) buff

https://juejin.cn/post/7229165980932276285
https://netty.io/wiki/reference-counted-objects.html
https://blog.csdn.net/qq_38411796/article/details/139897991



## 参考

[Netty之有效规避内存泄漏 ](https://www.cnblogs.com/549294286/p/5168454.html)

[Java的引用StrongReference、 SoftReference、 WeakReference 、PhantomReference](https://blog.csdn.net/mxbhxx/article/details/9111711)



