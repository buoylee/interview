# 压测工具对比与实操

## 主流压测工具全景

压测工具的选择直接影响压测效率和结果准确性。选错工具会导致要么功能不够用（反复折腾），要么过于复杂（杀鸡用牛刀）。本文对比六种主流工具并给出实操示例。

---

## 一、六种工具对比表

| 特性 | wrk | hey | Vegeta | k6 | Locust | JMeter |
|------|-----|-----|--------|----|---------| -------|
| 语言 | C (Lua 脚本) | Go | Go | Go (JS 脚本) | Python | Java |
| 协议 | HTTP/1.1 | HTTP/1.1, HTTP/2 | HTTP | HTTP, WebSocket, gRPC | HTTP, 自定义 | HTTP, JDBC, FTP, SOAP 等 |
| 脚本能力 | Lua（有限） | 无 | 无 | JavaScript（完整） | Python（完整） | GUI + Groovy |
| 分布式 | 不支持 | 不支持 | 不原生支持 | k6 Cloud / xk6-distributed | 原生支持 | 原生支持 |
| 报告能力 | 终端文本 | 终端文本 | 终端/JSON/HDR | 终端/JSON/CSV/Cloud | Web UI 实时 | HTML/CSV/图表 |
| 资源消耗 | 极低 | 低 | 低 | 中 | 高（Python GIL） | 高（JVM） |
| 学习曲线 | 低 | 极低 | 低 | 中 | 中 | 高 |
| 适用场景 | 快速 HTTP 基准测试 | 快速 HTTP 测试 | CI 集成/管道压测 | 复杂场景脚本化压测 | 复杂场景/团队协作 | 企业级/多协议 |

---

## 二、选型决策树

```
你需要压测什么？
│
├── 简单 HTTP 接口快速测试
│   ├── 需要自定义请求头/Body？
│   │   ├── 是 → hey（简单好用）
│   │   └── 否 → wrk（性能最高）
│   └── 需要恒定请求速率？ → Vegeta（rate-based）
│
├── 复杂业务场景（登录→浏览→下单）
│   ├── 团队偏好 Python → Locust
│   └── 团队偏好 JS / 需要更好性能 → k6
│
├── 需要 GUI / 非开发人员使用 → JMeter
│
└── 需要集成到 CI Pipeline
    ├── Go 项目 → Vegeta（命令行管道友好）
    └── 通用 → k6（阈值 + CI 退出码）
```

---

## 三、各工具实操示例

### 1. wrk — 极致性能的 HTTP 压测

```bash
# 基本用法：12 线程、400 并发、持续 30 秒
wrk -t12 -c400 -d30s http://localhost:8080/api/users

# 带 Lua 脚本自定义请求
wrk -t4 -c100 -d30s -s post.lua http://localhost:8080/api/orders
```

```lua
-- post.lua
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"user_id": 1001, "product_id": 2001}'
```

**注意**：wrk 不支持恒定速率发送（constant rate），它是尽可能快地发请求，这会导致协调遗漏问题（Coordinated Omission）。如果需要修正，使用 `wrk2`。

### 2. hey — 最简单的压测工具

```bash
# 200 并发，发送 10000 个请求
hey -c 200 -n 10000 http://localhost:8080/api/health

# 带自定义 Header 和 Body
hey -c 50 -z 30s \
  -m POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token123" \
  -d '{"key":"value"}' \
  http://localhost:8080/api/data

# 输出包含延迟分布直方图，非常直观
```

### 3. Vegeta — 管道友好的恒定速率压测

Vegeta 的设计哲学是 Unix 管道，每个组件只做一件事。

```bash
# 基本用法：每秒 500 请求，持续 30 秒
echo "GET http://localhost:8080/api/users" | \
  vegeta attack -rate=500/s -duration=30s | \
  vegeta report

# 多个接口混合压测
cat targets.txt | vegeta attack -rate=1000/s -duration=60s | vegeta report

# targets.txt 内容：
# GET http://localhost:8080/api/users
# GET http://localhost:8080/api/products
# POST http://localhost:8080/api/orders
# Content-Type: application/json
# @body.json

# 生成 HDR Histogram 延迟分布图
echo "GET http://localhost:8080/api/users" | \
  vegeta attack -rate=500/s -duration=30s | \
  vegeta report -type=hdrplot > latency.hdr

# 实时编码输出为 JSON（可接入监控）
echo "GET http://localhost:8080/api/users" | \
  vegeta attack -rate=200/s -duration=60s | \
  vegeta encode --to=json | \
  jq -c '{status: .code, latency_ms: (.latency/1000000)}'
```

**Vegeta 最大优势**：恒定请求速率（constant rate），不受服务端延迟影响发送频率，能正确测量延迟，避免协调遗漏。

### 4. k6 — 现代化的脚本压测

k6 是目前最推荐的脚本化压测工具，平衡了性能和灵活性。

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

// 阶梯加压配置
export const options = {
  stages: [
    { duration: '1m', target: 50 },   // 1分钟内从 0 爬升到 50 并发
    { duration: '3m', target: 50 },   // 保持 50 并发 3 分钟
    { duration: '1m', target: 100 },  // 1分钟内从 50 爬升到 100
    { duration: '3m', target: 100 },  // 保持 100 并发 3 分钟
    { duration: '1m', target: 0 },    // 1分钟内降到 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // P95 < 500ms, P99 < 1s
    http_req_failed: ['rate<0.01'],                    // 错误率 < 1%
  },
};

