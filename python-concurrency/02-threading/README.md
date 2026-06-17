# 02 · threading —— 把 java.util.concurrent 平移到 Python

> 本章是你 Java 经验落地最快的一章。`threading` + `concurrent.futures` 几乎就是 Python 版的 `java.util.concurrent`：Thread、各种锁、阻塞队列、线程池、Future，一一对得上。读完你能用 Python 写出和 Java 等价的多线程代码，并知道哪些地方 Python 更原始、要小心。
>
> 前置：第 01 章（GIL）。本章默认你已经懂「线程受 GIL 限制、只适合 I/O 密集」。

---

## 1. 核心问题

1. Python 怎么起线程、起线程池？和 Java 的 `Thread` / `ExecutorService` 怎么对应？
2. JUC 里那些锁和同步工具（`ReentrantLock`/`Condition`/`Semaphore`/`CountDownLatch`/`BlockingQueue`），Python 的对应物是什么？
3. Python 有没有 `AtomicInteger`、`ThreadLocal`、`Thread.interrupt()`？哪些缺失、怎么替代？
4. 线程池大小怎么定？和 Java 的「IO 密集 = 2N」那套还成立吗？

---

## 2. 直觉理解

一句话：**`threading.Thread` 和 Java 的 `Thread` 是同一个东西**——都是 1:1 映射到操作系统内核线程，由内核调度。区别只在 GIL（已在第 01 章讲透）和 API 名字。

JUC 的版图在 Python 里这样对应：

| Java（java.util.concurrent） | Python | 在哪个模块 |
|---|---|---|
| `Thread` / `Runnable` | `threading.Thread(target=fn)` | `threading` |
| `ExecutorService` / `ThreadPoolExecutor` | `ThreadPoolExecutor` | `concurrent.futures` |
| `Callable` + `Future` | `executor.submit()` → `Future` | `concurrent.futures` |
| `ReentrantLock` | `threading.Lock`（不可重入）/ `RLock`（可重入） | `threading` |
| `synchronized` 块 | `with lock:` | `threading` |
| `Condition`（wait/notify） | `threading.Condition` | `threading` |
| `Semaphore` | `threading.Semaphore` | `threading` |
| `CountDownLatch` | `threading.Event`（1 次）/ `Barrier`（栅栏） | `threading` |
| `BlockingQueue`（ArrayBlockingQueue 等） | `queue.Queue` / `LifoQueue` / `PriorityQueue` | `queue` |
| `AtomicInteger` / CAS | ⚠️ **标准库没有**，用 `Lock` 替代 | — |
| `ThreadLocal` | `threading.local()` | `threading` |
| `Thread.interrupt()` 中断机制 | ⚠️ **没有**，用 `Event` 标志位自己实现 | — |

> 记住这张表，本章后面就是逐个展开。

---

## 3. 原理深入

### 3.1 起线程：两种写法（对应 Java 的 Runnable / 继承 Thread）

```python
# 需要: 仅标准库
import threading

# 写法一：传函数（最常用，相当于 Java 传 Runnable lambda）
def work(name):
    print(f"hi {name}")

t = threading.Thread(target=work, args=("A",))
t.start()      # 启动 → 进操作系统调度（对应 Java 的 start()，不是 run()）
t.join()       # 等它结束（语义同 Java Thread.join()）

# 写法二：继承 Thread 重写 run（相当于 Java extends Thread）
class Worker(threading.Thread):
    def run(self):
        print("running")
Worker().start()
```

> 和 Java 一个坑：**调 `run()` 不会起新线程**（只是普通函数调用），必须调 `start()`。

裸线程实际用得少，**生产几乎全用线程池**（见 3.5）。

### 3.2 锁：Lock / RLock

