# Python 常见性能反模式

## 概述

很多 Python 性能问题不是算法层面的，而是语言使用习惯层面的。本文列举后端开发中最常见的性能反模式，每个都给出反模式代码和正确的替代方案，并解释为什么慢。

## 1. 字符串拼接：循环中 += 的二次方复杂度

### 反模式

```python
def build_report(items):
    result = ""
    for item in items:
        result += f"Item: {item['name']}, Price: {item['price']}\n"  # O(n) 每次
    return result
# 总时间复杂度: O(n^2)，因为字符串不可变，每次 += 都创建新字符串并复制
```

### 正确做法

```python
def build_report(items):
    parts = []
    for item in items:
        parts.append(f"Item: {item['name']}, Price: {item['price']}")
    return "\n".join(parts)
# 总时间复杂度: O(n)
```

实际测量差异：

```bash
# 10000 个元素
python -m timeit -s "items = [{'name': f'item_{i}', 'price': i} for i in range(10000)]" \
  "result = ''; [result := result + f'Item: {x[\"name\"]}\n' for x in items]"
# 约 15ms

python -m timeit -s "items = [{'name': f'item_{i}', 'price': i} for i in range(10000)]" \
  "'\n'.join(f'Item: {x[\"name\"]}' for x in items)"
# 约 3ms
```

元素越多，差距越大。100000 个元素时差距会达到 100x 以上。

注意：CPython 有一个对 `s += t` 的优化（如果 s 的引用计数为 1 则原地扩展），但这个优化不可靠，不应该依赖它。

## 2. 列表推导 vs 生成器：内存差异

### 反模式

```python
# 一次性创建整个列表，占用大量内存
def process_large_file(filename):
    lines = [line.strip() for line in open(filename)]  # 全部加载到内存
    filtered = [line for line in lines if line.startswith("ERROR")]
    return len(filtered)
```

### 正确做法

```python
# 使用生成器，按需处理，内存占用恒定
def process_large_file(filename):
    with open(filename) as f:
        count = sum(1 for line in f if line.strip().startswith("ERROR"))
    return count
```

### itertools 工具库

```python
from itertools import islice, chain, groupby

# islice: 取前 N 个元素，不加载整个序列
first_100 = list(islice(large_generator(), 100))

# chain: 串联多个迭代器，不创建中间列表
all_items = chain(generator_a(), generator_b(), generator_c())

# 反模式：创建中间列表
all_items = list(generator_a()) + list(generator_b()) + list(generator_c())
```

### 何时用列表推导

生成器不总是更好。如果你需要**多次遍历**或**随机访问**结果，列表更合适：

```python
# 需要多次遍历 → 用列表
items = [transform(x) for x in data]
result_a = [x for x in items if x.type == 'A']
result_b = [x for x in items if x.type == 'B']

# 只遍历一次 → 用生成器
total = sum(x.price for x in orders)
```

## 3. 不必要的 dict/list 创建

### 反模式

```python
# 不需要的列表推导 —— 直接传生成器表达式
total = sum([x.price for x in orders])       # 创建临时列表
max_val = max([len(s) for s in strings])     # 创建临时列表
any_match = any([x > 100 for x in values])   # any 短路但列表已经全部求值

# 不需要的 try/except
def safe_get(d, key):
    try:
        return d[key]
    except KeyError:
        return None
```

### 正确做法

```python
# 去掉方括号，变成生成器表达式
total = sum(x.price for x in orders)         # 无临时列表
max_val = max(len(s) for s in strings)       # 按需计算
any_match = any(x > 100 for x in values)     # 找到第一个就停止

# 使用 dict.get
def safe_get(d, key):
    return d.get(key)  # 更快，无异常开销
```

`any()` 和 `all()` 配合生成器表达式可以短路求值 —— 找到第一个满足条件的元素就立即返回，不需要遍历全部。但如果传入的是列表推导，则必须先计算整个列表。

## 4. 深拷贝滥用

### 反模式

```python
import copy

def process_config(config):
    # 每次都深拷贝整个配置对象，递归复制所有嵌套结构
    local_config = copy.deepcopy(config)
    local_config['timeout'] = 30
    return do_work(local_config)
```

`copy.deepcopy` 的开销：
- 递归遍历所有嵌套对象
- 维护一个 memo 字典防止循环引用
- 调用每个对象的 `__deepcopy__` 或 `__copy__` 方法

### 正确做法

```python
# 如果只修改顶层 key，浅拷贝就够了
def process_config(config):
    local_config = {**config, 'timeout': 30}  # 浅拷贝 + 覆盖
    return do_work(local_config)

# 如果需要修改嵌套结构的某个分支，只拷贝那个分支
def process_config(config):
    local_config = config.copy()  # 浅拷贝
    local_config['database'] = {**config['database'], 'pool_size': 20}
    return do_work(local_config)

# 或者使用不可变数据结构，从根本上避免拷贝问题
from types import MappingProxyType
immutable_config = MappingProxyType(config)
```

