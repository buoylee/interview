# 04 · 函数:一等公民、闭包、装饰器

> **为什么这章重要**:函数在 Python 里是一等对象,这撑起了闭包、装饰器、`functools` 这套高频考点。本章还包含两个"必被问"的经典陷阱——可变默认参数、闭包延迟绑定——它们都是第 01 章"共享可变对象 + 名字是绑定"的直接后果。

## 一、函数是对象

函数能赋值、传参、当返回值、塞进容器——和 int、str 一样是对象:

```python
def shout(s): return s.upper()
f = shout                 # 赋给别的名字
print(f("hi"))            # HI
ops = {"up": str.upper, "low": str.lower}   # 函数当 dict 值
print(ops["up"]("hi"))    # HI
```

`def` 定义具名函数;`lambda` 定义匿名的单表达式函数,适合临时当参数(`sorted(xs, key=lambda p: p.age)`)。`lambda` 只能写一个表达式,逻辑稍复杂就该用 `def`。

## 二、参数体系

Python 的参数比 Java/Go 灵活得多:

```python
def connect(host, port=5432, *args, timeout=10, **kwargs):
    ...
```

- `host`:普通参数(可位置可关键字传)。
- `port=5432`:**默认值**参数。
- `*args`:收集多余的**位置**参数成元组。
- `timeout=10`:`*args` 之后的是**仅关键字**参数(只能 `timeout=...` 传)。
- `**kwargs`:收集多余的**关键字**参数成字典。

还能用 `/` 和 `*` 显式限定传参方式:

```python
def h(pos_only, /, normal, *, kw_only):
    return pos_only, normal, kw_only

h(1, 2, kw_only=3)          # (1, 2, 3)   pos_only 只能位置传
h(1, normal=2, kw_only=3)   # (1, 2, 3)   normal 两种都行
# h(pos_only=1, ...)        # 报错:/ 左边不许关键字传
```

`/` 左边是**仅位置**,`*` 右边是**仅关键字**。设计 API 时用它们锁定调用方式,避免调用方依赖参数名(将来改名不破坏兼容)。

## 三、陷阱一:可变默认参数

**默认值在函数定义时求值一次,之后所有调用共享同一个对象。** 如果默认值是可变对象(`[]`、`{}`),它会跨调用累积:

```python
def bad(x, acc=[]):       # acc=[] 只在 def 执行时创建这一次
    acc.append(x)
    return acc

print(bad(1))   # [1]
print(bad(2))   # [1, 2]    ← 上次的还在!
print(bad(3))   # [1, 2, 3]
```

根因还是第 01 章那条:`acc` 这个默认值是一个被函数对象持有的 list,每次调用都绑定到**同一个** list。正解是用 `None` 当哨兵,每次进函数新建:

```python
def good(x, acc=None):
    if acc is None:
        acc = []
    acc.append(x)
    return acc

print(good(1))  # [1]
print(good(2))  # [2]   ← 互不干扰
```

附带结论:默认值"定义时算一次"对任何表达式都成立。`def f(t=time.time())` 里的 `time.time()` 只在定义那一刻算一次,之后每次不传 `t` 拿到的都是那个固定时刻——也是同一个坑的变体。

## 四、闭包与陷阱二:延迟绑定

**闭包**是"记住了定义时所在作用域里变量"的内层函数。注意它记住的是**变量(绑定),不是当时的值**:

```python
funcs = [lambda: i for i in range(3)]
print([g() for g in funcs])     # [2, 2, 2]  ← 不是 [0, 1, 2]!
```

三个 lambda 都闭包了同一个变量 `i`;等你**调用**它们时才去查 `i`,而那时循环早跑完,`i` 停在 2。修复:用默认参数在定义那一刻**快照**当前值:

```python
fixed = [lambda i=i: i for i in range(3)]   # i=i 把当前 i 存进默认参数
print([g() for g in fixed])     # [0, 1, 2]
```

要在闭包里**修改**外层变量,得用 `nonlocal`(否则赋值会被当成新建局部变量,见第 03/下章作用域):

```python
def counter():
    n = 0
    def inc():
        nonlocal n      # 声明 n 是外层的,不是新建局部
        n += 1
        return n
    return inc

c = counter()
print(c(), c(), c())    # 1 2 3  —— 状态被闭包保住
```

> `nonlocal` 改外层函数的变量,`global` 改模块级全局变量。没有声明时,函数内对一个名字赋值会默认把它当局部变量。

## 五、`functools` 常用武器

```python
from functools import wraps, lru_cache, partial, reduce, singledispatch

@lru_cache                       # 自动记忆化缓存
def fib(n):
    return n if n < 2 else fib(n-1) + fib(n-2)
print(fib(30))                   # 832040,瞬间出(否则指数级慢)

square = partial(pow, 2)         # 固定第一个参数,得到新函数
print(square(10))                # 1024  == pow(2, 10)

print(reduce(lambda a, b: a + b, [1, 2, 3, 4]))   # 10  累积折叠
```

