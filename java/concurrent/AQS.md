[toc]

## 概述

java 层面的 管程:

抽象层: AQS(AbstractQueuedSynchronizer)
同步队列(双向列表), (cas state)抢锁, 抢不到就入队; 
条件队列(单向列表), (condition await/signel, signelAll)

## AQS

AQS 继承 AbstractOwnableSynchronizer

看一下代码注意区分, 
state, 资源数
waitStatus, node 的状态





## AbstractOwnableSynchronizer

AbstractOwnableSynchronizer 有独占属性 `private transient Thread exclusiveOwnerThread;`

## 最简单的锁实现(利用AQS)

```
protected boolean tryAcquire(int unused){
	//cas 加锁 state=0
	if(compareAndSetstate(0，1)){
		setExClusiveOwnerThread(Thread.currentThread()); // 当前执行
		return true;
	}
	return false;
	}
```

```
protected boolean tryRelease (int unused){
	//释放锁
	setExclusiveOwnerThread(null);
	setState(0) //因为只有上锁的线程可以解锁, 所以不需要cas
	return true；
}
```

## reentrantLock

### 公平与否

不公平

先尝试抢锁, 

<img src="Screenshot 2024-11-15 at 16.48.35.png" alt="Screenshot 2024-11-15 at 16.48.35" style="zoom: 33%;" />

公平则会直接调用 `acquire(1);`

## acquire()

<img src="Screenshot 2024-11-15 at 20.47.41.png" alt="Screenshot 2024-11-15 at 20.47.41" style="zoom:33%;" />

再次判断 tryAcquire(int)
addWaiter(Node mode) 加入waitQueue, mode 包含独占/共享node



## addWaiter(Node mode)

enq()

## enq()

如何**线程安全地尾插linklist**
<img src="Screenshot 2024-11-15 at 17.35.10.png" alt="Screenshot 2024-11-15 at 17.35.10" style="zoom:50%;" />



## tryAcquire(int)

调 nonFairTryAcquire(int)



## nonFairTryAcquire(int)

先判断 cas state 状态, 
如果还是0, 再尝试上锁. 成功则return true; 否则 false, 退出,
如果是 current Tread 是 owner Thread, state 是1, 则是重入锁, nextc = getState() + int acquire, 最后setState(nextc);

## AQS node(wait queue node)

<img src="Screenshot 2024-11-15 at 17.09.21.png" alt="Screenshot 2024-11-15 at 17.09.21" style="zoom: 33%;" />

### 属性 

thread
nextWaiter
waitStatus
prev
next

## acquireQueued(node, int)

先调 node.predecessor(),  如果 node.prev已经是head, 

<img src="Screenshot 2024-11-15 at 20.10.09.png" alt="Screenshot 2024-11-15 at 20.10.09" style="zoom: 33%;" />

则node尝试获取锁, tryAcquire(arg), 失败则调 
shouldParkAfterFailedAcquire(P, node) && parkAndCheckInterrupt())

## shouldParkAfterFailedAcquire（Node pred, Node node）

初始 waitState 是 0, 在这个方法中, 最终一定被修改称其他值,
0肯定会`compareAndSetWaitStatus(pred, ws, Node. SIGNAL)`变成 -1(signal), 会被`parkAndCheckInterrupt()`执行`park()` 挂起.

<img src="Screenshot 2024-11-15 at 20.37.20.png" alt="Screenshot 2024-11-15 at 20.37.20" style="zoom:33%;" />

可以看出, 如果被中断唤醒, 这里会清除标志位. 恢复打断标志位, 在acquire(int)方法中的`selfInterrupt();`复位.

## release

<img src="Screenshot 2024-11-15 at 21.03.40.png" alt="Screenshot 2024-11-15 at 21.03.40" style="zoom:33%;" />

`unparkSuccessor(h);` 先 cas state = 0 最终会调 `LockSupport.unpark(s.thread);`唤醒 `Node s = node.next;`,
唤醒的next的state == 0, 会去马上cas 加锁, 然后在 wait queue 中, head = 当前 node.

## tryRelease

<img src="Screenshot 2024-11-15 at 20.50.04.png" alt="Screenshot 2024-11-15 at 20.50.04" style="zoom:33%;" />

