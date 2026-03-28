# Python 基准测试

## 概述

基准测试（Benchmark）是验证性能优化效果的关键手段。没有基准测试，你不知道优化是否真的有效，也无法防止性能回退。但 Python 基准测试有很多陷阱，随手写个 `time.time()` 前后相减的做法是不可靠的。本文介绍正确的基准测试方法。

## 1. timeit — 标准库的微基准测试

`timeit` 是 Python 标准库提供的微基准测试工具，它自动处理了很多常见陷阱（多次运行、禁用 GC 等）。

### 命令行用法

```bash
# 基本用法：测试列表推导 vs map
python -m timeit "[x**2 for x in range(1000)]"
# 输出: 10000 loops, best of 5: 89.3 usec per loop

python -m timeit "list(map(lambda x: x**2, range(1000)))"
# 输出: 5000 loops, best of 5: 120.1 usec per loop

# -s 参数指定 setup 代码（只执行一次）
python -m timeit -s "import json; data = '{\"key\": \"value\"}'" "json.loads(data)"

# -n 指定每次测量的执行次数，-r 指定重复测量次数
python -m timeit -n 10000 -r 5 "sorted(range(100))"
```

### 代码中使用

```python
import timeit

# 测试两种字符串拼接方式
setup = "parts = [str(i) for i in range(1000)]"

# 方式 1: join
t1 = timeit.timeit("''.join(parts)", setup=setup, number=10000)

# 方式 2: += 循环
code2 = """
result = ''
for p in parts:
    result += p
"""
t2 = timeit.timeit(code2, setup=setup, number=10000)

print(f"join: {t1:.4f}s")    # join: 0.3456s
print(f"+=:   {t2:.4f}s")    # +=:   1.2345s
print(f"join 快 {t2/t1:.1f}x")  # join 快 3.6x
```

### 为什么不能用 time.time() 做基准测试

```python
import time

# 错误做法
start = time.time()
result = my_function()
end = time.time()
print(f"耗时: {end - start:.4f}s")
```

问题：
1. **精度不够**：`time.time()` 精度受系统时钟影响，可能只有毫秒级。应该用 `time.perf_counter()`。
2. **单次测量不可靠**：受系统负载、GC、CPU 调频等因素影响，单次结果方差很大。
3. **没有预热**：第一次运行可能因为 import 缓存、JIT 等原因偏慢。
4. **没有统计分析**：无法得到标准差、置信区间等。

## 2. pytest-benchmark — 集成到测试框架

pytest-benchmark 是最实用的基准测试工具，它集成到 pytest 中，提供丰富的统计分析和对比功能。

### 基本用法

```python
# test_perf.py
import json

def test_json_serialization(benchmark):
    data = {"users": [{"name": f"user_{i}", "age": i} for i in range(100)]}
    # benchmark fixture 自动多次运行并统计
    result = benchmark(json.dumps, data)
    assert isinstance(result, str)

def test_json_with_sort_keys(benchmark):
    data = {"users": [{"name": f"user_{i}", "age": i} for i in range(100)]}
    result = benchmark(json.dumps, data, sort_keys=True)
    assert isinstance(result, str)
```

```bash
# 运行基准测试
pytest test_perf.py --benchmark-only
```

### 输出解读

```
------------------------------ benchmark: 2 tests ------------------------------
Name (time in us)                  Min       Max      Mean   StdDev  Median     Rounds  Iterations
-----------------------------------------------------------------------------------------------
test_json_serialization        45.123    89.456   48.234    3.456   47.123     10000         1
test_json_with_sort_keys       52.345   102.789   55.678    4.567   54.234      8000         1
-----------------------------------------------------------------------------------------------
```

关键指标：
- **Min**: 最小耗时 — 最接近理论性能
- **Max**: 最大耗时 — 受 GC、系统调度等干扰
- **Mean**: 平均耗时
- **StdDev**: 标准差 — 衡量稳定性，越小越好
- **Median**: 中位数 — 比 Mean 更抗异常值干扰
- **Rounds**: 总共运行了多少轮
- **Iterations**: 每轮内的迭代次数

### 对比基准

```bash
# 保存基准结果
pytest test_perf.py --benchmark-only --benchmark-save=before_optimization

# ... 做优化 ...

# 再次运行并对比
pytest test_perf.py --benchmark-only --benchmark-compare=0001_before_optimization
```

对比输出会标注每个测试的性能变化百分比，红色表示回退，绿色表示提升。

### pedantic 模式 — 更精确的测量

```python
def test_critical_path(benchmark):
    data = prepare_data()
    benchmark.pedantic(
        process_data,
        args=(data,),
        iterations=100,     # 每轮内迭代次数
        rounds=50,          # 总轮数
        warmup_rounds=5,    # 预热轮数（不计入统计）
    )
```

