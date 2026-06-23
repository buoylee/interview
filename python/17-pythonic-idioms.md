# 16 · Python 风格与惯用法

> **为什么这章重要**:能跑 ≠ 地道。从 Java/Go 过来最容易"把母语直译成 Python"——写一堆 getter/setter、`for i in range(len(x))`、手动关资源。这章给你一份"怎么写得像资深 Python 工程师"的清单,以及**全书陷阱总览**(一页速查,面试前扫一遍)。

## 一、两条总纲:PEP 8 与 PEP 20

- **PEP 8**:官方代码风格。命名 `snake_case`(函数/变量)、`PascalCase`(类)、`UPPER_CASE`(常量);4 空格缩进;行宽约 79–100。**别手动遵守,交给 `ruff format`/`black`**(第 11 章),省心且团队一致。
- **PEP 20(Zen of Python,`import this`)**:可读性至上、显式优于隐式、扁平优于嵌套、应有一种显而易见的做法。它是"什么算 Pythonic"的价值观依据。

## 二、地道写法清单

```python
# 交换 / 多重赋值
a, b = b, a                       # 不要临时变量

# 带索引/并行遍历
for i, x in enumerate(xs): ...    # 不要 for i in range(len(xs))
for x, y in zip(xs, ys): ...      # 并行遍历

# 真值判断
if not items: ...                 # 判空,不写 if len(items) == 0
if x is None: ...                 # 判 None,不写 if x == None

# 字典取默认
v = d.get(key, default)           # 不要 if key in d: v = d[key] else ...
d.setdefault(k, []).append(x)     # 或 defaultdict

# 类型判断
if isinstance(x, int): ...        # 不要 type(x) == int(忽略子类)

# 资源管理
with open(path) as f: ...         # 不要手动 f = open(); ...; f.close()

# 字符串
f"{name}={value}"                 # 不要 "%s=%s" % (...) 或 + 拼接

# 推导式
squares = [x*x for x in xs]       # 简单转换/过滤优先推导式
```

EAFP 优先(第 08 章):直接做、出错再 `except`,而不是层层 `if` 预检查。

## 三、反模式:别把 Java 直译成 Python

| 反模式(Java 直译) | 地道 Python | 为什么 |
|---|---|---|
| 为每个字段写 `get_x()/set_x()` | 直接公开属性;需要逻辑才上 `@property` | Python 属性可后期无痛改成 property,不必预防性封装 |
| `for i in range(len(xs)): xs[i]` | `for x in xs` / `enumerate` | 直接迭代元素,更短更不易错 |
| `def f(x, acc=[])` | `acc=None` + 内部新建 | 可变默认参数会累积(第 04 章) |
| `type(x) == MyClass` | `isinstance(x, MyClass)` | `isinstance` 认子类,符合多态 |
| 一切都塞进类、深继承层级 | 模块函数 + 组合 + dataclass | Python 模块就是组织单位,不必万物皆类 |
| 手动 `try/finally` 关资源 | `with` | 上下文管理器更安全(异常也清理) |
| 用异常做正常控制流(到处 try) | 仅在真异常处用;正常分支用返回值/判断 | 异常用于异常,EAFP 不等于滥用异常 |
| `import *` 拉一堆名字 | 显式导入需要的 | 可追踪、不污染命名空间(第 10 章) |

核心心态转变:**Python 信任你**——属性默认公开、不强制封装、不强制万物皆类。地道 Python 是"用最少的结构表达清楚",不是"把 Java 的防御性样板照搬过来"。

## 四、全书陷阱总览(面试前速查)

每条都是高频"猜输出 / 解释一下"题,附最小复现与所属章节:

