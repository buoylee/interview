# GIL 与并发模型选型

## 概述

GIL（Global Interpreter Lock）是 CPython 中最被误解的机制之一。很多人听说"Python 不能利用多核"就认为 Python 不适合高并发，这是片面的。理解 GIL 的真实影响和四种并发模型的适用场景，才能做出正确的技术选型。

## 1. GIL 是什么

GIL 是 CPython 解释器中的一把全局互斥锁。同一时刻，**只有一个线程可以执行 Python 字节码**。

```python
import threading
import time

counter = 0

def increment():
    global counter
    for _ in range(1_000_000):
        counter += 1  # 这个操作不是原子的，但 GIL 使得同一时刻只有一个线程执行

threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

# counter 的结果不确定（因为 += 不是原子操作，GIL 可能在操作中间切换线程）
# 但这不是 GIL 的问题，而是线程安全问题
print(counter)  # 可能不是 4000000
```

注意：GIL 保证同一时刻只有一个线程执行字节码，但**不保证操作的原子性**。`counter += 1` 编译为多条字节码（LOAD, ADD, STORE），GIL 可以在任意两条字节码之间释放。

## 2. 为什么存在 GIL

GIL 的存在是为了简化 CPython 的内存管理：

1. **引用计数线程安全**：CPython 用引用计数管理内存。没有 GIL 的话，每次引用计数的增减都需要加锁或用原子操作，所有 Python 对象操作都会变慢。
2. **C 扩展兼容性**：大量 C 扩展（numpy、pandas 等）依赖 GIL 来保证线程安全。移除 GIL 会破坏整个 C 扩展生态。
3. **单线程性能**：GIL 使得单线程程序不需要承担任何锁的开销。

Python 3.13 引入了实验性的 free-threaded mode（PEP 703），可以禁用 GIL，但目前还不成熟，很多 C 扩展还不兼容。

## 3. GIL 何时释放

GIL 在以下情况下会被释放，允许其他线程运行：

```python
# 1. I/O 操作 — socket read/write, file I/O
data = socket.recv(4096)  # 等待网络 I/O 时释放 GIL

# 2. time.sleep
time.sleep(1)  # 释放 GIL

# 3. C 扩展显式释放（Py_BEGIN_ALLOW_THREADS）
import numpy as np
result = np.dot(large_matrix_a, large_matrix_b)  # numpy 在计算时释放 GIL

# 4. 等待锁、条件变量等同步原语
lock.acquire()  # 等待时释放 GIL
```

## 4. GIL 的实际影响

### CPU 密集：多线程无加速，甚至更慢

```python
import threading
import time

def cpu_bound():
    """纯 CPU 计算"""
    total = 0
    for i in range(10_000_000):
        total += i * i
    return total

# 单线程
start = time.perf_counter()
for _ in range(4):
    cpu_bound()
single = time.perf_counter() - start

# 多线程
start = time.perf_counter()
threads = [threading.Thread(target=cpu_bound) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
multi = time.perf_counter() - start

print(f"单线程: {single:.2f}s")  # 单线程: 4.56s
print(f"多线程: {multi:.2f}s")   # 多线程: 4.89s（更慢！GIL 争抢开销）
```

多线程甚至比单线程更慢，因为线程之间争抢 GIL 有上下文切换开销。

### I/O 密集：多线程有效

```python
import threading
import requests
import time

def fetch_url(url):
    """I/O 密集操作"""
    return requests.get(url)

urls = ["https://httpbin.org/delay/1"] * 10

# 单线程：串行请求
start = time.perf_counter()
for url in urls:
    fetch_url(url)
single = time.perf_counter() - start

# 多线程：并行请求
start = time.perf_counter()
threads = [threading.Thread(target=fetch_url, args=(url,)) for url in urls]
for t in threads:
    t.start()
for t in threads:
    t.join()
multi = time.perf_counter() - start

print(f"单线程: {single:.2f}s")  # ~10s
print(f"多线程: {multi:.2f}s")   # ~1s（10x 提速）
```

## 5. 四种并发模型

### 5.1 threading — I/O 密集适用

```python
from concurrent.futures import ThreadPoolExecutor

def download_file(url):
    response = requests.get(url)
    save_to_disk(response.content)

# 线程池
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(download_file, url) for url in urls]
    for future in futures:
        future.result()  # 等待完成并获取结果
```

