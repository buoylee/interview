# 07 · 迭代器、生成器、上下文管理器

> **为什么这章重要**:`for`、`with`、列表推导背后是两套协议——迭代协议和上下文管理协议。理解它们,你才能写出惰性、省内存的数据管道(生成器),以及不漏关资源的代码(`with`)。生成器还是 `asyncio` 协程的前身,这章给第 13 章打底。

## 一、可迭代 vs 迭代器:两个别混的概念

- **可迭代对象(iterable)**:能交出一个迭代器,即实现了 `__iter__`。`list`、`dict`、`str`、`range` 都是。
- **迭代器(iterator)**:能逐个产出元素,即实现了 `__next__`(且 `__iter__` 返回自己)。元素耗尽时抛 `StopIteration`。

```python
nums = [1, 2, 3]
it = iter(nums)           # list 是可迭代,iter() 交出一个迭代器
print(next(it), next(it)) # 1 2

print(iter(nums) is nums) # False —— list 不是自己的迭代器,每次 iter() 给新的
print(iter(it) is it)     # True  —— 迭代器的 __iter__ 返回自己
```

关键区别:**可迭代对象可以被遍历多次**(每次 `for` 重新要一个迭代器);**迭代器是一次性的**,走到头就空了。`for x in obj` 的真实过程是:先 `iter(obj)` 拿迭代器,再反复 `next()` 直到 `StopIteration`。

自己实现一个迭代器:

```python
class Countdown:
    def __init__(self, n): self.n = n
    def __iter__(self): return self          # 迭代器返回自己
    def __next__(self):
        if self.n <= 0:
            raise StopIteration               # 耗尽信号
        self.n -= 1
        return self.n + 1

print(list(Countdown(3)))    # [3, 2, 1]
```

## 二、生成器:写迭代器的简易方式

每次手写 `__iter__`/`__next__`/`StopIteration` 很啰嗦。**生成器**用 `yield` 让你像写普通函数一样写迭代器——函数里出现 `yield`,它就变成生成器函数,调用时不执行函数体,而是返回一个生成器(迭代器):

```python
def gen():
    yield 1
    yield 2
    yield 3

print(list(gen()))    # [1, 2, 3]
```

执行流:每次 `next()` 运行到下一个 `yield` 处**暂停并交出值**,保留全部局部状态;再 `next()` 从暂停处继续。函数结束等于 `StopIteration`。

### 惰性求值与省内存

生成器**按需产出**,不一次性把所有元素堆在内存里。这让它能表示**无限序列**,配合 `itertools.islice` 取前 N 个:

```python
import itertools
def naturals():
    n = 1
    while True:           # 无限!
        yield n
        n += 1

print(list(itertools.islice(naturals(), 5)))   # [1, 2, 3, 4, 5]
```

**生成器表达式**是推导式的惰性版,把 `[]` 换成 `()`,内存占用远小于列表推导:

```python
import sys
lst = [x for x in range(1000)]      # 立刻建好 1000 个元素
gen = (x for x in range(1000))      # 不产出,只在迭代时按需算
print(sys.getsizeof(lst) > sys.getsizeof(gen))   # True
```

处理大文件/大流时,**优先用生成器搭数据管道**(逐行读、逐条转换),内存恒定;用列表推导会把全部数据一次性载入。

### `yield from`:委托给子生成器

```python
def chain_two(a, b):
    yield from a          # 把 a 的元素逐个 yield 出去
    yield from b

print(list(chain_two([1, 2], [3, 4])))   # [1, 2, 3, 4]
```

`yield from` 把迭代委托给另一个可迭代对象,省去手写 `for x in a: yield x`,并能正确传递子生成器的返回值/异常。生成器还有 `send()`(往里塞值)、`close()`(关闭)等方法,是早期协程的基础——`asyncio` 的 `await` 机制由此演化而来(第 13 章)。

## 三、`itertools`:迭代器工具箱

标准库里一组高效、惰性的迭代器组合子,数据处理常用:

```python
import itertools

itertools.chain([1, 2], [3, 4])          # 串接 → 1 2 3 4
itertools.islice(gen, 5)                  # 切片(对迭代器)→ 前 5 个
itertools.accumulate([1, 2, 3, 4])        # 累积 → 1 3 6 10
itertools.product([0, 1], repeat=2)       # 笛卡尔积 → (0,0)(0,1)(1,0)(1,1)
itertools.count(10)                       # 无限计数 10,11,12...
itertools.groupby(data, key=...)          # 分组(注意:只对“已排序”数据正确分组)
```

> `groupby` 的坑:它只把**相邻**的同 key 元素分到一组,所以用前通常得先按 key 排序,否则同一个 key 会被切成多段。

## 四、上下文管理器:`with` 协议

`with` 保证"进入时做准备、退出时做清理",**即使中途抛异常也会清理**。它由 `__enter__`/`__exit__` 两个方法定义:

