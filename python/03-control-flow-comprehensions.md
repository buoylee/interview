# 03 · 控制流、推导式、解包

> **为什么这章重要**:控制流人人会写,但 Python 在几个点上藏着"看起来像 A、其实是 B"的语义:真值性让 `if x` 不只是判 `None`、`and`/`or` 返回的不是布尔、`for...else` 的 `else` 不在你以为的时候跑、推导式变量不泄漏但循环变量泄漏。这些既是 bug 源,也是高频"猜输出"。

## 一、真值性(truthiness)

`if`、`while`、`and`、`or`、`not` 接受任意对象,不止 `bool`。每个对象都有"真假":

**假值(falsy)**:`False`、`None`、数字 `0`/`0.0`、空序列/集合 `""`/`[]`/`()`/`{}`/`set()`、以及 `__bool__`/`__len__` 返回假的对象。**其余都是真。**

```python
print([bool(v) for v in [0, "", [], {}, None]])   # [False, False, False, False, False]
```

所以判断"非空"很地道:

```python
items = []
if not items:          # 空 list 为假
    print("空的")
```

⚠️ **但要分清"空"和"是 None"**:

```python
def f(items=None):
    if items is None:      # 明确判 None(没传)
        items = []
    if not items:          # 判空(传了但是空的)
        ...
```

`if not items` 对 `None`、`[]`、`0`、`""` 都成立;若你只想判"没传/缺失",必须 `is None`。混用会把"用户传了空列表"和"用户没传"当成一回事。

## 二、`and` / `or` 返回操作数,不是布尔

短路求值,但返回的是**触发短路的那个操作数本身**,不是 `True`/`False`:

```python
print(0 or "x")          # "x"   —— 0 假,返回后者
print("a" and "b")       # "b"   —— "a" 真,返回后者
print(None or [])        # []    —— 常用来给默认值
print(3 and 0 and 5)     # 0     —— 遇到第一个假值就返回它
```

- `a or b`:`a` 真返回 `a`,否则返回 `b`。常见写法 `name = user_input or "default"`。
- `a and b`:`a` 假返回 `a`,否则返回 `b`。

> 小心 `x or default` 当默认值:若 `x` 是合法的"假值"(如 `0`、`""`),会被误当成缺失而替换掉。要精确判缺失仍用 `x if x is not None else default`。

## 三、链式比较

`1 < x < 10` 不是 `(1 < x) < 10`,而是数学直觉的 `1 < x and x < 10`,且 `x` 只求值一次:

```python
x = 5
print(1 < x < 10)        # True
print(0 == 0 == 0)       # True
```

从 Java/Go 过来别误以为它先算 `1 < x` 得到布尔再跟 `10` 比——那是 C 系语言的行为,Python 是真链式。

## 四、循环与 `else` 子句

`for`/`while` 可以跟一个 `else`,它在**循环正常结束(没被 `break` 打断)时**执行——违反所有人的直觉:

```python
def find(seq, target):
    for v in seq:
        if v == target:
            return "found"
    else:                       # 没 break(也没 return)才执行
        return "not found"

print(find([1, 2, 3], 2))       # found
print(find([1, 2, 3], 9))       # not found
```

记忆法:把它读成 `for...else` = "**循环跑完都没 break 就执行 else**",典型用于"找了一圈没找到"的收尾。实战少用(容易看错),但面试爱考语义。

日常循环优先用这两个内置,而不是手动维护索引:

```python
for i, name in enumerate(["a", "b"], start=1):   # 带下标
    print(i, name)                               # 1 a / 2 b
for x, y in zip([1, 2], ["a", "b"]):             # 并行遍历
    print(x, y)                                  # 1 a / 2 b
```

## 五、`match`:结构化模式匹配(3.10+)

`match` 不是 C 的 `switch`——它按**结构**解构并绑定变量:

```python
def kind(cmd):
    match cmd:
        case ["go", direction]:       # 序列模式 + 绑定
            return f"go {direction}"
        case {"action": act}:         # 映射模式
            return f"action {act}"
        case [x, y] if x == y:        # 守卫 guard
            return "pair equal"
        case _:                       # 通配(default)
            return "unknown"

print(kind(["go", "north"]))   # go north
print(kind({"action": "jump"}))# action jump
print(kind([3, 3]))            # pair equal
print(kind(42))                # unknown
```

它能匹配字面量、序列、映射、类(`case Point(x=0, y=0)`)、带守卫 `if`、用 `|` 组合。比一长串 `if/elif` 处理"形状各异的数据"清爽得多。注意 `case Foo():` 是类模式,而光写一个裸名字 `case foo:` 是**捕获**(总匹配并绑定),别混。

## 六、推导式(comprehensions)

