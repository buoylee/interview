# 06 · OOP(二):继承、描述符、元类

> **为什么这章重要**:这是 OOP 的深水区,也是高级面试的分水岭。多继承的 MRO、`super()` 到底调谁、`@property` 背后的描述符、`__getattr__` 拦截、元类——这些撑起了 ORM、序列化库、依赖注入框架的"魔法"。看懂它们,你才答得上"property 怎么实现的""super 不是调父类那调谁"。

## 一、继承与方法解析顺序(MRO)

Python 支持多继承,于是"该调哪个父类的方法"需要一个确定顺序——**MRO(Method Resolution Order)**,由 **C3 线性化**算法算出,存在 `__mro__` 里:

```python
class A: ...
class B(A): ...
class C(A): ...
class D(B, C): ...

print([c.__name__ for c in D.__mro__])
# ['D', 'B', 'C', 'A', 'object']
```

这就是经典的"菱形继承"(D 继承 B、C,二者都继承 A)。C3 保证:子类排在父类前、`B` 排在 `C` 前(按声明顺序)、且每个类只出现一次。查找属性/方法就沿这条链从左到右找,第一个命中的胜出。

### C3 是怎么算的

C3 把每个类线性化成一条序列。记 `L(C)` 为 C 的 MRO,合并规则:

```
L(C) = C + merge(L(P1), L(P2), …, [P1, P2, …])
```

`merge` 每步取第一个列表的**头**,若该头**没出现在任何其它列表的尾部**(非头位置),就取出它、从所有列表删掉,继续;否则改看下一个列表的头。取不出来就报错。

对 `D(B,C)`、`B(A)`、`C(A)`:`merge([B,A], [C,A], [B,C])` → 取 B(没在别处尾部)→ 取 C → 取 A → 得 `D,B,C,A,object`。这保证**子类先于父类、声明序被尊重、每类只一次**。

若两条继承路径要求的顺序自相矛盾(如 `M(X,Y)` 与 `N(Y,X)`,再 `class Z(M,N)`),merge 卡死,Python **直接拒绝建类**:`TypeError: Cannot create a consistent method resolution order`。

## 二、`super()`:何时写、调的是谁

### 先搞清:什么情况才需要写 `super()`?

一句话:**`super()` = 「我重写了某个方法,但我还想让被我盖住的那一版也跑」**。只在「重写 + 还想保留父类那版」时才需要。决策树:

```
我有没有重写这个方法(自己又定义了一遍同名方法)?
├─ 没重写 ──────────────→ 不用 super()。父类版本自动继承,直接能用。
└─ 重写了 ──┐
            ├─ 想完全替换父类行为 ──→ 不写 super()
            └─ 想在父类行为上「加东西」→ 写 super()
```

```python
class Base:
    def save(self): print("真正写进数据库")

class Audited(Base):
    def save(self):
        print("先记审计日志")
        super().save()      # 加完日志,仍执行父类真正的保存;不写这行,父类那句永不执行
```

### `__init__` 的特例:Java 自动、Python 不自动(高频坑)

90% 写 `super()` 的场合是 `__init__`,而且对 Java 工程师有个反直觉点:**Java 会自动调父类无参构造器,Python 不会**。只要你重写了 `__init__`,父类的 `__init__` 就**完全不跑**,除非显式调用:

```python
class Animal:
    def __init__(self, name): self.name = name

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)    # 不写这行,self.name 根本不存在 → 之后访问 AttributeError
        self.breed = breed
```

反过来,若 `Dog` **不**定义 `__init__`,父类的会自动继承运行(回到"没重写"分支)。正因子类几乎总要在父类基础上多塞字段,「重写 `__init__` → 几乎总要 `super().__init__()`」成了铁律。

> **「我直接手抄 `self.name = name` 不就行了,非要 super 吗?」** 语法上不强制,父类只做纯赋值时手抄也等价。但 `super()` 的本质是**委托**——「父类那部分初始化交给父类负责」。父类 `__init__` 往往不止赋值(规范化字段、算派生值、注册副作用、设私有属性),手抄会**静默漏掉**;而且父类哪天改了,手抄的子类全部失修。继承 `Exception`/`dict`/ORM `Model` 这类第三方基类时,它内部做了啥你既不知道也抄不了,只能 `super()`。**判据:想「在父类基础上扩展」就 `super()`;只有想「彻底不要父类那套」才手写。**

### 单继承:把 `super()` 直接读成"父类"

