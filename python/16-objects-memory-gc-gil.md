# 16 · 对象模型 · 内存 · GC · GIL 机制

> **为什么这章重要**:这是脊柱下半段。[第 15 章](15-cpython-execution-model.md)讲"代码怎么跑",这章讲"对象怎么活、内存怎么收、多线程为什么跑不满多核"。三个最高频的资深/架构师问题——**Python 怎么管内存**、**循环引用会泄漏吗 / `__del__` 可靠吗**、**GIL 到底锁住了什么、怎么放锁**——答案都在这里,而且都得讲到机制层,不能停在"有个引用计数、有个 GIL"。
>
> 并发的**选型与实操**(threading/multiprocessing/asyncio 怎么选、worker、任务队列)在[第 13 章](13-concurrency-bridge.md)与 [`../python-concurrency/`](../python-concurrency/);本章只讲 GIL 的**机制**。性能剖析实操在 [`../performance-tuning-roadmap/`](../performance-tuning-roadmap/)。
>
> 环境:CPython **3.11.8** 实测。

## 一句话心智

**每个对象都背着对象头(引用计数 + 类型指针);内存靠引用计数实时收、分代 GC 偶尔扫一次兜循环;一把 GIL 决定同一时刻只有一个线程在跑字节码——三件事各管各的,却又互相牵动(GIL 存在的一大理由就是保护引用计数)。**

## 一、对象头与内存布局

CPython 里**每个对象在内存里都有个固定的对象头**(`PyObject`),至少装两样:

- **引用计数(`ob_refcnt`)**:有多少引用指向它;
- **类型指针(`ob_type`)**:指向它的类型对象(`type(x)` 读的就是它)。

变长对象(list/str/int…)还多一个 `ob_size`。这就是为什么 Python 对象比 C 原生值"重"——一个整数不是 8 字节裸值,而是带着头的完整堆对象:

```python
import sys
sys.getsizeof(0)        # 28   —— 一个 int 对象的开销(头 + 数字存储)
sys.getsizeof(2**30)    # 32   —— 大到放不下时多用一个 30 位"数字"
sys.getsizeof(2**100)   # 40   —— 再多两个数字,每个 +4 字节
sys.getsizeof([])       # 56   —— 空 list 也有头 + 容量字段
```

`int` 是**任意精度**的:超过一个 30 位数字就用一个动态数组放多个数字,所以 `getsizeof` 随大小线性增长(每多一段 +4 字节)。这也是为什么 Python 没有整数溢出,代价是大整数运算比 C 的 `int64` 慢。

> 实例的属性存储(`__dict__` vs `__slots__`)、容器(list/dict)的内部布局与扩容,是这层"对象重不重"的延伸:`__slots__` 见本章 §5,dict/list 的紧凑布局与过度分配见第 [02 章](02-builtin-types-data-structures.md)。

## 二、引用计数:99% 的内存是它收的

每个对象记着引用数,**增减引用时实时更新,归零立即回收**。在 C 层就是 `Py_INCREF` / `Py_DECREF` 这对宏:绑定一个名字、放进容器、作为函数参数传入、甚至循环变量每轮——都会让 refcount +1;名字离开作用域、`del`、容器销毁——则 -1。归零的瞬间对象被释放。

```python
import sys
a = []
sys.getrefcount(a)   # 2 —— 比你以为的多 1:getrefcount 的参数本身也是一个临时引用(+1)
b = a
sys.getrefcount(a)   # 3 —— b=a 又 +1
del b
sys.getrefcount(a)   # 2 —— 归位
```

那个"凭空多 1"是经典面试点:`sys.getrefcount(a)` 调用时,`a` 作为**实参**被传进函数,这本身就是一个额外引用,所以读数永远比"真实外部引用数"多 1。

- **优点**:回收**及时、可预测**——对象一没人用就立刻释放,不用等 GC 扫描,内存占用平稳。
- **致命短板**:**处理不了循环引用**。`a.ref = b; b.ref = a`,即使外部再也够不到它俩,彼此的 refcount 仍 ≥ 1,永不归零 → 这就要靠 §4 的 GC 兜底。

> 对比:Java/Go 是**纯追踪式 GC**,没有 per-object 引用计数,所以没有"立即回收"的确定性,但天然不怕循环引用。Python 反过来:引用计数给了确定性,循环留给 GC 补。

