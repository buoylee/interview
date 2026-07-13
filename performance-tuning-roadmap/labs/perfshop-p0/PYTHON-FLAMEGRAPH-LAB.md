# Python `py-spy` 火焰图实验

> 目标：在同一个 PerfShop Python 服务上制造 CPU hotspot，用 `py-spy` 生成 hotspot/reset 两张火焰图，并用相同负载比较 QPS、P99 与 top 3 热点。

本实验是**故障 on/off 的诊断验证**。Reset 只是关闭故障注入，不代表完成了真实代码优化。

## 1. 前置条件

- Docker 与 Docker Compose
- `curl`
- host 已安装 `wrk`
- 当前目录为 `performance-tuning-roadmap/labs/perfshop-p0`

确认 `wrk`：

```bash
wrk --version
```

`py-spy` 会读取目标进程内存。实验通过独立 Compose override 仅为 App 增加 `SYS_PTRACE`；不要改成 `privileged`，不要把这份 override 用于生产环境。

## 2. 启动 profiling 环境

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  up --build -d
```

检查 App 与 profiler：

```bash
curl http://127.0.0.1:8080/health
docker exec perfshop-p0-app py-spy --version
```

预期版本：

```text
py-spy 0.4.2
```

## 3. 第一轮：CPU hotspot

### 3.1 开启故障

90 秒窗口为切换两个 Terminal 留出余量：

```bash
curl -X POST 'http://127.0.0.1:8080/chaos/cpu?duration=90'
```

预期响应包含：

```json
{"cpu_hotspot_enabled_seconds": 90}
```

### 3.2 Terminal A：执行固定负载

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

记录输出中的 `Requests/sec` 与 99% latency。

### 3.3 Terminal B：同时采样 30 秒

Terminal A 开始后立即执行：

```bash
docker exec perfshop-p0-app py-spy record \
  --pid 1 \
  --duration 30 \
  --rate 100 \
  --format flamegraph \
  -o /artifacts/profiling/cpu-hotspot.svg
```

检查产物：

```bash
test -s artifacts/profiling/cpu-hotspot.svg
rg -n 'burn_cpu_if_enabled' artifacts/profiling/cpu-hotspot.svg
```

预期：SVG 非空，并包含 `burn_cpu_if_enabled`。

## 4. 第二轮：CPU reset

先关闭所有 chaos：

```bash
curl -X POST http://127.0.0.1:8080/chaos/reset
```

预期响应包含：

```json
{"status": "reset"}
```

Terminal A 使用**完全相同**的负载：

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

Terminal B 同时采样，只有输出文件名不同：

```bash
docker exec perfshop-p0-app py-spy record \
  --pid 1 \
  --duration 30 \
  --rate 100 \
  --format flamegraph \
  -o /artifacts/profiling/cpu-reset.svg
```

检查产物：

```bash
test -s artifacts/profiling/cpu-reset.svg
```

`burn_cpu_if_enabled` 仍可能因为快速 guard return 出现在 reset 样本中；正确预期是 frame 明显缩窄，不是必须完全消失。

## 5. 阅读与比较

- X 轴宽度：函数出现在样本中的比例，不是时间轴。
- Y 轴：调用栈深度。
- 顶部宽 frame：直接消耗 CPU 的热点。
- 搜索 `burn_cpu_if_enabled`，沿下方 frame 还原调用路径。

填写结果：

| 轮次 | QPS | P99 | top 1 | top 2 | top 3 |
|---|---:|---:|---|---|---|
| CPU hotspot |  |  |  |  |  |
| CPU reset |  |  |  |  |  |

回答：

1. 哪条 stack path 直接支持 CPU hotspot 假设？
2. Reset 后，`burn_cpu_if_enabled` frame、QPS、P99 如何变化？
3. 这组证据能证明什么？不能证明什么？

预期结论：hotspot 图中 `burn_cpu_if_enabled` 与 busy loop 占据明显宽度；reset 后该路径缩窄，QPS 上升、P99 下降。具体数值依硬件而异，不设固定通过门槛。

## 6. 常见问题

### `Permission denied`

确认启动时同时使用两份 Compose file，并 recreate App：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  up -d --force-recreate app
```

不要用 `privileged` 绕过问题。

### PID 或 executable 错误

确认 App 正常，target 使用 container 内 PID 1：

```bash
curl http://127.0.0.1:8080/health
docker exec perfshop-p0-app py-spy dump --pid 1
```

### SVG 没有预期 hotspot

确认：

- chaos API 返回成功；
- 90 秒窗口尚未结束；
- `wrk` 与 `py-spy record` 同时运行；
- 压测 endpoint 是 `GET /api/products/1`。

### 两轮数据不可比

两轮必须保持相同 endpoint、threads、connections、duration、sample rate 与测试环境。不要一轮执行其他高负载任务。

## 7. 清理

停止本实验启动的服务：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  down
```

SVG 保留在：

```text
artifacts/profiling/cpu-hotspot.svg
artifacts/profiling/cpu-reset.svg
```

这些文件已被 Git ignore，不应提交。
