# 15 · CPython 内部与性能心智

> **为什么这章重要**:这章把前面散落的"实现细节"(引用计数、GC、`__slots__`、小整数缓存)收束成一套连贯的内部模型,并回答两个高频问题:**Python 的内存是怎么管的**、**为什么 Python 慢、慢在哪、怎么办**。性能剖析/调试的实操(火焰图、py-spy、cProfile)在 [`../performance-tuning-roadmap/06a-python-profiling`](../performance-tuning-roadmap/06a-python-profiling)、[`06b-python-debugging`](../performance-tuning-roadmap/06b-python-debugging)。

## 一、字节码与执行:`dis` 一窥

[第 00 章](00-mental-model-and-setup.md)说过源码先编译成字节码再由虚拟机解释。`dis` 模块让你看到这些字节码:

```python
import dis
def f(a, b):
    return a + b * 2
dis.dis(f)
```
```
  LOAD_FAST    0 (a)      # 把局部变量 a 压栈
  LOAD_FAST    1 (b)      # 把 b 压栈
  LOAD_CONST   1 (2)      # 把常量 2 压栈
  BINARY_OP    5 (*)      # 弹出 b、2,算 b*2,结果压栈
  BINARY_OP    0 (+)      # 弹出 a、(b*2),算和,压栈
  RETURN_VALUE            # 返回栈顶
```

CPython 是**基于栈的虚拟机**:指令在一个求值栈上压入/弹出操作数。执行时有个 **eval 循环**(一个巨大的指令分发循环)逐条解释字节码,配合**帧对象(frame)** 保存每次函数调用的局部变量、栈、指令指针。

> 具体 opcode 随版本变(3.11 起引入 `RESUME`、`BINARY_OP` 合并了算术指令),不用背;知道"能用 `dis` 看、CPython 是栈式解释器 + eval 循环 + 帧"即可。

## 二、对象模型:每个对象都背着一个头

CPython 里每个对象在内存里都有个固定的**对象头**,至少包含:

- **引用计数(refcount)**:有多少引用指向它;
- **类型指针**:指向它的类型对象(`type(x)` 读的就是它)。

这就是为什么 Python 对象比 C 的原生值"重"——一个 `int` 不是 8 字节,而是带着头的完整对象(小整数还被缓存复用,见[第 01 章](01-names-objects-memory.md))。

## 三、内存管理:引用计数为主 + 分代 GC 兜底

### 引用计数

每个对象记着引用数,**增减引用时实时更新,归零立即回收**:

```python
import sys
a = []
sys.getrefcount(a)   # 比你以为的多 1:getrefcount 的参数自己也是一个临时引用
b = a                # refcount +1
del b                # refcount -1,归零则立刻释放
```

优点:回收及时、可预测。缺点:**处理不了循环引用**——`a.ref = b; b.ref = a`,即使外部再也够不到,两者 refcount 仍 ≥ 1,永不归零。

### 分代垃圾回收(GC)

为补引用计数的短板,CPython 另有一个**分代 GC** 专门回收循环垃圾:

```python
import gc
class Node:
    def __init__(self): self.ref = None
a = Node(); b = Node()
a.ref = b; b.ref = a        # 循环引用
del a, b                    # 外部引用没了,但它俩互指,refcount 不为 0
print(gc.collect() > 0)     # True —— GC 检测并回收了这组循环垃圾
print(len(gc.get_count()))  # 3 —— 三代
```

- **分代假设**:大多数对象"朝生暮死",越老的对象越可能继续活着。于是分**三代**(0/1/2),新对象在第 0 代、频繁扫;熬过回收的晋升到老代、扫得少。这样 GC 不必每次全堆扫描。
- GC 只针对**可能产生循环**的容器对象(list/dict/对象等),不管 int/str 这种不会循环引用的。
- 副作用:依赖 `__del__` 做清理不可靠(循环引用里 `__del__` 调用时机不确定),所以**资源清理用 `with` 而非 `__del__`**(第 07 章)。

