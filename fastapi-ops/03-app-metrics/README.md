# 03 — 应用级指标：Prometheus + Grafana

## 目标

让服务"说出"自己的状态。能用 PromQL 回答：当前 P99 延迟是多少？哪个接口错误率在上升？

## Prometheus 数据模型

### 四种指标类型

| 类型 | 特点 | 典型用途 |
|------|------|---------|
| **Counter** | 只增不减，重启归零 | 请求总数、错误总数 |
| **Gauge** | 可增可减 | 当前连接数、内存使用量 |
| **Histogram** | 分桶统计，可算分位数 | 请求延迟分布 |
| **Summary** | 客户端计算分位数 | 分位数（不推荐，无法聚合） |

### 关键理解
- Counter 本身没意义，要配合 `rate()` 看速率
- Histogram 的 bucket 划分影响分位数精度（`le` 标签）
- 标签（label）是高基数的坑：不要把 user_id 放进标签

## 接入 FastAPI

### 方案一：自动埋点（快速上手）

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

自动获得：
- `http_requests_total` — 请求计数（按 method / handler / status）
- `http_request_duration_seconds` — 延迟直方图

### 方案二：手动埋点（精细控制）

```python
from prometheus_client import Counter, Histogram, Gauge

# 业务指标
orders_created = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"]  # success / failed
)

order_processing_time = Histogram(
    "order_processing_seconds",
    "Order processing duration",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

active_connections = Gauge(
    "db_active_connections",
    "Active database connections"
)

# 使用
with order_processing_time.time():
    result = await create_order(data)
orders_created.labels(status="success").inc()
```

## 并发资源饱和监控

FastAPI 生产环境最常见的「CPU 正常、P99 爆炸」根因,恰好是 `top` 看不见的那半张脸:anyio 线程池令牌耗尽、事件循环被阻塞、连接池检出数打满。本节给出可直接粘贴的 `prometheus_client` 埋点代码,配合 [capstone §4 速查表](../../performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md) 食用。

### 线程池 + 事件循环滞后

运行期的线程池状态和事件循环延迟都是「拉取时难取」的对象——在 `/metrics` 处理协程里直接调用会有上下文绑定问题。标准做法是**用一个后台采样协程统一刷新**:

```python
# 用一个后台采样协程统一刷新「拉取时」难取的运行期指标(避免在 /metrics 处理协程里取 loop 绑定对象)
import anyio.to_thread, asyncio, threading
from prometheus_client import Gauge

TP_BORROWED = Gauge("app_threadpool_borrowed_tokens", "anyio 线程池在用线程数")
TP_TOTAL    = Gauge("app_threadpool_total_tokens", "anyio 线程池容量上限")
TP_WAITING  = Gauge("app_threadpool_tasks_waiting", "排队等令牌的协程数(饱和领先指标)")
LOOP_LAG    = Gauge("asyncio_event_loop_lag_seconds", "事件循环单拍滞后(实际睡眠-预期)")
PY_THREADS  = Gauge("app_python_threads", "当前 Python 线程数")

async def sample_concurrency(interval: float = 0.5):
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(interval)
        LOOP_LAG.set(loop.time() - t0 - interval)            # 多睡的部分 = 循环被卡住的时间
        s = anyio.to_thread.current_default_thread_limiter().statistics()
        TP_BORROWED.set(s.borrowed_tokens); TP_TOTAL.set(s.total_tokens); TP_WAITING.set(s.tasks_waiting)
        PY_THREADS.set(threading.active_count())
```

`app_threadpool_tasks_waiting` 是**饱和领先指标**:等待数从 0 变正说明线程池已满、同步 `def` 端点在排队,比利用率指标早发出信号。`anyio.to_thread.current_default_thread_limiter().statistics()` 的三个字段(`borrowed_tokens`/`total_tokens`/`tasks_waiting`)对应 [fastapi-ops/01-foundation A6](../01-foundation/README.md) 里分析的 40 令牌上限。

> **何时需要这三个线程池 gauge:** 只在你的 app 实际跑同步 `def` 端点 / `run_in_threadpool` 时才有意义——这时线程池才被借用、`tasks_waiting` 才可能 > 0。若全程 async、从不碰线程池,它们恒为 0,可以不接。但 `asyncio_event_loop_lag_seconds` **无论如何都该留**:它抓的是「一行阻塞调用冻住整个事件循环」这一 FastAPI 头号坑,系统层完全看不见。

### 在 lifespan 挂起采样协程

```python
# 在 lifespan 里挂起采样协程
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(sample_concurrency())
    yield
    task.cancel()
```

### 连接池持续监控

连接池的「一次性排查」对比（如何在 shell 里临时检查连接数）见 [python-data/02-connection-pooling.md](../../python-data/02-connection-pooling.md)。本节给出的是**持续 Prometheus 监控**方案。`collect_db_pool` 是普通函数，本身不会被自动调用——由调用方决定触发时机。最简单的做法：把 `engine` 传进上面的 `sample_concurrency` 后台协程，在它的循环里追加一行 `collect_db_pool(engine)`，让连接池和线程池/事件循环共用同一个采样节拍；或把它包成 Prometheus 自定义 collector 在 `/metrics` 拉取时执行。

```python
# 连接池「持续」监控(对比 python-data/02 的一次性排查)
from prometheus_client import Gauge
DB_CHECKED_OUT = Gauge("app_db_pool_checked_out", "已借出连接数")
DB_OVERFLOW    = Gauge("app_db_pool_overflow", "溢出连接数(超过 pool_size 的临时连接)")
def collect_db_pool(engine):           # AsyncEngine 也用 engine.pool
    p = engine.pool
    DB_CHECKED_OUT.set(p.checkedout()); DB_OVERFLOW.set(p.overflow())
```

