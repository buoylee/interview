[TOC]

## 简述

### swap

swap(虚拟内存): 只是用来暂存, 内存放不下的数据. 和 page cache 不同.

**一些中间件建议关闭 `Swap`的原因是**:
**性能问题：** 例如 `ES`，`GC`会遍历所用到的堆的内存, 如果有内存被 `Swap` 到磁盘，那么 `GC` 遍历时就会去查磁盘,  `IO` 很慢，就会导致程序 `STW` 假死一段时间。
**管理问题：** 例如 `K8s`，开启 `Swap`后通过 `Cgroups` 设置的内存上限就会失效。

### mmap(是一个系统调用方法用来 替换read())/page cache

使用 mmap 就会 直接写到 page cache.
mmap 相对于 普通IO, 省去了从用户态到内核的文件系统这一步, 因为 `内核的文件系统` 还是会去找 `page cache` 或 direct IO.

### 0拷贝

从 OS的 mappedBuffer 直接拷贝到 socketBuff

## 参考

[kafka中使用的mmap和page cache](https://guosmilesmile.github.io/2020/02/11/kafka%E4%B8%AD%E4%BD%BF%E7%94%A8%E7%9A%84mmap%E5%92%8Cpage-cache/)

[一文明白 Linux 内存 Page Cache 和 Swap](https://juejin.cn/post/7125820067262464007) 这里有图

[认真分析mmap：是什么 为什么 怎么用 ](https://www.cnblogs.com/huxiao-tee/p/4660352.html)



