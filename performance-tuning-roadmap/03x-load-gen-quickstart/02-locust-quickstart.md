# Locust 快速上手

## Locust 是什么

Locust 是一个用 Python 编写的开源负载测试框架。它的核心理念是：**用 Python 代码定义用户行为**，而不是用 XML 或 GUI 配置。这使得测试场景的定义极其灵活 —— 任何 Python 能做的事情，Locust 都能做。

**与 wrk 的定位差异：**
- wrk：单接口、极致性能、快速验证
- Locust：多步骤用户场景、灵活脚本、可视化 UI、分布式施压

---

## 安装

```bash
pip install locust

# 验证安装
locust --version
# locust 2.29.x
```

建议在虚拟环境中安装：

```bash
python3 -m venv loadtest-env
source loadtest-env/bin/activate
pip install locust
```

---

## 写一个最简脚本

创建 `locustfile.py`：

```python
from locust import HttpUser, task, between

class OrderUser(HttpUser):
    """模拟一个下单用户的行为"""

    # 每个任务之间等待 1-3 秒（模拟真实用户的思考时间）
    wait_time = between(1, 3)

    @task(3)  # 权重为 3，被执行的概率更高
    def list_orders(self):
        """浏览订单列表"""
        self.client.get("/api/orders", name="/api/orders")

    @task(1)  # 权重为 1
    def create_order(self):
        """创建订单"""
        self.client.post("/api/orders",
            json={
                "productId": 1001,
                "quantity": 1,
                "userId": 12345
            },
            name="/api/orders [POST]"
        )

    def on_start(self):
        """每个虚拟用户启动时执行一次（如登录）"""
        resp = self.client.post("/api/login",
            json={"username": "testuser", "password": "testpass"})
        if resp.status_code == 200:
            self.token = resp.json().get("token")
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
```

### 核心概念

| 概念 | 说明 |
|------|------|
| `HttpUser` | 虚拟用户基类，自带 HTTP 客户端 |
| `@task` | 标记为任务方法，Locust 随机调用 |
| `@task(n)` | 权重为 n，调用概率 = n / 所有 task 权重之和 |
| `wait_time` | 两个任务之间的等待时间 |
| `between(1, 3)` | 随机等待 1-3 秒 |
| `constant(2)` | 固定等待 2 秒 |
| `on_start()` | 用户启动时执行（登录、初始化） |
| `on_stop()` | 用户停止时执行（清理资源） |
| `name` 参数 | 请求分组名（避免动态 URL 生成过多分组） |

---

## Web UI 使用

### 启动 Locust

```bash
# 在 locustfile.py 所在目录执行
locust

# 或指定文件路径
locust -f /path/to/locustfile.py

# 指定目标主机（也可以在 UI 中填写）
locust -f locustfile.py --host http://localhost:8080
```

启动后访问 `http://localhost:8089` 打开 Web UI。

### Web UI 配置

```
┌─────────────────────────────────────────────────┐
│ Start new load test                              │
│                                                   │
│ Number of users (peak concurrency): [ 100 ]      │
│ Ramp up (users started/second):     [ 10  ]      │
│ Host:                  [ http://localhost:8080 ]  │
│                                                   │
│ [ Start swarming ]                                │
└─────────────────────────────────────────────────┘
```

| 参数 | 含义 |
|------|------|
| Number of users | 最大并发虚拟用户数 |
| Ramp up | 每秒新增用户数（10 表示 10 秒达到 100 用户） |
| Host | 目标服务地址 |

### 实时图表

Web UI 提供三个核心图表：
1. **Total Requests per Second**：实时 RPS
2. **Response Times (ms)**：P50/P95 延迟趋势
3. **Number of Users**：当前活跃用户数

还有统计表格显示每个接口的：请求总数、失败数、中位数延迟、P95 延迟、P99 延迟、平均响应大小。

---

## 完整 locustfile.py 示例

以下是一个模拟电商场景的完整压测脚本：