你 99% 的业务代码是单继承,这时 `super()` 没有任何歧义,**就是父类**。下面的"MRO 下一个"是多继承才需要的精确模型——没写多继承前可以先跳过,别被它干扰。

### 多继承:不是"父类",是"MRO 里的下一个"

最大的认知纠正:`super().method()` **不是**"调我直接父类的 method",而是"调用 **MRO 链中我后面那个类** 的 method"。在多继承下,"后面那个"可能根本不是你的父类,而是个兄弟类。

```python
log = []
class A:
    def go(self): log.append("A")          # 链尾,不再 super
class B(A):
    def go(self): log.append("B"); super().go()
class C(A):
    def go(self): log.append("C"); super().go()
class D(B, C):
    def go(self): log.append("D"); super().go()

D().go()
print(log)        # ['D', 'B', 'C', 'A'] —— A 只执行一次!
```

跟着 MRO `D→B→C→A` 走:`D.go` 里的 `super()` 是 `B`,`B.go` 里的 `super()` 不是 `A` 而是 **`C`**(MRO 里 B 的下一个),`C.go` 的 `super()` 才是 `A`。这叫**协作式多继承(cooperative multiple inheritance)**:每个类都 `super()`,A 这个公共基类就只跑一次(避免菱形里被执行两遍)。

实践要点:**只要可能用于多继承,每个 `__init__`/方法都该调 `super().__init__(...)` 并透传 `*args, **kwargs`**,否则链会断。这跟 Java"`super` 明确指向唯一父类"完全不同——Java 单继承没有这个问题。

> 零参 `super()` 怎么知道"当前类"、从而沿 MRO 找"下一个"?编译器在用了 `super()` 的方法里偷偷塞了个 `__class__` 闭包变量(cell),绑定到**定义该方法的类**——`super()` ≈ `super(__class__, self)`。机制(cell/编译期注入)见[第 15 章](15-cpython-execution-model.md) §4。

## 三、描述符:`@property` 和方法的底层

**描述符**是实现了 `__get__`/`__set__`/`__delete__` 的对象。当它作为**类属性**存在时,对实例访问该属性会被这些方法接管。这是 Python 属性机制的底层引擎——`@property`、`@classmethod`、`@staticmethod`、甚至普通方法的"绑定 self",全是描述符在工作。

```python
class Positive:
    def __set_name__(self, owner, name):     # 类创建时告诉描述符它叫什么
        self.storage = "_" + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self                       # 通过类访问时返回描述符自己
        return getattr(obj, self.storage)
    def __set__(self, obj, value):
        if value < 0:
            raise ValueError("must be >= 0")
        setattr(obj, self.storage, value)

class Account:
    balance = Positive()                      # 描述符作为类属性
    def __init__(self, b):
        self.balance = b                      # 触发 Positive.__set__,带校验

acc = Account(100)
print(acc.balance)        # 100   —— 触发 __get__
# acc.balance = -5        → ValueError: must be >= 0
```

`@property` 就是一个现成的描述符——`property` 类实现了 `__get__`/`__set__`,把你的 getter/setter 函数包进去:

```python
print(hasattr(property, "__get__"))   # True —— property 本身是描述符
```

**data vs non-data 描述符**(优先级,面试加分点):同时实现 `__get__` 和 `__set__`(或 `__delete__`)的是 **data descriptor**,优先级**高于**实例 `__dict__`;只实现 `__get__` 的是 **non-data descriptor**,优先级**低于**实例 `__dict__`。这解释了为什么 `@property`(data)无法被实例属性遮蔽,而普通方法(non-data)可以被同名实例属性覆盖。完整的查找路径在[第 05 章](05-oop-1-classes-protocols.md) §2"属性查找的完整算法"。

**`__set_name__` 的时机**:类创建时,等类体执行完、命名空间填好,Python 会遍历类属性,对每个描述符调用 `__set_name__(owner, name)`,把"我叫什么、属于哪个类"告诉它——描述符因此不必你手动传名字(`Positive()`、ORM 字段自动知道自己绑在哪个属性上)。

## 四、属性拦截:`__getattr__` / `__getattribute__` / `__setattr__`

```python
class Proxy:
    def __init__(self, data):
        self._data = data
    def __getattr__(self, name):       # 只在“常规查找失败”后才触发
        return f"missing:{name}"

p = Proxy({"a": 1})
print(p._data)         # {'a': 1}      —— 正常找到,不触发 __getattr__
print(p.whatever)      # missing:whatever —— 找不到,兜底
```