`AsyncEngine` 和同步 `Engine` 均通过 `engine.pool` 访问连接池对象；`checkedout()` 返回已借出连接数，`overflow()` 返回超过 `pool_size` 的临时连接数，该值 > 0 即说明连接池饱和。

### 运行时指标无需手写

`prometheus_client` 默认已注册 `ProcessCollector` 和 `GCCollector`，`/metrics` 端点直接暴露：
- `process_open_fds` — 进程打开的文件描述符数
- `process_resident_memory_bytes` — RSS 内存
- `python_gc_collections_total` — 各代 GC 次数

**无需手写这些指标**；若要关闭默认注册，传 `registry=CollectorRegistry()` 给 `make_asgi_app()`。

### 上生产前:多 worker 与采样健壮性

上面那段是**教学骨架**,直接照抄上生产有两个会咬你的点:

**① 多 worker 必须开 `prometheus_client` multiprocess 模式。** uvicorn/gunicorn 的 worker 数通常 ≈ CPU 核数,每个 worker 是独立进程,各有自己的事件循环、自己的 anyio limiter、自己的这套 Gauge。`prometheus_client` 默认 registry 是**进程级**的——`/metrics` 被抓到哪个 worker,你就只看到那个 worker 的数,`tasks_waiting` 直接误导。生产必须:

```python
# 1) 启动前设环境变量,指向一个可写目录(启动时清空):
#    export PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc
# 2) Gauge 显式声明跨进程聚合方式
from prometheus_client import Gauge, CollectorRegistry, multiprocess
TP_WAITING = Gauge("app_threadpool_tasks_waiting", "...", multiprocess_mode="livesum")
# 3) /metrics 用聚合 registry 汇总所有 worker 写出的 .db
def metrics_registry():
    reg = CollectorRegistry()
    multiprocess.MultiProcessCollector(reg)
    return reg
```

`borrowed_tokens` / `tasks_waiting` / `total_tokens` 都用 `multiprocess_mode="livesum"`(对存活 worker 求和:总在用线程、总排队数、有效上限 = workers×40)。注意:multiprocess 模式下 `ProcessCollector` / `GCCollector` 的默认聚合行为受限,需单独处理。

**② 采样循环要包 `try/except`。** `while True` 裸跑时,`.statistics()` 万一抛一次,这个 task 就**静默死掉、监控从此冻住而你不知道**(监控自己挂了最危险)。生产版循环体 `try: … except Exception: log.exception(…)`,别让一次异常杀死整个采样器。

### 配套 PromQL / 告警

```promql
app_threadpool_tasks_waiting > 0                 # 同步 def 端点在排队(for: 30s → P2)
asyncio_event_loop_lag_seconds > 0.1             # 事件循环被阻塞(头号坑)
app_db_pool_overflow > 0                         # pool_size 已用尽、开始借临时连接 = 连接池饱和
```

三条告警均建在**饱和度/溢出**上，而非利用率——原因见 [capstone §2](../../performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md)（等待数是领先指标，利用率是滞后指标）。

---

**延伸阅读：**
- 连接池一次性排查对比：[python-data/02-connection-pooling.md](../../python-data/02-connection-pooling.md)
- 三语言速查表 + 通用告警范式：[performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md](../../performance-tuning-roadmap/03-observability/07-concurrent-resource-saturation.md)

---

## PromQL 核心语法

### 必会查询

```promql
# 过去 5 分钟的请求 QPS
rate(http_requests_total[5m])

# 错误率（5xx / 总请求）
rate(http_requests_total{status=~"5.."}[5m])
/ rate(http_requests_total[5m])

# P99 延迟
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[5m])
)

# 按接口分组的 P99
histogram_quantile(0.99,
  sum by (handler, le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)

# 当前数据库连接数
db_active_connections
```

### `rate` vs `irate`
- `rate`：时间窗口内的平均速率，适合告警（平滑）
- `irate`：最后两个点的瞬时速率，适合图表（响应快）

## Grafana Dashboard 设计

### RED 方法（面向用户体验）

| 指标 | 含义 | Panel 类型 |
|------|------|-----------|
| **R**ate | 每秒请求数（QPS） | Time series |
| **E**rror | 错误率 | Stat + Time series |
| **D**uration | P50 / P95 / P99 延迟 | Time series |

### USE 方法（面向资源）

| 指标 | 含义 |
|------|------|
| **U**tilization | CPU / 内存 / 连接池使用率 |
| **S**aturation | 队列长度、等待数 |
| **E**rrors | 系统错误计数 |

## 告警规则设计

```yaml
# alertmanager rules
groups:
  - name: fastapi
    rules:
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 5% for 2 minutes"

      - alert: SlowP99
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        annotations:
          summary: "P99 latency > 1s"
```

## Docker Compose 搭建观测栈

```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["8000:8000"]

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## 实践任务

- [ ] 接入自动埋点，能在 Prometheus 看到 http_requests_total
- [ ] 手动添加订单创建的 Counter 和 Histogram
- [ ] 在 Grafana 做出 RED Dashboard
- [ ] 编写 P99 > 1s 的告警规则

## 关键问题

1. 为什么不推荐把 `user_id` 作为 Prometheus 标签？
2. `rate(counter[5m])` 和直接用 counter 值的区别？
3. Histogram 的精度由什么决定？如何选择 bucket 边界？
4. 为什么 Summary 无法在多实例间聚合？
