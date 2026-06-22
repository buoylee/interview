# 09 · 类型系统与 typing

> **为什么这章重要**:Python 是动态类型,但现代生产代码几乎都上类型注解 + mypy/pyright。注解能让 IDE 补全、静态查错、自文档化,是资深与初级的明显分界。最该先建立的认知:**注解在运行时不强制**——它是给工具看的,不是给解释器执行的。

## 一、动态类型 + 鸭子类型 + 渐进类型

- **动态类型**:变量没有固定类型,类型属于**对象**不属于名字。`x = 1` 后 `x = "a"` 完全合法。
- **鸭子类型**:"长得像鸭子就当鸭子"——不看类型,只看有没有需要的方法。能 `len(x)` 只因为 `x` 有 `__len__`,不要求它继承什么。
- **渐进类型(gradual typing)**:你可以**逐步**加注解,加多少查多少,不加的部分按动态处理。注解是可选的、增量的。

**核心铁律:类型注解在运行时完全不强制。**

```python
def add(a: int, b: int) -> int:
    return a + b

print(add("x", "y"))    # "xy" —— 传 str 不报错!解释器无视注解
```

解释器不检查注解,该跑还跑。真正"用"注解的是**静态检查器**(mypy、pyright/Pylance)——它们在你运行前扫描代码、报类型错误。注解还存在 `__annotations__` 里供框架(pydantic、dataclass、FastAPI)运行时读取:

```python
print(add.__annotations__)   # {'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}
```

### 那"运行时不强制",到底靠什么解决"传错类型"?——关键是**时机**

既然解释器无视注解,你一定会问:那写注解 + mypy 到底"解决"了什么?**答案不在"运行时拦不拦",而在"什么时候查"。**

mypy 是**另一个程序**:它把你的源码当文本**读一遍、但不运行它**,纯靠分析就预测出哪里类型会错。

```python
def greet(name: str) -> str:
    return "Hi " + name

greet(123)        # 传了 int
```

```bash
$ mypy greet.py
greet.py:4: error: Argument 1 to "greet" has incompatible type "int"; expected "str"
# 注意:这时 python 根本还没跑
```

等你真的 `python greet.py`,这个 bug **已经在运行之前被你改掉了**——不是运行时把它挡下来,是它根本没机会发生。**"解决"=把发现时机从"运行到那一行才爆"提前到"还没运行就报错"。** 你怕的"不知道跑起来会传进来什么、跑到一半才崩",正是 mypy 消灭的东西。

**用 Java 对齐就秒懂:** 你以为 Java 的类型安全是 JVM 在运行时给的?不是——是 `javac` **编译那一步**查的,那一步也在运行之前。**mypy 就是你手动装回来的 `javac`**,只是从"语言强制、不过编译就没有 `.class`"降级成"工具可选、自己在 CI 里卡死"。

```
Java:           写码 → javac 编译【查类型,过不了就没 .class】→ JVM 运行
Python 无 mypy:  写码 →─────────(没有这一关)─────────→ python 运行(错到那一行才爆)
Python 有 mypy:  写码 → mypy 检查【你自己装回来的这一关】───→ python 运行
```

所以"加类型 + mypy"不是给解释器加运行时限制(那永远没有),而是**在运行之前补一道和 `javac` 同位置的静态检查**。一句话钉死:**Python 的类型检查和 Java 一样发生在"运行前",差别只是 Java 由语言强制、Python 由你用工具自愿强制。**

> 注意边界:mypy 只能查"你源码里看得见的类型"。运行时才从外部流进来的数据(JSON / 网络 / DB),mypy 读不到——那一块归 pydantic 在运行时校验(见本章第五节)。别把这两件事混成一件。

## 二、基础注解

```python
name: str = "Ann"
age: int = 18
scores: list[int] = [90, 85]            # 内置容器直接做泛型(3.9+)
mapping: dict[str, int] = {}

def greet(name: str, times: int = 1) -> str:
    return f"hi {name} " * times

def log(msg: str) -> None:               # 无返回值标 None
    print(msg)
```

### `Optional` 与联合类型 `X | Y`

```python
def find(uid: int) -> str | None:        # 3.10+ 推荐写法:可能返回 str 或 None
    ...
# 等价旧写法:from typing import Optional;  Optional[str]  ==  str | None

def parse(x: int | str) -> int:          # 接受 int 或 str
    return int(x)
```

