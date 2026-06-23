# 99 · 面试卡

> 全书面试要点的速查汇总 + "猜输出" drill 合集。每道猜输出题的答案都用 `python3` 实测过。面试前从头扫一遍,卡壳的回对应章补。各章末尾还有更详细的卡片。

## 一、分主题速查(问题 → 一句话答 → 关键词)

### 内存模型 / 对象(第 01 章)
- **`is` vs `==`?** `==` 比值(`__eq__`),`is` 比身份(同一对象);值比较一律 `==`,`is` 只配 `None`。｜身份/值
- **256 `is` 成立、257 不一定?** `-5~256` 小整数被缓存恒 True;区间外看编译上下文;实现细节,别依赖。｜小整数缓存
- **深浅拷贝?** 浅拷贝(`copy.copy`/`[:]`)只复制外层、内层共享;深拷贝(`deepcopy`)递归隔离。｜copy/deepcopy
- **内存怎么管?** 引用计数为主(归零即回收)+ 分代 GC 兜循环引用。｜refcount/GC

### 类型与数据结构(第 02 章)
- **`str` vs `bytes`?** 前者 Unicode 文本、后者原始字节,`encode`/`decode` 显式转换。｜文本/字节
- **`/` vs `//`?** `/` 永远 float,`//` 地板除(`-7//2==-4`),`%` 符号随除数。｜地板除
- **dict 有序吗?** 3.7+ 保插入序(语言规范),底层紧凑 dict。｜保序
- **bool?** `int` 子类,`True==1`、`True+True==2`。｜bool-is-int

### 控制流(第 03 章)
- **真值性?** 0/空容器/None/"" 为假;`if not x` 判空,`is None` 判缺失。｜truthy
- **`and`/`or` 返回?** 操作数本身,非布尔(`0 or "x"`→"x")。｜短路
- **`for...else`?** 没 `break` 才执行 `else`。｜else

### 函数 / 闭包 / 装饰器(第 04 章)
- **可变默认参数?** 定义时建一次、跨调用共享,用 `None` 哨兵。｜陷阱
- **闭包延迟绑定?** 捕获变量非值,调用时才查;`lambda i=i` 快照。｜late-binding
- **`@wraps` 为何要?** 保留被装饰函数的 `__name__`/`__doc__` 等元数据。｜装饰器
- **带参装饰器几层?** 三层:参数→函数→调用。｜三层
- **`nonlocal`/`global`?** 前者改外层函数变量、后者改全局;不声明则赋值新建局部。｜作用域

### OOP(第 05–06 章)
- **类变量 vs 实例变量?** 类变量共享、实例变量独立;可变类属性是共享陷阱。｜共享
- **`__new__` vs `__init__`?** 创建 vs 初始化,前者先。｜生命周期
- **`__eq__` 配 `__hash__`?** 定义 `__eq__` 不定义 `__hash__` → 不可哈希。｜契约
- **`__slots__`?** 固定槽位省内存、禁动态属性。｜内存
- **MRO?** C3 线性化定多继承顺序,`D(B,C)`→`D B C A object`。｜C3
- **`super()`?** 调 MRO 下一个,非必父类(协作式多继承)。｜协作
- **`@property` 原理?** 描述符(data descriptor)。｜描述符
- **`__getattr__` vs `__getattribute__`?** 前者找不到才触发、后者每次都触发。｜拦截
- **何时用元类?** 几乎不用;优先 `__init_subclass__`/描述符/类装饰器。｜元类
- **ABC vs Protocol?** 名义(显式继承)vs 结构化(长得像就行)。｜接口

### 迭代 / 异常 / 类型注解(第 07–09 章)
- **可迭代 vs 迭代器?** 前者给迭代器、可多次遍历;后者有 `__next__`、一次性。｜协议
- **生成器省内存?** 惰性按需产出、可表无限序列。｜lazy
- **`with` 原理?** `__enter__`/`__exit__`,异常时也清理;`__exit__` 返 True 吞异常。｜上下文
- **EAFP vs LBYL?** 先做再说 vs 先查再做;Python 偏 EAFP。｜EAFP
- **`raise X from e`?** 设 `__cause__` 保留根因。｜异常链
- **`assert` 能做输入校验?** 不能,`-O` 会跳过。｜assert
- **类型注解运行时强制?** 不强制,靠 mypy/pyright;运行时校验用 pydantic。｜渐进类型

### 模块 / 工程 / 测试(第 10–12 章)
- **import 执行几次?** 首次执行顶层 + 缓存 `sys.modules`,后续命中缓存。｜缓存
- **循环导入?** `partially initialized module`;抽公共模块/延迟导入。｜循环
- **锁文件 vs requirements.txt?** 锁文件记精确版本+哈希,可复现。｜lock
- **wheel vs sdist?** 预构建二进制 vs 源码分发。｜打包
- **fixture?** 按参数名注入的测试依赖,`yield` 分 setup/teardown。｜pytest
- **patch 位置?** patch 使用处而非定义处。｜mock

### 并发 / 内部(第 13、15 章)
- **GIL?** 同时只一个线程跑字节码;CPU 密集多线程不加速,IO 密集有效;3.14 free-threaded 构建(可选)/子解释器可真并行,见第 13 章。｜GIL
- **三选一?** CPU→多进程,IO+阻塞→线程,海量 IO/全异步→asyncio。｜选型
- **async 为何传染?** `await` 只能在 `async` 里,沿调用链蔓延。｜着色
- **为什么慢?** 解释执行+动态类型+对象开销+GIL;靠 numpy/C 扩展/多进程补。｜性能
- **GIL vs GC?** 并发控制 vs 内存回收,两码事。｜区分