- **`__getattr__(self, name)`**:仅当常规查找(实例 dict、类、描述符)**都失败**时才调用。用来做兜底、惰性加载、代理转发(`__getattr__` 转发给内部对象)。
- **`__getattribute__(self, name)`**:**每次**属性访问都先调用它(包括成功的)。功能最强但极危险——实现不当(比如里面又 `self.x`)会无限递归。轻易别碰。
- **`__setattr__(self, name, value)`**:拦截**所有**属性赋值。注意里面写 `self.name = value` 会再次触发自己,要用 `object.__setattr__(self, name, value)` 或改 `self.__dict__`。

记忆:`__getattr__` = "找不到才来"(常用、安全),`__getattribute__` = "每次都来"(危险、少用)。

## 五、元类:类也是对象

在 Python 里**类本身也是对象**,它的类型就是**元类**。默认元类是 `type`:

```python
class X: ...
print(type(X))        # <class 'type'>  —— X 这个类的类型是 type
print(type(type))     # <class 'type'>  —— type 的类型还是 type
```

`type` 不只是"查类型"的函数,它还能**动态造类**——`class` 语句本质就是调用元类:

```python
# class Y: def hi(self): return "hi"  等价于:
Y = type("Y", (), {"hi": lambda self: "hi"})
print(Y().hi())       # hi
```

`class Foo(Base, metaclass=Meta)` 会调用 `Meta(name, bases, namespace)` 来创建类。自定义元类能在**类被创建时**介入(改写类、注册、校验),ORM(Django Model)、序列化库靠它实现声明式魔法。

### 类创建的三段式(`__prepare__` → `__new__` → `__init__`)

`class Foo(metaclass=Meta):` 执行时,Python 按三步走:

1. **`Meta.__prepare__(name, bases)`** → 返回一个映射,**类体就在这个映射里执行**(键值=类体里的赋值/方法名)。默认返回普通 dict;返回自定义映射可"监听/改写"类体的定义过程(如记录定义顺序)。
2. 类体跑完、命名空间填好 → **`Meta.__new__(mcs, name, bases, ns)`** 真正**创建类对象**。
3. **`Meta.__init__(cls, …)`** 收尾(注册、校验)。

之后**实例化** `Foo()` 调的是 **`type(Foo).__call__`**(即 `Meta.__call__`),它再依次调 `Foo.__new__` 造实例、`Foo.__init__` 初始化——这就是元类能拦截"建实例"(如做单例)的位置。

```python
order = []
class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **k): order.append("prepare"); return {}
    def __new__(mcs, n, b, ns, **k): order.append("new"); return super().__new__(mcs, n, b, ns)
    def __init__(cls, *a, **k): order.append("init"); super().__init__(*a)
    def __call__(cls, *a, **k): order.append("call"); return super().__call__(*a, **k)
class Foo(metaclass=Meta):
    order.append("body")
Foo()
print(order)   # ['prepare', 'body', 'new', 'init', 'call']
```

**但是**:99% 的场景你**不需要**元类。它能做的事,更轻量的工具大多也能做:

### `__init_subclass__`:元类的轻量替代

想在"子类被定义时"做点事(如自动注册插件),用 `__init_subclass__` 而非元类——更简单、可读:

```python
registry = {}
class Plugin:
    def __init_subclass__(cls, /, key=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if key:
            registry[key] = cls

class Foo(Plugin, key="foo"): ...
class Bar(Plugin, key="bar"): ...
print(sorted(registry))    # ['bar', 'foo'] —— 子类一定义就自动注册
```

配套的 `__set_name__`(上面描述符用过)让类属性对象知道自己的名字。这俩 + 描述符,覆盖了过去要用元类的大部分需求。**面试答"何时用元类":先说"几乎不需要,优先 `__init_subclass__`/描述符/类装饰器;只有要批量改写类结构、做框架级声明式 API 时才上元类"。**

## 六、ABC vs Protocol:两种"接口"

Python 表达"必须具备某些方法"有两条路:

### ABC(抽象基类)——名义子类型

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

# Shape()  → TypeError:有未实现的抽象方法,不能实例化
class Circle(Shape):
    def __init__(self, r): self.r = r
    def area(self): return 3.14159 * self.r ** 2