`Optional[str]` 就是 `str | None` 的别名(表示"可能没有"),**不是**"参数可省略"。3.10 起优先用 `X | Y`,更简洁。

## 三、泛型

### 容器泛型

```python
def total(nums: list[int]) -> int:
    return sum(nums)
pairs: dict[str, list[int]] = {}
```

### 自定义泛型类/函数

需要"类型参数"时用 `TypeVar`。**两套语法,注意版本**:

```python
# ── 旧式(3.11 及以前,本教程实测可用)──
from typing import TypeVar, Generic
T = TypeVar("T")

class Box(Generic[T]):
    def __init__(self, value: T): self.value = value
    def get(self) -> T: return self.value

def first(xs: list[T]) -> T:
    return xs[0]

print(Box(123).get())     # 123
```

```python
# ── 新式 PEP 695(3.12+,语法糖,无需显式 TypeVar)──
# ⚠️ 这段需要 Python 3.12+,在 3.11 上是 SyntaxError
class Box[T]:
    def __init__(self, value: T): self.value = value
    def get(self) -> T: return self.value

def first[T](xs: list[T]) -> T:
    return xs[0]
```

两者语义一致,3.12+ 写法把 `TypeVar` 内联进 `[T]`,更干净。面试提一句"3.12 引入了 PEP 695 泛型语法"是加分项。

### `Self`(3.11+)

链式调用/工厂方法里,返回"自身类型"用 `Self`,子类调用时类型也正确:

```python
from typing import Self
class Builder:
    def __init__(self): self.parts = []
    def add(self, p) -> Self:            # 返回 Self,支持链式且对子类正确
        self.parts.append(p)
        return self

Builder().add(1).add(2)                  # 类型检查器知道返回的是 Builder
```

### 变型:协变、逆变、不变

这一节的全部内容,只回答一个 yes/no 问题:

> `Dog` 是 `Animal`。那「**一盒 Dog**」算不算「**一盒 Animal**」?

直觉脱口而出「当然算」,但正确答案是:**看你拿这盒子干嘛——只读、只写、还是又读又写。** 这个「读 / 写」就是判定变型的唯一原语,记住它,三个术语全部自己长出来。

**先认清下面三个类型「能干什么」不同**,变型方向才有意义——它们不是 `list` 的三种变体,而是允许的操作根本不同:

| 类型 | 能做的操作 | 做不了 | 本质 | → 变型 |
|---|---|---|---|---|
| `list[Dog]` | 读 `x[0]`/`for`/`len` + 写 `append`/`x[0]=` | —(读写全能) | 可读可写盒子 | 不变 |
| `Sequence[Dog]` | 读 `x[0]`/`for`/`len` | **没有** `append`、`x[0]=`(写方法被藏掉) | 只读盒子 | 协变 |
| `Callable[[Dog], None]` | **调用** `f(某dog)` | 它不是盒子,是**函数** | 接受 Dog 的函数 | 参数位逆变 |

注意 `Sequence` **不是另一个对象**:运行时你传的还是那个 `list`,`Sequence[Dog]` 只是更窄的**类型标签**,把 `append`/`__setitem__` 从「检查器允许你用的方法」里藏起来——标成 `Sequence` 就等于对 mypy 发誓「我只读不写」。`Callable[[Dog], None]` 则压根不是容器,是个**函数类型**;把它理解成「只写槽」的关键是:**调用一个函数 = 把值塞进它的参数槽,所以参数位 = 写/消费位**。下面 ①②③ 就是这张表的三行各自为什么是那个变型。

**① 只读 → 协变(covariant)。** 你只从盒子往外拿。一盒 Dog 当一盒 Animal 用绝对安全:你期待掏出 Animal,实际掏出的是 Dog,而 Dog 本来就是 Animal。**方向跟着子类型走**:`Dog <: Animal` ⇒ `只读盒[Dog] <: 只读盒[Animal]`。Python 里 `Sequence` 就是这种(没有 `append`,无写入途径)。

**② 又读又写 → 不变(invariant),这是 `list` 的情况,也是 Python 泛型的默认。** 假设 mypy 允许把 `list[Dog]` 传给接收 `list[Animal]` 的函数——那函数完全有权往里 `append(Animal())` 甚至 `append(Cat())`,函数返回后,你原来那盒 Dog 里就混进了猫,契约被悄悄破坏。所以可变容器**不允许向上传**:`list[Dog]` 和 `list[Animal]` 在 mypy 眼里是互不相干的两个类型。

