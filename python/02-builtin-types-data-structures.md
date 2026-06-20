# 02 · 内置类型与数据结构

> **为什么这章重要**:数据结构是日常代码的水和电。Python 的内置类型有几处和 Java/Go 直觉冲突——整数无限大、`/` 永远给浮点、`bool` 居然是 `int`、`dict` 保插入序、`str` 和 `bytes` 泾渭分明。把这些和"什么时候用哪个容器、各操作多快"一起内化,既少踩坑也答得出选型题。

## 一、数值

### int:任意精度

Python 的 `int` **没有上限**,要多大有多大,自动按需扩展:

```python
print(2 ** 100)   # 1267650600228229401496703205376,不溢出
```

没有 `int`/`long`/`BigInteger` 的区分,一个 `int` 通吃。代价是大整数运算比定长整数慢,但你不用操心溢出——这点比 Java/Go 省心得多。

### float、`/` 与 `//`

```python
print(7 / 2)    # 3.5   —— / 永远返回 float,即使整除
print(7 // 2)   # 3     —— // 是地板除(向下取整)
print(7.0 // 2) # 3.0   —— 操作数有 float,结果也是 float
```

**`/` 总是真除法返回 `float`** 是 Python 3 的硬规则(Python 2 不是,这是经典迁移坑)。要整数商用 `//`。

负数地板除最容易栽——`//` 向**负无穷**取整,不是向 0 截断;`%` 的结果符号**随除数**:

```python
print(-7 // 2)  # -4   (-3.5 向下取整到 -4,不是 Java 的 -3)
print(-7 % 2)   # 1    (余数符号跟除数 2 走)
print(7 % -2)   # -1   (跟除数 -2 走)
```

恒等式 `a == (a // b) * b + (a % b)` 始终成立。Java/Go 的 `/` 对整数是向 0 截断、`%` 符号随被除数,正好相反——跨语言移植取模逻辑时务必小心。

### decimal 与 fraction:别用 float 算钱

float 是 IEEE 754 二进制浮点,十进制小数大多存不精确:

```python
print(0.1 + 0.2)            # 0.30000000000000004
print(0.1 + 0.2 == 0.3)     # False
```

这不是 Python 的 bug,是所有语言的二进制浮点通病。涉及金额、需要精确十进制时用 `decimal.Decimal`;需要精确分数用 `fractions.Fraction`:

```python
from decimal import Decimal
print(Decimal("0.1") + Decimal("0.2"))   # 0.3  (注意用字符串构造,别用 Decimal(0.1))
```

### `round()` 是银行家舍入(五成双)

内置 `round()` **不是"逢五进一"**,而是 **round-half-to-even**(银行家舍入)——正好 `.5` 时向**最近的偶数**靠:

```python
print(round(0.5), round(1.5), round(2.5), round(3.5))   # 0 2 2 4 —— 全进到偶数
```

Java 的 `Math.round`、手算、Excel 默认都是"逢五进一",会得到 `1 2 3 4`。这是**静默给错结果**的坑:报表、计费、对账里用 `round` 凑整,数字就和别的系统对不上。更阴的一层——浮点本身存不精确,`round(x, n)` 看的是 float 真实存储值,不是字面量:

```python
print(round(2.675, 2))   # 2.67(不是 2.68)—— 2.675 实际存成 2.67499…
```

要"逢五进一"或精确十进制舍入,用 `decimal.Decimal` 显式指定模式:

```python
from decimal import Decimal, ROUND_HALF_UP
print(Decimal("2.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP))   # 3
```

心智:**`round()` 只配"差不多就行"的展示;算钱、对账、要可预测进位规则,一律走 `Decimal` + 显式 rounding 模式。**

### `float('nan')`:不等于自己,还会骗过 `in`

`nan`(非数)有个 IEEE 754 规定的怪癖——**它不等于任何值,包括它自己**:

```python
nan = float("nan")
print(nan == nan)    # False
print(nan != nan)    # True   —— 唯一 != 自己的值
```

这条很多人知道,但 Python **容器**里的连锁反应才是真坑。`in`、`list.count`、`index` 出于性能会**先比 identity(`is`)再比 `==`**,于是"同一个 nan 对象"能被找到,而 `==` 语义又是假的:

