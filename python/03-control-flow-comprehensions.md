# 03 · 控制流、推导式、解包

> **为什么这章重要**:控制流人人会写,但 Python 在几个点上藏着"看起来像 A、其实是 B"的语义:真值性让 `if x` 不只是判 `None`、`and`/`or` 返回的不是布尔、`for...else` 的 `else` 不在你以为的时候跑、推导式变量不泄漏但循环变量泄漏。这些既是 bug 源,也是高频"猜输出"。

## 〇、先建地图:Python 内核四原语

从 Go/Java 过来常觉得 Python「语法又多又杂」——这感觉**一半是真的**(Python 三十年层层加糖,表面积确实比刻意做小的 Go 大),**一半是错觉**:那些花样语法 90% 是**糖**,底下就靠四条原语撑着。先把这四条钉死,后面每个「新语法」你都能挂回去,而不是一个个孤立地背。

| 原语 | 一句话 | 它解释了哪些「看似不相干」的语法 |
|---|---|---|
| **① 万物皆对象,名字只是绑定** | 变量不是盒子,是贴在对象上的标签;赋值 = 重新贴标签 | `a = b`、函数当值传递、`x is None`、可变默认参数的坑(详见[第 01 章](01-names-objects-memory.md)) |
| **② 可迭代协议** | 「能被 `for` 走一遍」是统一协议,凡实现它的都能套用同一批工具 | `for`、`enumerate`、`zip`、`*args`、推导式、生成器([第 07 章](07-iterators-generators-context-managers.md)) |
| **③ 真值性** | 每个对象天生有真假,不止 `bool` | `if x:`、`if not seq:`、`a or default`、`while data:`(本章 §一、§二) |
| **④ 结构解构** | 按「形状」把零件拆出来、就地绑定成变量 | 解包赋值 `a, b = ...`、`for i, name in ...`、`match`/`case`(本章 §五、§八) |

**关键:这四条会反复串台。** 你最容易卡住的 `enumerate(...)` 和 `case ["go", direction]`,根子其实是**同两条**——②可迭代(产出一串元组)+ ④解构(把元组拆成变量)。语法长得不一样,脑子里是**一个概念**。本章后面每出现一个「新花样」,先问自己它落在哪条原语上,杂乱感会塌掉一大半。

> 配套的取舍判断力(资深标志):不是把所有花样都练到能默写,而是知道**哪些该躲**——`for...else`、深层嵌套推导式、`match` 写业务……都属于「读得懂、能讲语义」即可,日常代码少写。本章会逐个标注。

## 〇之二、符号地图:括号 `( )` 到底在干嘛(给 Java/Go 来的)

> 这节专治一个具体卡点:满屏的 `( )` 看不出在干嘛。从 Java/Go 过来会觉得「Python 的括号语义太多」——**但真正比你已会的多出来的只有两个**(元组、生成器表达式),其余完全一样。先给一把钥匙,任何一个 `(` 都能当场判出来。

### 一把钥匙:看 `(` 左边是不是「一个值」

| `(` 左边是…… | 它就是 | 例子 |
|---|---|---|
| 一个能求值的东西(名字、`)`、`]`、`.属性`) | **调用 call**:把左边那个可调用对象叫起来 | `f(x)`、`obj.m()`、`Class(...)`、`(lambda: 1)()` |
| 空的(行首,或紧跟在 `=` `,` `return` `(` `[` 之后) | **不是调用**,只是「括起来」,具体看里面 ↓ | 见下表 |

> 跟空格无关:`print (x)` 加了空格照样是调用——看的是**语法位置**(左边有没有一个完整的值),不是贴不贴着。这点 Java/Go 一致,不是新东西。

左边是「空的」时,再看**括号里有什么**:

| 括号里…… | 它就是 | 例子 |
|---|---|---|
| 有逗号,或者空 | **元组 tuple**(原语④的常客) | `()` 空元组、`(1, 2)`、`(1,)` 单元素 |
| 有 `for` | **生成器表达式**(惰性,见 §六、[第 07 章](07-iterators-generators-context-managers.md)) | `(x*x for x in xs)` |
| 就一个表达式、没逗号 | **纯分组**:调优先级 / 跨行续行 | `(a + b) * c`、`from m import (a, b)` 换行 |

### 逗号才是 tuple 的本体,括号只是边界

最反直觉、也最该钉死的一条:**造元组的是逗号,不是括号。**

```python
t = 1, 2, 3      # 这就是元组,根本没括号
print(type(t))   # <class 'tuple'>

x = (1)          # 不是元组!就是 int 1,括号只在调优先级
y = (1,)         # 这才是单元素元组——逗号撑起来的
z = ()           # 空元组(唯一真靠括号的特例)
```

