# Python Profiling 工具

## 概述

性能优化的第一步是找到瓶颈在哪里，而不是凭直觉猜测。Python 生态有多种 profiling 工具，从标准库的 cProfile 到生产级的 py-spy，各有适用场景。本文介绍四种主流工具的用法与选型。

## 1. cProfile — 标准库确定性 Profiler

cProfile 是 CPython 内置的确定性 profiler，它记录每个函数的调用次数和耗时。"确定性"意味着它跟踪每次函数进入和退出，因此结果精确但有约 10-20% 的性能开销。

### 基本用法

最简单的方式是命令行直接运行：

```bash
# 按累计时间排序，显示 profiling 结果
python -m cProfile -s cumtime script.py

# 将结果保存到文件，后续分析
python -m cProfile -o profile.prof script.py
```

输出示例：

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      1    0.000    0.000   12.345   12.345 script.py:1(<module>)
   1000    8.234    0.008   10.100    0.010 script.py:15(process_item)
  50000    1.500    0.000    1.500    0.000 {built-in method json.loads}
   1000    0.366    0.000    0.366    0.000 {method 'execute' of 'cursor'}
```

关键列说明：
- **ncalls**: 调用次数
- **tottime**: 函数自身耗时（不含子函数）
- **cumtime**: 累计耗时（含子函数调用）

### pstats 分析

保存为 `.prof` 文件后，可以用 pstats 模块做更灵活的分析：

```python
import pstats

p = pstats.Stats('profile.prof')
p.sort_stats('cumulative')
p.print_stats(20)  # 显示前 20 个最耗时的函数

# 查看某个函数的调用者
p.print_callers('process_item')

# 查看某个函数调用了谁
p.print_callees('process_item')
```

### snakeviz 可视化

文本输出不直观，snakeviz 提供浏览器交互式可视化：

```bash
pip install snakeviz
snakeviz profile.prof
```

snakeviz 会启动本地 HTTP 服务器，在浏览器中展示 icicle 图或 sunburst 图，可以点击放大特定函数，直观看到时间分布。

### cProfile 的局限

- **开销较大**：确定性跟踪每次函数调用，对高频调用的代码影响显著
- **无法 attach**：必须从启动时就开启，不能对运行中的进程做 profiling
- **不适合生产环境**：性能开销太大

## 2. py-spy — 采样 Profiler（生产环境首选）

py-spy 是用 Rust 编写的采样 profiler，通过定时读取目标进程的调用栈来收集数据。它不修改目标进程的代码，不注入任何东西，因此几乎零开销。

### 核心优势

- **无需修改代码**：不需要 import 任何库
- **可以 attach 到运行中进程**：生产环境排查的关键能力
- **极低开销**：采样方式，对目标进程几乎无影响
- **支持 Docker 容器内进程**

### 三种模式

```bash
# top 模式 — 实时查看最耗时函数，类似 htop
py-spy top --pid 12345
py-spy top -- python app.py

# record 模式 — 录制并生成报告
py-spy record --pid 12345 -o profile.svg
py-spy record -- python app.py -o profile.svg

# dump 模式 — 打印当前所有线程的调用栈快照
py-spy dump --pid 12345
```

### 火焰图生成

py-spy record 默认生成 SVG 格式的火焰图：

```bash
# 生成火焰图，采样 30 秒
py-spy record --format flamegraph --duration 30 \
    -o profile.svg -- python app.py

# 对运行中的进程生成火焰图
py-spy record --format flamegraph --pid 12345 -o profile.svg

# 指定采样频率（默认 100Hz）
py-spy record --rate 200 --pid 12345 -o profile.svg

# 生成 speedscope 格式（可在 speedscope.app 打开）
py-spy record --format speedscope -o profile.json -- python app.py
```

在火焰图中：
- **X 轴**：不是时间轴，是按字母排序的函数名，宽度代表该函数出现在采样中的比例
- **Y 轴**：调用栈深度
- **越宽的函数占用 CPU 越多**

### 生产环境使用

```bash
# Docker 容器中需要 SYS_PTRACE 权限
docker run --cap-add SYS_PTRACE ...