```python
print(nan in [nan])                      # True  —— 先比 is,命中同一个对象
print(float('nan') in [float('nan')])    # False —— 不同对象,只能靠 ==,失败
print(sorted([3, nan, 1, 2]))            # [3, nan, 1, 2] —— nan 让排序失去意义,却不报错
```

后果:含 nan 的数据**去重、排序、查找全不可靠,而且不报错**。实务上在入口就用 `math.isnan(x)` 拦掉或替换。**判 nan 必须用 `math.isnan()`,不能写 `x == nan`(永远 False)。**

### bool 是 int 的子类

```python
print(True + True)      # 2
print(True == 1)        # True
print([10, 20][True])   # 20  —— True 当下标就是 1
print(isinstance(True, int))  # True
```

`bool` 继承自 `int`,`True == 1`、`False == 0`。这偶尔有用(`sum(flags)` 数有几个真),但也会埋坑:别把 `True`/`1` 混用当字典 key,`{True: "a", 1: "b"}` 会塌成一个键。

## 二、文本与字节:str vs bytes

这是 Java 工程师最该重新校准的地方。Java 的 `String` 内部是字符序列,`byte[]` 是字节,转换时编码常常隐式发生、埋下乱码。Python 3 把两者**彻底分开**,且强制你显式编码:

- **`str`**:不可变的 **Unicode 码点**序列。`len(s)` 数的是字符数。
- **`bytes`**:不可变的**字节**序列(0–255)。`bytearray` 是它的可变版。
- 两者之间靠 **`encode` / `decode`** 显式转换,且必须指定编码:

```python
s = "héllo"
b = s.encode("utf-8")        # str → bytes
print(len(s), len(b))        # 5 6  —— é 在 UTF-8 占 2 字节,所以字节比字符多
print(b.decode("utf-8"))     # bytes → str:héllo
```

**`str` 永远是文本,`bytes` 永远是原始字节。** 网络/文件 IO、哈希、加密的边界上拿到的是 `bytes`,要当文本处理就得先 `decode`。Python 3 不会帮你隐式转换(Python 2 会,于是到处是 `UnicodeDecodeError`)——显式反而救了你。

f-string 是日常拼接首选,可读且快:

```python
name, n = "Ann", 3
print(f"{name} has {n} items, {n*2=}")   # Ann has 3 items, n*2=6
```

f-string 还有一套**格式规约**(冒号后),控制精度/对齐/进制,日常和面试常用:

```python
import math
f"{math.pi:.2f}"      # '3.14'      保留 2 位小数
f"{42:>6}"            # '    42'    右对齐宽 6(<左 ^居中)
f"{255:08b}"          # '11111111'  补零的二进制(x 十六进制 o 八进制)
f"{1234567:,}"        # '1,234,567' 千分位
f"{0.1234:.1%}"       # '12.3%'     百分比
```

### Unicode 规范化:看起来相等却 `!=`

同一个「字形」可以由不同的码位序列表示。以 `é` 为例:预组合形式(NFC)是 1 个码位 U+00E9;分解形式(NFD)是基字符 `e` 加组合尖音符 U+0301,共 2 个码位。两者肉眼无法区分,但 Python 的 `==` 按码位逐个比较——结果是 `False`。`len` 同理:它数的是码位(code point),不是字形(grapheme),所以这两个 `é` 的 `len` 分别是 1 和 2。

解法是在比较、去重、当 dict key、入库之前,先用 `unicodedata.normalize` 统一到同一形式:
- `"NFC"`:合成(最短),网络协议和数据库入库首选;
- `"NFD"`:完全分解;
- `"NFKC"` / `"NFKD"`:在 NFC/NFD 基础上做**兼容折叠**——全角→半角、`①`→`1` 等。兼容折叠会丢失格式信息,用于搜索归一化可以,存档慎用。

用户输入、文件名、跨系统数据来源不一,不做规范化就会出现「搜不到 / 去重失败 / `==` 为 False」的诡异 bug。

**大小写比较用 `casefold()`,不是 `lower()`**:`casefold()` 是更彻底的大小写折叠,专为不区分大小写的比较而设计——`lower()` 只做基本映射,不处理德语 `ß`→`ss` 这类多字符展开,`casefold()` 则全覆盖。