**③ 只写 → 逆变(contravariant),方向反过来。** 「往里塞」什么时候反而安全?当目标盒子接收的范围**更宽**时:一个「能装任意 Animal」的盒子,可以安全地当「装 Dog 的盒子」用——你要塞 Dog,它照单全收。所以 `Dog <: Animal` ⇒ `写盒[Animal] <: 写盒[Dog]`,**箭头掉头**。最常见的「只写位」是**函数的参数位**:`Callable[[Animal], None]` 是 `Callable[[Dog], None]` 的子类型——你要一个处理 Dog 的回调,给它一个「能处理任意 Animal」的函数完全没问题。

**Java 桥:这正是你早就会的 PECS**——*Producer Extends, Consumer Super*:

- 盒子当**生产者**(你从里读)→ `List<? extends Animal>` → 协变
- 盒子当**消费者**(你往里写)→ `List<? super Dog>` → 逆变
- 普通 `List<Animal>` 读写都要 → 不变

唯一区别:**Java 把变型写在使用点**(每次用 `?` 通配符声明),**Python 写在定义点**(`TypeVar` 上标 `covariant=`/`contravariant=`,或 3.12+ 让检查器自动推断)。规则一模一样。

**一句话记忆:能写就不变,只读可协变,消费者(回调入参)逆变。**

**变型在代码里其实是两道关卡,看清这点就彻底懂了。** 下面 ①②③ 是**调用点**:别人把 `list[Dog]`/`Sequence[Dog]` 传给你时,mypy 放行还是标红。而变型的**声明**在**定义点**——`TypeVar("T_co", covariant=True)` 是一句承诺「这个 `T` 只出现在**返回位**(产出),绝不出现在**参数位**(吃进)」,mypy 会**逐个方法验你有没有违约**:协变 `T` 落在参数位 → 报 `Cannot use a covariant type variable as a parameter`;逆变 `T` 落在返回位 → 报 `Cannot use a contravariant type variable as return type`。这正是 PECS 落到代码的硬约束(协变 = Producer = 只进返回位;逆变 = Consumer = 只进参数位),也是「只读才能安全协变」被机制保证的原因——**协变盒子里你根本写不出 `put`**,定义点这关就过不去。(3.12+ 的 `class Box[T]` 由检查器自动推断变型,不必手写这些 `TypeVar`。)第①关你天天撞见,第②关解释了第①关的「为什么」。

```python
from typing import TypeVar, Generic, Sequence, Callable

class Animal: ...
class Dog(Animal): ...

# ① 只读容器:协变(covariant)
dogs: list[Dog] = [Dog()]
def count(xs: Sequence[Animal]) -> int:
    return len(xs)
count(dogs)                      # mypy OK:Sequence 只读,Dog 是 Animal,塞不坏

# ② 可变容器:不变(invariant)—— Python 默认
def feed_all(xs: list[Animal]) -> None:
    xs.append(Animal())          # 它有权往里塞 Animal
# feed_all(dogs)                 # mypy 标红:list 不变

# ③ 回调参数位:逆变(contravariant)
handler: Callable[[Dog], None]
def on_animal(a: Animal) -> None: ...
handler = on_animal              # mypy OK:能处理任意 Animal,必能处理 Dog

# ④ 定义点的强制(变型最硬核的体现):承诺写进 TypeVar,mypy 逐方法验
T_co = TypeVar("T_co", covariant=True)        # 承诺:T 只产出,绝不吃进
class ReadOnlyBox(Generic[T_co]):
    def __init__(self, v: T_co) -> None: self._v = v
    def get(self) -> T_co: return self._v     # OK:返回位 = 产出
    # def put(self, v: T_co) -> None: ...      # 若解开 → mypy 报:
    #   error: Cannot use a covariant type variable as a parameter

T_contra = TypeVar("T_contra", contravariant=True)   # 承诺:T 只吃进,绝不产出
class Sink(Generic[T_contra]):
    def put(self, v: T_contra) -> None: ...   # OK:参数位 = 吃进
    # def get(self) -> T_contra: ...           # 若解开 → mypy 报:
    #   error: Cannot use a contravariant type variable as return type
```

## 四、进阶武器

### `Protocol`:结构化类型(鸭子类型的静态版)

