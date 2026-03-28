# Python Web 框架调优

## 概述

选对框架只是开始，真正的性能差异在于如何配置和使用框架。本文覆盖 FastAPI 和 Django 两大主流框架的性能调优要点，以及 Gunicorn worker 模型选型、ASGI vs WSGI 对比和连接池配置。

## 1. FastAPI 性能调优

### 异步 vs 同步路由

```python
# 异步路由 — 在事件循环中直接执行
# 适合：内部全是 async 操作的处理器
@app.get("/async")
async def async_handler():
    result = await async_db_query()
    return result

# 同步路由 — FastAPI 自动放到线程池执行
# 适合：需要调用同步库的处理器
@app.get("/sync")
def sync_handler():
    result = sync_db_query()  # 不会阻塞事件循环
    return result
```

**关键陷阱**：如果路由声明为 `async def`，但内部调用了同步阻塞代码，会阻塞事件循环。要么改为 `def`（让 FastAPI 自动放入线程池），要么确保内部全部使用 async API。

### 依赖注入缓存

```python
from functools import lru_cache
from fastapi import Depends

class Settings:
    database_url: str = "postgresql://..."
    redis_url: str = "redis://..."

# 错误：每次请求都创建新的 Settings 实例
@app.get("/bad")
async def bad_handler(settings: Settings = Depends(Settings)):
    ...

# 正确：用 lru_cache 缓存，只创建一次
@lru_cache
def get_settings():
    return Settings()

@app.get("/good")
async def good_handler(settings: Settings = Depends(get_settings)):
    ...
```

对于数据库连接等需要请求级生命周期的依赖：

```python
async def get_db():
    async with async_session() as session:
        yield session  # 请求结束后自动关闭

@app.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    ...
```

### Pydantic v2 性能提升

Pydantic v2 用 Rust 重写了核心验证逻辑，序列化和反序列化性能提升 5-50x。

```python
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = {
        # 禁用不需要的功能以提升性能
        "frozen": True,           # 不可变模型，可以被哈希和缓存
        "extra": "forbid",        # 禁止额外字段，加快验证
    }

# 批量序列化优化
users = [UserResponse(id=i, name=f"user_{i}", email=f"u{i}@example.com")
         for i in range(1000)]

# v2 的 model_dump() 比 v1 的 dict() 快 5-10x
data = [u.model_dump() for u in users]
```

### 中间件开销

每个中间件都会在每个请求上执行。中间件数量和复杂度直接影响延迟。

```python
# 检查中间件耗时
import time

@app.middleware("http")
async def timing_middleware(request, call_next):
    # 中间件本身要尽可能轻量
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}"
    return response

# 避免在中间件中做重计算或 I/O
# 如果某些路径不需要某个中间件，考虑用 dependency 替代
```

## 2. Django 性能调优

### select_related / prefetch_related 解决 N+1

N+1 查询是 Django ORM 最常见的性能问题。

```python
# N+1 问题：1 次查询订单 + N 次查询用户
orders = Order.objects.all()  # SELECT * FROM orders
for order in orders:
    print(order.user.name)  # 每次访问 user 都触发一次 SELECT

# select_related — 用 JOIN 一次查出（ForeignKey / OneToOneField）
orders = Order.objects.select_related('user').all()
# SELECT orders.*, users.* FROM orders JOIN users ON ...
for order in orders:
    print(order.user.name)  # 不再触发查询

# prefetch_related — 用两次查询 + Python 合并（ManyToManyField / 反向关系）
orders = Order.objects.prefetch_related('items').all()
# 查询 1: SELECT * FROM orders
# 查询 2: SELECT * FROM order_items WHERE order_id IN (...)
```

### QuerySet 惰性加载陷阱

```python
# QuerySet 是惰性的，定义不会执行查询
qs = Order.objects.filter(status='pending')  # 不执行

# 以下操作会触发查询执行
list(qs)           # 转为 list
len(qs)            # 用 qs.count() 替代，更高效
qs[0]              # 切片
for order in qs:   # 迭代
    ...
bool(qs)           # 用 qs.exists() 替代

# 陷阱：在模板中多次访问同一个 QuerySet，每次都重新查询
# 解决：在视图中用 list() 强制求值
context['orders'] = list(orders_qs)
```

### 缓存框架

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# 视图级缓存
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 缓存 15 分钟
def product_list(request):
    products = Product.objects.all()
    ...

# 片段级缓存
from django.core.cache import cache

def get_hot_products():
    cache_key = "hot_products_v1"
    result = cache.get(cache_key)
    if result is None:
        result = list(Product.objects.filter(is_hot=True)[:20])
        cache.set(cache_key, result, timeout=300)
    return result