## 三、weakref:不增加引用计数的引用

普通引用会让 refcount +1、阻止回收。**弱引用(`weakref`)** 指向对象但**不增加引用计数**,对象该回收就回收:

```python
import weakref
class Big: pass
b = Big()
r = weakref.ref(b)
r() is b      # True —— 对象还在,r() 取回它
del b
r() is None   # True —— 对象已被回收,弱引用自动失效
```

典型用途:`weakref.WeakValueDictionary` 做"对象还活着才缓存"的缓存——缓存本身不会把对象钉在内存里,避免缓存造成的内存滞留;以及打断本会导致循环引用的反向指针(子节点指回父节点用弱引用)。

## 四、分代 GC:偶尔扫一次,专收循环

为补引用计数收不掉循环的短板,CPython 另有一个**分代垃圾回收器**,专门检测回收**循环垃圾**:

```python
import gc
class Node:
    def __init__(self): self.ref = None
a = Node(); b = Node()
a.ref = b; b.ref = a         # 循环引用
del a, b                     # 外部引用没了,但互指,refcount 不为 0
gc.collect() > 0             # True —— GC 检测并回收了这组循环垃圾
gc.get_threshold()           # (700, 10, 10)
```

**两个时钟的心智**:引用计数**时刻在转**(实时增减、归零即收);分代 GC **偶尔才跑**(攒够一批新对象才扫一次)。机制要点:

- **算法是标记-清除(mark-sweep)**:从根集合出发遍历可达对象、标记存活,没标记到的(包括只在循环内部互相可达、但从根够不到的)就是垃圾,清掉。引用计数解决不了循环,正因为"互指"让 refcount 骗过了它;而可达性分析不被互指骗。
- **触发不是定时器,而是计数**:按"分配数 − 释放数"累计超阈值才扫第 0 代。默认 `(700, 10, 10)`:第 0 代净增 700 个对象触发一次扫描;每满 10 次 0 代回收才连带扫 1 代;2 代更稀。所以 GC 是"攒够一批才来扫"。
- **分代假设**:多数对象"朝生暮死",越老的越可能继续活着。于是分**三代**(0/1/2),新对象进第 0 代、频繁扫;熬过一次回收就**晋升**到老代、扫得越来越少。这样 GC 不必每次全堆扫描。
- **只管可能成环的容器对象**(list/dict/自定义实例等);int/str 这种不会引用别人的,不进 GC。

### 副作用:`__del__` 在循环里不可靠

如果一组循环引用里的对象定义了 `__del__`,GC 回收它们时**析构顺序是不确定的**(A→B→A 里谁先析构由遍历顺序定,规范不保证),历史上某些版本甚至可能**拒绝回收**这组对象造成泄漏。结论:

> **资源清理(关文件/连接/锁)永远用 `with`/上下文管理器(第 [07 章](07-iterators-generators-context-managers.md)),不要依赖 `__del__`。** `__del__` 只适合做"无关紧要的兜底"。

`gc` 模块还可手动干预:`gc.disable()`(确定无环的批处理里关掉省 CPU)、`gc.collect()`(关键点主动回收)、`gc.freeze()`(把当前存活对象移出扫描范围,常用于 fork 前减少 copy-on-write 抖动)。

## 五、`__slots__` 的机制

默认每个实例用一个 `__dict__`(哈希表)存属性,灵活但每个实例都背着一份 dict 开销。`__slots__` 让类为每个声明的属性创建一个 **member descriptor**(C 级的、记录固定偏移的描述符),实例改用紧凑的**固定槽位**存储,省掉 per-instance 的 `__dict__`:

```python
class Slotted:
    __slots__ = ("x", "y")

type(Slotted.x).__name__         # 'member_descriptor'  ← 类上是描述符
hasattr(Slotted(), "__dict__")   # False                ← 实例没有 __dict__
```

`Slotted.x` 是一个 `member_descriptor`,读写 `instance.x` 时它按固定偏移直接存取那块槽位内存(描述符协议见第 [05 章](05-oop-1-classes-protocols.md))。海量小对象(几十万个点/记录)用 `__slots__` 能省可观内存。代价与陷阱:

- 不能再动态加未声明的属性(因为没 `__dict__`);
- 与 `functools.cached_property`、`@cached_property` 不兼容(它们要往实例 `__dict__` 写缓存);
- 子类若不声明 `__slots__`,实例又会长出 `__dict__`,省内存的效果就没了。

