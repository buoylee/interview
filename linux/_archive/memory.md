[toc]



## free

`free -h`

```
              total        used        free      shared  buff/cache   available
Mem:           8.0Gi       2.0Gi       4.0Gi       100Mi      2.0Gi       6.0Gi
```

**used = total - free - buff/cache** 
**available = free + buff/cache**

**buff/cache**: 虽然它们是已使用的内存，但由于可以很**容易被释放**，因此它们通常被**认为是“可回收的”内存**。
**buffers** **文件系统缓冲区**内存，存储文件系统**元数据**（如 inode、目录项等）以及一些块设备 I/O 的缓存(**IObuffer, 磁盘页缓存, 不足会刷盘或释放**)。
**cache** 由**应用程序**（或文件系统）用来**缓存文件**内容的内存。与缓冲区不同，缓存的内容可以根据需要被丢弃。**应用程序**缓存比**文件系统****缓存更难回收.



## 查看最高佔用(線程/進程)

**線程:**
ps aux --sort=-%mem

**進程:**
ps -eLo pid,tid,%mem,rss,command --sort=-%mem | grep "1234"  先查出所有process, 再過濾需要找對應process的Threads.

top -H -p 1234 或 top -H（然后按 M 排序）, 同理, 先查所有再過濾, -H是所有Thread.







## **RES (Resident Set Size)**

进程在物理内存中占用的内存总量，**不包括交换到磁盘的内存**，**包括共享内存**部分

**包含内容**：
进程自己的独立内存区域（比如堆和栈）。
共享库和其他进程共享的内存区域。
被进程实际使用的物理内存（即被加载到 RAM 中的部分）。

**不包括**：
交换空间（swap）的内存。
虚拟内存中的未被加载到物理内存的部分。



## **RSS (Resident Set Size)**

与 RES 类似, 但 **不包含共享内存**.