### `__slots__` 省内存的原理

默认每个实例用一个 `__dict__`(哈希表)存属性,灵活但每个实例都背着一个 dict 的开销。`__slots__` 让实例改用**固定槽位**(类似 C struct 的字段),省掉 per-instance 的 `__dict__`:

```python
import sys
class Normal:
    def __init__(self): self.x = 1; self.y = 2
class Slotted:
    __slots__ = ("x", "y")
    def __init__(self): self.x = 1; self.y = 2

print(hasattr(Normal(), "__dict__"))    # True
print(hasattr(Slotted(), "__dict__"))   # False —— 没有 __dict__,省下它的开销
print(sys.getsizeof(Normal().__dict__)) # 296 —— 这块开销 slotted 实例没有
```

海量小对象(几十万个点/记录)用 `__slots__` 能省可观内存。代价:不能动态加属性(第 05 章)。

### pymalloc

CPython 还有专门的小对象分配器 **pymalloc**:向操作系统大块申请内存(arena),再切成小块复用,避免频繁 `malloc`/`free` 的开销。这是底层细节,知道"CPython 有自己的内存池、不是每个小对象都直接找 OS 要"即可。

### `weakref`:不增加引用计数的引用

普通引用会让对象的 refcount +1、阻止回收。**弱引用(`weakref`)** 指向对象但**不增加引用计数**,对象该回收就回收——用于缓存、观察者、避免循环引用导致的内存滞留:

```python
import weakref
class Big: pass
b = Big()
r = weakref.ref(b)
r() is b          # True —— 对象还在,r() 取回它
del b
r() is None       # True —— 对象已被回收,弱引用自动失效
```

典型用途:`weakref.WeakValueDictionary` 做"对象还活着才缓存"的缓存(不会因为缓存本身把对象钉在内存里)。

### `functools.cached_property`:惰性计算一次

把"贵的计算"包成属性,**首次访问才算、之后缓存在实例上**:

```python
from functools import cached_property
class Report:
    @cached_property
    def summary(self):
        ...           # 只在第一次访问 self.summary 时执行,结果存进实例 __dict__
        return result
```

适合"实例生命周期内不变、但算起来贵"的派生值;注意它把结果存进实例 `__dict__`,所以**和 `__slots__` 不兼容**。

## 四、为什么 Python 慢,慢在哪

诚实面对:**纯 Python 计算比 C/Java/Go 慢一两个数量级**。原因:

1. **解释执行**:逐条解释字节码,没有(传统上)JIT 编译成机器码;
2. **动态类型**:每次操作都要运行时查类型、找方法(`a + b` 要查 `a` 的类型再找 `__add__`);
3. **一切皆对象**:连整数都是带头的堆对象,装箱开销大;
4. **GIL**:挡住了多线程的 CPU 并行(第 13 章)。

### 怎么办:性能惯用法

- **别用纯 Python 做重数值计算**——用 **numpy**(向量化,循环在 C 层跑)、或 C 扩展 / **Cython** / 把热点写成原生扩展。这些库在 C 层执行且常**释放 GIL**,能真正并行。
- **CPU 密集并行用多进程**(第 13 章),绕开 GIL。
- **微观惯用法**:把热循环里的属性查找/全局查找提到循环外用局部变量;优先用内置函数和内置类型(它们是 C 实现的,如 `sum`/`map`/`str.join`);用生成器避免一次性建大列表(第 07 章);用 `set`/`dict` 做成员判断而非 `list`(第 02 章)。
- **但先测量再优化**:用 `cProfile`/`py-spy` 找到真正的热点,别凭感觉(实操见 perf-roadmap)。

### 3.13 / 3.14:free-threaded、子解释器与 JIT