所以 `return a, b`、`a, b = b, a` 里那串看不见括号的东西,全是元组在背后干活(原语④结构解构,见 §八)。

⚠️ **call 括号里的逗号是分隔实参,不是造元组**——同一个逗号,在不在 call 括号里意思相反:

```python
f(a, b)      # 两个参数 a、b
f((a, b))    # 一个参数:元组 (a, b)
```

### genexp 的括号能和 call 括号合并

生成器表达式当**唯一实参**时,不用套两层括号:

```python
sum(x*x for x in range(5))     # ✅ 30:call 的 () 顺便当 genexp 的边界,不用套两层
sorted((3, 1, 2))              # 想把「一个元组」整个传进去,得自己加括号
sorted(3, 1, 2)                # ✗ TypeError:被当成三个参数
```

### 收口:三种括号一张表(同一把钥匙)

`[ ]` 和 `{ }` 也吃这套「左边有没有值 = **操作** vs **字面量**」:

| | 左边有值(操作) | 左边没值(字面量 / 展示) |
|---|---|---|
| `( )` | 调用 `f(x)` | 元组 `(1,2)` · 分组 `(a+b)` · 生成器 `(x for …)` |
| `[ ]` | 下标·切片·泛型 `a[0]`、`a[1:3]`、`list[int]` | 列表 `[1,2]` · 列表推导 `[x for …]` |
| `{ }` | (没有这种用法) | 字典/集合 `{...}` · 字典/集合推导 · f-string 占位 |

`def f(a, b):` 的参数列表、`class C(Base):` 的基类列表,视觉上都是「名字后面跟 `()`」——归到「像调用」那一档记就行,不用单开一类。

> **塌缩一下**:你以为 `()` 有七八种意思,其实是「**调用 + 分组**(你早会的两个,跟 Java/Go 一样)」加「**元组 + 生成器表达式**(Python 真正新增的两个)」。def/class 的括号是「调用的同款长相」,海象 `:=`、解包 `*`/`**` 是**别的符号**(见 §七、§八),不算在 `()` 头上。爆炸感到这里就该塌一大半。

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

## 三之二、三元条件表达式 `x if cond else y`

Python 的三元和 C/Java/Go 的 `cond ? x : y` **语序相反**:把**正常值放最前**,条件塞中间。

```python
status = "成年" if age >= 18 else "未成年"
#        └真时取这个┘    └─条件─┘   └假时取这个┘
```

读法是「**取 `x`,如果 `cond`,否则取 `y`**」——主语(想要的值)先说,条件后置。它是**表达式**(求值出一个值),不是语句,所以能嵌进 return、推导式、函数实参:

```python
return n if n < 2 else fib(n-1) + fib(n-2)
labels = ["偶" if x % 2 == 0 else "奇" for x in xs]
```

- 别和 `x or default` 混:`a or b` 在 `a` 为**任意假值**(`0`/`""`/`[]`)时就 fallback;而 `a if a is not None else b` 只在 `a` 是 `None` 时 fallback(见 §二末的警告)。当 `0`/空串是合法值,必须用三元。
- 链式可以但伤可读:`"a" if c1 else "b" if c2 else "c"` 等价于右结合嵌套,超过一层就改用 `if` 语句或字典分派。

## 四、循环与 `else` 子句

`for`/`while` 可以跟一个 `else`,它在**循环自然跑完、没被 `break` 打断时**执行——违反所有人的直觉。关键:`else` 是配 **`break`** 用的,用来区分"中途 break 跳出"和"整圈跑完":

```python
def check(nums):
    for n in nums:
        if n < 0:
            print(f"发现负数 {n},中止")
            break
    else:                       # 没 break = 整圈都没负数才执行
        print("全部非负,通过")

check([1, 2, -3])               # 发现负数 -3,中止
check([1, 2, 3])                # 全部非负,通过
```

用 Java/Go 的脑袋类比:它替代了"labeled break + 标志变量"的组合。等价手写版是循环前设 `ok = True`、break 时改 `False`、循环后 `if ok:`。

**陷阱:没有 `break` 时 `else` 是多余的。** 最常见的误用是拿它写"找一圈没找到"的收尾,但循环里用的是 `return` 而非 `break`——这时 `else` 纯属装饰,删掉、把分支往左退一格行为完全一样:

```python
def find(seq, target):
    for v in seq:
        if v == target:
            return "found"
    return "not found"          # 不需要 else:压根没有 break
```