export default function () {
  // 模拟用户行为
  const loginRes = http.post('http://localhost:8080/api/login', JSON.stringify({
    username: 'testuser',
    password: 'testpass',
  }), { headers: { 'Content-Type': 'application/json' } });

  check(loginRes, {
    'login status is 200': (r) => r.status === 200,
    'login has token': (r) => r.json('token') !== '',
  });

  const token = loginRes.json('token');

  // 带 token 请求
  const usersRes = http.get('http://localhost:8080/api/users', {
    headers: { Authorization: `Bearer ${token}` },
  });

  check(usersRes, {
    'users status is 200': (r) => r.status === 200,
    'users count > 0': (r) => r.json('data').length > 0,
  });

  sleep(1); // 模拟用户思考时间
}
```

```bash
# 运行压测
k6 run load-test.js

# 输出 JSON 结果用于 CI
k6 run --out json=results.json load-test.js

# 如果 thresholds 不满足，k6 退出码非 0，天然适合 CI
```

### 5. Locust — Python 生态的分布式压测

```python
# locustfile.py
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)  # 每次请求间隔 1-3 秒

    def on_start(self):
        """用户启动时执行一次（如登录）"""
        self.client.post("/api/login", json={
            "username": "testuser",
            "password": "testpass"
        })

    @task(3)  # 权重 3，被调用概率更高
    def view_products(self):
        self.client.get("/api/products")

    @task(1)  # 权重 1
    def create_order(self):
        self.client.post("/api/orders", json={
            "product_id": 1001,
            "quantity": 1
        })
```

```bash
# 启动 Web UI 模式
locust -f locustfile.py --host=http://localhost:8080
# 浏览器打开 http://localhost:8089 配置并发数和加压速率

# 无头模式（适合 CI）
locust -f locustfile.py --host=http://localhost:8080 \
  --headless -u 100 -r 10 -t 5m \
  --csv=results

# 分布式模式（master + workers）
locust -f locustfile.py --master  # 主节点
locust -f locustfile.py --worker --master-host=192.168.1.100  # 工作节点
```

### 6. JMeter — 基本使用流程

JMeter 适合需要 GUI、多协议支持的场景（如 JDBC 直接压测数据库）。

```bash
# 命令行模式运行（推荐，GUI 模式本身消耗大量资源）
jmeter -n -t test-plan.jmx -l results.jtl -e -o report/

# 参数说明：
# -n 非 GUI 模式
# -t 测试计划文件
# -l 结果日志
# -e -o 生成 HTML 报告
```

JMeter 测试计划核心组件：
- **Thread Group**：定义并发数、加压方式
- **HTTP Request**：定义请求详情
- **Assertions**：响应断言
- **Listeners**：结果收集（Summary Report, Aggregate Report）

---

## 四、工具常见坑

### 1. 客户端瓶颈

```
现象：QPS 上不去，但服务端 CPU 很闲
原因：压测客户端自身成为瓶颈

排查方法：
$ top  # 看压测客户端的 CPU 使用率
$ ss -s  # 看连接数是否到达系统限制
$ ulimit -n  # 检查文件描述符限制
```

**解决方案**：
- 使用资源消耗更低的工具（wrk > k6 > Locust > JMeter）
- 分布式部署多个压测节点
- 确保压测客户端和服务端之间网络带宽充足

### 2. 连接数限制

```bash
# 系统级别限制
$ sysctl net.core.somaxconn
$ sysctl net.ipv4.ip_local_port_range

# 用户级别限制
$ ulimit -n  # 文件描述符（每个连接占一个 fd）

# 临时调大
$ ulimit -n 65535
$ sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
```

### 3. DNS 解析开销

压测时用域名而非 IP，每次请求都做 DNS 解析会引入不可控延迟。

```bash
# 解决方案 1：直接用 IP
wrk -t4 -c100 -d30s http://10.0.1.50:8080/api/users

# 解决方案 2：在 /etc/hosts 中写死
echo "10.0.1.50 api.example.com" >> /etc/hosts
```

### 4. TIME_WAIT 堆积

短连接压测时，客户端会快速积累 TIME_WAIT 状态连接，导致端口耗尽。

```bash
# 检查
$ ss -s | grep TIME-WAIT

# 解决：使用 HTTP Keep-Alive（长连接）
# k6 默认使用 Keep-Alive
# wrk 默认使用 Keep-Alive
# hey 需要显式关闭 -disable-keepalive=false
```

---

## 五、推荐组合

根据团队和场景，推荐以下组合：

| 场景 | 推荐组合 |
|------|---------|
| 日常开发快速验证 | wrk / hey |
| CI 性能门禁 | k6（阈值 + 退出码）或 Vegeta |
| 完整性能测试 | k6（脚本化场景）+ Grafana 监控 |
| 大规模分布式压测 | Locust（分布式模式）或 k6 Cloud |
| 多协议/遗留系统 | JMeter |

**最终建议**：如果只选一个工具深入学习，选 **k6**。它在性能、脚本能力、CI 友好度之间取得了最佳平衡，且社区活跃、文档优秀。