适用场景：网络请求、文件 I/O、数据库查询等 I/O 等待为主的任务。

### 5.2 multiprocessing — CPU 密集适用

```python
from multiprocessing import Pool

def cpu_heavy(data):
    """CPU 密集计算，每个进程有独立的 GIL"""
    return heavy_computation(data)

# 进程池
with Pool(processes=4) as pool:
    results = pool.map(cpu_heavy, data_chunks)
```

进程间通信开销：
- **参数和返回值通过 pickle 序列化**，大对象传递代价高
- 共享内存可以用 `multiprocessing.shared_memory` 减少序列化开销
- 进程启动比线程慢得多（fork/spawn）

```python
from multiprocessing import shared_memory
import numpy as np

# 创建共享内存
shm = shared_memory.SharedMemory(create=True, size=large_array.nbytes)
shared_array = np.ndarray(large_array.shape, dtype=large_array.dtype, buffer=shm.buf)
np.copyto(shared_array, large_array)

# 子进程可以直接访问，无需序列化
```

### 5.3 asyncio — 大量 I/O 等待适用

```python
import asyncio
import httpx

async def fetch_url(client, url):
    response = await client.get(url)
    return response.text

async def main():
    async with httpx.AsyncClient() as client:
        # 并发发起所有请求
        tasks = [fetch_url(client, url) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

asyncio.run(main())
```

asyncio 是单线程事件循环模型：
- **优点**：没有线程切换开销，没有锁的问题，可以支撑上万并发连接
- **缺点**：一个阻塞操作会卡住整个事件循环
- **关键约束**：所有 I/O 必须使用 async 版本的库

### 5.4 concurrent.futures — 统一接口

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def process_item(item):
    return heavy_work(item)

# 根据任务类型选择 Executor，接口完全相同
Executor = ProcessPoolExecutor if is_cpu_bound else ThreadPoolExecutor

with Executor(max_workers=8) as executor:
    # map — 按顺序返回结果
    results = list(executor.map(process_item, items))

    # submit — 异步提交，按完成顺序获取
    from concurrent.futures import as_completed
    futures = {executor.submit(process_item, item): item for item in items}
    for future in as_completed(futures):
        item = futures[future]
        result = future.result()
```

## 6. 选型决策树

```
你的任务类型是什么？
│
├── CPU 密集（计算、图像处理、数据转换）
│   ├── 数据可以分块并行处理？
│   │   └── multiprocessing.Pool / ProcessPoolExecutor
│   ├── 需要共享大量数据？
│   │   └── multiprocessing + shared_memory
│   └── 考虑用 C 扩展/numpy 替代纯 Python 计算
│
├── I/O 密集（HTTP 请求、数据库查询、文件读写）
│   ├── 并发连接数 > 1000？
│   │   └── asyncio（单线程事件循环，最低开销）
│   ├── 需要调用同步库（无 async 版本）？
│   │   └── ThreadPoolExecutor
│   └── 并发连接数 < 100？
│       └── ThreadPoolExecutor（简单够用）
│
└── 混合型（CPU + I/O）
    └── asyncio + ProcessPoolExecutor
        （事件循环处理 I/O，CPU 密集任务提交到进程池）
```

### 混合型示例

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

# CPU 密集函数
def resize_image(image_data):
    return heavy_image_processing(image_data)

async def handle_upload(request):
    # I/O: 读取上传数据
    image_data = await request.body()

    # CPU: 在进程池中处理图片
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, resize_image, image_data)

    # I/O: 保存到对象存储
    await s3_client.put_object(Body=result, ...)
    return {"status": "ok"}
```

## 小结

| 模型 | 适用场景 | GIL 影响 | 开销 |
|------|---------|---------|------|
| threading | I/O 密集 | I/O 时释放 GIL | 低 |
| multiprocessing | CPU 密集 | 每个进程独立 GIL | 高（序列化+进程创建） |
| asyncio | 大量 I/O 等待 | 单线程无 GIL 问题 | 最低 |
| ProcessPoolExecutor | CPU 密集统一接口 | 独立 GIL | 高 |
| ThreadPoolExecutor | I/O 密集统一接口 | I/O 时释放 GIL | 低 |

选型的核心问题是**任务是 CPU 密集还是 I/O 密集**，而不是"Python 多线程没用"这种笼统判断。