| 陷阱 | 最小复现 | 结果 / 要点 | 章 |
|------|----------|-------------|----|
| **可变默认参数** | `def f(x,acc=[]): acc.append(x); return acc` | 跨调用累积(默认值定义时建一次) | 04 |
| **嵌套乘法共享引用** | `g=[[0]*2]*2; g[0][0]=9` | `[[9,0],[9,0]]` 三行/两行同变 | 01 |
| **闭包延迟绑定** | `[lambda:i for i in range(3)]` 全调用 | `[2,2,2]`,捕获变量非值 | 04 |
| **可变类属性共享** | `class C: items=[]` 实例 append | 所有实例共享同一 list | 05 |
| **`is` 比值** | `1000 is int("1000")` | `False`(且会 SyntaxWarning);值比较用 `==` | 01 |
| **小整数缓存** | `256 is 256` vs 大数 | `-5~256` 缓存恒 True,区间外看上下文 | 01 |
| **漏逗号隐式拼接** | `["Tom" "Jerry"]` | `['TomJerry']` 一个元素 | (字符串) |
| **`for...else`** | 循环 `else` | 没 `break` 才执行 | 03 |
| **负数地板除** | `-7//2`,`-7%2` | `-4`,`1`(向 -∞、余数随除数) | 02 |
| **`/` 返回 float** | `7/2` | `3.5`(整除用 `//`) | 02 |
| **bool 是 int** | `True+True`,`[a,b][True]` | `2`,取下标 1 | 02 |
| **`round` 银行家舍入** | `round(0.5)`,`round(2.5)` | `0`,`2`(五成双,非逢五进一) | 02 |
| **NaN 不等于自己** | `nan==nan`,`nan in [nan]` | `False`,但 `in` 可为 True;判它用 `math.isnan` | 02 |
| **遍历时改容器** | 边 `for` 边 `remove`/`del` | dict 抛 RuntimeError、list 静默漏删 | 02 |
| **`__x` 名字改写** | `self.__x` 被重写 | 实为 `_Class__x`,防碰撞非私有 | 05 |
| **推导式 vs for 变量泄漏** | `[i for i...]` 后 `i` / `for j...` 后 `j` | 推导式不泄漏、`for` 泄漏 | 03 |
| **`finally` 吞 return** | `try: return 1 finally: return 2` | `2` | 08 |
| **`__eq__` 无 `__hash__`** | 只定义 `__eq__` | 对象变不可哈希 | 05 |
| **`and`/`or` 返回操作数** | `0 or "x"`,`"a" and "b"` | `"x"`,`"b"`(非布尔) | 03 |
| **`super()` 不是调父类** | 多继承 MRO | 调 MRO 下一个,可能是兄弟类 | 06 |
| **import 顶层副作用** | 顶层建连接/配日志 | 谁 import 谁触发,难排查 | 10 |
| **循环导入** | A↔B 互导 | `partially initialized module` | 10 |
| **类型注解不强制** | `def f(x:int)` 传 str | 运行时不报错 | 09 |
| **asyncio 里阻塞调用** | 协程里 sleep/重计算无 await | 卡死整个事件循环 | 13 |

> 把这张表的"根因"串起来:**前 4 个(可变默认参数、`[[]]*n`、闭包延迟绑定、类变量共享)同源**——都是第 01 章"名字是绑定、可变对象被共享"的不同马甲。面试答这类题,先说现象,再点根因,最高分。

## Java/Go 对照框

| Java/Go 习惯 | 在 Python 里 |
|---|---|
| 封装一切、getter/setter | 默认公开属性,需要时才 `@property` |
| 万物皆类 | 模块函数 + dataclass + 组合 |
| 索引遍历 `for(i=0;i<n;i++)` | `for x in xs` / `enumerate` |
| `try-finally` / `defer` 关资源 | `with` |
| 显式类型、编译期检查 | 注解 + mypy(运行时不强制) |
| 检查式编程(LBYL) | 偏 EAFP |

## 章末面试卡

**Q1. 什么是 Pythonic?举两个例子。**
指符合 Python 习惯与 PEP 20 价值观(可读、显式、简洁)的写法。例:用 `for x in xs`/`enumerate` 而非 `range(len(xs))` 索引遍历;用 `with` 管资源而非手动 `try/finally`;用 `d.get(k, default)`、解包交换、推导式、EAFP 等。

**Q2. 为什么 Python 不流行写 getter/setter?**
因为属性可后期无痛升级为 `@property`(接口不变),不需要为"将来可能加逻辑"预防性封装。直接公开属性更简洁,需要校验/计算时再换成 property——这是 Python 的"信任 + 按需"哲学。

**Q3. `isinstance(x, T)` 和 `type(x) == T` 有什么区别?该用哪个?**
`isinstance` 认子类(`isinstance(True, int)` 为 True),符合多态;`type(x) == T` 要求类型精确相等(`type(True) == int` 为 False)。一般用 `isinstance`;只有在确实需要"精确这个类、排除子类"时才用 `type(x) is T`。

**Q4. 列举几个你知道的 Python 经典陷阱。**
可变默认参数(累积)、`[[0]*n]*m` 共享内层引用、闭包延迟绑定(`[2,2,2]`)、可变类属性被实例共享、`is` 误用于值比较、`finally` 里 `return` 吞返回值、负数地板除符号。其中前四个同根:名字是绑定 + 可变对象被共享。

**Q5. EAFP 是不是鼓励到处用异常?**
不是。EAFP 是"正常路径直接做、真出错才 `except`",针对的是"操作通常会成功"的场景;它不等于用异常做正常分支控制流。异常仍应用于异常情况,正常分支用返回值/条件判断。