- **free-threaded(可关 GIL)构建**:3.13 实验性,**3.14 经 PEP 779 转为官方支持**(仍是可选构建,默认带 GIL),单线程约 5–10% 开销。「多线程跑不满多核」的老结论开始被改写,但默认发行版仍带 GIL,生产要确认构建与 C 扩展适配。
- **子解释器**:PEP 734 在 3.14 进标准库 `concurrent.interpreters`,每个解释器独立 GIL,进程内真并行(选型见[第 13 章](13-concurrency-bridge.md))。
- **实验性 JIT**:3.13 引入(把热点编译成机器码),3.14 仍属实验 / 可选,逐步成熟中,短期别指望默认开启。

## 五、深入:性能剖析/调试实操

本章讲"内部机制 + 心智",真正动手定位性能问题去:

- [`../performance-tuning-roadmap/06a-python-profiling`](../performance-tuning-roadmap/06a-python-profiling) —— cProfile、py-spy、火焰图、内存剖析。
- [`../performance-tuning-roadmap/06b-python-debugging`](../performance-tuning-roadmap/06b-python-debugging) —— pdb、调试技巧。

## Java/Go 对照框

| | Java | Go | Python(CPython) |
|--|------|-----|------------------|
| 执行 | 字节码 + JIT(HotSpot) | 编译成原生机器码 | 字节码 + 解释(3.13 起实验 JIT) |
| 内存回收 | 纯 GC(分代/并发) | 并发标记清除 GC | **引用计数为主** + 分代 GC 兜循环 |
| 对象开销 | 对象头 + 字段;基本类型不装箱 | struct 紧凑 | 一切皆对象,连 int 都带头 |
| 多核计算 | 线程真并行 | goroutine 真并行 | 受 GIL,需多进程/扩展;3.14 free-threaded 构建(可选)可进程内真并行 |
| 提速手段 | JIT 自动 | 编译器 | numpy/Cython/C 扩展 + 多进程 |

一句话:**Python 用"开发效率"换"运行效率"**,慢的部分交给 C 写的库(numpy/扩展)去补。这就是为什么数据/AI 生态在 Python 里繁荣——胶水用 Python,重活在 C/CUDA。

## 章末面试卡

**Q1. Python(CPython)怎么管理内存?**
以**引用计数**为主:每个对象记引用数,增减实时更新,归零立即回收(及时、可预测)。引用计数无法处理**循环引用**,故另有**分代 GC**(三代,基于"多数对象朝生暮死"假设)检测回收循环垃圾。

**Q2. 循环引用会内存泄漏吗?`__del__` 可靠吗?**
普通情况下不会——分代 GC 会回收循环垃圾。但若对象定义了 `__del__` 又陷入循环引用,回收时机/顺序不确定(历史上甚至可能不回收),所以**资源清理别依赖 `__del__`,用 `with`/上下文管理器**。

**Q3. 为什么 Python 比 Java/Go 慢?**
解释执行(无传统 JIT)、动态类型(每次操作运行时查类型找方法)、一切皆对象(装箱开销)、GIL 挡住多线程 CPU 并行。提速靠 numpy/Cython/C 扩展(在 C 层跑、释放 GIL)和多进程。

**Q4. `__slots__` 为什么能省内存?**
默认实例用 `__dict__`(哈希表)存属性,每个实例都背着这份开销;`__slots__` 改用固定槽位存储,省去 per-instance 的 `__dict__`。海量小对象时省内存明显,代价是不能动态加未声明的属性。

**Q5. GIL 和 GC 是一回事吗?**
不是。GIL 是**并发控制**(全局解释器锁,限制同时执行字节码的线程数,影响多线程 CPU 并行);GC 是**内存回收**(引用计数 + 分代回收循环垃圾)。两者独立,常被混问。

**Q6. 听说过 3.13 / 3.14 的变化吗?**
3.13 引入实验性 JIT 与实验性 free-threaded(可关 GIL)构建;**3.14 经 PEP 779 把 free-threaded 转为官方支持的可选构建**(默认发行版仍带 GIL),并把子解释器(PEP 734)纳入标准库 `concurrent.interpreters`。影响:「Python 多线程跑不满多核」正被改写,但当前默认仍带 GIL,生产需确认构建与 C 扩展适配。JIT 仍属实验。