## 六、GIL 机制:它到底锁住了什么

**GIL(全局解释器锁)= 一把进程级互斥锁,保证同一时刻只有一个线程在执行 Python 字节码。**

**为什么要有**:就是为了保护 §2 的引用计数。`Py_INCREF/DECREF` 若被多个线程并发执行而不加锁,refcount 会被写坏(丢更新),导致对象提前释放或泄漏。给每个对象单独加锁太贵,CPython 早年选了最省事的方案:一把大锁锁住整个解释器。

**怎么工作**(这是架构师追问的重点):

- eval 循环里,**持有 GIL 的线程才能执行字节码**。
- 它不会一直霸占:有个 **eval breaker** 周期性地请求当前线程"让出 GIL",让别的线程有机会跑。这个间隔由 `sys.setswitchinterval()` 控制,**默认 5ms**(`sys.getswitchinterval()` → `0.005`)。
- 关键:**线程进入会阻塞的 IO 系统调用(read/write/recv…),或进入主动释放 GIL 的 C 扩展时,会先把 GIL 放掉**,等 IO 回来再重新抢。所以**IO 等待的时间里,别的线程能跑**。

这条机制直接解释了那个老结论:

```python
import time, threading
def burn(n):
    x = 0
    for _ in range(n): x += 1
N = 20_000_000

t = time.perf_counter(); burn(N); burn(N)
seq = time.perf_counter() - t                      # 顺序两遍

t = time.perf_counter()
ts = [threading.Thread(target=burn, args=(N,)) for _ in range(2)]
[x.start() for x in ts]; [x.join() for x in ts]
par = time.perf_counter() - t                      # 两线程并行

print(f"顺序 {seq:.2f}s  两线程 {par:.2f}s")
# 顺序 0.60s  两线程 0.59s   —— 加速 1.01×,几乎没有
```

两个**CPU 密集**线程抢同一把 GIL,只能轮流跑字节码,所以**零加速**(还多了切换开销)。但若 `burn` 换成"等网络/读盘",IO 期间 GIL 被放掉,多线程就有意义了——这就是"IO 密集用线程、CPU 密集用多进程"的机制根(选型见第 [13 章](13-concurrency-bridge.md))。

> `setswitchinterval` 能调:调大减少切换开销但增大延迟尾巴,调小反之。它**只影响"多久强制让一次锁"**,改变不了"同一时刻只有一个线程跑字节码"的事实——别指望靠它榨出多核 CPU 并行。

## 七、free-threading:真去掉 GIL(3.13t / 3.14)

「Python 多线程跑不满多核」这条结论正在被改写:

- **free-threaded(可关 GIL)构建**:3.13 实验性,**3.14 经 PEP 779 转为官方支持的可选构建**(默认发行版仍带 GIL)。去掉 GIL 后怎么保护引用计数?靠 **biased reference counting**(偏向引用计数):每个对象记一个"属主线程",属主线程改 refcount 走**非原子**的快路径,别的线程改才走**原子**慢路径;再加上必要处的每对象锁。代价是单线程约 **5–10%** 开销,且 C 扩展要适配后才在该模式下安全。
- **子解释器(PEP 734)**:3.14 进标准库 `concurrent.interpreters`,一个进程里开多个解释器、**每个独立 GIL**,从而进程内真并行(数据要显式传递,像轻量进程)。
- **实验性 JIT**:3.13 引入、3.14 仍实验/可选,逐步成熟,短期别指望默认开启。

生产判断:**默认发行版当下仍带 GIL**,要吃 free-threading 的多核红利,得确认构建版本与全部 C 扩展都适配。

## 八、为什么 Python 慢、怎么办(总纲)

把前两章的机制串起来,纯 Python 计算比 C/Java/Go 慢一两个数量级,四个根因各有出处:

1. **解释执行**:逐条过 eval 循环(第 15 章 §2),没有传统 JIT 把整段编译成机器码;
2. **动态类型**:每个操作要运行时查类型找方法——但 3.11 的自适应专门化对热路径已部分缓解(第 15 章 §6);
3. **一切皆对象**:连整数都是带头的堆对象,装箱开销大(本章 §1);
4. **GIL**:挡住多线程的 CPU 并行(本章 §6)。

**怎么办**:

