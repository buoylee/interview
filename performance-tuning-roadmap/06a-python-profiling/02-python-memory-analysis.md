# Python 内存分析

## 概述

内存问题是 Python 后端服务最常见的生产事故之一。进程 RSS 持续增长、OOM Kill、响应变慢 —— 这些现象背后往往是内存泄漏或不当的内存使用。本文介绍 Python 内存分析的核心工具链。

## 1. tracemalloc — 标准库内存追踪

tracemalloc 是 Python 3.4+ 内置的内存分配追踪器，能追踪每个内存分配的来源（文件名和行号）。

### 基本用法

```python
import tracemalloc

# 启动追踪（nframe 指定保留的调用栈深度）
tracemalloc.start(25)

# ... 运行业务代码 ...

# 拍摄内存快照
snapshot = tracemalloc.take_snapshot()

# 按文件统计内存分配 Top 10
top_stats = snapshot.statistics('lineno')
print("[ Top 10 内存分配 ]")
for stat in top_stats[:10]:
    print(stat)
```

输出示例：

```
[ Top 10 内存分配 ]
app/models.py:42: size=25.3 MiB, count=150000, average=177 B
app/cache.py:18: size=12.1 MiB, count=50000, average=254 B
app/utils.py:95: size=8.7 MiB, count=200000, average=46 B
```

### 内存快照对比 — 找出增长源头

单个快照只能看当前状态，真正有用的是**对比两个快照**，找出内存增长最多的位置：

```python
import tracemalloc
import time

tracemalloc.start(25)

# 第一次快照：压测前的稳态
snapshot1 = tracemalloc.take_snapshot()

# 模拟压测或一段时间的业务运行
run_workload()
time.sleep(60)

# 第二次快照
snapshot2 = tracemalloc.take_snapshot()

# 对比两个快照，找出增长最大的位置
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
print("[ 内存增长 Top 10 ]")
for stat in top_stats[:10]:
    print(stat)
```

输出示例：

```
[ 内存增长 Top 10 ]
app/cache.py:18: size=45.2 MiB (+33.1 MiB), count=180000 (+130000), average=263 B
app/handlers.py:67: size=12.8 MiB (+12.8 MiB), count=50000 (+50000), average=268 B
```

可以看到 `cache.py:18` 增长了 33.1 MiB，这就是需要重点排查的位置。

### 按调用栈分组

按 `traceback` 分组可以看到完整的调用链，定位到是谁调用了分配内存的代码：

```python
top_stats = snapshot.statistics('traceback')
# 查看最大分配的完整调用栈
print(top_stats[0].traceback.format())
```

## 2. memory_profiler — 逐行内存增量

memory_profiler 提供函数级和行级的内存分析，适合精确定位哪一行代码导致了内存增长。

### 逐行分析

```python
# pip install memory_profiler
from memory_profiler import profile

@profile
def process_data(filename):
    with open(filename) as f:
        data = f.readlines()         # 读入全部内容
    results = []
    for line in data:
        parsed = parse_line(line)    # 解析每行
        results.append(parsed)
    return results
```

运行 `python -m memory_profiler script.py`，输出：

```
Line #    Mem usage    Increment  Occurrences   Line Contents
=============================================================
     4     45.2 MiB     45.2 MiB           1   @profile
     5                                         def process_data(filename):
     6     45.2 MiB      0.0 MiB           1       with open(filename) as f:
     7    245.8 MiB    200.6 MiB           1           data = f.readlines()
     8    245.8 MiB      0.0 MiB           1       results = []
     9    345.2 MiB     99.4 MiB      100000       for line in data:
    10    345.2 MiB      0.0 MiB      100000           parsed = parse_line(line)
    11    345.2 MiB      0.0 MiB      100000           results.append(parsed)
    12    345.2 MiB      0.0 MiB           1       return results
```

一眼看出第 7 行 `f.readlines()` 一次性读入了 200 MiB 的数据。修复方案：改为逐行处理或使用生成器。

### mprof — 内存时间线

```bash
# 录制内存使用随时间的变化
mprof run python script.py

# 生成可视化图表
mprof plot
```

mprof plot 会生成内存随时间变化的折线图，可以直观看到内存是否在持续增长（泄漏），还是在某个阶段突然飙升。

## 3. objgraph — 对象引用图

objgraph 专注于分析 Python 对象的引用关系，是排查循环引用和内存泄漏的利器。

### 查看最多的对象类型

```python
import objgraph

# 显示数量最多的对象类型
objgraph.show_most_common_types(limit=10)
```

输出：

```
dict                   12345
list                    8901
str                     7654
tuple                   5432
MyModel                 3210   # <- 异常！为什么有这么多 MyModel 实例？
```

### 查看对象增长