## 二、"猜输出" drill 合集(答案已实测)

**D1 可变默认参数**
```python
def f(x, acc=[]):
    acc.append(x); return acc
print(f(1)); print(f(2))
```
→ `[1]` 然后 `[1, 2]`。默认值定义时建一次、跨调用共享。【第 04】

**D2 嵌套乘法共享引用**
```python
g = [[0]*2]*2; g[0][0] = 9; print(g)
```
→ `[[9, 0], [9, 0]]`。外层 `*2` 复制同一内层 list 的引用。【第 01】

**D3 / D4 闭包延迟绑定与修复**
```python
print([f() for f in [lambda: i for i in range(3)]])      # [2, 2, 2]
print([f() for f in [lambda i=i: i for i in range(3)]])  # [0, 1, 2]
```
→ 捕获变量非值,调用时 `i==2`;默认参数 `i=i` 在定义时快照。【第 04】

**D5 可变类属性共享**
```python
class Dog:
    tricks = []
    def add(self, t): self.tricks.append(t)
a, b = Dog(), Dog(); a.add("roll"); print(b.tricks)
```
→ `['roll']`。`tricks` 是共享的类属性。【第 05】

**D6 and/or 返回操作数**
```python
print(0 or "a", "b" and "c", [] or 0)
```
→ `a c 0`。返回触发短路的那个操作数。【第 03】

**D7 地板除**
```python
print(-7 // 2, -7 % 2, 7 / 2)
```
→ `-4 1 3.5`。`//` 向 -∞,`%` 符号随除数,`/` 给 float。【第 02】

**D8 bool 是 int**
```python
print(True + True, [10, 20][True])
```
→ `2 20`。`True==1`,当下标即 1。【第 02】

**D9 推导式不泄漏、for 泄漏**
```python
[i for i in range(3)]
for j in range(3): pass
print(j)            # 2
print(i)            # NameError
```
→ `2` 然后 `NameError`。推导式有独立作用域,`for` 变量泄漏。【第 03】

**D10 finally 吞 return**
```python
def t():
    try: return 1
    finally: return 2
print(t())
```
→ `2`。`finally` 的 `return` 覆盖一切。【第 08】

**D11 切片 vs 索引越界**
```python
print([1,2,3][5:10])    # []
print([1,2,3][5])       # IndexError
```
→ `[]` 然后 `IndexError`。切片安全、单索引越界报错。【第 02】

**D12 生成器一次性**
```python
gen = (x for x in [1, 2]); next(gen)
print(next(gen))         # 2
print(list(x for x in [1, 2]))   # [1, 2]
```
→ `2` 然后 `[1, 2]`。原生成器被消耗,新生成器完整。【第 07】

**D13 默认值是同一个对象**
```python
def h(a=[]): return id(a)
print(h() == h())        # True
```
→ `True`。默认值只在定义时建一次,每次不传拿到同一个对象。【第 04】

**D14 哨兵:区分「没传」和「传了 None」**
```python
_MISSING = object()
def patch(name=_MISSING):
    return "没传" if name is _MISSING else f"传了 {name!r}"
print(patch(), patch(None))
```
→ `没传 传了 None`。当 `None` 本身是合法值(如 PATCH 把字段清空)时,不能拿 `None` 当哨兵——造个 `object()` 唯一对象、用 `is` 判定。标准库 `functools.lru_cache`/`dataclasses.MISSING`/`inspect.Parameter.empty` 都是这招。【第 04】

> 答这类题的套路:**先报输出,再一句话点根因**。D1/D2/D3/D5 同根——"名字是绑定 + 可变对象被共享"(第 01 章),能说出这层就是高分。

## 三、系统 / 设计类追问

**为什么(不)选 Python?**
选:开发快、生态全(数据/AI/Web/脚本)、可读、胶水能力强。不选/注意:CPU 密集性能弱(靠 C 扩展补)、GIL 限制多线程并行、动态类型大项目需 mypy + 测试托底、打包/部署生态碎片。

**Python 适合做高并发后端吗?**
适合 IO 密集型高并发——用 asyncio + 异步框架(FastAPI)+ 异步驱动可撑大量连接;CPU 密集部分下沉到多进程或 C/numpy。纯 CPU 密集的高吞吐计算服务不是 Python 强项。

**大型 Python 项目怎么保证质量?**
类型注解 + mypy/pyright(CI 拦类型错)、ruff(lint+format)、pytest(高价值断言而非堆覆盖率)、pre-commit、pydantic 守数据边界、清晰的模块边界与依赖锁定(uv/poetry)。

**Python 的内存/并发模型一句话总结?**
内存:引用计数为主 + 分代 GC 兜循环。并发:GIL 下多线程只并发不并行 CPU,CPU 并行靠多进程,海量 IO 靠 asyncio;3.14 起 free-threaded 构建(可选)/子解释器(`concurrent.interpreters`)可进程内真并行。

**类型系统:动态类型还要注解,矛盾吗?**
不矛盾。运行时仍是动态(注解不强制),注解是给静态检查器和框架的渐进式增强——既保留动态灵活,又在大型项目里获得可检查性与可读性,按需采用。