```python
import unicodedata
a = "é"          # 'é' 预组合:1 个码位 U+00E9
b = "é"         # 'é' 分解:'e' + 组合尖音符 U+0301,2 个码位
print(a == b)         # False —— 肉眼相同,码位不同
print(len(a), len(b)) # 1 2 —— len 数码位,不数字形

n = unicodedata.normalize
print(n("NFC", a) == n("NFC", b))   # True —— 先规范化再比

print("ß".casefold() == "ss")       # True —— casefold 比 lower 更激进
print("ß".lower())                  # 'ß' —— lower 不折叠
```

## 三、序列:list / tuple / range

| 类型 | 可变? | 典型用途 |
|------|--------|----------|
| `list` | 可变 | 同质或异质的有序集合,日常默认 |
| `tuple` | 不可变 | 固定记录、可作 dict key/set 元素、函数多返回值 |
| `range` | 不可变、惰性 | 循环计数,不实际存元素(省内存) |

`tuple` 不只是"不可变的 list"——因为不可变所以**可哈希**,能当 `dict` 键或放进 `set`;`list` 不行。`range(1_000_000)` 不会真造一百万个数,它惰性按需产出(Python 3 的 `range` 是对象不是 list)。

### `range` 的三种形式

`range` 循环里天天用,但参数语义和 Java/Go 的 `for (i=0; i<n; i++)` 不是逐字对应,值得说清三种形式:

```python
range(stop)               # 0,1,…,stop-1         start 默认 0、step 默认 1
range(start, stop)        # start,…,stop-1
range(start, stop, step)  # 按 step 跳,可负
```

```python
list(range(5))            # [0, 1, 2, 3, 4]       不含 5
list(range(2, 5))         # [2, 3, 4]
list(range(0, 10, 2))     # [0, 2, 4, 6, 8]
list(range(10, 0, -1))    # [10, 9, …, 1]         负步长倒序
```

**两个和别的语言差异最大的直觉:**

- **左闭右开**:含 `start`、**不含 `stop`**。所以 `range(len(xs))` 正好覆盖全部合法下标 `0..len-1`,天然不越界——这是它和切片 `[start:stop]`、`enumerate` 共用的同一套区间约定,**记一次用三处**。
- **倒序必须靠负 `step`**,没有"自动反向":`range(5, 0)` 是**空**的(start≥stop 且 step>0 → 一个都不产)。要倒序写 `range(n-1, -1, -1)`,或更易读的 `reversed(range(n))`。

`range` 不只是"能 for 的东西",它是个**惰性序列对象**,支持序列操作而不展开成 list:

```python
r = range(0, 100, 2)
len(r)        # 50               O(1),不遍历
r[10]         # 20               支持索引
r[5:8]        # range(10, 16, 2) 切片结果还是 range
50 in r       # True             O(1) 解方程判断,不逐个扫
49 in r       # False
```

最后一条尤其反直觉:`x in range(...)` 是**常数时间**(它按等差数列算,不像 `x in list` 要逐个比)。但日常别把它当容器用——真要存一串数就 `list(range(...))`。

### 切片(slicing)

切片是 Python 序列的瑞士军刀,语法 `seq[start:stop:step]`,几个关键行为:

```python
a = [0, 1, 2, 3, 4, 5]
print(a[1:3])      # [1, 2]      左闭右开
print(a[::2])      # [0, 2, 4]   步长 2
print(a[::-1])     # [5,4,3,2,1,0] 步长 -1 = 反转
print(a[-2:])      # [4, 5]      负索引从尾部数
```

**切片永不越界**(超出范围自动截断为空),但**单个索引越界会报错**——这个不对称常被考:

```python
print([1, 2, 3][5:10])   # []          安全
[1, 2, 3][5]             # IndexError  炸
```

切片还能赋值,甚至改变长度:

```python
a = [0, 1, 2, 3]
a[1:3] = [9, 9, 9]       # 用 3 个元素替换 2 个
print(a)                 # [0, 9, 9, 9, 3]
```

## 四、映射与集合:dict / set

### dict 保插入序(且是语言保证)

```python
d = {}
for k in ["c", "a", "b"]:
    d[k] = 1
print(list(d))   # ['c', 'a', 'b'] —— 按插入顺序,不是哈希顺序
```

从 **3.7 起这是语言规范**(3.6 是 CPython 实现细节),底层用"紧凑 dict"——一个按插入序排列的条目数组 + 一个哈希索引表,既省内存又保序。所以 Python 的 `dict` 不像 Java `HashMap` 那样无序;它更接近 `LinkedHashMap`,但是默认行为。