- **重数值计算别用纯 Python**——用 **numpy**(向量化,循环在 C 层跑且常释放 GIL)、Cython、或写成 C 扩展;这些在 C 层执行并能真并行。
- **CPU 密集并行用多进程**(第 13 章)绕开 GIL,或上 free-threading 构建(§7)。
- **微观惯用法**:热循环里把全局/属性查找提到循环外变成局部(第 15 章 §3 的 `LOAD_FAST` vs `LOAD_GLOBAL`);优先用内置函数与内置类型(C 实现,如 `sum`/`map`/`str.join`);用生成器避免一次性建大列表;用 `set`/`dict` 做成员判断而非 `list`。
- **但先测量再优化**:用 `cProfile`/`py-spy` 找真正的热点,别凭感觉(实操见 [`../performance-tuning-roadmap/`](../performance-tuning-roadmap/))。

## Java/Go 对照框

| | Java | Go | Python(CPython) |
|--|--|--|--|
| 内存回收 | 纯追踪式 GC(分代/并发) | 并发标记-清除 GC | **引用计数为主** + 分代 GC 兜循环 |
| 回收时机 | 不确定(等 GC) | 不确定 | refcount 部分**即时可预测**,循环等 GC |
| 对象开销 | 对象头 + 字段;基本类型不装箱 | struct 紧凑,基本类型不装箱 | 一切皆对象,连 int 都带头 |
| 多核计算 | 线程真并行 | goroutine 真并行 | 受 GIL,需多进程/扩展;3.14 free-threaded(可选)可进程内真并行 |
| 循环引用 | 天然不怕(追踪式) | 天然不怕 | 引用计数怕,靠分代 GC 补 |

一句话:**Python 用"开发效率"换"运行效率"**,慢的部分交给 C 写的库(numpy/扩展)补。这就是数据/AI 生态在 Python 繁荣的原因——胶水用 Python,重活在 C/CUDA。

## 章末面试卡

**Q1. Python(CPython)怎么管理内存?**
以**引用计数**为主:每个对象记引用数,增减实时更新、归零立即回收(及时、可预测,99% 内存它收)。引用计数处理不了**循环引用**,故另有**分代 GC**(三代、标记-清除、基于"多数对象朝生暮死"假设、按分配计数触发)兜底回收循环垃圾。

**Q2. 循环引用会内存泄漏吗?`__del__` 可靠吗?**
正常不会——分代 GC 会回收循环垃圾。但若循环里的对象定义了 `__del__`,析构顺序不确定(历史上甚至可能不回收),所以**资源清理别依赖 `__del__`,用 `with`/上下文管理器**。

**Q3. `sys.getrefcount(x)` 为什么总比预期多 1?**
`x` 作为实参传进 `getrefcount` 时本身就是一个额外引用,所以读数永远比真实外部引用数多 1。

**Q4. GIL 和 GC 是一回事吗?GIL 到底锁住了什么?**
不是。GC 是**内存回收**;GIL 是**并发控制**——一把进程级锁,保证同一时刻只有一个线程执行字节码,存在的主因是保护引用计数不被并发写坏。它在 IO 系统调用 / 主动释放的 C 扩展处会放锁,所以 IO 密集多线程有用、CPU 密集没用。

**Q5. eval 循环里 GIL 在哪儿放?能调吗?**
持锁线程才跑字节码;eval breaker 按 `sys.setswitchinterval()`(默认 5ms)周期请求让出;线程进入阻塞 IO 或主动释放 GIL 的 C 扩展时也会放。`setswitchinterval` 只改"多久强制换一次锁",改变不了"同时只一个线程跑字节码"。

**Q6. `__slots__` 为什么省内存?有什么代价?**
它为每个声明属性建 member descriptor、按固定偏移存取,省掉 per-instance 的 `__dict__`。代价:不能动态加属性、与 `cached_property` 不兼容、子类不声明 `__slots__` 又会长回 `__dict__`。

**Q7. 听说过 free-threading 吗?它怎么去掉 GIL?**
3.13 实验、**3.14 经 PEP 779 转为官方支持的可选构建**(默认仍带 GIL)。去 GIL 后用 **biased reference counting**(属主线程非原子快路径 + 他线程原子慢路径)+ 每对象锁保护引用计数,单线程约 5–10% 开销,C 扩展需适配。另有子解释器(PEP 734)每解释器独立 GIL 实现进程内并行。
