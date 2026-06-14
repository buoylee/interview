# 05 · OOP(一):类、属性、协议

> **为什么这章重要**:Python 的 OOP 表面像 Java,内里很不同——属性是动态的、类变量全实例共享、"协议"靠魔法方法(dunder)而非接口实现、相等与哈希要成对手写。这章覆盖日常 80% 的 OOP,以及"类变量陷阱""`__eq__` 配 `__hash__`"这些高频题。继承/描述符/元类等深水区在[第 06 章](06-oop-2-inheritance-descriptors-metaclasses.md)。

## 一、类、实例、`self`

```python
class User:
    def __init__(self, name: str, age: int):
        self.name = name       # 实例属性
        self.age = age

    def greet(self):           # 实例方法,第一个参数永远是 self
        return f"{self.name}({self.age})"

u = User("Alice", 18)
print(u.greet())               # Alice(18)
```

- `self` 是当前实例,**必须显式写**(Java 的 `this` 隐式,Python 不藏)。
- `__init__` 是**初始化器**,不是构造器本体:对象已经被创建出来后,它负责往上面填实例属性。
- 真正"创建对象"的是 `__new__`(先于 `__init__`),日常基本不碰——只有做不可变类型子类、单例、对象池时才覆盖它。

```python
class Demo:
    def __new__(cls, *a, **k):
        print("new: 创建对象")
        return super().__new__(cls)
    def __init__(self):
        print("init: 初始化")
# Demo() 会先打印 new 再打印 init
```

## 二、类属性 vs 实例属性(高频陷阱)

类属性写在类体里,**属于类、所有实例共享**;实例属性在 `__init__` 里 `self.x=` 设,**每个实例独立**:

```python
class User:
    role = "guest"             # 类属性:共享
    def __init__(self, name):
        self.name = name       # 实例属性:独立
```

### 属性查找顺序

读 `obj.attr` 时:**先找实例属性 → 再找类属性 → 再沿继承链找父类**。给实例赋同名属性会"遮蔽"类属性,但不改类属性本身:

```python
class C:
    role = "guest"
u = C()
u.role = "admin"               # 新建实例属性,遮蔽类属性
print(u.role, C.role)          # admin guest  —— 类属性没变
```

### 陷阱:可变类属性被所有实例共享

这是第 01 章"共享可变对象"母题在 OOP 里的化身:

```python
class Dog:
    tricks = []                # 可变类属性 —— 危险!
    def add(self, t):
        self.tricks.append(t)  # 就地 mutate 的是那个共享 list

a, b = Dog(), Dog()
a.add("roll")
print(b.tricks)                # ['roll'] —— b 也被改了!
```

为什么?`self.tricks.append(...)` 没有给 `self` 新建属性,而是先按查找顺序找到**类属性**那个 list,再原地改它——所有实例指向同一个 list。正解:在 `__init__` 里给每个实例新建:

```python
class Dog:
    def __init__(self):
        self.tricks = []       # 每个实例独立的 list
    def add(self, t):
        self.tricks.append(t)
```

> 区分两个动作:`self.x = ...`(赋值)**新建/覆盖实例属性**;`self.x.append(...)`(就地修改)改的是当前查找到的那个对象——若它来自类属性,就是在改共享数据。可变默认参数、`[[]]*n`、可变类属性,三个坑一个根。

## 三、方法的三种类型

```python
class Pizza:
    def __init__(self, ingredients):
        self.ingredients = ingredients

    @classmethod
    def margherita(cls):           # 收到类 cls,常用作“替代构造器”
        return cls(["cheese", "tomato"])

    @staticmethod
    def oven_temp():               # 既不收 self 也不收 cls,就是个挂在类上的函数
        return 450

Pizza.margherita().ingredients     # ['cheese', 'tomato']
Pizza.oven_temp()                  # 450
```

- **实例方法**:收 `self`,操作实例。
- **`@classmethod`**:收 `cls`(类本身),最常见用途是**替代构造器**(`dict.fromkeys`、`datetime.now` 都是),且子类调用时 `cls` 是子类,天然支持继承。
- **`@staticmethod`**:不收 `self`/`cls`,逻辑上属于类但不依赖实例/类状态。如果只是个工具函数,Python 更推荐直接写成**模块级函数**,别为了模仿 Java 硬塞进类里。

## 四、`@property`:把方法伪装成属性

需要在取/存属性时加逻辑(校验、计算、惰性),又不想暴露 `get_x()/set_x()` 这种调用形式,就用 `@property`:

