# CPython GC 机制

## 概述

理解 CPython 的垃圾回收机制对性能调优至关重要。CPython 使用**引用计数 + 分代 GC** 的混合策略：引用计数处理大部分对象的回收，分代 GC 负责解决引用计数无法处理的循环引用问题。

> 本文是**排查视角**的 GC 速查（工具操作、禁用场景、PyPy 差异）；机制层的系统教学（对象头、pymalloc 与 RSS、GC 生产调优、GIL 与 free-threading）见 [`python/16`](../../python/16-objects-memory-gc-gil.md)。

## 1. 引用计数机制

CPython 中每个对象都有一个 `ob_refcnt` 字段，记录当前有多少个引用指向它。

### 引用计数的增减时机

```python
import sys

a = [1, 2, 3]           # ob_refcnt = 1（变量 a 引用）
print(sys.getrefcount(a))  # 输出 2（getrefcount 本身也会创建一个临时引用）

b = a                    # ob_refcnt = 2（a 和 b 都引用）
c = [a, a]               # ob_refcnt = 4（a, b, c[0], c[1]）

del b                    # ob_refcnt = 3
c.pop()                  # ob_refcnt = 2
```

引用计数增加的场景：
- 赋值给变量：`a = obj`
- 添加到容器：`list.append(obj)`, `dict[key] = obj`
- 作为函数参数传递

引用计数减少的场景：
- `del` 语句删除变量
- 变量离开作用域
- 从容器中移除
- 变量被重新赋值

### 引用计数为 0 立即释放

```python
def process():
    data = [0] * 10_000_000  # 分配 ~80MB 内存
    result = sum(data)
    return result
    # data 离开作用域，引用计数归零，Python 对象立即释放
```

**优点**：对象不再使用时通常立即回收，不需要等待循环 GC。

注意：对象释放只表示内存可被 Python allocator 再利用，不保证 RSS 立即下降。allocator 可能保留 arena，供后续分配复用。

**缺点**：无法处理循环引用。

## 2. 循环引用问题

```python
class Node:
    def __init__(self, name):
        self.name = name
        self.partner = None

# 创建循环引用
a = Node('A')
b = Node('B')
a.partner = b  # a -> b
b.partner = a  # b -> a

del a  # a 的引用计数从 2 降到 1（b.partner 还引用着）
del b  # b 的引用计数从 2 降到 1（a.partner 还引用着）
# 两个对象的引用计数都是 1，不会靠引用计数降到 0
# 它们是 cyclic garbage，等待循环 GC 识别并回收
```

这种情况需要分代 GC 来处理。

## 3. 分代垃圾回收

CPython 的分代 GC 专门用于检测和回收循环引用。

### 分代设计（版本敏感）

```python
import gc

# 查看当前 GC trigger counters 和阈值
print(gc.get_count())      # 例如: (687, 8, 2)
print(gc.get_threshold())  # 实际值取决于 Python 版本与运行时配置
```

- **第 0 代 (gen0)**：新创建的对象；净分配计数超过当前 `threshold0` 后触发检查。
- **第 1 代 (gen1)**：在较年轻代 collection 中存活的对象。
- **第 2 代 (gen2)**：长期存活对象所在的最老一代。

上述三代描述适用于 CPython 3.13 与 3.14.5+；3.14.0–3.14.4 曾移除 gen1 并忽略 `threshold2`，之后的 3.14 patch release 又恢复。promotion 与 threshold 行为可能随版本变化；排查时记录完整 Python 版本，以对应版本文档为准，不要把示例数值当成固定契约。

