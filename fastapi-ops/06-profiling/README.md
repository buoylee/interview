# 06 — 性能剖析（Profiling）

## 目标

CPU 占满或接口慢，能在生产环境拿到火焰图，精确定位是哪个函数消耗了资源。

## 工具选择

| 工具 | 原理 | 生产可用 | 适合场景 |
|------|------|---------|---------|
| `cProfile` | 确定性剖析（侵入每个函数调用） | 否（性能损耗大） | 开发/测试环境 |
| `py-spy` | 采样式剖析（外部进程读内存） | **是** | 生产 CPU 分析 |
| `memray` | 内存分配追踪 | 谨慎 | 内存泄漏/高内存 |
| `aiomonitor` | asyncio 运行时监控 | 是 | 协程卡死/慢协程 |

## py-spy：生产环境 CPU 分析

### 核心优势
- 不需要修改代码（外部进程采样）
- 性能开销 < 1%（采样式）
- 支持 GIL 锁持有分析

### 基本用法

```bash
# 安装
pip install py-spy

# 实时 top（类似 htop，但按函数）
py-spy top --pid 12345

# 生成火焰图（30秒采样）
py-spy record -o flame.svg --pid 12345 --duration 30

# 在压测期间采样（更有代表性）
py-spy record -o flame.svg --pid 12345 --duration 60 --rate 100
```

### 在容器中使用

```bash
# 需要 SYS_PTRACE 权限
docker run --cap-add SYS_PTRACE ...

# 或者在容器内安装 py-spy，对同容器进程 attach
docker exec -it container_name py-spy top --pid 1
```

### 火焰图阅读方法

```
宽度 = 函数占用 CPU 时间比例（越宽越值得优化）
高度 = 调用栈深度
颜色 = 没有特殊含义（随机区分）

找热点：找最宽的平顶山（没有子调用的宽函数）
```

## cProfile：开发环境详细分析

```python
import cProfile
import pstats
import io

def profile_func(func, *args, **kwargs):
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # 前 20 个最耗时函数
    print(s.getvalue())
    return result
```

### 配合 snakeviz 可视化

```bash
pip install snakeviz
python -m cProfile -o output.prof your_script.py
snakeviz output.prof
```

### FastAPI 中临时开启剖析

```python
from fastapi import Request
import cProfile, pstats, io

@app.middleware("http")
async def profiling_middleware(request: Request, call_next):
    if request.headers.get("X-Profile") == "1":
        pr = cProfile.Profile()
        pr.enable()
        response = await call_next(request)
        pr.disable()
        # 输出到日志或文件
        return response
    return await call_next(request)
```

## memray：内存分析

开发/测试环境可由 Memray 启动目标程序：

```bash
pip install memray

# 采集内存分配
memray run -o output.bin app.py

# 以 module 方式启动 ASGI server
memray run -o uvicorn.bin -m uvicorn main:app

# 生成火焰图
memray flamegraph output.bin

# 生成表格报告
memray table output.bin
```

首选在 staging 用相同镜像与负载复现。只有问题无法复现、又必须取得生产证据时，才执行 break-glass 诊断：先从负载均衡摘除一个可随时销毁的 replica，确认没有用户流量后，再对其中的目标 PID 做限时 attach；不要 attach 仍在服务用户流量的 worker。

```bash
# 只记录 attach 之后发生的 allocation
memray attach --output output.bin --duration 60 <pid>

# C/C++ stack 也需要时才开启；额外 overhead 更高
memray attach --native --output native.bin --duration 60 <pid>
```

带 `--output` 的 attach 注入 tracker 后会立即返回，目标进程仍在后台采集。另等 `--duration` 完整结束并确认 capture file 已关闭后，再运行 reporter：

```bash
# 默认报告：采集窗口内的 peak allocation
memray flamegraph -o peak-flamegraph.html output.bin
memray table -o peak-table.html output.bin

# 泄漏视图：采集结束时仍未释放的 allocation
memray flamegraph --leaks -o leaks-flamegraph.html output.bin
memray table --leaks -o leaks-table.html output.bin
```

