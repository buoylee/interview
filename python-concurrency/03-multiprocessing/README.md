# 03 · multiprocessing —— Python 吃满多核的正路

> GIL 锁的是「一个进程内」。想用 Python 做 CPU 密集计算还吃满多核，办法就是**多开进程，每个进程一个独立解释器、一把独立的「笔」**。本章讲多进程的模型、API、进程间通信，以及几个一定会踩的坑（fork vs spawn、pickle 开销、`__main__` 守卫）。
>
> 前置：第 01 章（GIL）、第 02 章（线程池接口，本章的进程池接口和它对称）。

---

## 1. 核心问题

1. 为什么 CPU 密集要用多进程而不是多线程？（第 01 章已答，这里落地）
2. 进程和线程在用法上最大的区别是什么？（答：不共享内存，传数据要序列化）
3. `fork` 和 `spawn` 是什么？为什么 macOS/Windows 上代码不放进 `if __name__` 会出事？
4. 进程间怎么通信、怎么共享大数据而不被序列化拖垮？

---

## 2. 直觉理解

回到第 01 章那个「只有一支笔的办公室」比喻：

- **多线程**：一个办公室、一支笔、4 个员工抢着写 → GIL 限制，计算上串行。
- **多进程**：开 4 间办公室，每间一支笔、各一个员工 → **4 个人真的同时在写** → 真并行，吃满 4 核。

代价是什么？4 间办公室是**互相隔离的**（独立地址空间）。员工之间想传东西，不能像同一间屋里直接递（共享内存），得**打包成快递寄过去**（序列化）。这就是多进程相比多线程的核心代价：

| 维度 | 线程（第 02 章） | 进程（本章） |
|---|---|---|
| 地址空间 | 共享，直接读写同一对象 | **独立**，对象要序列化（pickle）后传 |
| 参数/返回值 | 直接传引用，零成本 | **pickle 序列化**，大对象很贵 |
| 启动开销 | 轻（~10μs） | 重（fork ~ms / spawn 要重启解释器，更慢） |
| 通信 | 共享变量 + 锁 / `queue.Queue` | `mp.Queue`、`Pipe`、`Manager`、共享内存 |
| 崩溃隔离 | 弱（一个挂全进程挂） | **强**（一个子进程崩溃不连累别人） |
| 吃多核 | ❌（GIL） | ✅ |

> 对标 Java：多进程 ≈ 你启动多个独立的 JVM 实例来分摊计算。它们之间不共享堆，要通信只能走 socket/文件/共享内存——和这里完全一个道理。

---

## 3. 原理深入

### 3.1 进程池：ProcessPoolExecutor（接口和线程池对称）

最省心的入口——和第 02 章的 `ThreadPoolExecutor` **接口完全一样，只换类名**：

```python
# 需要: 仅标准库
from concurrent.futures import ProcessPoolExecutor

def heavy(n):                              # 纯 CPU 计算
    return sum(i * i for i in range(n))

if __name__ == "__main__":                 # ← 这行很重要，见 3.3
    with ProcessPoolExecutor(max_workers=4) as pool:   # 一般设为 CPU 核数
        results = list(pool.map(heavy, [10**7] * 8))   # 这次是真·多核加速
```

> 这就是「CPU 密集」的标准答案：`ThreadPoolExecutor` 换成 `ProcessPoolExecutor`。`submit` / `map` / `Future.result()` / `as_completed` 全部一样用。

### 3.2 底层 API：Process / Pool

```python
import multiprocessing as mp

# 裸进程（对应裸 Thread）
def work(name):
    print(f"hi {name}")

if __name__ == "__main__":
    p = mp.Process(target=work, args=("A",))
    p.start()
    p.join()

# mp.Pool（比 ProcessPoolExecutor 更老的池接口，功能类似）
if __name__ == "__main__":
    with mp.Pool(processes=4) as pool:
        results = pool.map(heavy, data)
```

> 日常优先用 `concurrent.futures.ProcessPoolExecutor`（和线程池统一接口）；`mp.Pool` 在老代码里常见，知道它等价即可。