## doReleaseShared

<img src="Screenshot 2024-11-15 at 23.52.13.png" alt="Screenshot 2024-11-15 at 23.52.13" style="zoom:33%;" />

head cas 成功, 就去 unpark

## unparkSuccessor

<img src="Screenshot 2024-11-15 at 23.55.06.png" alt="Screenshot 2024-11-15 at 23.55.06" style="zoom:33%;" />

## setHeadAndPropagate

对于SHARED node, 会继续检查 next, 如果还是 SHARED, 就unpark, 直到没有资源.



## Sync

`abstract static class Sync extends AbstractOueuedSynchronizer`



## semaphore

俗称**信号量**，它是操作系统中**PV操作的原语在java的实现**，它也是**基于AbstractQueuedSynchronizer实现**的。
**PV**是荷兰语**(Proberen)的(Test in Dutch)**和 **(Verhogen)的(Increment in Dutch)**;
**P**: 尝试申请资源，如果信号量值大于 0, -1, 通过; 否则, 阻塞.
**V**: 释放资源，将信号量  +1, 如果有**被阻塞**的进程或线程**等待该资源**，**唤醒其一**.
**P(S)/V(S) 表示操作S** 

### 构造函数

<img src="Screenshot 2024-11-15 at 22.36.25.png" alt="Screenshot 2024-11-15 at 22.36.25" style="zoom:33%;" />



### API

<img src="Screenshot 2024-11-15 at 22.37.52.png" alt="Screenshot 2024-11-15 at 22.37.52" style="zoom:33%;" />

### 源码概述

state 就是 Semaphore 的 permits



### nonfairTryAcquireshared

<img src="Screenshot 2024-11-15 at 22.53.29.png" alt="Screenshot 2024-11-15 at 22.53.29" style="zoom:33%;" />

只要有资源, 直接抢锁

## AQS.doAcquireSharedInterruptibly

addWaiter(Node.SHARED)



## CountDownLatch

await方法会阻塞直到当前的计数值（count）达到0，之后所有等待的线程都会被释放，随后对await方法的调用都会立即返回。这是一个一次性现象——count不会被重置。如果你需要一个**重置count的版本, 使用CyclicBarrier**。

### 原理

**基于 AbstractQueuedSynchronizer 实现**，CountDownLatch 构造函数中指定的**count直接赋给AQS的state**;
每次countDown()则都是release(1)减1, **最后一个执行countdown**方法的线程**减到0**时unpark阻塞线程。

### CountDownLatch与Thread.join的区别

- CountDownLatch可以手动控制在n个线程里调用n次countDown()方法使计数器进行减一操作，**也可以在一个线程里调用n次执行减一操作**。
- 而 **join()**的实现原理是**不停检查join线程是否存活**，如果**join 线程存活则让当前线程永远等待**。所以两者之间相对来说还是**CountDownLatch使用起来较为灵活**。

### CountDownLatch与CyclicBarrier的区别

- CyclicBarrier一般用于**一组线程互相等待至某个状态**，然后这**一组线程再同时执行**
- **CountDownLatch**是**减计数**，计数减为0后**不能重用**；而**CyclicBarrier是加计数，可置0后复用**。
- CyclicBarrier是通过**ReentrantLock的"独占锁"和Conditon来实现**一组线程的阻塞唤醒的，而**CountDownLatch则是通过AQS的"共享锁"**实现

### CountDownLatch.tryAcquireShared

<img src="Screenshot 2024-11-16 at 15.04.11.png" alt="Screenshot 2024-11-16 at 15.04.11" style="zoom:33%;" />

所有子线程进来state都不是 0, 会马上变 -1, 阻塞.

### CountDownLatch.tryAcquireShared.tryReleaseShared

<img src="Screenshot 2024-11-16 at 15.07.34.png" alt="Screenshot 2024-11-16 at 15.07.34" style="zoom:33%;" />

最后一个线程进来解锁时, state是1, cas 成0, 就是子线程都抵达了, 唤醒主线程.



## CyclicBarrier

回环栅栏（循环屏障），可以实现让一组线程重复**(多次)等待至某个状态(屏障点)之后再全部同时执行**。

### demo

