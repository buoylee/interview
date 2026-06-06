# 线程 / I/O / event loop：谁是系统线程，谁在并行？

## 一句话回答

普通 CPython 里，`threading.Thread` 通常是真 OS 线程；GIL 限制的是**同一进程内多个线程不能同时执行 Python 字节码**。一个线程释放 GIL 去做阻塞 I/O、内核 syscall 或 native 代码时，另一个线程可以执行 Python 字节码；这叫 I/O 与计算重叠，某些时刻也可能是真 CPU 并行。`asyncio.Task` 不是 OS 线程，它只是 event loop 在线程内调度的用户态任务。

## 四层模型

### 1. Java / Go / Python 线程先对齐

```text
Java Thread        -> OS thread -> CPU core
Go goroutine       -> Go runtime -> OS thread -> CPU core
Python Thread      -> OS thread -> 抢 GIL -> 执行 Python 字节码
Python coroutine   -> Task -> event loop -> OS thread -> CPU core
```

- Java 传统线程通常 1:1 映射 OS 线程，能不能并行由 OS 调度和 CPU 核数决定。
- Go goroutine 是 runtime 管理的轻量任务，runtime 把它们调度到一组 OS 线程上。
- Python `threading.Thread` 也是 OS 线程，但执行 Python 字节码前要抢 GIL。
- Python `asyncio` coroutine / Task 不是 OS 线程，默认多个 Task 跑在同一个 event loop 线程里。

### 2. GIL 精确限制的是什么

```text
Thread A 执行 Python 字节码 + Thread B 执行 Python 字节码
=> 普通 CPython 下不能同时并行

Thread A 等 I/O / 执行释放 GIL 的 native 代码 + Thread B 执行 Python 字节码
=> 可以同时推进
```

所以「Python 多线程不能并行」这句话要补完整：

> 普通 CPython 的纯 Python CPU 密集多线程，不能同时在多个核心上执行 Python 字节码。

它不等于：

- 不能并发。
- 不能做 I/O 并发。
- 单进程完全不能利用多核。
- 任何 native/C 扩展都不能并行。

### 3. 阻塞 I/O 时，那个 Python 线程去哪了

阻塞 I/O 常见流程：

```text
Thread A:
  Python 代码
    -> sock.recv() / file.read()
    -> 释放 GIL
    -> syscall 进入内核态
    -> 数据没好，线程被挂起，不占 CPU

Thread B:
  抢到 GIL
  在 CPU 上执行 Python 字节码

内核/设备:
  网络包、磁盘、DMA、驱动、中断继续推进 I/O
```

这里不要把「线程还活着」和「线程正在 CPU 上运行」混为一谈。阻塞等待时，Thread A 可能已经睡眠，不占 CPU；但 I/O 在内核/设备层面继续推进，所以可以说 I/O 与 Python 计算重叠。

如果 Thread A 正在 syscall 内执行内核代码，或正在跑释放 GIL 的 C/native 代码，同时 Thread B 在另一个核心跑 Python 字节码，那么这就是更严格意义上的 CPU 并行。

### 4. asyncio：event loop 是线程，Task 不是线程

```text
Main OS Thread
  -> event loop while 循环
       -> Task A / coroutine A
       -> Task B / coroutine B
       -> Task C / coroutine C
```

- event loop 通常运行在一个普通 OS 线程里。
- coroutine 是「可以在 `await` 处暂停/恢复的函数执行状态」。
- Task 是 coroutine 的调度包装，像一个交给 event loop 的 Future。
- `await` 是主动让出执行权：当前 coroutine 暂停，event loop 去跑别的 Task 或等 I/O。

简化内部流程：

```text
Task 恢复 coroutine
  -> coroutine 一直跑
  -> 遇到 await
  -> 注册 Future / I/O / timer
  -> coroutine 暂停
  -> event loop 跑别的 Task
  -> Future 完成
  -> Task 回到 ready queue
  -> event loop 再次恢复 coroutine
```

所以：

```text
coroutine ~= 可暂停的 Callable/Runnable
Task      ~= 已提交给 event loop 的 Future/调度句柄
event loop 才是跑在 OS thread 上的执行器
```

`Task` 不等于 Java `Thread`。更好的类比是：

```text
Java:   Runnable/Callable -> ThreadPool/Thread -> OS thread
Python: coroutine         -> Task + event loop -> OS thread
```

## 线程数怎么定的复习锚点

- Java 传统线程创建受线程栈、native memory、OS 线程数限制，不是 CPU 核心数直接限制。
- CPU 密集线程数通常接近核心数：`cores` 或 `cores + 1`。
- I/O 密集线程数取决于等待占比：`cores * (1 + wait_time / compute_time)` 是估算起点。
- 最终要压测找拐点：吞吐不涨、P99 变差、上下文切换变多，就是线程过量。
- Python CPU 密集不要靠 `ThreadPoolExecutor` 加线程，改用多进程或释放 GIL 的 native 库。

## 面试可背版本

> CPython 的线程是真 OS 线程，不是假的用户态线程；它们由 OS 调度，也会在系统调用时进入内核态。GIL 限制的是同一进程内不能有多个线程同时执行 Python 字节码。线程做阻塞 I/O 时通常会释放 GIL 并在内核里等待，另一个线程可以执行 Python 字节码，所以 I/O 与计算可以重叠。asyncio 又是另一层：Task/coroutine 不是 OS 线程，而是 event loop 在一个 OS 线程里协作式恢复的用户态任务。

## 证据链接

- 执行模型：[00-execution-model](../00-execution-model/README.md)
- GIL 原理：[01-foundations-gil](../01-foundations-gil/README.md)
- Python 线程：[02-threading](../02-threading/README.md)
- asyncio 核心：[04-asyncio-core](../04-asyncio-core/README.md)
- Java 线程对照：[java/concurrent/thread-进程-goroutine.md](../../java/concurrent/thread-进程-goroutine.md)
