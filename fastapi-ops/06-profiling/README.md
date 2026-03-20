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

```bash
pip install memray

# 采集内存分配
memray run -o output.bin python app.py

# 生成火焰图
memray flamegraph output.bin

# 生成表格报告
memray table output.bin
```

### 内存泄漏排查思路

```
1. 观察 RSS 增长：python -c "import psutil; ..."
2. 确认是泄漏还是缓存（重启后恢复 = 泄漏；业务增长 = 正常）
3. memray 采集两个时间点的内存快照，对比差异
4. 常见原因：
   - 全局列表/字典不断 append（事件监听器、缓存未设 TTL）
   - 循环引用（Python GC 能处理，但有延迟）
   - C 扩展库的内存泄漏（memray 可见）
```

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