**实战建议(资深共识):** `for...else` 是 Python 公认的设计疣(Guido 自己说该叫 `nobreak`),可读性差、协作里是负分,日常优先换掉:判断在不在用 `if x in seq`,取第一个匹配用 `next((v for v in seq if cond), default)`,收尾逻辑用 early `return`。只有"真要区分 break / 跑完"两种结局时才用它,并**务必加注释**。面试要会讲语义,代码里少写。

日常循环优先用这两个内置,而不是手动维护索引(对应原语 ②可迭代 + ④解构):

```python
for i, name in enumerate(["a", "b"], start=1):   # 带下标
    print(i, name)                               # 1 a / 2 b
for x, y in zip([1, 2], ["a", "b"]):             # 并行遍历
    print(x, y)                                  # 1 a / 2 b
```

**`enumerate` 在干嘛?** Go 里你手动维护计数器(`i := 0; …; i++`),Python 不让你写这个。`enumerate` 把可迭代对象「包」一层,每轮吐出一个 `(下标, 元素)` 的**二元组**:

```python
list(enumerate(["a", "b"]))            # [(0, 'a'), (1, 'b')]
list(enumerate(["a", "b"], start=1))   # [(1, 'a'), (2, 'b')]   ← start 改的是下标从几开始
```

- `start=1` = 下标从 1 数(给人看的编号常用),默认从 0。
- `for i, name in …` 这行的 `i, name` 是**解构**(原语④):每轮拿到的 `(1, "a")` 被自动拆成 `i=1`、`name="a"`,所以打印出 `1 a`。

`zip` 同理:把多个序列「拉链」对位组成元组,`x, y` 再解构出来。两者都是「②产出一串元组 → ④当场拆开」的同一套路——记住这一条,就不用把它们当两个孤立语法。

**`zip` 的三个坑(Java/Go 没有对应物,容易栽):**

```python
list(zip([1, 2, 3], ["a", "b"]))   # [(1, 'a'), (2, 'b')]   ← 第三个 3 被悄悄丢了
```

- **截断到最短,且静默**:长度不齐时 `zip` 停在最短的那个、**不报错**。本该等长的数据被悄悄吞掉,是隐蔽 bug 源。要"短了就报错"用 **`strict=True`**(3.10+):`zip(a, b, strict=True)` 长度不等抛 `ValueError`。要"短了补默认"用 `itertools.zip_longest(a, b, fillvalue=0)`。
- **`zip(*matrix)` 是转置**:`*` 把每一行摊成独立实参,`zip` 再按列重组,行列互换:

```python
matrix = [[1, 2, 3], [4, 5, 6]]
list(zip(*matrix))                 # [(1, 4), (2, 5), (3, 6)]   列变行
rows = [[1, 2], [3, 4]]
cols = list(zip(*rows))            # 同一招也能把 (键, 值) 对拆回两列
```

- **惰性、只能走一遍**:`zip(...)`/`enumerate(...)` 返回的是迭代器不是 list,迭代一次就空了;要复用或要下标随机访问,先 `list(...)`。

## 五、`match`:结构化模式匹配(3.10+)

最关键的一句:`match` **不是** C/Java 的 `switch`。`switch` 比的是「值**相不相等**」;`match` 比的是「**形状对不对得上**」,对上了还顺手把里面的零件**拆出来绑成变量**(原语④的最强形态)。

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

**逐条拆开看(`cmd` 是传进来的值):**

- `case ["go", direction]:` 要**同时**满足三件事才命中:① `cmd` 是个**列表**;② 长度**正好 2**;③ 第 0 格**等于**字面量 `"go"`。而第 1 格**不比较**、任何值都接受,并被**抓出来塞进 `direction`**。
- `case {"action": act}:` ——`cmd` 是个**含 `"action"` 键的字典**就命中(多几个别的键也算),该键的值绑进 `act`。
- `case [x, y] if x == y:` ——先匹配形状(两元素列表),**再加一道守卫** `if x == y`;形状对但 `x != y` 就跳过这条、继续往下找。
- `case _:` ——`_` 是通配符,**永远命中**,等同 `switch` 的 `default`,兜底。

**一句话记牢:写死的格子要相等,变量的格子只负责接值。** 这就是它跟 `switch` 的本质区别——`switch case "go north"` 只能整体比一个值;`match` 能「认出结构 + 顺手拆零件」:

```python
kind(["go", "north"])   # ✅ 命中,direction = "north"
kind(["go", 42])        # ✅ 命中,direction = 42      ← 第二格是数字也行,不比较
kind(["stop", "north"]) # ❌ 第 0 格不是 "go"
kind(["go"])            # ❌ 长度 1,不是 2
kind(["go", "a", "b"])  # ❌ 长度 3
kind("go north")        # ❌ 这是字符串不是列表
```