```
import java.util.concurrent.CyclicBarrier;
public class CyclicBarrierDemo {
    public static void main(String[] args) {
        // 定义一个CyclicBarrier，等待所有线程准备好后执行一个任务
        int numberOfRunners = 5; // 假设有5个运动员
        CyclicBarrier barrier = new CyclicBarrier(numberOfRunners, () -> {
            System.out.println("所有运动员已到达起跑线，比赛开始！"); // 当所有都到达时, 触发的事件处理, 只执行一次.
        });
        // 创建并启动运动员线程
        for (int i = 1; i <= numberOfRunners; i++) {
            new Thread(new Runner(barrier, i)).start();
        }
    }
}
// 模拟运动员的类
class Runner implements Runnable {
    private final CyclicBarrier barrier;
    private final int runnerId;
    public Runner(CyclicBarrier barrier, int runnerId) {
        this.barrier = barrier;
        this.runnerId = runnerId;
    }
    @Override
    public void run() {
        try {
            System.out.println("运动员 " + runnerId + " 正在热身...");
            Thread.sleep((long) (Math.random() * 3000)); // 模拟热身时间
            System.out.println("运动员 " + runnerId + " 到达起跑线，等待其他人...");
            // 等待所有线程到达
            barrier.await();
            // 所有线程通过屏障后继续执行
            System.out.println("运动员 " + runnerId + " 开始比赛！");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

```
运动员 1 正在热身...
运动员 2 正在热身...
运动员 3 正在热身...
运动员 4 正在热身...
运动员 5 正在热身...
运动员 2 到达起跑线，等待其他人...
运动员 5 到达起跑线，等待其他人...
运动员 1 到达起跑线，等待其他人...
运动员 3 到达起跑线，等待其他人...
运动员 4 到达起跑线，等待其他人...
所有运动员已到达起跑线，比赛开始！
运动员 2 开始比赛！
运动员 5 开始比赛！
运动员 1 开始比赛！
运动员 3 开始比赛！
运动员 4 开始比赛！
```

### 原理



###  doWait()

await->dowait

子线程一上来先

 <img src="Screenshot 2024-11-16 at 18.05.23.png" alt="Screenshot 2024-11-16 at 18.05.23" style="zoom:33%;" />

因为要wait(), 必先加锁.

<img src="Screenshot 2024-11-16 at 18.08.19.png" alt="Screenshot 2024-11-16 at 18.08.19" style="zoom:33%;" />

当 count >0 时, 就会去trip.await(), 
`Node node = addConditionWaiter();` 放入的是condition wait queue(单向链表), 然后马上 LockSupport.park(this),

当 count == 0, 如果有 runnable barrierCommand, 执行; 然后NexGeneration();

**NextGeneration()** 中  **`trip.signall()`**;

<img src="Screenshot 2024-11-16 at 18.41.19.png" alt="Screenshot 2024-11-16 at 18.41.19" style="zoom:33%;" />

<img src="Screenshot 2024-11-16 at 19.18.51.png" alt="Screenshot 2024-11-16 at 19.18.51" style="zoom:33%;" />

<img src="Screenshot 2024-11-16 at 19.19.23.png" alt="Screenshot 2024-11-16 at 19.19.23" style="zoom:33%;" />

### transferForSignal(first)

statue 改为0后, 就回到 AQS的 条件队列 enq() 插入到等锁同步queue.

然后回到 **unlock**, 回到reentrantLock逻辑



## ReentrantReadWriteLodk

ReentrantReadWriteLock **内部维护着一对读写锁**，用一个**变量维护2种状态**，一个变量分为两部分：高位16为表示读，低位16为表示写。

holdCounter 保存某个thread的重入次数, 放在threadLocal中.

**tryAcquire（int acquires）**

int w= exclusiveCount （c）；// 检查有没写锁
current ！= getExclusiveownerThread（） //检查当前线程是不是就是排他锁的所有者

**writershouldBlock** 

用于判断是否公平



### 锁降级

支持锁**降级(先上读锁再解写锁)**
**先锁**是因为了**可见性**, 上锁调用cas 保证cas前的修改可见. 

### 为什么不能锁升级 

已存在的其他读锁, 会读到脏数据. 