```

### 数据库连接管理

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        # CONN_MAX_AGE: 连接在连接池中保持的秒数
        # 0 = 每次请求新建连接（默认，开销大）
        # None = 永不关闭（需要确保数据库支持）
        # 600 = 保持 10 分钟
        'CONN_MAX_AGE': 600,
    }
}
```

注意：`CONN_MAX_AGE` 不是真正的连接池。每个线程/进程独立持有一个连接。如果需要真正的连接池，使用 pgbouncer 或 Django 4.1+ 的 `CONN_HEALTH_CHECKS`。

## 3. Gunicorn Worker 模型对比

### sync — 同步阻塞 Worker

```bash
gunicorn app:application -w 4 --worker-class sync
```

- 每个 worker 是一个进程，一次只处理一个请求
- 简单可靠，适合 CPU 密集型 Django 应用
- 并发数 = worker 数

### gthread — 线程池 Worker

```bash
gunicorn app:application -w 4 --worker-class gthread --threads 4
```

- 每个 worker 进程内有多个线程
- 并发数 = workers x threads
- 适合 I/O 密集型 Django 应用
- 内存效率比 sync 高（线程共享进程内存）

### uvicorn — ASGI Worker

```bash
# 方式 1: uvicorn 直接启动
uvicorn main:app --workers 4

# 方式 2: gunicorn + uvicorn worker
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

- 支持 async/await
- 适合 FastAPI、Starlette 等 ASGI 框架
- 单个 worker 可以处理大量并发连接

### Worker 数量计算

```bash
# 经验公式：2 * CPU 核数 + 1
# 依据：假设一半 worker 在做 I/O 等待，另一半在计算
workers = 2 * multiprocessing.cpu_count() + 1

# 实际调优时需要根据负载类型调整
# CPU 密集：workers = CPU 核数（更多没有意义）
# I/O 密集：可以适当增加，但要监控内存

gunicorn main:app -w $(( 2 * $(nproc) + 1 )) -k uvicorn.workers.UvicornWorker
```

## 4. ASGI vs WSGI

| 维度 | WSGI | ASGI |
|------|------|------|
| 协议 | 同步，每个请求一个线程/进程 | 异步，支持 async/await |
| 并发模型 | 进程/线程 | 事件循环 |
| WebSocket | 不支持 | 原生支持 |
| 长连接 | 不适合 | 适合 |
| 框架 | Django, Flask | FastAPI, Starlette, Django(ASGI) |
| 服务器 | Gunicorn, uWSGI | Uvicorn, Daphne, Hypercorn |
| 适用场景 | 传统 Web 应用 | 高并发 I/O、实时通信 |

**选型建议**：
- 新项目且 I/O 密集 → ASGI (FastAPI + Uvicorn)
- 已有 Django 项目 → 先用 WSGI，需要 WebSocket 或高并发时逐步迁移 ASGI
- CPU 密集型 → WSGI 和 ASGI 差异不大

## 5. 连接池配置

### SQLAlchemy 连接池

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

# 同步引擎
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    pool_size=10,         # 连接池大小（常驻连接数）
    max_overflow=20,      # 超出 pool_size 后最多额外创建多少连接
    pool_timeout=30,      # 获取连接超时秒数
    pool_recycle=1800,    # 连接回收时间（防止数据库端超时断开）
    pool_pre_ping=True,   # 使用前检测连接是否有效
)
# 总并发连接上限 = pool_size + max_overflow = 30

# 异步引擎
async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
```

### asyncpg 连接池

```python
import asyncpg

# asyncpg 自带连接池，性能优于 SQLAlchemy 的 async 模式
pool = await asyncpg.create_pool(
    "postgresql://user:pass@localhost/db",
    min_size=5,      # 最小连接数
    max_size=20,     # 最大连接数
    max_inactive_connection_lifetime=300,  # 空闲连接超时
)

async with pool.acquire() as conn:
    result = await conn.fetch("SELECT * FROM users WHERE id = $1", user_id)
```

### 连接池大小计算

```
连接池大小 = Gunicorn workers * 每个 worker 的 pool_size

例如：
4 workers * 10 pool_size = 40 个数据库连接
确保不超过 PostgreSQL 的 max_connections（默认 100）

如果需要更多连接 → 在数据库前面加 pgbouncer 做连接复用
```

## 小结

Web 框架调优的优先级：
1. **修复 N+1 查询**（最常见的性能问题，select_related/prefetch_related）
2. **正确配置 Worker 模型**（匹配负载类型）
3. **连接池配置**（避免连接耗尽或频繁创建）
4. **缓存热数据**（减少数据库压力）
5. **中间件精简**（移除不必要的中间件）

不要一上来就做微观优化（换序列化库、换 JSON 库），先解决架构层面的问题。
