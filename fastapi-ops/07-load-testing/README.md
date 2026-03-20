# 07 — 压测：Locust

## 目标

能设计合理的压测场景，边压边看 Grafana 指标，找到系统的性能瓶颈在哪里先触发。

## 压测的核心认知

**压测不是为了让服务挂掉，是为了找到：**
1. 当前配置下的性能上限（RPS / 最大并发）
2. 瓶颈首先出现在哪里（CPU / 内存 / 数据库连接 / 外部依赖）
3. 量化调优效果（调优前后对比）

## Locust 基础

```bash
pip install locust
```

```python
# locustfile.py
from locust import HttpUser, task, between

class OrderUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 每个用户请求间等待时间

    def on_start(self):
        """用户启动时执行（登录、获取 token）"""
        resp = self.client.post("/auth/login", json={
            "username": "test", "password": "test"
        })
        self.token = resp.json()["token"]

    @task(3)  # 权重 3，出现频率更高
    def get_order(self):
        self.client.get(
            f"/orders/{random.randint(1, 1000)}",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/orders/[id]"  # 归组，防止不同 id 被当成不同接口
        )

    @task(1)
    def create_order(self):
        self.client.post("/orders", json={
            "product_id": random.randint(1, 100),
            "quantity": 1
        }, headers={"Authorization": f"Bearer {self.token}"})
```

```bash
# 启动（有 Web UI）
locust -f locustfile.py --host http://localhost:8000

# 无头模式（CI/CD 用）
locust -f locustfile.py --host http://localhost:8000 \
    --users 100 --spawn-rate 10 --run-time 5m --headless \
    --csv results
```

## 压测场景设计

### 场景一：阶梯加压（找上限）

```python
from locust import LoadTestShape

class StepLoadShape(LoadTestShape):
    """每 2 分钟增加 50 并发，找到性能拐点"""
    step_time = 120
    step_load = 50
    max_users = 500

    def tick(self):
        run_time = self.get_run_time()
        current_step = run_time // self.step_time
        users = min(self.step_load * (current_step + 1), self.max_users)
        return (users, self.step_load)
```

### 场景二：峰值冲击（测稳定性）

```python
class SpikeShape(LoadTestShape):
    """模拟流量突刺"""
    phases = [
        {"duration": 60, "users": 10},    # 低流量热身
        {"duration": 30, "users": 500},   # 突刺
        {"duration": 60, "users": 10},    # 恢复观察
    ]
```

### 场景三：长时稳定性（测内存泄漏）

保持中等负载运行 30 分钟以上，观察：
- RSS 内存是否持续增长
- 错误率是否随时间升高
- P99 延迟是否随时间增大（说明有积累效应）

## 压测时观测清单

**同时开着 Grafana，对照看：**

```
应用指标（03-app-metrics）：
  □ QPS 是否达到目标
  □ P99 延迟变化趋势
  □ 错误率（特别关注 5xx）

系统指标（02-system-metrics）：
  □ CPU us/sy/wa 变化
  □ 内存 RSS 增长
  □ 数据库连接池使用率

网络指标：
  □ ss -s 看 TIME_WAIT 数量
  □ 全连接队列是否溢出
```

## 识别瓶颈类型

### CPU Bound
- 特征：`us` 高，延迟随并发线性增长
- 解法：增加 Worker 数，优化算法，缓存

### IO Bound（数据库）
- 特征：`wa` 高，数据库连接池耗尽，错误是连接超时
- 解法：连接池调大，查询优化（索引），读写分离

### IO Bound（网络/外部调用）
- 特征：`wa` 低 `sy` 正常，追踪看外部 Span 时间长
- 解法：超时控制，熔断，并行化外部调用

### 内存压力
- 特征：RSS 高，Swap 开始使用，延迟抖动
- 解法：memray 找泄漏，减少对象创建，增加实例

### 连接泄漏
- 特征：初始正常，随时间推移错误率升高，重启后恢复
- 解法：检查连接池的归还逻辑，是否有异常路径未关闭连接

## 压测报告解读

```
Locust 输出关键指标：
  RPS        当前每秒请求数
  Failures   失败率（目标：< 0.1%）
  p50/p95/p99 延迟分位数
  Max        最大延迟（偶发尖刺）
```

**性能拐点识别**：
- P99 开始快速上升而非线性增长 = 资源开始饱和
- 错误率从 0 开始出现 = 系统到达上限

## 实践任务

- [ ] 编写包含读/写的 Locust 脚本（模拟真实业务比例）
- [ ] 用阶梯加压找到服务的 RPS 上限
- [ ] 压测时看 Grafana，记录到达上限时各项指标的值
- [ ] 人为制造数据库连接池耗尽，观察现象和错误信息

## 关键问题

1. Locust 的 `wait_time` 设置影响什么？设为 0 和 `between(1, 3)` 有什么区别？
2. 压测时看到 CPU `wa` 高但 iostat `%util` 低，可能是什么原因？
3. 压测结束后，服务响应变慢但不恢复，最可能是什么问题？
4. 为什么压测要在类生产环境而非开发机上做？