```python
import threading

lock = threading.Lock()      # 不可重入：同一线程重复 acquire 会死锁自己
rlock = threading.RLock()    # 可重入：同一线程可多次 acquire（对应 Java ReentrantLock）

# 推荐 with 写法，等价于 try/finally 里 acquire/release
# —— 正好对应你"unlock 必须放 finally"的肌肉记忆，with 帮你自动做了
with lock:
    counter += 1             # 临界区
```

为什么需要锁（呼应第 01 章）：GIL 不保证 `counter += 1` 原子，多线程下会丢更新。

> 注意 `Lock` 默认**不可重入**——这点和 Java 的 `synchronized`/`ReentrantLock`（都可重入）不同。要可重入用 `RLock`。

### 3.3 Condition：等待-唤醒（对应 wait/notify）

```python
import threading, collections

buf = collections.deque()
cond = threading.Condition()

def producer(x):
    with cond:
        buf.append(x)
        cond.notify()          # 唤醒一个等待者（notify_all() 唤醒全部）

def consumer():
    with cond:
        while not buf:         # 必须 while 而非 if —— 防虚假唤醒，和 Java 完全一样
            cond.wait()        # 释放锁并等待，被唤醒后重新拿锁
        return buf.popleft()
```

> 和 Java 的肌肉记忆一致：**等待条件用 `while` 包住 `wait()`**，防止虚假唤醒（spurious wakeup）。

### 3.4 Semaphore / Event / Barrier

```python
import threading

# Semaphore：限制同时进入的线程数（限流/连接池许可），对应 Java Semaphore
sem = threading.Semaphore(3)         # 3 个许可
with sem:                            # acquire 一个许可，超出则阻塞
    call_rate_limited_api()

# Event：一次性闸门，对应 CountDownLatch(1) 的常见用法
ready = threading.Event()
# 线程 A: ready.wait()    ← 阻塞直到被放行
# 线程 B: ready.set()     ← 放行所有等待者
# 也是实现"优雅停止"的标准手段（见 3.7）

# Barrier：栅栏，N 个线程都到齐才一起放行，对应 CyclicBarrier
barrier = threading.Barrier(3)
# 每个线程: barrier.wait()   ← 等齐 3 个才继续
```

> `CountDownLatch(N)`（等 N 个事件）Python 没有直接对应物，可用 `Semaphore` 或自己拿 `Condition` 计数实现；最常见的「等一件事」用 `Event` 即可。

### 3.5 线程池：ThreadPoolExecutor（重点，对标 ExecutorService）

```python
# 需要: pip install requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

def fetch(url):
    return requests.get(url, timeout=5).status_code   # I/O 密集，等待时放 GIL

urls = [...]
with ThreadPoolExecutor(max_workers=20) as pool:      # ≈ newFixedThreadPool(20)
    # 方式一：map —— 按输入顺序返回结果
    for code in pool.map(fetch, urls):
        print(code)

    # 方式二：submit + as_completed —— 谁先完成先拿（≈ ExecutorCompletionService）
    futures = {pool.submit(fetch, u): u for u in urls}
    for fut in as_completed(futures):
        url = futures[fut]
        try:
            print(url, fut.result())     # result() 阻塞取值；异常在这里被重新抛出
        except Exception as e:
            print(url, "failed:", e)
# with 块退出 = 自动 shutdown(wait=True)，等所有任务跑完
```

> **不传 `max_workers` 时的默认值**（高频追问「默认是多少」）：
> - `ThreadPoolExecutor()` → **`min(32, CPU核数 + 4)`**（Python 3.8 起；旧版是 `CPU核数 × 5`，多核上会爆，故改）。`+4` 让单核机器也有几条线程顶 I/O，`32` 封顶防你在多核上为「默认 I/O 负载」一口气开几百条线程白吃内存。
> - `ProcessPoolExecutor()` → **`CPU核数`**（`os.cpu_count()`，见第 03 章）。
> - 这个默认值很关键：`asyncio.to_thread` / `run_in_executor(None, …)` 复用的就是这个 ≈32 的默认线程池（见第 05 章）——坑位占满，后续调用就排队，所以**别拿 `to_thread` 当高并发引擎**。