```python
# 第一次调用记录基线
objgraph.show_growth(limit=5)

# ... 运行一段业务代码 ...

# 第二次调用显示增长
objgraph.show_growth(limit=5)
```

输出：

```
MyModel         3210     +3200   # 增长了 3200 个，很可能泄漏
dict           12345      +500
list            8901      +200
```

### 查看引用关系 — 排查循环引用

```python
# 找到一个泄漏对象
leaked_obj = objgraph.by_type('MyModel')[0]

# 生成反向引用图（谁引用了这个对象）
objgraph.show_backrefs(
    leaked_obj,
    max_depth=5,
    filename='backrefs.png'  # 需要安装 graphviz
)

# 生成正向引用图（这个对象引用了谁）
objgraph.show_refs(
    leaked_obj,
    max_depth=3,
    filename='refs.png'
)
```

生成的 PNG 图直观展示引用链，可以看到是哪个全局变量、缓存字典或回调函数持有了对象引用，阻止了 GC 回收。

## 4. pympler — 递归计算对象大小

### asizeof — 真实的对象大小

```python
from pympler import asizeof

data = {'key': [1, 2, 3, 'hello', {'nested': True}]}

# asizeof 递归计算，包含所有引用的对象
print(asizeof.asizeof(data))  # 输出: 888 (bytes)
```

### tracker — 跟踪对象数量变化

```python
from pympler import tracker

tr = tracker.SummaryTracker()

# ... 运行一些代码 ...
create_objects()

# 显示自上次调用以来的对象变化
tr.print_diff()
```

输出：

```
                       types |   # objects |   total size
========================== | =========== | ============
                      list |        1234 |    567.8 KB
                      dict |         890 |    345.6 KB
           app.models.User |         500 |    234.5 KB
```

## 5. sys.getsizeof 的陷阱

很多人用 `sys.getsizeof` 来估算对象大小，但这个函数有一个严重的误导性：**它不递归计算**。

```python
import sys

# 一个包含大量数据的列表
data = [{'key': 'value'} for _ in range(10000)]

# sys.getsizeof 只算列表对象本身（指针数组），不算元素
print(sys.getsizeof(data))    # 输出: 87624（只是列表容器的大小）

# pympler.asizeof 递归计算所有内容
from pympler import asizeof
print(asizeof.asizeof(data))  # 输出: 2880448（包含所有 dict 和 str）
```

差距可以超过 30 倍。**永远不要用 `sys.getsizeof` 来估算复杂数据结构的内存占用**，用 `pympler.asizeof` 替代。

同样的陷阱也存在于 dict：

```python
d = {i: 'x' * 1000 for i in range(1000)}
print(sys.getsizeof(d))      # 36960（只是 hash table 本身）
print(asizeof.asizeof(d))    # 1093284（包含所有 key 和 value）
```

## 6. 内存快照对比方法论

生产环境排查内存泄漏的标准流程：

```python
# 在 FastAPI 中暴露内存分析端点（仅限内部使用）
import tracemalloc
from fastapi import FastAPI

app = FastAPI()
tracemalloc.start(25)
_snapshot = None

@app.post("/debug/memory/snapshot")
async def take_snapshot():
    """压测前调用，记录基线"""
    global _snapshot
    _snapshot = tracemalloc.take_snapshot()
    return {"status": "snapshot taken"}

@app.get("/debug/memory/diff")
async def memory_diff():
    """压测后调用，对比增长"""
    if _snapshot is None:
        return {"error": "no baseline snapshot"}
    current = tracemalloc.take_snapshot()
    stats = current.compare_to(_snapshot, 'lineno')
    return {
        "top_allocations": [
            {
                "file": str(stat.traceback),
                "size_mb": stat.size / 1024 / 1024,
                "size_diff_mb": stat.size_diff / 1024 / 1024,
                "count": stat.count,
                "count_diff": stat.count_diff,
            }
            for stat in stats[:20]
        ]
    }
```

操作步骤：

1. 服务启动后等待稳态（处理几十个请求后）
2. 调用 `POST /debug/memory/snapshot` 记录基线
3. 开始压测，发送大量请求
4. 调用 `GET /debug/memory/diff` 查看内存增长
5. 分析结果，找到增长最大的代码位置
6. 结合 objgraph 分析引用关系，确认是否有泄漏

## 小结

| 工具 | 用途 | 适用阶段 |
|------|------|---------|
| tracemalloc | 追踪内存分配来源、快照对比 | 开发/测试 |
| memory_profiler | 逐行内存增量分析 | 开发 |
| objgraph | 对象引用图、排查循环引用 | 开发/排查 |
| pympler.asizeof | 递归计算对象真实大小 | 开发 |
| pympler.tracker | 跟踪对象数量变化 | 开发/测试 |

实际排查中，通常先用 tracemalloc 做快照对比找到可疑位置，再用 objgraph 分析引用关系确认根因。