### 3.3 坑①：fork vs spawn（跨平台行为不同，必踩）

子进程是怎么「诞生」的，有三种启动方式：

| 启动方式 | 行为 | 默认平台 |
|---|---|---|
| `fork` | 直接复制父进程内存（写时复制 COW），快 | Linux |
| `spawn` | 从零启动新解释器，**重新 import 你的模块**，慢但干净 | **macOS（3.8+）、Windows** |
| `forkserver` | 先起一个干净的 server 进程，之后从它 fork | Linux 可选 |

**关键后果**：spawn 平台下，子进程会**重新 import 你的主模块**。如果你的建进程代码写在模块顶层（不在 `if __name__` 里），子进程 import 时又会执行一遍建进程 → **无限递归创建进程**，程序爆炸。

```python
# ✅ spawn 平台必须这样：入口逻辑放进守卫里
def heavy(n): ...

if __name__ == "__main__":          # 子进程 import 模块时，__name__ != "__main__"，不会重复执行
    with ProcessPoolExecutor() as pool:
        pool.map(heavy, range(8))
```

> 你在 macOS 开发（默认 spawn）、Linux 上线（默认 fork），同一份代码行为可能不同。**养成习惯：multiprocessing 代码一律加 `if __name__ == "__main__":` 守卫。** 想显式统一可 `mp.set_start_method("spawn")`。

> 另一个 fork 的隐患：fork 只复制调用线程，**不复制其他线程持有的锁状态**。如果父进程里有线程正持有锁、日志 handler 锁等，fork 后子进程可能死锁。这也是 spawn 更「干净安全」的原因。

### 3.4 坑②：参数和返回值必须可 pickle

进程间传数据靠 **pickle 序列化**。所以：

- 传给 `submit/map` 的**函数和参数、返回值都必须可被 pickle**。
- **lambda、局部函数、不可序列化对象（如打开的文件句柄、数据库连接、线程锁）传不过去**，会报错。函数要定义在模块顶层。
- **大对象代价高**：给子进程传一个几百 MB 的 DataFrame，光来回 pickle 就能把多核收益吃光。

```python
# ❌ lambda 不可 pickle
pool.map(lambda x: x*x, data)            # 报错

# ✅ 用顶层函数
def square(x): return x*x
pool.map(square, data)
```

### 3.5 进程间通信（IPC）的几种方式

```python
import multiprocessing as mp

# ① mp.Queue —— 进程安全队列，最常用（对标 Java 跨进程时只能用外部 MQ，这里语言内置了）
q = mp.Queue()
# 生产进程 q.put(x)；消费进程 q.get()

# ② Pipe —— 两个进程间的双向管道
parent_conn, child_conn = mp.Pipe()

# ③ Manager —— 跨进程共享的"代理"对象（dict/list 等），用着方便但每次访问都走 IPC，慢
mgr = mp.Manager()
shared = mgr.dict()              # 多个进程能读写，但每次操作都有序列化开销

# ④ 共享内存 —— 大数据零拷贝，最快（见 3.6）
```

### 3.6 共享大数据：shared_memory（避开序列化）

需要在进程间共享大数组时，别走 pickle，用共享内存让多个进程**直接映射同一块物理内存**：

```python
# 需要: pip install numpy
from multiprocessing import shared_memory
import numpy as np

arr = np.arange(10_000_000, dtype=np.float64)
shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
buf = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
buf[:] = arr[:]                  # 写进共享内存
# 把 shm.name 传给子进程，子进程用同名 attach 即可直接读，无需序列化
# 用完记得 shm.close() / shm.unlink()
```

> 更实用的捷径：**很多 CPU 密集其实不必自己开多进程**。numpy/pandas/scipy 这类 C 扩展在计算时**会主动释放 GIL**（第 01 章 3.4），底层还用了 SIMD/多线程 BLAS。把热点交给它们，常常比你手写 multiprocessing 又快又省心。先问自己：能不能向量化？

---

## 4. 日常开发应用