对标速记：

| Python | Java | 说明 |
|---|---|---|
| `ThreadPoolExecutor(max_workers=N)` | `Executors.newFixedThreadPool(N)` | 固定大小池 |
| `pool.submit(fn, *args)` | `executor.submit(Callable)` | 返回 Future |
| `future.result(timeout=)` | `future.get(timeout)` | 阻塞取结果，异常重抛 |
| `as_completed(futures)` | `ExecutorCompletionService` | 按完成顺序取 |
| `pool.map(fn, iterable)` | `invokeAll` 的简化 | 按序返回 |
| `with pool:` 退出 | `shutdown() + awaitTermination` | 优雅关闭 |

> 重要差异：Python 的 `ThreadPoolExecutor` **没有 Java 那套丰富的队列/拒绝策略/keepAlive 配置**。任务队列是无界的（不会拒绝，可能堆积），没有 `RejectedExecutionHandler`。要精细控制并发上限，靠 `max_workers` + 自己加 `Semaphore` 限流。

### 3.6 线程间通信首选 queue.Queue（对标 BlockingQueue）

不要自己拿锁玩生产者-消费者，用线程安全的阻塞队列：

```python
import queue, threading

q = queue.Queue(maxsize=100)     # 有界队列，满了 put 会阻塞（≈ ArrayBlockingQueue）

def producer():
    for item in source:
        q.put(item)              # 阻塞式投递
    q.put(None)                  # 毒丸：通知消费者收工

def consumer():
    while True:
        item = q.get()           # 阻塞式获取
        if item is None:
            break
        handle(item)
        q.task_done()            # 配合 q.join() 可等"所有任务被处理完"
```

`queue.Queue`（FIFO）、`LifoQueue`（栈）、`PriorityQueue`（优先级）对应 Java 的各种 `BlockingQueue` 实现。

### 3.7 你必须重新记住的三个「Python 更原始」之处

**① 没有 AtomicInteger / CAS。** 标准库不提供原子类。计数器老老实实用 `Lock`：

```python
class Counter:
    def __init__(self):
        self._v = 0
        self._lock = threading.Lock()
    def inc(self):
        with self._lock:
            self._v += 1
```

（CPython 里某些单字节码操作恰好原子，比如 `list.append`，但**别依赖**这种隐式行为。）

**② 没有 Thread.interrupt()，不能从外部杀线程。** Java 那套中断标志位机制 Python 没有。优雅停止靠**自己用 `Event` 设标志位**，线程循环里检查：

```python
stop = threading.Event()

def worker():
    while not stop.is_set():      # 自己轮询标志位
        do_one_chunk()

# 主线程要停它：stop.set()
```

**③ daemon 线程**：`t.daemon = True`（或 `Thread(daemon=True)`）表示「主线程退出时它跟着死」，对应 Java 的 `setDaemon(true)`。非 daemon 线程会阻止进程退出。

### 3.8 ThreadLocal

```python
import threading
local = threading.local()
local.user_id = 42        # 每个线程看到自己的副本，互不干扰（同 Java ThreadLocal）
```

常用于把「请求上下文」(如 trace id、当前用户) 隐式传递，不用层层传参。

---

## 4. 日常开发应用

- **什么时候用 threading**：I/O 密集 + 并发量不大（几十到几百），或必须调用没有 async 版本的同步库。例：爬一批 URL、并发查多个下游服务、批量读写文件。
- **首选 `ThreadPoolExecutor`，别裸 `Thread`**：池化复用、统一拿结果/异常、自动关闭。
- **CPU 密集别用线程**（第 01 章已证明没用），用第 03 章的多进程。
- **共享状态就加锁，或干脆用 `queue.Queue` 把共享变成消息传递**——后者更不容易错（和 Go「不要用共享内存通信，要用通信共享内存」一个思路）。

---

## 5. 生产 & 调优实战