key 必须**可哈希**(实现了 `__hash__` 且不可变):`str`/`int`/`tuple` 可以,`list`/`dict` 不行。

### dict 的视图是动态的

`keys()`/`values()`/`items()` 返回的是**视图对象**,不是快照——它随 dict 变化:

```python
d = {"a": 1}
ks = d.keys()
d["b"] = 2
print(list(ks))   # ['a', 'b'] —— 视图看得到后加的 b
```

### 遍历时改容器:dict 抛错,list 静默漏删

**一边遍历一边增删同一个容器**是后端常踩的坑,且两类容器表现还不一样。dict/set 会**当场抛 `RuntimeError`**(fail-fast,类似 Java 的 `ConcurrentModificationException`):

```python
d = {1: "a", 2: "b", 3: "c"}
for k in d:
    if k == 2:
        del d[k]        # RuntimeError: dictionary changed size during iteration
```

list **更阴——不报错,而是静默漏删**:

```python
xs = [1, 2, 3, 4, 5, 6]
for x in xs:
    if x % 2 == 0:
        xs.remove(x)    # 不报错
print(xs)               # [1, 3, 5] —— 你以为删光偶数,其实漏了 4
```

原因:list 迭代器按**下标**推进,`remove` 让后面元素整体前移,下一轮下标就**跳过**了补位的那个。正解一律是**别在原容器上边遍历边改**——遍历副本,或推导式重建:

```python
xs[:] = [x for x in xs if x % 2]              # 重建后整体替换;[:] 保持原对象 id
d = {k: v for k, v in d.items() if k != 2}    # dict 同理
```

### get / setdefault / defaultdict

取值带默认、避免 `KeyError` 的地道写法:

```python
d = {"a": 1}
print(d.get("z", 0))           # 0,不报错
d.setdefault("c", []).append(1)  # c 不存在则设为 [] 再 append

from collections import defaultdict
g = defaultdict(list)
g["x"].append(1)               # 首次访问自动建 []
print(dict(g))                 # {'x': [1]}
```

### set / frozenset

`set` 是可变的无序唯一集合,做去重和集合运算;`frozenset` 是不可变版,可作 dict key / set 元素:

```python
print({1, 2, 2, 3})            # {1, 2, 3} 去重
print({1, 2, 3} & {2, 3, 4})   # {2, 3} 交集;| 并,- 差,^ 对称差
```

## 五、复杂度与扩容(够用就好)

常见操作的平均复杂度,选型时心里有数:

| 操作 | list | dict / set |
|------|------|------------|
| 按索引/键访问 | `a[i]` O(1) | `d[k]` O(1) 平均 |
| 末尾增删 | `append`/`pop()` O(1) 摊销 | — |
| 头部增删 | `insert(0,x)`/`pop(0)` O(n) | — |
| 成员判断 `x in` | O(n) | O(1) 平均 |
| 增删任意键 | — | O(1) 平均 |

两条实用结论:

- **频繁判断"在不在"用 `set`/`dict`(O(1)),别用 `list`(O(n))**。
- **频繁在头部增删用 `collections.deque`(两端 O(1)),别用 list**(`pop(0)` 是 O(n))。

`list` 和 `dict` 都靠**过度分配**摊销扩容:list 满了按比例多要一块空间,所以 `append` 平均 O(1) 而非每次都搬;dict 装载因子超阈值时整体扩容并重新散列。细节(紧凑 dict 内存布局、为什么 `append` 是摊销 O(1))在[第 15 章](15-cpython-internals-performance.md)。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 整数 | `int`/`long` 定长会溢出,大数要 `BigInteger`/`math/big` | 单一 `int`,任意精度,不溢出 |
| 整数除 `/` | 向 0 截断,`-7/2 == -3` | `//` 地板除,`-7//2 == -4`;`/` 给 float |
| 取模符号 | 随被除数 | 随除数 |
| 舍入 | `Math.round` 逢五进一 | `round()` 银行家舍入(五成双);要逢五进一用 `Decimal`+`ROUND_HALF_UP` |
| NaN | `Double.NaN`,`==` 也为 false | `float('nan')`,但 `nan in [nan]` 可为 True(容器先比 `is`);判它用 `math.isnan` |
| 循环计数 | `for(i=0;i<n;i++)`,自己控边界 | `range(n)` 左闭右开惰性序列;倒序 `range(n-1,-1,-1)` 或 `reversed(range(n))` |
| 哈希表顺序 | `HashMap` 无序(`LinkedHashMap` 才有序) | `dict` 默认保插入序(语言保证) |
| 遍历时改集合 | `ConcurrentModificationException` | dict/set 抛 `RuntimeError`;**list 静默漏删** |
| 不可变集合作 key | 任意 `equals`/`hashCode` 对象 | 必须可哈希:用 `tuple`/`frozenset`,不能用 `list` |
| Unicode 规范化 | `java.text.Normalizer.normalize(s, NFC)` | `unicodedata.normalize("NFC", s)`;`casefold` ≈ 不区分大小写折叠 |

