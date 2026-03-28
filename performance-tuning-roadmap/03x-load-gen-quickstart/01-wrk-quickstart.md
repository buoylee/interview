# wrk 快速上手

## wrk 是什么

wrk 是一个高性能的 HTTP 压测工具，使用 C 语言编写，基于 epoll/kqueue 实现多路复用，单机就能产生大量并发连接和请求。它是后端开发者快速验证接口性能最常用的工具之一。

**定位：轻量级、单机、适合快速验证。** 复杂的压测场景（多步骤流程、数据参数化、分布式施压）请使用 Locust、k6 或 JMeter。

---

## 安装方法

### macOS

```bash
brew install wrk
```

### Ubuntu / Debian

```bash
sudo apt-get install -y build-essential libssl-dev git
git clone https://github.com/wg/wrk.git
cd wrk
make
sudo cp wrk /usr/local/bin/
```

### CentOS / RHEL

```bash
sudo yum groupinstall 'Development Tools'
sudo yum install -y openssl-devel git
git clone https://github.com/wg/wrk.git
cd wrk
make
sudo cp wrk /usr/local/bin/
```

### 验证安装

```bash
wrk --version
# wrk 4.2.0 [epoll] ...
```

---

## 基本用法

```bash
wrk -t4 -c100 -d30s http://localhost:8080/api/orders
```

### 参数详解

| 参数 | 含义 | 说明 |
|------|------|------|
| `-t4` | 4 个线程 | 施压线程数，通常设为 CPU 核数 |
| `-c100` | 100 个并发连接 | 所有线程共享，每个线程 25 个连接 |
| `-d30s` | 持续 30 秒 | 支持 s（秒）、m（分）、h（时） |
| `-H` | 自定义 Header | `-H "Authorization: Bearer xxx"` |
| `-s` | Lua 脚本 | 用于自定义请求逻辑 |
| `--latency` | 输出详细延迟分布 | 显示 50/75/90/99 分位数 |
| `--timeout` | 请求超时 | 默认无超时，建议设置 `--timeout 5s` |

### 常用参数组合

```bash
# 轻量测试：快速验证接口是否正常
wrk -t2 -c10 -d10s http://localhost:8080/api/health

# 中等压力：模拟正常业务负载
wrk -t4 -c100 -d30s --latency http://localhost:8080/api/orders

# 高压测试：探测系统极限
wrk -t8 -c500 -d60s --latency --timeout 5s http://localhost:8080/api/orders
```

---

## 读懂输出

```
Running 30s test @ http://localhost:8080/api/orders
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    12.34ms    5.67ms  98.76ms   72.34%
    Req/Sec     2.05k   234.56     3.12k    68.50%
  Latency Distribution
     50%   11.23ms
     75%   14.56ms
     90%   19.87ms
     99%   45.32ms
  245678 requests in 30.01s, 123.45MB read
  Socket errors: connect 0, read 5, write 0, timeout 3
Requests/sec:   8186.12
Transfer/sec:      4.11MB
```

### 各字段解读

**Thread Stats：**

| 字段 | 含义 |
|------|------|
| Latency Avg | 平均延迟 12.34ms |
| Latency Stdev | 延迟标准差 5.67ms（越大说明延迟越不稳定） |
| Latency Max | 最大延迟 98.76ms |
| +/- Stdev | 72.34% 的请求在平均值 ±1 标准差内 |
| Req/Sec Avg | 每线程每秒 2050 请求 |

**Latency Distribution：**

| 分位数 | 含义 |
|--------|------|
| 50%（P50） | 一半请求在 11.23ms 内完成 |
| 75%（P75） | 75% 的请求在 14.56ms 内完成 |
| 90%（P90） | 90% 的请求在 19.87ms 内完成 |
| 99%（P99） | 99% 的请求在 45.32ms 内完成 |

**关注重点：P99 远大于 P50 说明有长尾延迟，需要排查是什么导致了偶尔的慢请求。**

**Socket errors：**

| 错误类型 | 含义 |
|---------|------|
| connect | 连接建立失败（服务拒绝连接） |
| read | 读取响应失败（连接被重置） |
| write | 发送请求失败 |
| timeout | 请求超时 |

如果 Socket errors 数量显著，说明服务已经过载，需要降低并发量或排查瓶颈。

**汇总指标：**
- `Requests/sec: 8186.12` —— 系统整体 QPS
- `Transfer/sec: 4.11MB` —— 吞吐带宽

---

## Lua 脚本扩展

wrk 的 Lua 脚本支持自定义请求方法、Header、Body 等。

### POST 请求

```lua
-- post.lua
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"productId": 1001, "quantity": 1, "userId": 12345}'
```

使用方式：

```bash
wrk -t4 -c100 -d30s -s post.lua http://localhost:8080/api/orders
```

### 带 Token 认证