版本对应行为见 [Python `gc` 官方文档](https://docs.python.org/3/library/gc.html)。

**核心思想**：大部分对象生命周期很短（"朝生暮死"），只需要频繁扫描新生代。长期存活的对象被提升到老年代，减少扫描频率。

### GC 的工作原理

分代 GC 使用**标记-清除 (mark-sweep)** 算法来检测循环引用：

1. 对 gc 跟踪的容器对象（list, dict, set, class instance 等），将它们的引用计数复制一份
2. 遍历所有对象，对每个被引用的对象，将副本引用计数减 1
3. 副本引用计数仍大于 0 的对象是从外部可达的（根对象）
4. 从根对象出发，标记所有可达对象
5. 未被标记的对象就是循环引用垃圾，回收之

注意：**分代 GC 只处理循环引用**。非循环引用的对象由引用计数机制自动处理，不需要 GC 介入。

## 4. gc 模块实用操作

```python
import gc

# 查看触发自动 collection 使用的计数器；不是对象总数或累计 GC 次数
print(gc.get_count())  # (687, 8, 2)

# 手动触发全量 GC
collected = gc.collect()
print(f"发现了 {collected} 个不可达对象（含已回收与不可回收）")

# 调整阈值
gc.set_threshold(1000, 15, 15)  # 降低 GC 频率

# Python 3.4+ 通常为空；DEBUG_SAVEALL 会刻意把所有不可达对象放进来，
# 少数未正确支持 GC 的 C extension type 也可能留下不可回收对象
print(gc.garbage)

# 关闭分代 GC
gc.disable()
```

### 监控与诊断不要混用

- `gc.get_count()` 是自动 collection 使用的当前计数器，不是累计 collection 次数。
- `gc.get_stats()` 才提供各代累计 `collections`、`collected`、`uncollectable`。
- `gc.collect()` 会主动改变 heap 状态并引入暂停；只用于受控诊断，不要定时调用它充当监控。
- 生产服务优先使用 `prometheus_client` 默认的 `python_gc_*` counters，接入与多 worker 限制见 [`fastapi-ops/03-app-metrics`](../../fastapi-ops/03-app-metrics/README.md)。

### 何时禁用 GC

```python
import gc

# 场景：批量数据处理，中间不会产生循环引用
gc.disable()
try:
    for chunk in read_large_file_in_chunks():
        process(chunk)
finally:
    gc.enable()
    gc.collect()  # 最后手动收集一次
```

禁用 GC 的典型场景：
- **批量导入/导出**：已知不会产生循环引用，禁用 GC 可以减少 5-10% 的运行时间
- **Instagram 的实践**：Instagram 曾通过禁用 GC 将 Web 服务器的内存使用降低了 10%（因为 GC 会复制 refcount 导致 copy-on-write 在 fork 后失效）
- **注意**：GC 关闭期间产生的循环引用会持续占用内存，直到重新启用自动 GC 或手动 `gc.collect()`

## 5. weakref — 弱引用

弱引用不增加对象的引用计数，当对象被回收时，弱引用自动变为 None。

```python
import weakref

class ExpensiveObject:
    def __init__(self, data):
        self.data = data

# 正常引用
obj = ExpensiveObject("large data")

# 创建弱引用
weak_obj = weakref.ref(obj)

print(weak_obj())  # <ExpensiveObject object>（对象存在）

del obj
print(weak_obj())  # None（对象已被回收）
```

### WeakValueDictionary 用于缓存

```python
import weakref

class UserCache:
    """使用弱引用的缓存，当对象不再被其他地方使用时自动清除缓存条目"""
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get_user(self, user_id):
        user = self._cache.get(user_id)
        if user is None:
            user = load_user_from_db(user_id)
            self._cache[user_id] = user
        return user

# 当外部不再持有 user 对象的引用时，
# WeakValueDictionary 中的条目自动消失，不会导致内存泄漏
```

这比普通 dict 缓存安全得多 —— 普通 dict 会持有强引用，导致对象永远无法被回收。

## 6. `__del__` 的陷阱

```python
class Resource:
    def __del__(self):
        print(f"Cleaning up {self}")
        self.cleanup()  # 可能抛异常，可能对象状态不完整
```

`__del__` 的问题：

1. **阻碍 GC**：在 Python 3.4 之前，有 `__del__` 的对象如果参与循环引用，GC 无法确定安全的析构顺序，会放入 `gc.garbage` 而不回收。Python 3.4+ (PEP 442) 改善了这个问题，但仍可能有意外行为。

2. **调用时机不确定**：不保证在程序退出时被调用，也不保证调用顺序。

3. **正确的替代方案**：使用上下文管理器。

```python
# 不要这样做
class DBConnection:
    def __del__(self):
        self.close()

# 应该这样做
class DBConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

# 或者使用 weakref.finalize（更可靠的析构回调）
import weakref

class DBConnection:
    def __init__(self):
        self._conn = create_connection()
        self._finalizer = weakref.finalize(self, close_connection, self._conn)
```

## 7. PyPy 与 CPython 的 GC 差异

| 维度 | CPython | PyPy |
|------|---------|------|
| 基本策略 | 引用计数 + 分代 GC | 增量标记-清除（无引用计数） |
| 对象释放时机 | 引用计数归零时立即释放 | 不确定，由 GC 周期决定 |
| `__del__` 调用时机 | 相对及时 | 延迟且不确定 |
| 文件关闭 | `del f` 后很快关闭 | 可能延迟很久 |
| 性能 | GC 暂停较短 | JIT 编译带来整体性能提升 |

**实际影响**：如果代码依赖引用计数的即时释放行为（如打开文件后 `del f` 期望立即关闭），在 PyPy 上可能出问题。正确做法是始终用 `with` 语句管理资源。

```python
# 在 CPython 上"碰巧"能工作
f = open('data.txt')
data = f.read()
del f  # CPython 中引用计数归零，立即关闭文件

# 在 PyPy 上可能导致文件描述符泄漏
# 正确做法：
with open('data.txt') as f:
    data = f.read()
# 文件在 with 块结束时确定性关闭
```

## 小结

CPython 的引用计数提供了及时的内存回收，分代 GC 补充处理循环引用。性能调优时需要注意：

1. 避免不必要的循环引用（减轻 GC 压力）
2. 批量操作时可以临时禁用 GC 提升性能
3. 用 weakref 实现缓存，避免强引用导致的内存泄漏
4. 不要依赖 `__del__`，用上下文管理器管理资源
5. 用 `gc.get_stats()` 或 Prometheus `python_gc_*` counters 监控；仅在受控诊断时手动 `gc.collect()`