## 章末面试卡

**Q1. `str` 和 `bytes` 有什么区别?为什么 Python 3 要分开?**
`str` 是不可变 Unicode 码点序列(文本),`bytes` 是不可变字节序列(原始数据),靠 `encode`/`decode` 显式转换且必须指定编码。分开是为了消除 Python 2 时代隐式编码导致的乱码与 `UnicodeError`——边界上拿到 `bytes`,要当文本必须显式 `decode`。

**Q2. `/` 和 `//` 区别?`-7 // 2` 等于几?**
`/` 是真除法,永远返回 `float`(`7/2 == 3.5`);`//` 是地板除,向负无穷取整。`-7 // 2 == -4`(不是向 0 截断的 -3)。`%` 符号随除数,`-7 % 2 == 1`。

**Q3. Python 的 dict 有序吗?怎么实现的?**
有序——3.7 起按**插入顺序**是语言规范。底层是"紧凑 dict":条目按插入序存在一个数组里,另有哈希索引表指向它,既省内存又天然保序。

**Q4. `bool` 是什么类型?`True + True` 等于几?**
`bool` 是 `int` 的子类,`True==1`、`False==0`,所以 `True + True == 2`,`[a, b][True]` 取下标 1。注意别拿 `True` 和 `1` 同时当 dict key,会冲突成一个键。

**Q5(猜输出).**
```python
print([1, 2, 3][5:10], end=" | ")
try:
    print([1, 2, 3][5])
except IndexError:
    print("IndexError")
```
`[] | IndexError`。切片越界安全返回空,单索引越界抛 `IndexError`。

**Q6. 判断元素是否在集合里,用 list 还是 set?为什么?**
用 `set`(或 `dict`):成员判断平均 O(1);`list` 的 `in` 是 O(n) 线性扫描。数据量大或频繁判断时差距巨大。

**Q7. 两个肉眼完全相同的字符串,`==` 却是 False,怎么回事?**
很可能是 Unicode 规范化不同——同一字形可由「预组合(NFC,1 码位)」或「分解(NFD,基字符+组合符,多码位)」表示,`==` 按码位比就不等,`len` 也不同。修法:比较/去重/做 key 前先 `unicodedata.normalize("NFC", s)` 统一。不区分大小写用 `casefold()`(比 `lower()` 更彻底,如 `ß`→`ss`)。

**Q8(猜输出).** `round(0.5), round(1.5), round(2.5)` 是几?
`0 2 2`。`round()` 是银行家舍入(round-half-to-even),正好 `.5` 时向最近偶数靠,不是逢五进一。要逢五进一用 `decimal.Decimal(...).quantize(..., rounding=ROUND_HALF_UP)`。另:`round(2.675, 2)==2.67`,因为 2.675 浮点存成 2.67499…。

**Q9. 怎么判断一个 float 是不是 NaN?为什么不能用 `==`?**
用 `math.isnan(x)`。`nan` 按 IEEE 754 不等于任何值(含自己),`x == float('nan')` 永远 False。还要小心:`nan in [nan]` 可能为 True,因为容器成员判断先比 `is` 再比 `==`——含 nan 的数据去重/排序/查找都不可靠,入口就该拦掉。

**Q10(猜输出).**
```python
xs = [1, 2, 3, 4, 5, 6]
for x in xs:
    if x % 2 == 0:
        xs.remove(x)
print(xs)
```
`[1, 3, 5]`,漏删了 4。list 迭代按下标推进,`remove` 后元素前移导致跳过。dict/set 同样情形会直接抛 `RuntimeError`。正解:遍历副本或推导式重建(`xs[:] = [x for x in xs if x % 2]`)。