**线程池大小怎么定？** 你 Java 的经验**部分**还成立，但 GIL 改变了上限：

- **I/O 密集**：线程多数时间在等 I/O（已放 GIL），可以开得比核数多很多。经验起点 `线程数 ≈ 目标并发 / (1 - I/O等待占比)`，实务上几十到一两百常见。但**别无脑堆**——线程栈占内存（每个 ~MB 级），且 GIL 争用在线程多时会上升。
- **CPU 密集**：在 Python 里加线程**毫无意义**（GIL），加了只会更慢。这点和 Java 不同——Java 里 `线程数 ≈ 核数` 对 CPU 密集有效，Python 必须改用多进程。

**生产里的「线程」长什么样**（第 07 章细讲）：

```bash
# gunicorn 的 gthread worker：每个 worker 进程内开一个线程池处理请求
gunicorn app:wsgi --workers 4 --worker-class gthread --threads 8
# = 4 进程（绕 GIL 吃多核）× 每进程 8 线程（进程内并发 I/O）
```

**两个生产坑**：
- **线程泄漏**：没用线程池、不断 `Thread().start()` 又不回收，线程数飙升拖垮进程。用池。
- **阻塞不退出**：worker 里有线程卡在没有超时的网络调用上，`shutdown` 时挂住。**所有网络调用都要带 timeout**。

调优/排查工具见 `performance-tuning-roadmap/06b-python-debugging/`（py-spy 看线程栈、定位卡住的线程）。

---

## 6. 面试高频考点

**Q1：Python 的 `threading.Thread` 和 Java `Thread` 一样吗？**
本质一样，都是 1:1 内核线程、内核调度。区别是 Python 受 GIL 限制，多线程只适合 I/O 密集；API 也更精简（没有丰富的池配置/拒绝策略）。

**Q2：`Lock` 和 `RLock` 区别？**
`Lock` 不可重入，同一线程重复 acquire 会死锁；`RLock` 可重入（记录持有线程和重入次数），对应 Java `ReentrantLock`。

**Q3：Python 怎么做原子计数？**
标准库无 `AtomicInteger`，用 `threading.Lock` 保护「读-改-写」。别依赖「GIL 让某操作恰好原子」的隐式行为。

**Q4：怎么优雅停止一个线程？**
Python 不能从外部强杀线程，也没有 `interrupt()`。用 `threading.Event` 设标志位，线程循环里 `while not stop.is_set()` 轮询；阻塞调用要带 timeout 才能及时响应停止。

**Q5：`ThreadPoolExecutor` 的队列满了会怎样？**
不会拒绝——任务队列无界，会一直堆积（和 Java 有界队列 + 拒绝策略不同）。要限流得自己加 `Semaphore` 或控制提交速率。

**Q6：I/O 密集线程池开多大？默认是多少？**
比核数多，按 I/O 等待占比估算（等得越久可开越多），但受内存（线程栈）和 GIL 争用约束，实务几十到一两百。CPU 密集则不该用线程。不显式指定时，`ThreadPoolExecutor()` 默认 `min(32, 核数+4)`、`ProcessPoolExecutor()` 默认 `核数`；`asyncio.to_thread` 用的就是前者那个 ≈32 的默认池。

---

## 7. 一句话总结

`threading` + `concurrent.futures` ≈ Python 版 `java.util.concurrent`，你的 Java 锁/队列/线程池知识直接平移、换个 API 名即可。要重新记住的是 Python 更原始的三点：**没有原子类（用 Lock）、不能外部杀线程（用 Event 标志位）、线程池配置很简陋（队列无界）**。而最大的约束始终是 GIL——所以 threading 只用于 I/O 密集，CPU 密集交给下一章的多进程。

---

> **下一章** `03-multiprocessing/`：多开进程 = 多支「笔」，Python 吃满多核的正路。
>
> **延伸**：Java 侧基础对照 `java/concurrent/`（AQS、线程池、CAS）。