不需继承,只要"长得对"就算符合——把鸭子类型交给静态检查器验证(详见[第 06 章](06-oop-2-inheritance-descriptors-metaclasses.md)):

```python
from typing import Protocol

class SupportsLen(Protocol):
    def __len__(self) -> int: ...

def describe(x: SupportsLen) -> str:     # 任何有 __len__ 的对象都能传
    return f"长度 {len(x)}"

describe([1, 2, 3])    # OK,list 没继承 SupportsLen 但有 __len__
describe("abc")        # OK
```

### `TypedDict`:给 dict 标字段类型

```python
from typing import TypedDict
class Movie(TypedDict):
    title: str
    year: int

m: Movie = {"title": "Matrix", "year": 1999}   # 检查器校验键和类型
# 运行时 m 就是普通 dict,TypedDict 不创建新类型
```

适合"约定形状的 JSON/dict",比定义完整类更轻。

### `Literal`、`Final`、`@overload`

```python
from typing import Literal, Final, overload

def set_mode(mode: Literal["r", "w", "a"]) -> None: ...   # 只允许这几个字面值
MAX: Final = 100                                          # 不应被重新赋值(检查器盯着)

@overload
def parse(x: int) -> int: ...        # 多个签名重载(仅供检查器)
@overload
def parse(x: str) -> str: ...
def parse(x):                        # 唯一真实现
    return x
```

`@overload` 让"输入类型决定输出类型"能被精确表达(运行时只保留最后那个真实现,前面的纯标记)。更高阶的还有 `ParamSpec`/`Concatenate`(给装饰器保类型,这里不展开)。

### `Annotated`:类型不变,额外挂元数据

`Annotated[T, ...]` 的**第一个参数才是真正的类型**,后面可以挂任意个"元数据"。对静态检查器来说 `Annotated[int, ...]` 就等于 `int`——元数据完全透明、不影响类型判断;它是留给**框架在运行时读**的。

```python
from typing import Annotated, get_type_hints, get_args

# 语法:Annotated[真正的类型, 元数据1, 元数据2, ...]
Age = Annotated[int, "单位:岁", "must be > 0"]

def birthday(age: Age) -> int:
    return age + 1

print(birthday(18))          # 19 —— 运行时 age 就是普通 int,检查器也把它当 int
```

元数据不会自己生效,要靠代码**主动取出来**用。关键坑:`get_type_hints` 默认会把元数据剥掉,得加 `include_extras=True`:

```python
hints = get_type_hints(birthday, include_extras=True)
print(hints["age"])          # typing.Annotated[int, '单位:岁', 'must be > 0']

base, *meta = get_args(hints["age"])
print(base)                  # <class 'int'>             —— 真正的类型
print(meta)                  # ['单位:岁', 'must be > 0']  —— 挂上去的元数据

print(get_type_hints(birthday)["age"])   # <class 'int'> —— 不加 include_extras,元数据被丢掉
```

**它解决什么问题**:你想给一个 `int` 附加"语义/约束"(单位、取值范围、校验规则),又不想为此造一个新类型(包装类会让 `+ - *` 全失效),也不想塞进文档字符串(工具读不到)。`Annotated` 让**类型保持 `int`**(检查器和运行时都当 int),同时携带结构化元数据供框架读取。

真实世界里库就是这么用的——把"约束对象"放进元数据位:

```python
# pydantic v2 / FastAPI(示意,需装库):
# from pydantic import Field
# Score = Annotated[int, Field(ge=0, le=100)]   # 类型仍是 int,Field 是给 pydantic 读的元数据
# pydantic 运行时读出 Field(ge=0, le=100),对传入值做 0~100 校验;FastAPI 的 Query/Path/Depends 同理
```

> Java 背景可类比 Bean Validation 的 `@Min(0) @Max(100) int score`:注解挂在类型上、由框架在运行时读取才生效——`Annotated` 是 Python 把这种"类型 + 框架元数据"塞进类型注解的方式。

## 五、工具链与运行时类型