# 也可以在 docker-compose 中配置
# cap_add:
#   - SYS_PTRACE

# 对 Kubernetes Pod 中的进程做 profiling
kubectl exec -it pod-name -- py-spy top --pid 1
```

## 3. Scalene — CPU + 内存 + GPU 三合一 Profiler

Scalene 是一个综合性 profiler，最大特点是能同时分析 CPU、内存和 GPU 使用，并且能区分 Python 代码和 C 扩展代码的开销。

```bash
pip install scalene

# 基本用法
scalene script.py

# 只分析 CPU
scalene --cpu-only script.py

# 指定输出格式
scalene --json --outfile profile.json script.py

# 分析指定模块（忽略其他代码）
scalene --profile-only mymodule script.py
```

Scalene 的输出会逐行标注：
- **Python 时间**：纯 Python 代码的 CPU 时间
- **Native 时间**：C 扩展/系统调用的 CPU 时间
- **内存增长/减少**：每行代码的内存变化

这种区分非常有价值 —— 如果瓶颈在 C 扩展（如 numpy 计算），优化 Python 代码毫无意义。

## 4. 工具选型对比

| 维度 | cProfile | py-spy | Scalene |
|------|----------|--------|---------|
| 类型 | 确定性 | 采样 | 采样+确定性混合 |
| 开销 | 中等(10-20%) | 极低(<1%) | 低(5-10%) |
| Attach 运行中进程 | 不支持 | 支持 | 不支持 |
| 生产环境 | 不推荐 | 推荐 | 不推荐 |
| 内存分析 | 不支持 | 不支持 | 支持 |
| 火焰图 | 需额外工具 | 内置 | 内置 |
| 逐行分析 | 不支持 | 不支持 | 支持 |
| 安装依赖 | 标准库 | 需安装 | 需安装 |

**选型建议**：
- **开发调试阶段**：cProfile + snakeviz 快速定位，或 Scalene 做深入分析
- **生产环境排查**：py-spy（唯一合理选择）
- **需要内存分析**：Scalene 或配合下一节的 tracemalloc

## 5. 实操：用 py-spy 找到 FastAPI 应用的热点函数

假设有一个 FastAPI 应用响应变慢，按以下步骤排查：

```bash
# 1. 找到 uvicorn 进程 PID
ps aux | grep uvicorn
# 输出: user 12345 ... uvicorn main:app

# 2. 先用 top 模式实时观察
py-spy top --pid 12345
```

py-spy top 输出：

```
Total Samples 2000
GIL: 45.00%

  %Own   %Total  OwnTime  TotalTime  Function (filename:line)
 35.20%  35.20%    7.04s     7.04s   process_data (app/services.py:42)
 22.10%  57.30%    4.42s    11.46s   handle_request (app/routes.py:18)
  8.50%   8.50%    1.70s     1.70s   serialize (app/serializers.py:55)
  5.30%   5.30%    1.06s     1.06s   validate (app/validators.py:30)
```

可以清楚看到 `process_data` 函数占了 35% 的 CPU 时间。

```bash
# 3. 录制 30 秒火焰图做详细分析
py-spy record --format flamegraph --duration 30 \
    --pid 12345 -o fastapi_profile.svg

# 4. 用浏览器打开火焰图
open fastapi_profile.svg  # macOS
```

通过火焰图可以看到 `process_data` 内部的调用链，进一步定位到具体是哪个操作最耗时，比如可能是一个嵌套循环或低效的序列化。

## 小结

profiling 的核心原则是**先测量再优化**。不要猜测瓶颈在哪里，用工具说话。开发阶段用 cProfile/Scalene 做精确分析，生产环境用 py-spy 做低开销采样。找到热点函数后，再用下一节的内存分析工具或 line_profiler 做逐行级别的深入排查。