### `match` 还能匹配什么(类模式 + OR)

除了序列/映射,常用的还有**类模式**和 **OR 模式**:

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

def where(p):
    match p:
        case Point(x=0, y=0):   # 类模式:类型对得上 + 属性对得上
            return "原点"
        case Point(x=0, y=y):   # x 必须是 0;y 任意,抓出来绑进变量 y
            return f"y轴 {y}"
        case 1 | 2 | 3:         # OR 模式:任一命中即可
            return "small int"
        case str() | bytes():   # 类型选择:是 str 或 bytes(空括号=只判类型)
            return "文本"
        case _:
            return "其他"
```

### 头号坑:裸名字永远是「捕获」,不是「比较」

从 `switch` 过来最容易中招的一条——想拿一个常量去比相等:

```python
NORTH = "north"
match direction:
    case NORTH:        # ⚠️ 不是"等于 NORTH"!这是把 direction 绑进新变量 NORTH,无条件命中
        ...
    case "south":      # 想再加分支?下面这行直接让整段编译失败 ↓
        ...
# SyntaxError: name capture 'NORTH' makes remaining patterns unreachable
```

`case NORTH:` 里的 `NORTH` 被当成**待绑定的变量名**,`match` 把 `direction` 的值塞进它、然后**总命中**。好消息:只要后面还有别的 `case`(哪怕只是 `case _`),Python **直接编译期报 `SyntaxError`**,等于替你抓出了这个坑——报错里 "name capture makes remaining patterns unreachable" 说的就是"这个裸名永远匹配,后面的全够不着"。

真正阴险的是它**作为最后一个 / 唯一一个 `case`** 时:能编译、静默生效,一个你以为不该命中的值照样掉进来。要"和某常量比相等",名字必须**带点**(`case Color.RED:`、`case status.OK:`)或改用守卫(`case x if x == NORTH:`)。

**一句话记牢:写死的值要么是字面量、要么带 `.`;光秃秃的名字一律是捕获。** 这也呼应前面 `["go", direction]` 的规律——`"go"` 是字面量(比较),`direction` 是裸名(捕获)。

`as` 模式则可以"匹配并起名":`case [Point() as p, _]:` ——第 0 格匹配 `Point` 类型、同时把它绑到 `p` 备用。

**实战提醒:** `match` 虽强,日常业务很少真用得上(它擅长「形状各异的数据」:解析 AST、解析协议/命令、拆嵌套 JSON)。面试**认得出、讲得清"结构匹配 + 捕获"的语义和上面两个坑**即可,别强行拿它替代普通 `if/elif`。

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

**一句话:`:=` 让「赋值」变成一个能吐出值的表达式。** 普通赋值 `=` 是**语句**、不产生值,所以进不了只接受表达式的地方;`:=` 既赋值、又把值吐出来,于是 `if`/`while` 条件、推导式里都能「边赋值边用」,省掉「先算一遍再判断」的重复:

```python
data = [1, 2, 3]
if (n := len(data)) > 2:        # ① 算 len(data) ② 存进 n ③ 整个 (n:=…) 取值为 3 ④ 跟 2 比
    print(f"长度 {n} 超标")     # n 在 if 体里、乃至 if 之后都还能用
```

### 它和 Go 的 `:=` 同形异义,别混

Java/Go 程序员第一眼会把它当成 Go 的 `:=`——**长得一样,根本不是一回事**:

| | Go `:=` | Python `:=` |
|---|---|---|
| 本质 | 短变量**声明**,是**语句**(不产值) | 赋值**表达式**(赋值 + 返回值) |
| 用在哪 | 到处都是,造新变量的常规手段 | 少数场景内联捕获值的**特例** |
| 造新变量的常规写法 | 就是 `:=` | 是 `=`,`:=` 只是特例 |
| 能否写进 if 条件 | **不能**,Go 用 `if 初始化; 条件` 另解 | **能**,这正是它的用途 |

```go
// Go::= 是语句,进不了条件。边赋值边判断要靠 "初始化; 条件" 语法
if n := len(data); n > 2 {   // 分号前是语句,分号后才是条件
    // 用 n
}
```

### Python 普通 `=` 为什么进不了 if(以及为什么符号这么丑)

直接在条件里写普通赋值,会**编译期报错**:

```python
if n = len(data) > 2:   # ❌ SyntaxError,根本不让你写
```

这是**故意**的历史设计:C/Java 允许 `if (x = 5)`(赋值)而你本想写 `if (x == 5)`(比较)——少打一个 `=`,程序不报错却逻辑全错,是经典 bug 源头。Python 几十年来干脆禁止「赋值当表达式」,从根上杜绝。3.8 的 `:=`(PEP 572)才把这能力补回来,但**故意选了个又特殊又显眼的符号**,让你永远不会和 `==` 搞混、也不会手滑误打。

### 三个限制 / 坑(都和 Go 直觉相反)

**1. 不是声明,`n` 新旧通吃。** Python 没有「声明 vs 赋值」的区分,`:=` 既能造新名字、也能**覆盖已存在的名字**——这点和 Go「`:=` 必须至少有一个新变量」正好相反:

```python
n = 999
if (n := len(data)) > 2:     # 合法!直接把已存在的 n 覆盖成 3
    ...