```python
import random
from locust import HttpUser, task, between, SequentialTaskSet, events

class BrowseAndBuy(SequentialTaskSet):
    """模拟完整的浏览-加购-下单流程（按顺序执行）"""

    def on_start(self):
        # 登录获取 token
        resp = self.client.post("/api/auth/login", json={
            "username": f"user_{random.randint(1, 10000)}",
            "password": "test123"
        })
        if resp.status_code == 200:
            self.token = resp.json()["token"]
            self.client.headers["Authorization"] = f"Bearer {self.token}"
        else:
            self.interrupt()  # 登录失败，中断此用户

    @task
    def browse_products(self):
        """浏览商品列表"""
        page = random.randint(1, 10)
        self.client.get(f"/api/products?page={page}&size=20",
                       name="/api/products?page=[N]")

    @task
    def view_product_detail(self):
        """查看商品详情"""
        product_id = random.randint(1, 5000)
        resp = self.client.get(f"/api/products/{product_id}",
                              name="/api/products/[id]")
        if resp.status_code == 200:
            self.product_id = product_id

    @task
    def add_to_cart(self):
        """加入购物车"""
        if hasattr(self, 'product_id'):
            self.client.post("/api/cart/items", json={
                "productId": self.product_id,
                "quantity": random.randint(1, 3)
            })

    @task
    def create_order(self):
        """下单"""
        self.client.post("/api/orders", json={
            "paymentMethod": random.choice(["ALIPAY", "WECHAT", "CARD"]),
            "addressId": random.randint(1, 100)
        })

    @task
    def stop(self):
        """完成一轮购买流程后重新开始"""
        self.interrupt()


class EcommerceUser(HttpUser):
    wait_time = between(1, 5)
    tasks = [BrowseAndBuy]

    # 可以混合多种用户行为
    @task(2)
    def check_order_status(self):
        """查看订单状态（独立于购买流程）"""
        order_id = random.randint(1, 100000)
        self.client.get(f"/api/orders/{order_id}",
                       name="/api/orders/[id]")


# 自定义事件监听：打印测试汇总
@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    if environment.stats.total.fail_ratio > 0.01:
        print(f"WARNING: 失败率 {environment.stats.total.fail_ratio:.2%} 超过 1%")
```

---

## 阶梯加压（LoadTestShape）

Locust 支持自定义加压曲线，模拟逐步增加负载的场景：

```python
from locust import HttpUser, task, between, LoadTestShape

class StepLoadShape(LoadTestShape):
    """
    阶梯加压：每 60 秒增加 50 个用户，直到 300 个用户
    然后保持 300 用户运行 120 秒
    """
    stages = [
        {"duration": 60,  "users": 50,  "spawn_rate": 10},
        {"duration": 120, "users": 100, "spawn_rate": 10},
        {"duration": 180, "users": 150, "spawn_rate": 10},
        {"duration": 240, "users": 200, "spawn_rate": 10},
        {"duration": 300, "users": 250, "spawn_rate": 10},
        {"duration": 360, "users": 300, "spawn_rate": 10},
        {"duration": 480, "users": 300, "spawn_rate": 10},  # 保持 120s
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None  # 返回 None 停止测试
```

```
用户数
  300 │                          ┌──────────┐
  250 │                     ┌────┘          │
  200 │                ┌────┘               │
  150 │           ┌────┘                    │
  100 │      ┌────┘                         │
   50 │ ┌────┘                              │
    0 │─┘                                   └── 停止
      └──────────────────────────────────────── 时间
       0   60  120  180  240  300  360  480s
```

---

## 无头模式运行

CI/CD 流水线或服务器上不需要 Web UI，使用 `--headless` 模式：

```bash
# 基本无头模式
locust -f locustfile.py \
  --host http://localhost:8080 \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m

# 输出 CSV 报告
locust -f locustfile.py \
  --host http://localhost:8080 \
  --headless \
  --users 200 \
  --spawn-rate 20 \
  --run-time 10m \
  --csv=results/load-test \
  --csv-full-history

# 生成 HTML 报告
locust -f locustfile.py \
  --host http://localhost:8080 \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --html=results/report.html
```

CSV 输出文件：
- `load-test_stats.csv`：每个接口的汇总统计
- `load-test_stats_history.csv`：每秒的统计数据
- `load-test_failures.csv`：失败请求详情
- `load-test_exceptions.csv`：脚本异常

---

## 分布式压测

单机的并发能力有限。Locust 原生支持 master/worker 分布式模式：

```
┌──────────────┐
│   Master     │ ← Web UI + 协调
│ (不产生负载)  │
└──────┬───────┘
       │ 分配任务
  ┌────┼────┐
  ▼    ▼    ▼
┌───┐┌───┐┌───┐
│ W1 ││ W2 ││ W3 │  ← Worker（产生实际负载）
└───┘└───┘└───┘
```

### 启动命令

