# asyncio 排查

## 概述

asyncio 是 Python 高并发 I/O 的首选方案，但它有独特的调试挑战：事件循环阻塞、忘记 await、在 async 函数中调用同步阻塞代码 —— 这些问题在开发阶段往往不明显，到生产环境高并发时才暴露。本文介绍 asyncio 常见问题的排查方法。

## 1. 事件循环阻塞检测

asyncio 的核心是单线程事件循环：所有协程在同一个线程上轮流执行。如果某个协程执行了阻塞操作（CPU 计算、同步 I/O），整个事件循环都会停住，所有其他协程都无法运行。

### 开启 debug 模式

```python
import asyncio

# 方式 1: 环境变量
# PYTHONASYNCIODEBUG=1 python app.py

# 方式 2: 代码中设置
loop = asyncio.get_event_loop()
loop.set_debug(True)

# 方式 3: asyncio.run 参数
asyncio.run(main(), debug=True)
```

### 慢回调检测

debug 模式下，asyncio 会自动检测执行时间过长的回调：

```python
import asyncio
import logging

# 设置日志级别为 WARNING 以看到慢回调警告
logging.basicConfig(level=logging.WARNING)

loop = asyncio.get_event_loop()
loop.set_debug(True)

# 默认阈值 100ms，可以自定义
loop.slow_callback_duration = 0.05  # 50ms

async def slow_handler():
    # 模拟阻塞操作
    import time
    time.sleep(0.2)  # 阻塞 200ms

asyncio.run(slow_handler(), debug=True)
```

输出：

```
WARNING:asyncio:Executing <Task ...slow_handler()> took 0.203 seconds
```

这个警告直接告诉你哪个协程阻塞了事件循环，以及阻塞了多久。

## 2. 常见错误：忘记 await

```python
async def get_user(user_id):
    return await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)

async def handle_request(user_id):
    # 错误！忘记 await，user 是一个 coroutine 对象，不是查询结果
    user = get_user(user_id)
    print(type(user))  # <class 'coroutine'>
    print(user.name)   # AttributeError: 'coroutine' object has no attribute 'name'

    # 正确
    user = await get_user(user_id)
```

debug 模式下，未 await 的协程在被垃圾回收时会产生警告：

```
RuntimeWarning: coroutine 'get_user' was never awaited
```

**开发阶段务必开启 debug 模式**，可以在 pytest conftest 中全局设置：

```python
# conftest.py
import asyncio

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()

# 或设置环境变量
# PYTHONASYNCIODEBUG=1
```

## 3. 在 async 函数中调用同步阻塞

这是生产环境最常见的 asyncio 性能问题。

### 典型错误

```python
import requests  # 同步 HTTP 库
import time

async def notify_user(user_id, message):
    # 错误！requests.post 是同步阻塞调用
    # 它会阻塞整个事件循环，其他所有请求都会等待
    response = requests.post(
        "https://api.notification.com/send",
        json={"user_id": user_id, "message": message}
    )
    return response.status_code

async def process_order(order):
    # 错误！time.sleep 阻塞事件循环
    time.sleep(1)

    # 错误！同步文件 I/O
    with open("large_file.csv") as f:
        data = f.read()  # 阻塞
```

### 正确做法

```python
import httpx
import asyncio
import aiofiles

async def notify_user(user_id, message):
    # 正确：使用 async HTTP 客户端
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notification.com/send",
            json={"user_id": user_id, "message": message}
        )
    return response.status_code

async def process_order(order):
    # 正确：使用 asyncio.sleep
    await asyncio.sleep(1)

    # 正确：使用 aiofiles 做异步文件 I/O
    async with aiofiles.open("large_file.csv") as f:
        data = await f.read()
```

### 常见的同步阻塞库及其 async 替代

| 同步库 | 阻塞操作 | async 替代 |
|--------|---------|-----------|
| requests | HTTP 请求 | httpx / aiohttp |
| time.sleep | 等待 | asyncio.sleep |
| open() | 文件 I/O | aiofiles |
| psycopg2 | PostgreSQL | asyncpg |
| PyMySQL | MySQL | aiomysql |
| redis-py (同步模式) | Redis | redis.asyncio / aioredis |
| subprocess.run | 子进程 | asyncio.create_subprocess_exec |
| smtplib | 发邮件 | aiosmtplib |

## 4. run_in_executor — 桥接同步代码

有些库没有 async 版本，或者迁移成本太高。这时可以用 `run_in_executor` 将同步调用放到线程池中执行，不阻塞事件循环。

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from PIL import Image  # Pillow 没有 async 版本

# 创建专用线程池
io_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="io")

async def process_image(image_path):
    loop = asyncio.get_event_loop()

    # 将同步阻塞操作放到线程池
    image = await loop.run_in_executor(
        io_pool,
        Image.open,
        image_path
    )

    # CPU 密集操作也可以放到线程池（或进程池）
    resized = await loop.run_in_executor(
        io_pool,
        lambda: image.resize((800, 600))
    )

    return resized
