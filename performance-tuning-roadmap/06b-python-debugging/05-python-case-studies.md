# Python 性能排查案例集

## 概述

理论知识需要通过实战案例来巩固。本文包含 4 个真实场景的性能排查案例，每个案例按照标准排查流程展开：现象 → 假设 → 排查过程 → 根因 → 修复 → 验证。

---

## 案例 1: GIL 导致多线程 CPU 密集任务无加速

### 现象

图片处理服务使用 ThreadPoolExecutor 并行处理用户上传的图片（缩放、裁剪、加水印）。监控显示：

- 服务器 4 核 CPU，使用率始终不超过 30%
- 配置了 8 个线程，但处理速度和单线程几乎一样
- 吞吐量只有 15 张/秒，预期应该是 50+

### 假设

多线程 CPU 密集任务受 GIL 限制，无法利用多核。

### 排查过程

```bash
# 1. 用 py-spy 查看线程状态
py-spy top --pid 12345
```

输出：

```
Total Samples 1000
GIL: 98.50%    # GIL 占用率 98.5%，几乎所有时间都在等 GIL

  %Own   %Total  OwnTime  TotalTime  Function
 45.20%  45.20%    4.52s     4.52s   resize_image (app/image.py:34)
 30.10%  30.10%    3.01s     3.01s   add_watermark (app/image.py:67)
 22.30%  22.30%    2.23s     2.23s   crop_to_square (app/image.py:15)
```

关键发现：**GIL: 98.50%** —— 几乎所有 CPU 时间都在 GIL 保护下执行，多线程完全无法并行。

```python
# 2. 确认图片处理代码是纯 Python（Pillow 的部分操作释放 GIL，部分不释放）
# 检查代码发现使用了 PIL 的逐像素操作
def add_watermark(image, watermark):
    for x in range(image.width):
        for y in range(image.height):
            pixel = image.getpixel((x, y))
            # 逐像素操作，纯 Python 循环，不释放 GIL
            blended = blend_pixel(pixel, watermark.getpixel((x % watermark.width, y % watermark.height)))
            image.putpixel((x, y), blended)
```

### 根因

图片处理逻辑使用纯 Python 逐像素操作，是 CPU 密集型任务。由于 GIL 的存在，多个线程轮流执行 Python 字节码，无法实现并行计算。加上线程间 GIL 争抢的上下文切换开销，实际性能甚至略低于单线程。

### 修复

```python
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageDraw

# 方案 1: 切换为进程池（每个进程有独立的 GIL）
def process_image(image_path):
    image = Image.open(image_path)
    image = image.resize((800, 600))
    image = add_watermark_optimized(image)
    output_path = image_path.replace('.jpg', '_processed.jpg')
    image.save(output_path)
    return output_path

with ProcessPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_image, image_paths))

# 方案 2: 同时用 Pillow 内置操作替代逐像素 Python 循环
def add_watermark_optimized(image, watermark):
    # 使用 Image.paste 或 Image.alpha_composite，内部是 C 实现
    # 这些操作会释放 GIL
    watermark_resized = watermark.resize(image.size)
    return Image.alpha_composite(image.convert('RGBA'), watermark_resized)
```

### 验证

```
修复前: 15 张/秒, CPU 使用率 30%
修复后 (进程池): 55 张/秒, CPU 使用率 95%
修复后 (进程池 + C 操作优化): 120 张/秒, CPU 使用率 90%
```

---

## 案例 2: 循环引用导致内存泄漏

### 现象

Django Web 服务运行 3-4 天后 RSS 内存从 500MB 增长到 4GB，触发 OOM Kill。重启后恢复正常，几天后再次出现。

### 假设

存在内存泄漏，某些对象被持续创建但无法被 GC 回收。

### 排查过程

```python
# 1. 在 Django 管理命令中添加内存分析
# management/commands/memory_debug.py
import gc
import objgraph

class Command(BaseCommand):
    def handle(self, *args, **options):
        gc.collect()
        objgraph.show_growth(limit=10)

        # 等待一段时间，处理一些请求
        time.sleep(60)

        gc.collect()
        objgraph.show_growth(limit=10)
```

输出：

```
OrderProcessor      12500     +12480
SignalContext         12500     +12480
dict                 45000      +6200
```

`OrderProcessor` 和 `SignalContext` 在 60 秒内增长了 12480 个，明显是泄漏。

```python
# 2. 查看引用关系
leaked = objgraph.by_type('OrderProcessor')[0]
objgraph.show_backrefs(leaked, max_depth=5, filename='leak.png')
```

引用图显示：

```
OrderProcessor.signal_ctx → SignalContext.processor → OrderProcessor
                                       ↓
                              order_signal._receivers (全局信号列表)
```