```

ABC 像 Java 的抽象类/接口:子类必须**显式继承**并实现抽象方法,否则无法实例化。适合"我定义契约,你来实现"。

### Protocol——结构化子类型(鸭子类型的静态化)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Sized(Protocol):
    def __len__(self) -> int: ...

print(isinstance([1, 2, 3], Sized))    # True —— list 没继承 Sized,但有 __len__
```

`Protocol` 不要求继承——**只要对象长得对(有对应方法签名)就算符合**,这正是鸭子类型,只是能被类型检查器(mypy)静态校验。它对应 Go 的 interface(隐式满足)。

选型:你拥有继承体系、想强制实现 → ABC;面对不受你控制的类型、或想要"长得像就行"的松耦合 → Protocol(类型系统细节见[第 09 章](09-typing.md))。

## Java/Go 对照框

| | Java | Python |
|--|------|--------|
| 多继承 | 类单继承,接口可多实现 | 类可多继承,用 C3 MRO 定序 |
| `super` | 指向唯一直接父类 | 指向 **MRO 里的下一个**(协作式,可能是兄弟类) |
| 属性拦截 | 无内建;靠 AOP/代理/字节码增强 | `__getattr__`/`__getattribute__`/描述符,语言内建 |
| getter/setter 机制 | 方法调用 | 描述符(`@property` 是其封装) |
| 类的元信息 | `Class<?>`,靠反射 | 类是 `type` 的实例,元类可在创建时改写它 |
| 接口 | `interface`(名义) | ABC(名义)+ Protocol(结构化,≈ Go interface) |

## 章末面试卡

**Q1. 什么是 MRO?`D(B, C)`、B/C 都继承 A 时,MRO 是什么?**
MRO 是多继承下方法/属性的解析顺序,由 C3 线性化算出,存于 `__mro__`。该例为 `D → B → C → A → object`:子类先于父类、B 先于 C(声明序)、每类只出现一次。

**Q2. `super()` 是调用父类方法吗?**
不完全是。`super()` 调用的是 **MRO 链中当前类的下一个类**的方法,在多继承下可能是兄弟类而非父类。这是协作式多继承,配合"每个类都 `super()`"能让公共基类只执行一次。

**Q3. `@property` 是怎么实现的?**
靠**描述符协议**。`property` 是一个实现了 `__get__`/`__set__`/`__delete__` 的类(data descriptor),把你的 getter/setter 包进去;作为类属性时,实例对该属性的读写被这些方法接管。因为是 data descriptor,优先级高于实例 `__dict__`,不会被实例属性遮蔽。

**Q4. `__getattr__` 和 `__getattribute__` 区别?**
`__getattribute__` 在**每次**属性访问时都被调用(成功与否都先经过它,危险、易递归);`__getattr__` 只在常规查找**失败后**作为兜底被调用(安全、常用于代理/惰性/默认值)。

**Q5. 什么时候需要元类?**
极少。需要在**类创建时**批量改写/校验/注册类结构(框架级声明式 API,如 ORM)时才用。日常的"子类自动注册""属性命名"用 `__init_subclass__`、`__set_name__`、描述符或类装饰器即可,优先选它们。

**Q6. ABC 和 Protocol 有什么区别?**
ABC 是名义子类型:必须显式继承并实现抽象方法,否则不能实例化(像 Java 抽象类)。Protocol 是结构化子类型:不需继承,只要具备对应方法就算符合(鸭子类型 + 静态检查,像 Go interface)。面对不可控类型或要松耦合时用 Protocol。

**Q7. C3 线性化怎么算?什么时候会报 MRO 冲突?**
`L(C) = C + merge(各父类的 L, [父类列表])`;merge 每步取第一个列表的头,若它不出现在其它列表的非头位置就取出、各列表删之,否则看下一个列表的头。保证子类先于父类、声明序被尊重、每类一次。若两条路径要求的顺序自相矛盾(`M(X,Y)` vs `N(Y,X)` 再 `Z(M,N)`),merge 卡死 → `TypeError: Cannot create a consistent method resolution order`。

**Q8. 元类创建类有哪三步?`MyClass()` 实例化时元类哪个方法被调?**
建类三步:`Meta.__prepare__`(给类体准备命名空间)→ `Meta.__new__`(造类对象)→ `Meta.__init__`(收尾)。实例化 `MyClass()` 调的是 `type(MyClass).__call__`(即 `Meta.__call__`),它再调 `MyClass.__new__` + `__init__`——元类拦截"建实例"(如单例)就在这里。顺序实测:`prepare, body, new, init, call`。