```

在 FastAPI 中更简洁的写法：

```python
from fastapi.concurrency import run_in_threadpool

@app.post("/convert")
async def convert_file(file: UploadFile):
    content = await file.read()
    # run_in_threadpool 是 FastAPI 对 run_in_executor 的封装
    result = await run_in_threadpool(sync_convert_function, content)
    return {"result": result}
```

**注意**：FastAPI 的同步路由函数（不带 async）会自动在线程池中运行，不会阻塞事件循环：

```python
# 这个同步函数不会阻塞事件循环
# FastAPI 自动将其放到线程池执行
@app.get("/sync-route")
def sync_handler():
    time.sleep(1)  # 不会阻塞其他请求
    return {"ok": True}

# async 路由中的同步调用会阻塞
@app.get("/async-route")
async def async_handler():
    time.sleep(1)  # 会阻塞整个事件循环！
    return {"ok": True}
```

## 5. uvloop — 高性能事件循环

uvloop 是用 Cython 和 libuv 实现的高性能事件循环，替代 CPython 默认的 asyncio 事件循环。

### 安装与使用

```bash
pip install uvloop
```

```python
# 方式 1: 全局替换
import uvloop
uvloop.install()  # 必须在 asyncio.run() 之前调用
asyncio.run(main())

# 方式 2: uvicorn 自动使用（如果安装了 uvloop）
# uvicorn main:app --loop uvloop
# uvicorn 会自动检测 uvloop 并使用
```

### 性能提升

根据官方 benchmark，uvloop 在大部分场景下比默认事件循环快 **2-4 倍**：

- HTTP 服务器吞吐量提升约 2x
- TCP echo 服务器提升约 3x
- DNS 解析提升约 2x

性能提升来源于：
- libuv 的高效 I/O 多路复用（epoll/kqueue 封装）
- Cython 减少了 Python 层面的开销
- 更高效的定时器和回调调度

### 注意事项

```python
# uvloop 不支持 Windows
# uvloop 不支持 asyncio.get_event_loop().add_signal_handler() 的部分信号
# 某些 edge case 行为可能与标准库不同
```

## 6. 实操：检测 FastAPI 中的事件循环阻塞

### 步骤 1: 编写检测中间件

```python
import asyncio
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("loop_block_detector")

class LoopBlockDetectorMiddleware(BaseHTTPMiddleware):
    """检测请求处理中的事件循环阻塞"""

    async def dispatch(self, request, call_next):
        # 记录事件循环的"真实时间"和"挂钟时间"差异
        loop = asyncio.get_event_loop()
        wall_start = time.perf_counter()
        loop_start = loop.time()

        response = await call_next(request)

        wall_duration = time.perf_counter() - wall_start
        loop_duration = loop.time() - loop_start

        # 如果挂钟时间和事件循环时间差距很大，说明有阻塞
        # 正常情况下两者应该接近
        blocking_time = wall_duration - loop_duration
        if blocking_time > 0.1:  # 超过 100ms
            logger.warning(
                f"Potential event loop blocking detected: "
                f"path={request.url.path} "
                f"wall_time={wall_duration:.3f}s "
                f"loop_time={loop_duration:.3f}s "
                f"blocking_time={blocking_time:.3f}s"
            )

        return response

app.add_middleware(LoopBlockDetectorMiddleware)
```

### 步骤 2: 用 py-spy 确认阻塞位置

```bash
# 发送触发阻塞的请求后，立即 dump 调用栈
py-spy dump --pid $(pgrep -f uvicorn)
```

输出中如果看到同步库的调用栈（如 `requests/adapters.py`、`socket.recv`），就确认了事件循环被同步 I/O 阻塞。

### 步骤 3: 自动化阻塞检测

```python
import asyncio

async def watchdog(interval=1.0, threshold=0.5):
    """事件循环阻塞看门狗"""
    while True:
        start = time.perf_counter()
        await asyncio.sleep(interval)
        actual = time.perf_counter() - start
        delay = actual - interval
        if delay > threshold:
            logger.error(
                f"Event loop was blocked for {delay:.3f}s "
                f"(expected sleep: {interval}s, actual: {actual:.3f}s)"
            )

# 启动时添加看门狗任务
@app.on_event("startup")
async def startup():
    asyncio.create_task(watchdog())
```

这个看门狗原理是：如果 `asyncio.sleep(1)` 实际睡了 2 秒，说明事件循环被阻塞了 1 秒。

## 小结

asyncio 排查的核心关注点：

1. **开启 debug 模式**：自动检测忘记 await 和慢回调
2. **绝不在 async 函数中调用同步阻塞**：用 async 库替代，或用 run_in_executor 桥接
3. **使用 uvloop**：简单替换即可获得 2-4x 性能提升
4. **添加阻塞检测中间件/看门狗**：生产环境持续监控

记住一个原则：**async 函数中的每一行代码，如果不是 await 表达式，就是在独占事件循环**。任何耗时超过 1ms 的非 await 操作都值得关注。