```python
class Temp:
    def __init__(self, celsius):
        self._c = celsius
    @property
    def fahrenheit(self):              # 读 t.fahrenheit 时计算
        return self._c * 9/5 + 32
    @fahrenheit.setter
    def fahrenheit(self, value):       # 写 t.fahrenheit = ... 时反算
        self._c = (value - 32) * 5/9

t = Temp(0)
print(t.fahrenheit)    # 32.0   —— 像读属性,其实在算
t.fahrenheit = 212
print(t._c)            # 100.0  —— 像写属性,其实在反算
```

好处:接口是属性形态(`t.fahrenheit`),将来从"存的字段"改成"算出来的"无需改调用方。`property` 底层是**描述符**,原理在[第 06 章](06-oop-2-inheritance-descriptors-metaclasses.md)。

## 五、`__slots__`:省内存、禁止动态属性

默认每个实例用一个 `__dict__` 存属性,灵活但费内存。声明 `__slots__` 后,实例改用固定槽位存储,**省内存、访问略快,但禁止新增未声明的属性**:

```python
class Point:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x, self.y = x, y

p = Point(1, 2)
# p.z = 3   → AttributeError:'Point' object has no attribute 'z'
```

适合海量创建的小对象(几十万个点/记录)。代价:没了 `__dict__`,失去动态加属性能力,多继承时也有限制。

## 六、数据模型:用 dunder 接入语言协议

Python 不靠"实现某接口",而靠**实现魔法方法(dunder)** 让你的对象支持内置语法。这叫"数据模型"或"协议"。资深必备的几组:

### 字符串表示:`__repr__` vs `__str__`

```python
class User:
    def __init__(self, name): self.name = name
    def __repr__(self): return f"User(name={self.name!r})"   # 面向开发者/调试,尽量可还原
    def __str__(self):  return f"User<{self.name}>"          # 面向用户的友好文本

u = User("Ann")
print(str(u))    # User<Ann>
print(repr(u))   # User(name='Ann')
print(u)         # User<Ann>  —— print/str() 优先用 __str__
```

规则:`__repr__` 给开发者看(理想情况下 `eval(repr(x))` 能重建对象),`__str__` 给终端用户看。**只实现一个就实现 `__repr__`**——没有 `__str__` 时 `str()` 会回退到 `__repr__`。

### 相等与哈希:`__eq__` 必须配 `__hash__`

```python
class Point:
    def __init__(self, x, y): self.x, self.y = x, y
    def __eq__(self, other):
        return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)
    def __hash__(self):
        return hash((self.x, self.y))    # 与 __eq__ 用到的字段保持一致

print(Point(1, 2) == Point(1, 2))        # True
print(len({Point(1, 2), Point(1, 2)}))   # 1 —— 相等且哈希相同,集合里算一个
```

**契约**:`a == b` 为真则 `hash(a) == hash(b)` 必须也为真(反之不要求)。**坑**:一旦你定义了 `__eq__` 却没定义 `__hash__`,Python 会把 `__hash__` 设为 `None`,对象变得**不可哈希**,放进 `set`/做 dict key 会 `TypeError`:

```python
class Bad:
    def __eq__(self, o): return True
# {Bad()}  → TypeError: unhashable type: 'Bad'
```

### 容器与迭代、可调用、上下文

- `__len__`→`len(obj)`;`__getitem__`→`obj[k]`;`__contains__`→`x in obj`;`__iter__`→`for x in obj`(详见[第 07 章](07-iterators-generators-context-managers.md))。
- `__call__`→让实例像函数一样被调用 `obj(...)`。
- `__enter__`/`__exit__`→支持 `with`(第 07 章)。
- 运算符重载:`__add__`/`__lt__`/`__getattr__` 等(`__getattr__` 等属性拦截在第 06 章)。

```python
class Multiplier:
    def __init__(self, factor): self.factor = factor
    def __call__(self, value):  return value * self.factor
double = Multiplier(2)
print(double(5))   # 10 —— 实例可调用
```

> 不是所有 dunder 都作用在实例上:`__init_subclass__`、`__class_getitem__` 作用在类层面,更底层的还涉及元类(第 06 章)。日常业务主要用实例级 dunder。

## 七、少写样板:dataclass / namedtuple / enum

### `@dataclass`

自动生成 `__init__`、`__repr__`、`__eq__` 等,专治"一堆字段的数据类":

```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: int
    y: int = 0
    tags: list = field(default_factory=list)   # 可变默认值必须用 default_factory!

p = Point(1, 2)
print(p)                    # Point(x=1, y=2, tags=[])
print(Point(1, 2) == Point(1, 2))   # True,自动按字段比较
```

