## 重排序 和 内存屏障 关系

重排序可以**出现在编译/处理器**, 处理器就是硬件层面的, 汇编, 

内存屏障有**处理器的和 JVM的**

## 硬件层内存屏障
硬件层提供了一系列的内存屏障 memory barrier / memory fence（Intel的提法）来提供一致性的能力。X86有几种主要
的内存屏障：

1. Ifence，是一种Load Barrier 读屏障

2. sfence， 是一种Store Barrier 写屏障

3. mfence，是一种全能型的屏障，具备lfence和sfence的能力

4. Lock前缀，Lock不是一种内存屏障，但它能完成类似内存屏障的功能。Lock会对CPU总线和高速缓存加锁，可以理解为CPU指令级的一种锁。它后面可以跟ADD, ADC, AND, BTC, BTR, BTS, CMPXCHG, CMPXCH8B, DEC, INC, NEG, NOT, OR, SBB，SUB, XOR, XADD, and XCHG等指令。

## 內存屏障有两个能力：

1. 阻止屏障前后的指令重排序
2. 刷新处理器缓存/冲刷处理器缓存





## 内存屏障作用

保证 **屏障前的操作, 在屏障后一定读得到(可见性)**, 也就是**阻止了重排序(屏障前的一定先执行)**

在JSR规范中定义了**4种内存屏障**：
LoadLoad屏障：（指令Load1;LoadLoad; Load2），在Load2及后续读取操作要读取的数据被访问前，保证Load1要读取的数据被读取
完毕。
LoadStore屏障：（指令Load1;LoadStore; Store2），在Store2及后续写入操作被刷出前，保证Load1要读取的数据被读取完毕。
StoreStore屏障：（指令Store1；StoreStore; Store2），在Store2及后续写入操作执行前，保证Store1的写入操作对其它处理器可见。

**StoreLoad屏障**：（指令Store1;StoreLoad; Load2），在Load2及后续所有读取操作执行前，保证Store1的写入对所有处理器可见。它的开销是四种屏障中最大的。在大多数处理器的实现中，这个屏障是个万能屏障，兼具其它三种内存屏障的功能

由于x86只有store load可能会重排序，所以**只有JSR的StoreLoad屏障**对应它的mfence或lock前缀指令，**其他屏障对应空操作**

## JAVA 手动开启屏障

```
UnsafeFactory.getUnsafe().storeFence();
```

## volatile

**可见性**：读一个volatle变量，总是能看到（任意线程）对这个volatile变量最后的写入(时间上的确是先执行的, 所以**多线程间先后顺序不保证**)。
**原子性**：**只对任意单个volatile变量的读/写具有原子性**，但类似于**volatile++**这种**复合操作不具有原子性**（**基于这点，我们通过会
认为volatile不具备原子性**）。volatile仅仅保证对单个volatle变量的读/写具有原子性，而锁的互斥执行的特性可以确保对整个临界
区代码的执行具有原子性。
**例**: 64位的long型和double型变量，只要它是volatile变量，对该变量的读/写就具有原子性。
**有序性**：对volatile修饰的变量的读写操作前后加上各种特定的内存屏障来禁止指令重排序来保障有序性。