```python
# 3. 找到问题代码
# signals.py
from django.dispatch import Signal

order_created = Signal()

class OrderProcessor:
    def __init__(self, order):
        self.order = order
        self.signal_ctx = SignalContext(self)
        # 每次创建 OrderProcessor 都注册信号接收器
        order_created.connect(self.signal_ctx.on_order_created)

class SignalContext:
    def __init__(self, processor):
        self.processor = processor  # 循环引用: Processor → Context → Processor

    def on_order_created(self, sender, **kwargs):
        self.processor.handle(kwargs['order'])
```

### 根因

1. 每个请求创建 `OrderProcessor`，它在 `__init__` 中向全局 Signal 注册接收器
2. `OrderProcessor` 和 `SignalContext` 互相引用，形成循环引用
3. Signal 的 `_receivers` 列表持有对 `SignalContext.on_order_created` 方法的强引用
4. 即使请求结束，`OrderProcessor` 也无法被回收（Signal 全局列表持有引用链）
5. 分代 GC 虽然能处理循环引用，但 Signal 的全局列表是外部根引用，使得对象始终可达

### 修复

```python
import weakref

class OrderProcessor:
    def __init__(self, order):
        self.order = order
        # 使用 weak=True，Signal 使用弱引用存储接收器
        order_created.connect(self.on_order_created, weak=True)

    def on_order_created(self, sender, **kwargs):
        self.handle(kwargs['order'])

    def cleanup(self):
        order_created.disconnect(self.on_order_created)

# 或者更好的方式：在请求结束时显式断开
class OrderView(View):
    def post(self, request):
        processor = OrderProcessor(request.data)
        try:
            result = processor.process()
            return JsonResponse(result)
        finally:
            processor.cleanup()  # 显式清理
```

### 验证

```
修复前: RSS 每天增长 ~800MB
修复后: RSS 稳定在 500-600MB（正常波动），运行 14 天无增长
验证: gc.collect() 后 objgraph.show_growth() 显示 OrderProcessor 数量稳定
```

---

## 案例 3: asyncio 事件循环阻塞导致所有请求超时

### 现象

FastAPI 服务在接入第三方支付回调通知后，偶发性所有 API 请求超时。监控显示：

- p50 延迟正常（50ms）
- p99 延迟偶尔飙升到 30s+
- 错误率在支付高峰期达到 15%
- 服务器 CPU 使用率不高（20%）

### 假设

某个 async 路由中调用了同步阻塞代码，阻塞了事件循环。

### 排查过程

```bash
# 1. 在高峰期 dump 调用栈
py-spy dump --pid $(pgrep -f uvicorn)
```

输出：

```
Thread 0x7f... (main thread - asyncio event loop):
    ...
    File "app/payment.py", line 45, in notify_payment_result
    File "/usr/lib/python3.11/site-packages/requests/api.py", line 59, in post
    File "/usr/lib/python3.11/site-packages/requests/sessions.py", line 589, in post
    File "/usr/lib/python3.11/site-packages/urllib3/connectionpool.py", line 703, in urlopen
    File "/usr/lib/python3.11/socket.py", line 706, in readinto
    <<<< blocked here - waiting for socket read >>>>
```

关键发现：主线程（事件循环线程）阻塞在 `requests.post` 的 socket 读取上。

```python
# 2. 查看问题代码
# app/payment.py
@app.post("/payment/callback")
async def payment_callback(data: PaymentCallback):
    # 验证支付结果
    verified = verify_signature(data)

    if verified:
        await update_order_status(data.order_id, "paid")

        # 问题在这里！在 async 函数中调用了同步的 requests.post
        # 通知业务系统支付结果
        response = requests.post(           # 阻塞事件循环！
            "http://biz-service/notify",
            json=data.dict(),
            timeout=30                      # 最长阻塞 30 秒
        )

    return {"status": "ok"}
```

### 根因

`payment_callback` 是 `async def` 路由，在事件循环线程中执行。其中调用了同步的 `requests.post`，当第三方服务响应慢时，`requests.post` 会阻塞事件循环最多 30 秒。在这 30 秒内，事件循环无法处理任何其他请求，导致所有请求超时。

### 修复

```python
import httpx

# 创建异步 HTTP 客户端（应用级别复用）
http_client = httpx.AsyncClient(timeout=10.0)

@app.post("/payment/callback")
async def payment_callback(data: PaymentCallback):
    verified = verify_signature(data)

    if verified:
        await update_order_status(data.order_id, "paid")

        # 修复：使用 async HTTP 客户端
        try:
            response = await http_client.post(
                "http://biz-service/notify",
                json=data.dict(),
                timeout=10.0
            )
        except httpx.TimeoutException:
            # 异步超时不会阻塞事件循环
            logger.warning(f"Notify timeout for order {data.order_id}")
            # 放入重试队列
            await retry_queue.put(data)

    return {"status": "ok"}

@app.on_event("shutdown")
async def shutdown():
    await http_client.aclose()
```

### 验证