## 3. line_profiler — 逐行耗时分析

当你知道瓶颈在某个函数内部，但不确定具体是哪一行时，line_profiler 提供逐行级别的耗时分析。

```python
# slow_function.py
@profile  # line_profiler 的标记装饰器
def process_orders(orders):
    results = []
    for order in orders:
        validated = validate_order(order)
        enriched = enrich_with_user_data(validated)
        price = calculate_price(enriched)
        results.append({"order": enriched, "price": price})
    return results
```

运行：

```bash
# 安装
pip install line_profiler

# 使用 kernprof 运行
kernprof -l -v slow_function.py
```

输出：

```
Total time: 5.23456 s
File: slow_function.py
Function: process_orders at line 2

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
     2                                           @profile
     3                                           def process_orders(orders):
     4         1          2.0      2.0      0.0      results = []
     5      1000       1234.0      1.2      0.0      for order in orders:
     6      1000     234567.0    234.6      4.5          validated = validate_order(order)
     7      1000    4567890.0   4567.9     87.3          enriched = enrich_with_user_data(validated)
     8      1000     398765.0    398.8      7.6          price = calculate_price(enriched)
     9      1000      32100.0     32.1      0.6          results.append(...)
    10         1          1.0      1.0      0.0      return results
```

一目了然：`enrich_with_user_data` 占了 87.3% 的时间，这就是优化目标。

## 4. 基准测试的常见陷阱

### 陷阱 1: Import 缓存

```python
# 第一次运行
import heavy_module  # 300ms（需要编译 .pyc）
# 第二次运行
import heavy_module  # 0.1ms（从 __pycache__ 加载）
```

解决：确保基准测试的 setup 阶段完成所有 import。

### 陷阱 2: GC 干扰

```python
import gc
import timeit

# GC 可能在测量期间触发，导致结果偏高
# timeit 默认会临时禁用 GC
t = timeit.timeit("create_objects()", setup="...", number=10000)

# 如果要测试包含 GC 的真实场景，显式启用
t = timeit.timeit("create_objects()", setup="gc.enable(); ...", number=10000)
```

### 陷阱 3: CPU 频率缩放

现代 CPU 有动态频率调节。基准测试前可以固定 CPU 频率：

```bash
# Linux: 设置 performance 模式
sudo cpupower frequency-set -g performance

# macOS: 无法直接控制，但可以多次运行取最小值
```

### 陷阱 4: PyPy JIT Warmup

```python
# PyPy 的 JIT 需要预热，前几千次调用是解释执行
# 必须设置足够的 warmup rounds
benchmark.pedantic(func, warmup_rounds=10, rounds=100)
```

### 陷阱 5: 测量无意义的微操作

```python
# 这种测试没有意义
timeit.timeit("x = 1 + 1", number=10000000)

# 应该测量真实的业务场景
timeit.timeit("process_request(mock_data)", setup="...", number=1000)
```

## 5. 如何写有意义的 Benchmark

### 原则 1: 测试真实场景

```python
def test_api_serialization(benchmark):
    """测试 API 响应序列化的真实场景"""
    # 使用接近真实的数据量和数据结构
    orders = generate_realistic_orders(count=100)
    benchmark(serialize_order_response, orders)
```

### 原则 2: 控制变量

```python
def test_dict_vs_dataclass(benchmark):
    """只改变数据结构，其他不变"""
    data = load_test_data()

    # A/B 测试：只改变一个因素
    # test_a: 使用 dict
    # test_b: 使用 dataclass
    benchmark(process_with_dict, data)
```

### 原则 3: 记录环境信息

```python
# conftest.py
def pytest_benchmark_generate_machine_info():
    """记录测试环境，确保对比时环境一致"""
    return {
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "os": platform.platform(),
    }
```

### 原则 4: 集成到 CI

```bash
# CI 中运行基准测试并检查性能回退
pytest tests/benchmarks/ \
    --benchmark-only \
    --benchmark-compare=baseline \
    --benchmark-compare-fail=mean:10%  # 平均值回退超过 10% 则失败
```

## 小结

| 工具 | 用途 | 粒度 |
|------|------|------|
| timeit | 快速比较两种实现 | 表达式/语句 |
| pytest-benchmark | 系统化的基准测试 | 函数 |
| line_profiler | 定位函数内的耗时行 | 行 |

工作流程：
1. 用 pytest-benchmark 建立基线
2. 用 profiler 找到热点函数
3. 用 line_profiler 定位到具体行
4. 优化后用 pytest-benchmark --benchmark-compare 验证效果
5. 将基准测试集成到 CI 防止性能回退