- `lru_cache`(或 `cache`):缓存函数结果,纯函数 + 递归/重复调用的提速神器。
- `partial`:偏函数,固定部分参数。
- `reduce`:折叠(Java 的 `Stream.reduce`、Go 手写循环)。
- `singledispatch`:按第一个参数类型做函数重载(Python 没有 Java 那种签名重载)。
- `wraps`:写装饰器必备,见下。

## 六、装饰器

装饰器就是"接收一个函数、返回一个(通常增强过的)函数"的语法糖。`@deco` 等价于 `fn = deco(fn)`。

### 无参装饰器

```python
from functools import wraps

def timer(fn):
    @wraps(fn)                   # 关键:见下
    def wrapper(*args, **kwargs):
        # 前置逻辑(如计时开始)
        result = fn(*args, **kwargs)
        # 后置逻辑
        return result
    return wrapper

@timer
def greet(name):
    return f"hi {name}"

print(greet("Ann"))              # hi Ann
```

**`@wraps(fn)` 为什么必须有**:不加的话,`greet` 被换成了内层的 `wrapper`,于是 `greet.__name__` 变成 `"wrapper"`、文档字符串丢失,调试和反射全乱。`@wraps` 把原函数的 `__name__`/`__doc__` 等元数据复制到 wrapper 上:

```python
print(greet.__name__)            # greet  (有 @wraps);没有则是 wrapper
```

### 带参装饰器(三层)

装饰器要接收自己的参数时,得再套一层——最外层吃装饰器参数,返回真正的装饰器:

```python
def repeat(times):               # ① 吃装饰器参数
    def deco(fn):                # ② 吃被装饰函数
        @wraps(fn)
        def wrapper(*args, **kwargs):   # ③ 吃调用参数
            return [fn(*args, **kwargs) for _ in range(times)]
        return wrapper
    return deco

@repeat(3)
def hello():
    return "hi"

print(hello())                   # ['hi', 'hi', 'hi']
```

`@repeat(3)` 先调用 `repeat(3)` 得到 `deco`,再用 `deco` 装饰 `hello`。三层结构记牢:**参数 → 函数 → 调用**。

### 堆叠顺序

多个装饰器从**下往上**应用(离函数最近的先包):

```python
@a
@b
def fn(): ...
# 等价于 fn = a(b(fn)) —— b 先包,a 后包(最外层是 a)
```

类装饰器、`@property`、`@dataclass` 本质都是这套机制,后续章节会再见到。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 函数地位 | 方法非一等;Java 用函数式接口/方法引用,Go 函数是一等 | 函数是一等对象,可赋值/传参/返回 |
| 重载 | Java 按签名重载 | 无签名重载;用默认参数 / `*args` / `singledispatch` |
| 默认参数 | Java 无(靠重载);Go 无 | 有,但**定义时求值一次**(可变默认值会累积) |
| 注解 vs 装饰器 | Java 注解是元数据,靠框架反射处理 | 装饰器是**真函数包装**,立即改变被装饰对象 |
| 闭包捕获 | Java lambda 只能捕获 effectively-final | Python 捕获变量绑定,可变;循环里有延迟绑定坑 |

最大认知差:Java 注解"声明意图、等框架解释",Python 装饰器"当场把函数换成包装版"。别把 `@app.route(...)` 当成纯标注——它真的在调用函数改写行为。

## 章末面试卡

**Q1(必考·猜输出).**
```python
def f(x, lst=[]):
    lst.append(x)
    return lst
print(f(1)); print(f(2))
```
`[1]` 然后 `[1, 2]`。默认值 `[]` 在定义时只建一次,所有调用共享,于是累积。修复:`lst=None` + 进函数 `if lst is None: lst = []`。

**Q2(必考·猜输出).**
```python
fs = [lambda: i for i in range(3)]
print([f() for f in fs])
```
`[2, 2, 2]`。闭包捕获的是变量 `i` 本身,调用时才求值,此时 `i==2`。修复:`lambda i=i: i` 在定义时快照。

**Q3. 装饰器里为什么要用 `@wraps`?**
不加 `@wraps`,被装饰函数会被内层 `wrapper` 替换,导致 `__name__`、`__doc__`、签名等元数据丢失,影响调试、日志、反射和文档工具。`functools.wraps` 把原函数元数据复制到 wrapper。

**Q4. 写一个带参数的装饰器需要几层函数?为什么?**
三层:最外层接收装饰器参数,返回真正的装饰器;中层接收被装饰函数,返回 wrapper;内层接收调用参数。因为 `@deco(arg)` 会先 `deco(arg)` 求值得到装饰器,再拿它去装饰函数。

**Q5. `nonlocal` 和 `global` 区别?不写会怎样?**
`nonlocal` 绑定到最近的外层函数作用域变量,`global` 绑定到模块级全局变量。函数内只要对某名字**赋值**,默认就把它当局部变量;想修改外层/全局的同名变量必须先声明,否则要么新建局部、要么触发 `UnboundLocalError`。

**Q6. `lru_cache` 有什么用?用它有什么前提?**
缓存函数的返回值,相同参数直接命中,极大加速递归/重复计算(如 `fib`)。前提:函数应是**纯函数**(同参同果、无副作用),且参数必须**可哈希**(因为要当缓存 key)。
