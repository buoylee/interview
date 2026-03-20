# 08 — 应用层调优

## 目标

找到瓶颈后，有系统化的应用层调优手段，并能量化调优效果。

## Worker 配置调优

### Gunicorn + UvicornWorker

```python
# gunicorn.conf.py
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
keepalive = 5
timeout = 30
graceful_timeout = 30

# 关键：IO密集型可以更多 worker；CPU密集型反而可能适得其反
```

### 决策矩阵

| 场景 | Worker 数 | 原因 |
|------|-----------|------|
| IO 密集（数据库/外部API）| CPU核数 × 2 ~ 4 | 大量时间在等待，多 worker 并行 |
| CPU 密集（计算/序列化）| CPU核数 | 超过核数会增加上下文切换开销 |
| 混合型 | CPU核数 × 2 | 折中 |

### Uvicorn 单进程 + asyncio（IO密集的最优解）

```bash
# 单进程，但每个请求都是协程，并发能力取决于 IO 等待
uvicorn app:app --workers 1 --loop uvloop

# uvloop 比标准 asyncio 快 2-4 倍（基于 libuv）
pip install uvloop
```

## 异步最佳实践

### 1. 消灭同步阻塞

```python
# 检查清单：这些操作在 async 函数里会阻塞事件循环
import time; time.sleep(1)         # ❌ → asyncio.sleep(1)
import requests; requests.get(url)  # ❌ → httpx.AsyncClient().get(url)
open("file").read()                 # ❌ → aiofiles
subprocess.run(cmd)                 # ❌ → asyncio.create_subprocess_exec

# CPU 密集型
heavy_computation(data)             # ❌ → run_in_executor(None, heavy_computation, data)
```

### 2. 并发化独立 IO

```python
# 串行（慢）：300ms
async def bad():
    user = await get_user(user_id)        # 100ms
    orders = await get_orders(user_id)    # 100ms
    credits = await get_credits(user_id)  # 100ms
    return user, orders, credits

# 并行（快）：100ms
async def good():
    user, orders, credits = await asyncio.gather(
        get_user(user_id),
        get_orders(user_id),
        get_credits(user_id),
    )
    return user, orders, credits
```

### 3. 超时控制（避免慢外部调用拖垮）

```python
import asyncio

async def call_external():
    try:
        async with asyncio.timeout(2.0):  # Python 3.11+
            return await external_api.get(url)
    except asyncio.TimeoutError:
        log.warning("external_api_timeout")
        return None  # 降级处理
```

## 数据库连接池调优

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # 常驻连接数
    max_overflow=20,        # 额外可借用的连接数（峰值时）
    pool_timeout=30,        # 等待连接超时时间（秒）
    pool_recycle=3600,      # 连接复用最大时间（防止被 MySQL 断开）
    pool_pre_ping=True,     # 取连接前 ping 一下（检测断连）
)
```

### 连接数计算

```
数据库最大连接数（如 PostgreSQL 默认 100）
= worker 数 × pool_size + 管理工具连接

示例：4 workers × pool_size=10 = 40 个连接
建议留 20% 给 pgAdmin / 监控工具
```

### 监控连接池状态

```python
@router.get("/metrics/db_pool")
async def db_pool_metrics():
    pool = engine.pool
    return {
        "size": pool.size(),           # 当前池大小
        "checked_in": pool.checkedin(),  # 空闲连接
        "checked_out": pool.checkedout(),  # 使用中连接
        "overflow": pool.overflow(),   # 溢出连接数
    }
```

## 缓存策略

### Redis 缓存（减少数据库压力）

```python
from functools import wraps
import json

def cache(ttl: int = 60, key_prefix: str = ""):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{args}:{kwargs}"
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            await redis.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

@cache(ttl=300, key_prefix="order")
async def get_order(order_id: int):
    return await db.query(Order, order_id)
```

### 缓存失效策略

| 策略 | 适用场景 |
|------|---------|
| TTL 过期 | 数据可以短暂不一致 |
| 写时失效（Cache-Aside） | 写操作后主动删 key |
| 写时更新 | 写操作后立即更新缓存（复杂但一致） |
| 布隆过滤器 | 防止缓存穿透（不存在的 key 大量查询） |

### HTTP 缓存（减少重复请求）

```python
from fastapi.responses import Response

@router.get("/products/{id}")
async def get_product(id: int, response: Response):
    product = await get_product_from_db(id)
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["ETag"] = compute_etag(product)
    return product
```

## 序列化优化

```python
# 标准 json（慢）
import json
json.dumps(data)  # 约 1x

# orjson（快 3-10 倍，C 实现）
import orjson
orjson.dumps(data)

# FastAPI 接入
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
```

## 后台任务 vs 消息队列

```python
# FastAPI BackgroundTasks：简单但不可靠（进程崩溃任务丢失）
@router.post("/orders")
async def create_order(background_tasks: BackgroundTasks):
    order = await save_order()
    background_tasks.add_task(send_confirmation_email, order)  # 快速返回
    return order

# 消息队列（可靠）：Celery + Redis/RabbitMQ
from celery import Celery
app_celery = Celery(broker="redis://localhost:6379")

@app_celery.task(bind=True, max_retries=3)
def send_email_task(self, order_id):
    try:
        send_email(order_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

## 调优量化表（压测前后对比）

| 指标 | 调优前 | 调优后 | 改动 |
|------|--------|--------|------|
| QPS | - | - | - |
| P99 延迟 | - | - | - |
| CPU 使用率 | - | - | - |
| 数据库连接数 | - | - | - |

## 关键问题

1. `asyncio.gather` 和多进程的区别？什么时候用哪个？
2. 连接池 `pool_timeout` 超时后会怎样？用户会看到什么错误？
3. Redis 缓存雪崩、穿透、击穿三种情况各是什么，如何防止？
4. 什么时候用 BackgroundTasks，什么时候必须用消息队列？