- **CPU 密集就上 `ProcessPoolExecutor`**，`max_workers` 设为 CPU 核数（`os.cpu_count()`）。
- **任务要能分块**：把大计算切成独立的块并行处理（map-reduce 思路），块之间无共享最理想。
- **优先向量化**：能用 numpy/pandas 解决的，别急着开进程。
- **避免频繁传大对象**：要么共享内存，要么让每个进程自己去读数据源（如各读一段文件），减少 pickle。

```python
# 典型：把图片批量处理分发到多核
import os
from concurrent.futures import ProcessPoolExecutor

def process_one(path): ...     # CPU 密集：解码/缩放/编码

if __name__ == "__main__":
    paths = [...]
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        list(pool.map(process_one, paths, chunksize=8))   # chunksize 减少调度开销
```

> `chunksize`：一次派给子进程一批任务，减少「每个任务都来回 IPC」的开销。任务多且单个轻时，调大 chunksize 收益明显。

---

## 5. 生产 & 调优实战

- **进程数 ≈ CPU 核数**。开太多进程不会更快（核就那么多），反而增加内存和调度开销。CPU 密集设 `os.cpu_count()`；若任务也有点 I/O，可略多。
- **进程启动贵，池要复用**。别在循环里反复建 `ProcessPoolExecutor`，建一次重复用。
- **内存是大头**：spawn 下每个子进程是独立解释器，N 个进程 ≈ N 份内存。大模型/大数据场景注意 OOM。fork 下靠 COW 省一些，但子进程一旦写就触发复制。
- **超时与异常**：`future.result(timeout=...)` 防止某个子任务卡死拖住全局；子进程崩溃会让对应 future 抛 `BrokenProcessPool`。
- **生产部署里的「多进程」**：其实你最常见的多进程不是手写 `ProcessPoolExecutor`，而是 **gunicorn/uvicorn 的多 worker**（第 07 章）和 **Celery 的 prefork 池**（第 08 章）——本质都是「多进程绕 GIL」。

---

## 6. 面试高频考点

**Q1：CPU 密集为什么用多进程不用多线程？**
GIL 让多线程在计算上串行（吃不满多核）；多进程每个进程有独立解释器、独立 GIL，能真并行吃满多核。代价是地址空间隔离、传数据要序列化。

**Q2：多进程相比多线程的主要代价？**
启动慢、内存翻倍、进程间传数据要 pickle 序列化（大对象很贵）、通信比共享内存麻烦。好处是崩溃隔离强、能吃多核。

**Q3：`fork` 和 `spawn` 区别？为什么要加 `if __name__ == "__main__"`？**
fork 复制父进程内存（快，Linux 默认）；spawn 从零启新解释器并重新 import 模块（macOS/Win 默认）。spawn 下若建进程代码不在 `__main__` 守卫里，子进程 import 时会递归建进程。fork 还有「不复制其他线程的锁状态」可能死锁的隐患。

**Q4：怎么在进程间共享大数据而不被序列化拖垮？**
用 `multiprocessing.shared_memory` 让多进程映射同一块物理内存（零拷贝）；或让每个进程各自去读数据源；或干脆用会释放 GIL 的 numpy 向量化，避免开进程。

**Q5：进程池开多大？**
CPU 密集 ≈ 核数（`os.cpu_count()`），多开无益还耗内存。

---

## 7. 一句话总结

多进程 = 多开解释器、多支「笔」，是 Python 做 CPU 密集、吃满多核的正路；接口和线程池对称（`ProcessPoolExecutor`），换类名即可。要记牢两个坑：**spawn 平台必加 `__main__` 守卫**、**传参/返回值要可 pickle 且别太大**。能向量化（numpy）就优先向量化，常常比手写多进程更划算。

---

> **下一章** `04-asyncio-core/`：换一套思路——单线程事件循环 + 协程，海量 I/O 并发的首选，也是 FastAPI 的根基。注意：它像 goroutine，但本质不同。
>
> **延伸**：fork/COW 的 OS 原理见 `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`。