`--leaks` 也可能把 pymalloc 保留的 arena 误判成对象泄漏。若必须追踪小 Python 对象，在**已 drain 的可丢弃 replica** 上给 attach 加 `--trace-python-allocators`；它会显著增加 overhead 与 capture size。开发环境也可在启动前设置 `PYTHONMALLOC=malloc`，但不要在 production 服务上为了 profiling 改 allocator 行为。

`memray attach --method auto` 的注入机制取决于 Python/Memray 版本：Python 3.14 可选择 `sys.remote_exec`，其他环境通常使用 gdb/lldb；后两者还要求镜像内有对应 debugger binary。注入方式不会绕过 OS 的跨进程权限检查：Linux container 通常仍需 `CAP_SYS_PTRACE` 或等价权限，并受 `ptrace_scope` 等策略限制。只给已 drain 的诊断 replica 临时授权，不要给所有 production Pod 永久添加该 capability。先用相同镜像在 staging 验证 method、权限与版本兼容性；attach 会向运行中解释器注入代码，失败时可能 crash 或 deadlock，所以目标必须已 drain 且可立即替换。详细限制见 [Memray attach 官方文档](https://bloomberg.github.io/memray/attach.html)。

### 内存泄漏排查思路

```
1. 从 Prometheus 确认 RSS/working set 是否持续增长，并对照流量、worker 数、缓存 warm-up
2. 选定异常 Pod 与 PID；重启后恢复不能区分泄漏、缓存或 allocator fragmentation
3. Python allocation 可疑时先做 tracemalloc diff；RSS 与 tracemalloc 不一致时，短时 `memray attach`
4. 先用默认 report 看 peak，再用 `--leaks` 看结束时仍存活的 allocation；结合 pymalloc caveat 解读
5. 常见原因：
   - 全局列表/字典不断 append（事件监听器、缓存未设 TTL）
   - 循环引用（Python GC 能处理，但有延迟）
   - C 扩展或 native allocator 增长（需要定位到 C/C++ frame 时加 `--native`）
```

完整的 RSS ↔ tracemalloc 判断树和受控诊断边界见 [`performance-tuning-roadmap/06a-python-profiling/02-python-memory-analysis`](../../performance-tuning-roadmap/06a-python-profiling/02-python-memory-analysis.md)。

## asyncio 专项：慢协程检测

### aiomonitor

```bash
pip install aiomonitor
```

```python
import aiomonitor

async def main():
    with aiomonitor.start_monitor(loop=asyncio.get_event_loop()):
        # 通过 telnet localhost 50101 连接，查看协程状态
        await app_main()
```

### 检测阻塞协程（事件循环卡死）

```python
import asyncio
import time

async def monitor_event_loop(threshold_ms=100):
    """检测事件循环卡顿超过阈值的情况"""
    while True:
        start = time.monotonic()
        await asyncio.sleep(0.01)
        elapsed = (time.monotonic() - start) * 1000
        if elapsed > threshold_ms:
            log.warning(
                "event_loop_blocked",
                elapsed_ms=elapsed,
                # 这里可以 dump 当前协程栈
            )
```

### 常见阻塞陷阱

```python
# 错误：在协程里做同步 I/O
async def bad_handler():
    data = open("file.txt").read()    # 阻塞整个事件循环！
    result = requests.get(url)        # 阻塞！

# 正确：用 asyncio 的异步版本
async def good_handler():
    async with aiofiles.open("file.txt") as f:
        data = await f.read()
    async with httpx.AsyncClient() as client:
        result = await client.get(url)

# 正确：CPU 密集型用线程池
async def cpu_intensive_handler():
    result = await asyncio.get_event_loop().run_in_executor(
        None,  # 默认线程池
        heavy_computation,
        input_data
    )
```

## 实践任务

- [ ] 对运行中的 FastAPI 进程用 py-spy 生成火焰图
- [ ] 人为制造一个 N+1 查询，在火焰图中识别它
- [ ] 在协程中插入同步阻塞调用，用事件循环监控检测到它
- [ ] 用 memray 追踪一次内存分配，找到分配最多的代码路径

## 关键问题

1. 为什么 `cProfile` 不能在生产使用，而 `py-spy` 可以？
2. 火焰图的"平顶"意味着什么？为什么这是优化目标？
3. asyncio 事件循环被阻塞，表现是什么？用什么工具检测？
4. Python 有 GC，为什么还会发生内存泄漏？