## 5. 全局变量滥用与 import 开销

### 模块级代码在 import 时执行

```python
# config.py
import requests

# 这行在 import config 时就执行，如果服务不可达会阻塞或报错
REMOTE_CONFIG = requests.get("http://config-service/config").json()

# 更好的做法：延迟加载
_config_cache = None

def get_remote_config():
    global _config_cache
    if _config_cache is None:
        _config_cache = requests.get("http://config-service/config").json()
    return _config_cache
```

### 延迟 import 技巧

```python
# 重型库只在需要时 import，加速启动时间
def generate_pdf(data):
    from weasyprint import HTML  # 延迟 import，weasyprint import 耗时约 500ms
    html = render_template(data)
    return HTML(string=html).write_pdf()

# 条件 import
def serialize(data, format='json'):
    if format == 'msgpack':
        import msgpack  # 只在需要 msgpack 时才 import
        return msgpack.packb(data)
    import json
    return json.dumps(data)
```

### 循环 import 的性能影响

循环 import 本身不一定导致错误（Python 的 import 系统有处理机制），但会导致：
- 模块部分初始化状态被使用
- import 顺序依赖问题
- 不可预测的 `AttributeError`

解决：重构模块结构，提取公共依赖到独立模块。

## 6. 属性访问开销

### 反模式

```python
import math

def compute_distances(points):
    results = []
    for p in points:
        # 每次循环都做 3 次属性查找: math.sqrt, p.x, p.y
        dist = math.sqrt(p.x ** 2 + p.y ** 2)
        results.append(dist)
    return results
```

Python 的属性访问涉及字典查找（`__dict__`）。在热路径上，频繁的属性查找可以通过局部变量缓存来优化。

### 正确做法

```python
def compute_distances(points):
    # 将频繁访问的属性缓存到局部变量
    sqrt = math.sqrt
    results = []
    append = results.append
    for p in points:
        append(sqrt(p.x ** 2 + p.y ** 2))
    return results

# 实测：约 15-20% 的性能提升（大量迭代时）
```

这个优化看起来很丑，只在**真正的热路径**上有意义。不要到处这么写，可读性更重要。

## 7. C 扩展与 Cython

当纯 Python 优化已经到极限时，可以考虑用 C 扩展加速关键路径。

### 何时值得用 C 扩展

- profiling 确认瓶颈在纯 Python 计算（不是 I/O）
- 优化后的 Python 代码仍不够快
- 该代码路径被高频调用

### Cython 基本用法

```cython
# distance.pyx
import cython

@cython.boundscheck(False)
@cython.wraparound(False)
def compute_distances(double[:, :] points):
    cdef int n = points.shape[0]
    cdef double[:] result = np.empty(n)
    cdef int i
    cdef double x, y

    for i in range(n):
        x = points[i, 0]
        y = points[i, 1]
        result[i] = (x * x + y * y) ** 0.5

    return np.asarray(result)
```

```python
# setup.py
from setuptools import setup
from Cython.Build import cythonize

setup(ext_modules=cythonize("distance.pyx"))
```

```bash
python setup.py build_ext --inplace
```

### ctypes / cffi — 调用现有 C 库

```python
# ctypes: 标准库，调用 .so/.dll
import ctypes
lib = ctypes.CDLL("./libfast.so")
lib.compute.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int]
lib.compute.restype = ctypes.c_double
result = lib.compute(data_ptr, len(data))

# cffi: 更 Pythonic 的 C FFI
from cffi import FFI
ffi = FFI()
ffi.cdef("double compute(double* data, int n);")
lib = ffi.dlopen("./libfast.so")
result = lib.compute(ffi.cast("double*", data_ptr), len(data))
```

**优先级建议**：先用 numpy/pandas 向量化 → 再考虑 Cython → 最后才写 C 扩展。大部分后端场景的瓶颈在 I/O 和数据库，不在计算。

## 小结

| 反模式 | 影响 | 修复 |
|--------|------|------|
| 循环中 `+=` 字符串 | O(n^2) 时间 | `''.join()` |
| 列表推导传给 sum/any/all | 额外内存分配 | 生成器表达式 |
| 滥用 deepcopy | 递归复制开销 | 浅拷贝或不可变数据 |
| 模块级执行重逻辑 | import 慢、启动慢 | 延迟加载 |
| 热路径属性查找链 | 字典查找开销 | 局部变量缓存 |
| 纯 Python 数值计算 | 解释器开销 | numpy 向量化或 Cython |

性能优化的原则：先 profiling 找到瓶颈，再针对性优化。不要在没有 profiling 数据的情况下做"预防性优化"，那往往是浪费时间。