```bash
# Master（只负责协调，不产生负载）
locust -f locustfile.py --master --host http://target:8080

# Worker（在每台施压机上启动）
locust -f locustfile.py --worker --master-host <master-ip>

# 本机多 Worker（利用多核 CPU）
locust -f locustfile.py --master &
locust -f locustfile.py --worker &
locust -f locustfile.py --worker &
locust -f locustfile.py --worker &

# 快捷方式：自动启动 1 master + N worker
locust -f locustfile.py --processes 4 --host http://target:8080
```

### Docker Compose 分布式

```yaml
# docker-compose.yml
version: '3'
services:
  master:
    image: locustio/locust
    ports:
      - "8089:8089"
    volumes:
      - ./:/mnt/locust
    command: -f /mnt/locust/locustfile.py --master -H http://target:8080

  worker:
    image: locustio/locust
    volumes:
      - ./:/mnt/locust
    command: -f /mnt/locust/locustfile.py --worker --master-host master
    deploy:
      replicas: 4
```

```bash
docker compose up --scale worker=8
```

---

## 配合 Grafana 观察

压测的价值不仅在于 Locust 自身的统计，更在于同时观察服务端的 Prometheus 指标。

### 压测观察流程

```
┌─────────────────────────────────────────────┐
│  终端 1: 启动 Locust                         │
│  locust -f locustfile.py --host ...          │
├─────────────────────────────────────────────┤
│  浏览器 Tab 1: Locust Web UI (8089)          │
│  → 观察 RPS、延迟、错误率                    │
├─────────────────────────────────────────────┤
│  浏览器 Tab 2: Grafana Dashboard             │
│  → 观察 CPU / 内存 / GC / 连接池 / 线程池    │
├─────────────────────────────────────────────┤
│  终端 2: 观察日志                            │
│  kubectl logs -f deployment/order-service    │
└─────────────────────────────────────────────┘
```

### Grafana Dashboard 关注要点

| 阶段 | Locust 观察 | Grafana 观察 |
|------|------------|-------------|
| 低压预热 | RPS 是否稳定 | 服务是否正常启动、JIT 编译完成 |
| 线性加压 | RPS 是否随用户数线性增长 | CPU/内存趋势 |
| 压力拐点 | RPS 不再增长、延迟突然上升 | 哪个资源先饱和（CPU?连接池?） |
| 持续高压 | 错误率是否上升 | GC 频率、线程池 reject、OOM |
| 回压测试 | 停止加压后恢复速度 | 资源是否正常释放 |

### Locust 指标导出到 Prometheus

Locust 可以通过 `locust-plugins` 将指标暴露给 Prometheus：

```bash
pip install locust-plugins
```

```python
# locustfile.py 中添加
from locust_plugins.listeners import TimescaleListener
# 或使用 prometheus exporter
import locust_plugins.listeners  # 自动注册 /metrics 端点
```

或者使用独立的 exporter：

```bash
pip install prometheus-client

# 在 locustfile.py 中
from prometheus_client import start_http_server, Counter, Histogram

start_http_server(9646)  # Prometheus metrics 端口
```

---

## 常用命令模板

```bash
# 快速冒烟测试
locust -f locustfile.py --host http://localhost:8080 \
  --headless -u 10 -r 2 --run-time 1m

# 标准压力测试
locust -f locustfile.py --host http://localhost:8080 \
  --headless -u 200 -r 20 --run-time 10m \
  --csv=results/standard --html=results/standard.html

# 峰值压力测试
locust -f locustfile.py --host http://localhost:8080 \
  --headless -u 1000 -r 50 --run-time 15m \
  --csv=results/peak

# 分布式压测（本机 4 进程）
locust -f locustfile.py --host http://localhost:8080 \
  --processes 4 --headless -u 2000 -r 100 --run-time 10m

# 带 Web UI 的交互式测试
locust -f locustfile.py --host http://localhost:8080
```

---

## 小结

```
Locust 使用要点
├── 安装：pip install locust
├── 脚本：HttpUser + @task + wait_time
├── 运行：Web UI（交互式）/ --headless（CI/CD）
├── 加压：线性加压 / LoadTestShape 阶梯加压
├── 分布式：master/worker 模式，--processes 快捷启动
├── 观察：Locust UI + Grafana Dashboard 双屏联动
└── 定位：复杂用户场景、多步骤流程、可编程压测
```

掌握了 wrk（快速验证）和 Locust（场景化压测）后，你已经具备了基本的负载生成能力。在后续的 Phase 7 中，我们会深入学习更系统的负载测试方法论，包括压测策略设计、基线建立和容量规划。
