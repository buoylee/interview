## 概述

线程安全, 还能起到一个隔离的作用。

## 分类

**有界**:

**无界**: LinkedBlockingoueue



## BlockingQueue常用API

<img src="Screenshot 2024-11-17 at 18.37.13.png" alt="Screenshot 2024-11-17 at 18.37.13" style="zoom: 33%;" />

## 类型

<img src="Screenshot 2024-11-17 at 19.58.39.png" alt="Screenshot 2024-11-17 at 19.58.39" style="zoom: 33%;" />

## ArrayBlockingQueue

最典型的**有界环形(index到达len时归0)阻塞队列**，用数组存储元素，**初始化需要指定容量**，利用**ReentrantLock 实现线程安全**。

在**生产者-消费者**模型中使用时，如果生产速度和**消费速度基本匹配**的情况下，**使用ArrayBlockingQueue**是个不错选择；
存取是同一把锁，操作同一个数组对象，**存取互斥**.

不可扩容
2个condition: notEmpty, notFull

###  **put()** 

通过 notFull.await(); 阻塞

<img src="Screenshot 2024-11-17 at 20.44.11.png" alt="Screenshot 2024-11-17 at 20.44.11" style="zoom:33%;" />

### dequeue
<img src="Screenshot 2024-11-17 at 21.05.30.png" alt="Screenshot 2024-11-17 at 21.05.30" style="zoom:33%;" />



## LinkedBlockingQueue

无界阻塞队列，可以指定容量，默认为Integer.MAX_VALUE，先进先出，存取大致互不干扰.

**线程池中为什么使用LinkedBlockingQueue而不用ArrayBlockingQueue？**
性能比 ArrayBlockingQueue 高, **2个锁, 提高吞吐量.**

### LinkedBlockingQueue#put

Put后, 如果**queue未满**, 先**通知其他wait**的put()线程
```
if(c + 1 < capacity)
	notFull.signal();
```

再通知wait的take()线程, 注意, 这里**加了take锁**

```
if(C == 0)
	signalNotEmpty();
```

<img src="Screenshot 2024-11-17 at 22.45.05.png" alt="Screenshot 2024-11-17 at 22.45.05" style="zoom:33%;" />

### LinkedBlockingQueue#take

同put, 同样的通知逻辑.

<img src="Screenshot 2024-11-17 at 22.55.27.png" alt="Screenshot 2024-11-17 at 22.55.27" style="zoom:33%;" />

### LinkedBlockingQueue#remove

<img src="Screenshot 2024-11-17 at 23.11.48.png" alt="Screenshot 2024-11-17 at 23.11.48" style="zoom:33%;" />

<img src="Screenshot 2024-11-17 at 23.13.01.png" alt="Screenshot 2024-11-17 at 23.13.01" style="zoom:33%;" /><img src="Screenshot 2024-11-17 at 23.13.15.png" alt="Screenshot 2024-11-17 at 23.13.15" style="zoom:33%;" />

删除2锁都加. 



## LinkedBlockingDeque

与 LinkedBlockingQueue 不同的是, 用的一把锁,



## SynchronousQueue

**没有数据缓冲**的BlockingQueue，容量为0，它不会为队列中元素维护存储空间，它只是**多个线程之间数据交换的媒介**。

**下边的queue是消费者的等待队列, 不是任务数.**

有分非公平/公平, 公平是链表, 非公平是栈

<img src="Screenshot 2024-11-18 at 02.31.10.png" alt="Screenshot 2024-11-18 at 02.31.10" style="zoom:33%;" />



### SynchronousQueue#put

<img src="Screenshot 2024-11-18 at 02.29.11.png" alt="Screenshot 2024-11-18 at 02.29.11" style="zoom:33%;" />



### SynchronousQueue#take

<img src="Screenshot 2024-11-18 at 02.29.45.png" alt="Screenshot 2024-11-18 at 02.29.45" style="zoom:33%;" />

## queue的选择