```lua
-- auth.lua
wrk.headers["Authorization"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6..."
wrk.headers["Content-Type"] = "application/json"
```

### 动态请求体（随机参数）

```lua
-- dynamic.lua
math.randomseed(os.time())

request = function()
    local userId = math.random(1, 100000)
    local productId = math.random(1, 5000)
    local body = string.format(
        '{"userId": %d, "productId": %d, "quantity": 1}',
        userId, productId
    )
    return wrk.format("POST", "/api/orders", {
        ["Content-Type"] = "application/json",
        ["Authorization"] = "Bearer test-token"
    }, body)
end
```

### 统计响应状态码

```lua
-- stats.lua
done = function(summary, latency, requests)
    io.write("------------------------------\n")
    io.write(string.format("Total requests: %d\n", summary.requests))
    io.write(string.format("Total errors:   %d\n", summary.errors.status))
    io.write(string.format("Avg latency:    %.2f ms\n", latency.mean / 1000))
    io.write(string.format("Max latency:    %.2f ms\n", latency.max / 1000))
    io.write(string.format("P99 latency:    %.2f ms\n", latency:percentile(99) / 1000))
    io.write("------------------------------\n")
end
```

---

## 常用命令模板

```bash
# GET 压测（带详细延迟分布）
wrk -t4 -c100 -d30s --latency http://localhost:8080/api/orders

# POST 压测
wrk -t4 -c100 -d30s -s post.lua http://localhost:8080/api/orders

# 带 Token 的 GET 压测
wrk -t4 -c100 -d30s \
  -H "Authorization: Bearer <token>" \
  --latency \
  http://localhost:8080/api/orders

# 高并发探测极限
wrk -t8 -c1000 -d60s --latency --timeout 10s http://localhost:8080/api/orders

# 低并发长时间稳定性测试
wrk -t2 -c20 -d300s --latency http://localhost:8080/api/orders
```

---

## wrk vs wrk2：协调遗漏修正

### 什么是协调遗漏（Coordinated Omission）

wrk 使用"闭环"模型：发送请求 → 等待响应 → 发送下一个请求。当服务变慢时，wrk 自动降低发送速率。

```
正常：请求1(10ms) → 请求2(10ms) → 请求3(10ms)    每秒 ~100 请求
变慢：请求1(10ms) → 请求2(500ms) → 请求3(10ms)   每秒 ~2 请求
```

问题在于：当请求 2 耗时 500ms 时，wrk 认为这段时间只有 1 个慢请求。但对真实用户来说，在这 500ms 内本应到达的其他请求也在等待。wrk 的延迟统计低估了真实延迟。

### wrk2 的改进

wrk2 使用"开环"模型：以固定速率（`-R` 参数）发送请求，不管上一个请求是否返回。

```bash
# wrk2 安装
git clone https://github.com/giltene/wrk2.git
cd wrk2
make
sudo cp wrk /usr/local/bin/wrk2

# wrk2 使用（-R 指定目标 QPS）
wrk2 -t4 -c100 -d30s -R 5000 --latency http://localhost:8080/api/orders
```

| 特性 | wrk | wrk2 |
|------|-----|------|
| 请求模型 | 闭环（响应驱动） | 开环（固定速率） |
| 延迟统计 | 可能低估（协调遗漏） | 更接近真实用户体验 |
| 速率控制 | 尽可能快 | `-R` 指定目标 QPS |
| 适用场景 | 探测极限 QPS | 验证固定负载下的延迟 |

### 何时用哪个

- **"这个接口最多能扛多少 QPS？"** → 用 wrk
- **"在 5000 QPS 下，P99 延迟是多少？"** → 用 wrk2
- **"我的 SLO 是 P99 < 200ms，当前能否满足？"** → 用 wrk2

---

## 实战注意事项

1. **压测前确认环境**：不要压生产环境；测试环境的配置要和生产环境一致
2. **预热**：第一轮压测结果不要采信，JVM/连接池需要预热
3. **逐步加压**：从低并发开始，逐步增加，观察拐点
4. **关注客户端瓶颈**：如果压测机 CPU 跑满，瓶颈可能在压测端而非服务端
5. **配合监控**：压测时打开 Grafana Dashboard，同时观察 CPU/内存/GC/连接池

---

## 小结

```
wrk 使用要点
├── 基本命令：wrk -t线程 -c连接 -d时长 URL
├── 核心输出：Latency 分布 + Req/Sec + Socket errors
├── Lua 脚本：POST 请求、自定义 Header、动态参数
├── wrk vs wrk2：闭环 vs 开环，协调遗漏修正
└── 定位：快速验证单接口性能，不适合复杂场景
```

wrk 适合快速验证单个接口的性能基线。当你需要模拟更复杂的用户行为（多步骤流程、条件分支、阶梯加压）时，请使用 Locust —— 这是下一节的内容。