- **mypy / pyright**:静态检查器。`mypy yourfile.py` 报类型错误;pyright(VS Code 的 Pylance 内核)随编辑器实时提示。CI 里跑 mypy 是生产项目标配。
- **`from __future__ import annotations`**:让注解延迟成字符串求值,可避免前向引用问题与一些循环依赖(3.x 普遍推荐加)。
- **运行时校验靠库**:注解本身不校验,需要"传错真报错"就用 **pydantic**(读注解做运行时验证 + 解析)——FastAPI 的请求校验就是这么来的(见[第 14 章](14-stdlib-and-ecosystem.md)生态地图)。

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 类型检查时机 | **运行前**(javac/go build 编译期),语言强制 | **也在运行前**(mypy/pyright 静态查),工具可选;解释器运行时无视注解 |
| 不写类型 | 不允许(Java)/类型推断(Go) | 允许,渐进式,不写按动态处理 |
| 泛型 | Java 类型擦除、Go 1.18+ 泛型 | `TypeVar`/`Generic`,3.12+ `class Foo[T]`;注解本就不进运行时 |
| 接口 | `interface`(名义) | `Protocol`(结构化,≈ Go interface 隐式满足) |
| 可空 | Java `Optional<T>`/`@Nullable`、Go 指针/零值 | `X | None`(即 `Optional[X]`) |
| 运行时校验 | 自带(类型安全) | 需 pydantic 等库显式做 |
| 变型 | Java 通配符 `? extends T`(协变)/`? super T`(逆变);Go 泛型无显式变型声明 | `TypeVar(covariant=/contravariant=)`;3.12+ 自动推断;只读协变、可变不变 |

最大差异:Java/Go 的类型是**语言强制**的;Python 的类型注解是**给工具的提示**,解释器无视它。所以"加了类型还传错值会怎样"——运行时啥事没有,只有 mypy 会标红。

## 章末面试卡

**Q1. Python 的类型注解在运行时强制吗?**
不强制。解释器完全无视注解,`def f(x: int)` 传 str 照样运行。注解给**静态检查器**(mypy/pyright)和**读 `__annotations__` 的框架**(pydantic/dataclass/FastAPI)用。想运行时真校验得靠 pydantic 这类库。

**Q2. `Optional[str]` 是什么意思?**
等于 `str | None`,表示"值可能是 str,也可能是 None"。**不表示**参数可省略(可省略是默认值的事)。3.10+ 推荐直接写 `str | None`。

**Q3. 鸭子类型和 `Protocol` 什么关系?`Protocol` 和 ABC 区别?**
`Protocol` 是鸭子类型的静态化:不要求继承,只要对象具备所需方法就算符合,并能被检查器验证(结构化子类型,像 Go interface)。ABC 要求显式继承并实现抽象方法(名义子类型,像 Java 抽象类)。

**Q4. Python 泛型和 Java 泛型有什么不同?**
Java 泛型在编译期做类型擦除(运行时拿不到具体类型参数);Python 注解**本就不进入运行时**,泛型 `list[int]`/`TypeVar` 只对静态检查器有意义。3.12 起有 PEP 695 的 `class Foo[T]` 简洁语法。

**Q5. 怎么给一个"固定字段的字典"加类型?**
用 `TypedDict` 声明每个键的类型,检查器会校验键名与值类型;运行时它仍是普通 dict。适合约定形状的 JSON/配置。

**Q6. 项目里怎么落地类型检查?**
逐步加注解(渐进式),在 CI 跑 `mypy`/`pyright` 拦截类型错误,编辑器用 Pylance 实时提示;需要运行时真正校验输入(如 API 边界)时用 pydantic。常配 `from __future__ import annotations` 规避前向引用。

**Q7. `Annotated[int, x]` 和 `int` 对类型检查器有区别吗?它拿来干嘛?**
没区别——对 mypy/pyright 来说 `Annotated[int, x]` 就是 `int`,元数据透明。它的用途是给类型**挂运行时元数据**:框架用 `get_type_hints(obj, include_extras=True)` + `get_args()` 把元数据取出来做事(pydantic 用它放 `Field(...)` 约束、FastAPI 放 `Query/Depends`)。好处是类型本身不变,不必造包装类。注意 `get_type_hints` 默认会剥掉元数据,必须传 `include_extras=True`。

**Q8. `list[Dog]` 能传给接收 `list[Animal]` 的函数吗?为什么?**
不能。`list` 可变,是**不变(invariant)**的——若允许,函数可往里 `append` 一个 `Animal`(甚至 `Cat`),破坏 `list[Dog]` 的契约,mypy 因此拒绝。要协变就用**只读**类型 `Sequence[Animal]`(放行)。规律:能写就不变,只读可协变,回调入参逆变。3.12+ 泛型由检查器自动推断变型。