注意:dataclass 里**可变默认值要用 `field(default_factory=list)`**,直接写 `tags: list = []` 会触发可变默认参数陷阱(dataclass 实际上会直接报错拦你)。`@dataclass(frozen=True)` 得到不可变、可哈希的数据类。

### `namedtuple` 与 `Enum`

```python
from collections import namedtuple
P = namedtuple("P", "x y")
print(P(1, 2).x)            # 1,轻量不可变记录,可解包

from enum import Enum
class Color(Enum):
    RED = 1
    GREEN = 2
print(Color.RED, Color.RED.value)   # Color.RED 1
```

选型:简单不可变记录 → `namedtuple`;有默认值/方法/要可变 → `dataclass`;有限取值集合 → `Enum`。

`Enum` 的几个进阶变体:

```python
from enum import Enum, auto, IntEnum, Flag
class Color(Enum):
    RED = auto(); GREEN = auto(); BLUE = auto()   # auto() 自动赋 1,2,3,不用手写值

class Status(IntEnum):           # 同时是 int:可与数字比较/运算
    OK = 200; NOTFOUND = 404
Status.OK == 200                 # True;Status.OK + 1 == 201

class Perm(Flag):                # 位标志:可用 | 组合、in 判断
    R = auto(); W = auto(); X = auto()
rw = Perm.R | Perm.W
Perm.R in rw                     # True;Perm.X in rw 为 False
```

`IntEnum` 用于需要和整数互通的场景(如 HTTP 状态码),`Flag` 用于权限位这类可组合标志。

## Java/Go 对照框

| | Java | Python |
|--|------|--------|
| `this`/`self` | `this` 隐式 | `self` 必须显式写 |
| 静态字段 | `static` 字段 | **类属性**(共享),或干脆放**模块变量** |
| getter/setter | 写 `getX()/setX()` | `@property`,调用方仍当属性用 |
| 相等 | 覆盖 `equals()` + `hashCode()` | 覆盖 `__eq__` + `__hash__`,契约相同;只写 `__eq__` 会变不可哈希 |
| toString | `toString()` | `__repr__`(调试)/`__str__`(展示) |
| record / POJO | `record` / Lombok | `@dataclass` / `namedtuple` |
| 接口实现 | `implements Iterable` | 实现 `__iter__` 等 dunder(鸭子类型,不需声明) |

核心差异:Java 靠 `implements` **声明**能力,Python 靠**实现 dunder** 获得能力——你不"声明实现了可迭代接口",你只要写了 `__iter__`,对象就能被 `for` 遍历。

## 章末面试卡

**Q1(必考·猜输出).**
```python
class Dog:
    tricks = []
    def add(self, t): self.tricks.append(t)
a, b = Dog(), Dog()
a.add("roll")
print(b.tricks)
```
`['roll']`。`tricks` 是**类属性**,被所有实例共享;`self.tricks.append` 原地修改的是那个共享 list。修复:在 `__init__` 里 `self.tricks = []` 给每个实例独立的 list。

**Q2. `__new__` 和 `__init__` 区别?**
`__new__` 负责**创建并返回**实例(先执行),`__init__` 负责**初始化**已创建的实例(后执行,不返回)。日常只写 `__init__`;覆盖 `__new__` 用于不可变类型子类化、单例、对象池等。

**Q3. `__str__` 和 `__repr__` 有什么区别?该实现哪个?**
`__repr__` 面向开发者/调试,理想可被 `eval` 还原;`__str__` 面向用户的友好展示。`print`/`str()` 优先用 `__str__`,缺失时回退 `__repr__`。只实现一个就实现 `__repr__`。

**Q4. 为什么定义了 `__eq__` 就要定义 `__hash__`?**
契约要求 `a == b` ⇒ `hash(a) == hash(b)`。Python 在你定义 `__eq__` 而未定义 `__hash__` 时会把 `__hash__` 置为 `None`,使对象不可哈希(进 set / 当 dict key 报 `TypeError`)。要可哈希就得用与 `__eq__` 一致的字段实现 `__hash__`(或用 `@dataclass(frozen=True)` 自动生成)。

**Q5. `@classmethod` 和 `@staticmethod` 区别?各用在哪?**
`classmethod` 收 `cls`,常作替代构造器且对子类友好(`cls` 是实际调用的类);`staticmethod` 不收 `self`/`cls`,只是逻辑归属于类的普通函数。纯工具函数其实更推荐写成模块级函数。

**Q6. `__slots__` 有什么用?代价是什么?**
用固定槽位代替每实例的 `__dict__`,省内存、属性访问略快,适合海量小对象。代价:不能再动态添加未声明的属性,且对多继承、`__dict__`/弱引用等有额外限制。