```
修复前:
  p50: 50ms, p99: 30000ms (支付高峰期)
  错误率: 15% (支付高峰期)

修复后:
  p50: 48ms, p99: 210ms
  错误率: 0.1%

验证方法:
  1. 模拟第三方服务慢响应（sleep 10s）
  2. 同时发送 100 个普通 API 请求
  3. 确认普通请求不受影响（p99 < 300ms）
```

---

## 案例 4: Django ORM N+1 查询导致列表页慢

### 现象

电商后台的商品列表页（100 条/页），页面加载时间 3-5 秒，数据库 CPU 使用率偶尔飙升到 80%。

### 假设

存在 N+1 查询问题。

### 排查过程

```python
# 1. 使用 django-debug-toolbar 或 django-silk 统计查询数
# settings.py (开发环境)
INSTALLED_APPS += ['silk']
MIDDLEWARE += ['silk.middleware.SilkyMiddleware']
SILKY_PYTHON_PROFILER = True

# 或者用 django.db.connection.queries 手动统计
from django.db import connection, reset_queries
from django.conf import settings

settings.DEBUG = True
reset_queries()

# 模拟视图调用
products = list(Product.objects.all()[:100])
for p in products:
    _ = p.category.name      # 触发查询
    _ = p.brand.name          # 触发查询

print(f"查询总数: {len(connection.queries)}")
# 输出: 查询总数: 201
```

201 条查询！1 条查询商品列表 + 100 条查询分类 + 100 条查询品牌。

```python
# 2. 查看具体查询内容
for q in connection.queries[:10]:
    print(f"[{q['time']}s] {q['sql'][:100]}")
```

输出：

```
[0.003s] SELECT * FROM products LIMIT 100
[0.001s] SELECT * FROM categories WHERE id = 1
[0.001s] SELECT * FROM brands WHERE id = 5
[0.001s] SELECT * FROM categories WHERE id = 2
[0.001s] SELECT * FROM brands WHERE id = 3
...
```

### 根因

视图代码：

```python
# views.py
def product_list(request):
    products = Product.objects.all()[:100]
    data = []
    for p in products:
        data.append({
            'name': p.name,
            'price': p.price,
            'category': p.category.name,  # 每次访问触发 SELECT category
            'brand': p.brand.name,        # 每次访问触发 SELECT brand
        })
    return JsonResponse({'products': data})
```

每个商品访问 `category` 和 `brand` 外键时，Django ORM 惰性加载，每次都发起一条 SELECT 查询。100 条商品 x 2 个外键 = 200 条额外查询。

### 修复

```python
def product_list(request):
    # select_related 将外键 JOIN 到主查询中
    products = Product.objects.select_related(
        'category', 'brand'
    ).all()[:100]

    # 现在只有 1 条 SQL:
    # SELECT products.*, categories.*, brands.*
    # FROM products
    # JOIN categories ON products.category_id = categories.id
    # JOIN brands ON products.brand_id = brands.id
    # LIMIT 100

    data = []
    for p in products:
        data.append({
            'name': p.name,
            'price': p.price,
            'category': p.category.name,  # 不再触发查询，已经 JOIN 了
            'brand': p.brand.name,
        })
    return JsonResponse({'products': data})
```

如果还需要加载多对多关系（如商品标签）：

```python
products = Product.objects.select_related(
    'category', 'brand'
).prefetch_related(
    'tags'  # 多对多关系用 prefetch_related
).all()[:100]
# 查询数: 2（1 条 JOIN 查询 + 1 条 tags IN 查询）
```

### 验证

```
修复前:
  SQL 查询数: 201
  页面加载时间: 3.2s
  数据库 CPU: 峰值 80%

修复后:
  SQL 查询数: 2
  页面加载时间: 0.15s
  数据库 CPU: 峰值 10%

查询数降低 99%，响应时间降低 95%。
```

### 防止回退

```python
# 在测试中使用 assertNumQueries 防止 N+1 回退
from django.test import TestCase

class ProductListTest(TestCase):
    def test_product_list_query_count(self):
        create_test_products(100)
        with self.assertNumQueries(2):  # 严格限制查询数
            response = self.client.get('/api/products/')
            self.assertEqual(response.status_code, 200)
```

---

## 总结

四个案例覆盖了 Python 后端最常见的性能问题类型：

| 案例 | 问题类型 | 排查工具 | 核心教训 |
|------|---------|---------|---------|
| 1. GIL + 多线程 | CPU 瓶颈 | py-spy（GIL 指标） | CPU 密集用进程池 |
| 2. 循环引用泄漏 | 内存泄漏 | objgraph | weakref + 显式清理 |
| 3. 事件循环阻塞 | 延迟飙升 | py-spy dump | async 中只用 async 库 |
| 4. N+1 查询 | 数据库瓶颈 | django-silk / assertNumQueries | select_related |

排查方法论：不要猜测，用工具说话。先确认现象（监控指标），再定位范围（profiler），最后找到根因（代码分析），修复后用数据验证效果。