把"建一个新序列"的循环压成一行,且通常比手写循环快:

```python
squares = [x*x for x in range(5)]              # list
evens = {x for x in range(10) if x % 2 == 0}   # set
idx = {c: i for i, c in enumerate("abc")}      # dict: {'a':0,'b':1,'c':2}
gen = (x*x for x in range(5))                  # 生成器(惰性,见第 07 章)
```

支持多重 `for` 和 `if` 过滤,但嵌套别太深,否则不如普通循环可读。

### 关键差异:推导式变量不泄漏,循环变量泄漏

Python **没有块级作用域**——`if`/`for` 不开新作用域。所以普通 `for` 的循环变量在循环后**还活着**:

```python
for j in range(3):
    pass
print(j)        # 2 —— j 泄漏到外面了

[i for i in range(3)]
print(i)        # NameError —— 推导式有自己的作用域,i 不泄漏
```

推导式(以及生成器表达式)在 Python 3 里**自带一层作用域**,内部变量不污染外面;而 `for`/`while`/`if` 不会。这点 Java/Go 程序员尤其要记:你们的 `{}` 是块级作用域,Python 只有**函数**和**推导式**开作用域。

## 七、海象运算符 `:=`(3.8+)

在表达式里**顺便赋值**,省掉"先算一遍再判断"的重复:

```python
data = [1, 2, 3]
if (n := len(data)) > 2:
    print(f"长度 {n} 超标")        # 长度 3 超标

# 典型:边读边判
# while (line := f.readline()):
#     process(line)
```

别滥用——只在能消除明显重复或让循环更紧凑时用,否则伤可读性。

## 八、解包(unpacking)

```python
a, b = 1, 2                  # 多重赋值
a, b = b, a                  # 交换,无需临时变量

first, *rest = [1, 2, 3, 4]  # 星号收集剩余
print(first, rest)           # 1 [2, 3, 4]

f, *mid, last = [1, 2, 3, 4, 5]
print(f, mid, last)          # 1 [2, 3, 4] 5
```

定义函数时 `*args` 收集多余位置参数、`**kwargs` 收集多余关键字参数;调用时 `*`/`**` 把序列/字典**摊开**成实参(第 04 章细讲):

```python
def g(a, b, c):
    return a + b + c
nums = [1, 2, 3]
print(g(*nums))              # 6 —— 把 list 摊成三个位置参数
d = {"a": 1, "b": 2, "c": 3}
print(g(**d))                # 6 —— 把 dict 摊成关键字参数
```

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 条件 | 必须是 `boolean` | 任意对象,按真值性判断 |
| `&&`/`\|\|` | 返回 `boolean` | `and`/`or` 返回**操作数本身** |
| 区间判断 | `1 < x && x < 10` | `1 < x < 10` 链式,等价且 `x` 只算一次 |
| switch | `switch` 按值跳转 | `match` 按**结构**解构并绑定 |
| 块级作用域 | `{}` 内变量出块即亡 | 仅函数/推导式开作用域;`for`/`if` 变量泄漏到外层 |
| 多返回值 | Go 原生 `a, b :=`;Java 无 | 元组解包 `a, b = f()`,星号收集 `a, *rest = ...` |

## 章末面试卡

**Q1. `if x:` 和 `if x is not None:` 有什么区别?**
`if x` 用真值性,对 `None`、`0`、`""`、`[]`、`{}` 都为假;`if x is not None` 只判"是不是 None"。当 `0`/空容器是合法值、你只想区分"有没有给"时,必须用 `is not None`,否则会把合法的空值当成缺失。

**Q2(猜输出). `print(0 or "a", "b" and "c", [] or 0)`**
`a c 0`。`or` 返回第一个真值或最后一个值;`and` 返回第一个假值或最后一个值。`0 or "a"`→"a",`"b" and "c"`→"c",`[] or 0`→0。

**Q3. `for...else` 的 `else` 什么时候执行?**
循环**没有被 `break` 中断**地正常结束时执行(包括循环体为空)。一旦 `break`,`else` 跳过。常用于"遍历找目标,没找到则……"。

**Q4(猜输出).**
```python
[i for i in range(3)]
for j in range(3): pass
print(j)
try: print(i)
except NameError: print("no i")
```
`2` 然后 `no i`。`for` 循环变量 `j` 泄漏到外层(值为最后一次的 2);推导式变量 `i` 有独立作用域,外面访问报 `NameError`。

**Q5. `match` 和 `switch` 有什么不同?**
`match` 是结构化模式匹配:能按序列/映射/类的**结构**解构并绑定变量、带守卫 `if`、用 `|` 组合,而不只是按单一值跳转。注意裸名字 `case x:` 是捕获(总匹配),类匹配要写 `case Foo(...)`。