print(n)                     # 3 —— 原来的 999 没了
```

**2. 目标必须是光秃秃的名字**,不能是属性或下标:

```python
if (n := len(data)) > 2:        # ✅ 普通名字
if (obj.size := len(data)): ...  # ❌ SyntaxError,属性不行
if (d['k'] := len(data)): ...    # ❌ SyntaxError,下标不行,退回普通 = 语句
```

**3. 会漏出去。** Python 没有块作用域,`n := …` 赋的 `n` 会**泄漏到整个函数**(对照第六节:`for` 循环变量同样泄漏,只有推导式不漏)。Go 里 `if n := …; …` 的 `n` 是 if 块内的新变量,出了块就没——这点 Python 没有。

### 什么时候真正值得用(`if` 反而最鸡肋)

| 场景 | 价值 |
|---|---|
| `if` 条件 | 锦上添花,省一行;**完全可以拆成两行**,可有可无 |
| `while` 条件 | 避免重复读取/计算 |
| 推导式 | **刚需**,没有别的写法 |

`if` 里它纯粹是糖——`n = len(data)` 写在上一行、再 `if n > 2:` 效果一样。它真正**离不开**的是下面两处:

```python
# while:不用 walrus 就得「循环外读一次、循环尾再读一次」,重复代码
while (line := f.readline()):
    process(line)

# 推导式:这是一个表达式,里面插不进赋值语句;想让 f(x) 只算一次,
# 既当过滤条件又当结果,只能靠 walrus(否则被迫算两次)
[y for x in data if (y := f(x)) > 0]
```

**一句话记牢:`:=` 解决的是「赋值不能当表达式」这个限制,让你在已经计算/判断某个值的当口顺手把它留下来——别用 Go「必须有新变量、且是常规写法」的眼光看它。**

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

**进阶几招(都从同一个「按形状拆 / 拼」长出来):**

```python
# 嵌套解包:按结构层层拆
(a, (b, c)) = (1, (2, 3))            # a=1 b=2 c=3
for i, (k, v) in enumerate(d.items()):   # 常见:枚举 + 二层拆
    ...

# 字面量里 splat:摊开来拼新容器(不是函数调用)
merged = [*nums, *[4, 5]]            # [1, 2, 3, 4, 5]   拼接成新 list
combined = {**d, "d": 4}             # {'a':1,'b':2,'c':3,'d':4}  合并 dict(右边同名键覆盖)
union = {*nums, *[3, 4]}             # {1, 2, 3, 4}      集合并集

# 占位丢弃:_ 是约定俗成的"我不要这个"
_, x, *_ = [10, 20, 30, 40]          # 只取第 2 个 x=20,其余全扔
```

**数量对不上会炸**(比 Go 严):`a, b = [1, 2, 3]` 抛 `ValueError: too many values to unpack`;少了抛 `not enough values`。带星号那格则**最贪心、也能为空**:`a, *rest = [1]` → `a=1, rest=[]`,不报错。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 条件 | 必须是 `boolean` | 任意对象,按真值性判断 |
| `&&`/`\|\|` | 返回 `boolean` | `and`/`or` 返回**操作数本身** |
| 区间判断 | `1 < x && x < 10` | `1 < x < 10` 链式,等价且 `x` 只算一次 |
| 三元 | `cond ? x : y` | `x if cond else y`(正常值在前,**语序相反**) |
| switch | `switch` 按值跳转 | `match` 按**结构**解构并绑定;裸名字是捕获不是比较 |
| 块级作用域 | `{}` 内变量出块即亡 | 仅函数/推导式开作用域;`for`/`if` 变量泄漏到外层 |
| 多返回值 | Go 原生 `a, b :=`;Java 无 | 元组解包 `a, b = f()`,星号收集 `a, *rest = ...` |
| 并行遍历 | 手写多重下标 | `zip` 对位成元组、`zip(*m)` 转置;**截断到最短**,`strict=` 才报错 |

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