```python
class Ctx:
    def __enter__(self):
        print("enter"); return self          # 返回值赋给 as 后的变量
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("exit")                          # 无论正常还是异常都执行
        return False                           # False/None:不吞异常,继续向上抛

with Ctx() as c:
    print("body")
# 输出 enter / body / exit
```

异常时的行为是重点:`__exit__` 仍会被调用,且收到异常信息 `(exc_type, exc_val, exc_tb)`;**返回 `True` 表示"我处理了,吞掉异常",返回 `False`/`None` 表示"异常继续传播"**:

```python
events = []
class Ctx:
    def __enter__(self): events.append("enter"); return self
    def __exit__(self, et, ev, tb):
        events.append(f"exit({et.__name__ if et else None})")
        return False                           # 不吞

try:
    with Ctx():
        events.append("body")
        raise ValueError("boom")
except ValueError:
    events.append("caught")

print(events)   # ['enter', 'body', 'exit(ValueError)', 'caught']
```

注意顺序:异常发生 → `__exit__` 先被调用(拿到异常)→ 因返回 False,异常继续传播 → 外层 `except` 捕获。这就是为什么用 `with open(...)` 永远不会漏关文件,哪怕读的过程中报错。

### `contextlib`:更轻量的写法

不想写整个类时,用 `@contextmanager` 把一个生成器变成上下文管理器——`yield` 之前是 `__enter__`,之后是 `__exit__`:

```python
from contextlib import contextmanager, suppress

@contextmanager
def tag(name):
    print(f"<{name}>", end="")    # 进入
    yield                          # 这里把控制权交给 with body
    print(f"</{name}>", end="")   # 退出(放 finally 里可保证异常时也执行)

with tag("b"):
    print("hi", end="")
# <b>hi</b>

with suppress(ZeroDivisionError):  # 优雅吞掉指定异常
    1 / 0
# 不报错,继续往下
```

实务里 `@contextmanager` 用得比手写类多。要管理多个/动态数量的资源,用 `contextlib.ExitStack`。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 遍历 | `Iterator`/`Iterable`、Go `range` | 迭代协议 `__iter__`/`__next__` + `StopIteration` |
| 惰性流 | Java `Stream`(惰性)、Go channel | 生成器 / 生成器表达式 / `itertools` |
| 资源管理 | try-with-resources(`AutoCloseable`)、Go `defer` | `with` + `__enter__`/`__exit__`,或 `@contextmanager` |
| 协程基础 | — | 生成器的 `yield`/`send` 是 `asyncio` 协程的前身 |

`with` 最接近 Java 的 try-with-resources / Go 的 `defer`,但更通用:它能包裹任意"进入—退出"逻辑(计时、加锁、临时改状态、事务提交/回滚),不限于关闭资源。

## 章末面试卡

**Q1. 可迭代对象(iterable)和迭代器(iterator)有什么区别?**
可迭代对象实现 `__iter__`、能交出一个迭代器,可被多次遍历(`list`/`dict`/`str`);迭代器实现 `__next__`(且 `__iter__` 返回自己)、逐个产出元素、耗尽抛 `StopIteration`,是一次性的。`for` 先 `iter()` 拿迭代器再反复 `next()`。

**Q2. 生成器为什么省内存?适合什么场景?**
生成器按需产出、不把全部元素堆在内存里,可表示无限序列。适合处理大文件/大数据流、搭惰性数据管道——内存占用恒定。代价是只能遍历一次、不能随机索引。

**Q3. `yield` 和 `return` 区别?函数里有 `yield` 会怎样?**
含 `yield` 的函数变成**生成器函数**,调用它不执行函数体,而是返回一个生成器;每次 `next()` 运行到下一个 `yield` 暂停并交出值、保留局部状态,再次 `next()` 从暂停处继续;函数结束触发 `StopIteration`。`return` 直接结束并返回单个值。

**Q4. `with` 是怎么保证资源被释放的?异常时还释放吗?**
`with` 进入时调 `__enter__`,退出时调 `__exit__`——**无论正常退出还是中途抛异常都会调 `__exit__`**(它能拿到异常信息)。`__exit__` 返回 `True` 吞掉异常,返回 `False`/`None` 让异常继续传播。所以 `with open(...)` 即使读取报错也不漏关文件。

**Q5(猜输出).**
```python
def g():
    yield 1
    yield 2
gen = g()
print(next(gen), next(gen))
print(list(g()))
```
`1 2` 然后 `[1, 2]`。`gen` 被 `next` 取了两个值后已耗尽;`list(g())` 是新生成器,完整产出 `[1, 2]`。

**Q6. 怎么快速写一个上下文管理器?**
用 `contextlib.contextmanager` 装饰一个生成器:`yield` 之前的代码相当于 `__enter__`,之后相当于 `__exit__`(用 `try/finally` 包住 `yield` 可确保异常时也清理)。比手写 `__enter__`/`__exit__` 类简洁。
