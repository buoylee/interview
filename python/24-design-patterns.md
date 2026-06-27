# 24 · 设计模式:哪些消失、哪些换形、哪些仍需

> **为什么这章重要**:GoF 那 23 个设计模式，多数是在 **C++/Java 这种「函数不是一等公民、类型靠继承」的语言**里，为了绕开语言缺陷而发明的脚手架。Python 有一等函数、duck typing、协议、装饰器，于是**很多模式直接消失、或塌缩成一行**。面试里「会分模式的人」和「背模式的人」差就差在这：你能说出*哪个模式在 Python 里根本不需要、为什么*，比能默写 UML 值钱得多。本章不重教前面的机制（装饰器→ch04、`__init_subclass__`/描述符→ch06、迭代协议/上下文管理器→ch07、import 副作用→ch10、DI→ch20），而是把它们**收口成一张「模式 → Python 原语」的地图**。

## 一、心智：GoF 是给「缺一等函数的语言」打的补丁

经典模式解决的真问题就两类：**「把行为当值传来传去」**和**「让代码对扩展开放、对修改封闭」**。Java 没有一等函数，只能用「一个接口 + 一个类 + 一个实例」把一段行为包起来传递——这就是 Strategy、Command、Template Method、Observer 一大半模式的由来。Python 里行为本身就是值（函数是对象，见 ch04），这层包装直接没了。

按「Python 拿原语消化掉的程度」分，模式有**三种命运**：

| 命运 | 含义 | 代表 |
|------|------|------|
| **① 消失** | 语言原生特性直接顶替，模式退化成「就这么写」 | Strategy、Command、Template Method、Singleton、Iterator |
| **② 换形** | 模式还在，但用 Python 原语重写，长相全变 | Registry/Plugin、Factory、Observer、Decorator(GoF)、Adapter |
| **③ 仍需** | 是结构性/状态性的真问题，Python 也省不掉，只是写得更轻 | State、Facade、Proxy、上下文管理器 |

> **一句话心智**：先问「这个模式当年是来补什么缺陷的？」——如果那个缺陷 Python 没有（比如「函数不能当值」），模式就消失或换形。

## 二、消失的模式——语言原生消化掉

### Strategy（策略）→ 传一个函数

GoF 版：定义 `Strategy` 接口 + 一堆实现类 + `Context` 持有一个策略对象。整套就为了「运行时换一段算法」。Python 里算法本身就能当参数：

```python
def cheapest_first(items): return sorted(items, key=lambda x: x.price)
def newest_first(items):   return sorted(items, key=lambda x: x.ts, reverse=True)

def render(items, strategy):          # strategy 就是一个函数
    return strategy(items)

render(cart, cheapest_first)          # 换策略 = 换一个函数
```

`sorted(key=...)`、`max(key=...)`、`list.sort(key=...)` 本身就是策略模式的标准库化。**不需要任何类。**

### Command（命令）→ callable / `partial`

GoF 版：把「一个请求」封装成对象（带 `execute()`），好排队、记日志、撤销。Python 里「一个待执行的动作」就是一个 callable，要绑参数用 `functools.partial`（见 ch04）：

```python
from functools import partial

queue = [
    partial(send_email, to="a@x.com"),   # 把动作 + 参数焊成一个零参 callable
    partial(charge, user_id=42, cents=999),
]
for cmd in queue:                        # 执行队列
    cmd()
```

要支持撤销时，才需要把它升级成带 `do()/undo()` 的对象——那时模式才「回来」。

### Template Method（模板方法）→ 钩子函数取代继承

GoF 版：基类定好算法骨架，把可变步骤留成抽象方法让子类覆盖。Python 里骨架是一个函数，可变步骤当参数传进去，**用组合而非继承**：

```python
def pipeline(data, *, clean, transform):     # 骨架固定，两个钩子可换
    data = clean(data)
    data = transform(data)
    return data

pipeline(rows, clean=drop_nulls, transform=to_upper)
```

继承版当然也能写，但「传函数」省掉了一棵类继承树。

### Singleton（单例）→ 模块即单例

GoF 版要私有构造函数 + 静态 `getInstance()` + 双重检查锁。Python 里**模块天生是单例**：模块第一次被 import 时执行一次，结果缓存进 `sys.modules`，之后任何 import 拿到的都是同一个对象（机制见 ch10）。

```python
# config.py
settings = load_settings()     # 模块顶层只跑一次

# 别处
from config import settings    # 永远是同一个 settings
```

需要单例「对象」时，就在模块顶层建好一个实例，让大家 import 它——比写 Singleton 类干净得多。

> **陷阱（面试爱问）**：模块单例的作用域是**单进程**。`sys.modules` 每个进程一份，所以多进程（`multiprocessing`、gunicorn 多 worker）下每个进程各有一份「单例」。跨进程要真共享得靠外部存储（Redis/DB），不是模块变量。

### Iterator（迭代器）→ 迭代协议

GoF 把遍历封装成 `Iterator` 对象，Python 把它做成了**语言协议**（`__iter__`/`__next__`，生成器 `yield`）——`for x in obj` 直接驱动。这是 ch07 的主题，这里只点名：**在 Python 里你几乎不会手写 Iterator 类，写个生成器函数即可。**

## 三、换形的模式——用 Python 原语重写（本章重头戏）

### Registry / Plugin（注册表 / 插件）★

这是「对扩展开放」最核心的模式，也是把代码从「一坨 if/elif」救出来的关键。目标：**加一个新东西 = 新增一个自包含单元 + 登记一下，不碰任何旧代码**（开闭原则）。Python 有三种主流写法，按耦合强度递增。

**写法 1：dict + 装饰器 + import 副作用（最常用）**

注册表本体就是一个 dict，「注册」就是 `dict[key] = value`，装饰器只是让登记动作贴在定义旁边：

```python
HANDLERS = {}                       # 注册表 = 一个 dict

def register(name):                 # 装饰器工厂
    def deco(fn):
        HANDLERS[name] = fn         # 核心就这一行
        return fn                   # 原样返回，不改包装
    return deco

@register("refund")                 # = register("refund")(handle_refund)
def handle_refund(args): ...

@register("order_status")
def handle_order(args): ...

# 派发方：只认 HANDLERS，不认任何具体 handler —— 旧代码零修改
HANDLERS[name](args)
```

依赖方向被**反转**了：派发器不再 import 每个 handler，是 handler 反过来把自己塞进表。这正是「对修改封闭」。

**写法 2：`__init_subclass__` 自动注册子类（类即插件）**

当每个插件是一个类、且共享基类时，用 `__init_subclass__`（见 ch06，比元类轻）让「子类一定义就自动登记」：

```python
INTENTS = {}
class Intent:
    def __init_subclass__(cls, /, key=None, **kw):
        super().__init_subclass__(**kw)
        if key:
            INTENTS[key] = cls      # 子类定义时触发

class Refund(Intent, key="refund"): ...
class OrderStatus(Intent, key="order_status"): ...
print(sorted(INTENTS))             # ['order_status', 'refund'] —— 无需手动登记
```

**写法 3：`entry_points`——跨包的真插件（工业级）**

前两种都要求插件代码在你自己的代码库里。要让**第三方在别的 pip 包里**给你加插件（pytest 插件、flake8 插件就是这么做的），用 setuptools 的 entry points：

```toml
# 插件包自己的 pyproject.toml
[project.entry-points."myapp.intents"]
refund = "refund_plugin:handle_refund"
```

```python
# 宿主应用启动时发现所有已安装插件
from importlib.metadata import entry_points

for ep in entry_points(group="myapp.intents"):
    HANDLERS[ep.name] = ep.load()      # 跨包自动发现，连 import 路径都不用写死
```

**自动发现的坑**：写法 1/2 的注册全靠「模块顶层被执行」，而模块**没被 import 就不会执行**——这是「插件没生效」的头号原因（等价于 Go 忘了 blank import）。解法是启动时扫描包目录全部 import：

```python
import importlib, pkgutil
import intents                          # 插件都放这个包下

for m in pkgutil.iter_modules(intents.__path__):
    importlib.import_module(f"{intents.__name__}.{m.name}")   # 逐个 import 触发注册
```

**三种写法怎么选**：

| 写法 | 适合 | 代价 |
|------|------|------|
| dict + 装饰器 | 插件是函数、都在本代码库 | 要确保模块被 import（自动发现） |
| `__init_subclass__` | 插件是类、共享基类、要带元数据 | 必须继承基类 |
| `entry_points` | 第三方跨包扩展、装上即生效 | 配置在打包元数据里，较重 |

> **工业版**：当「插件」多到上百个、还要跨网络/进程发现时，这套 dict 注册表会升级成**协议化的注册中心**——LLM Agent 圈现在收敛到的 **MCP（Model Context Protocol）** 就是 tool/agent 的跨进程注册+发现协议；高频派发再叠一层 embedding 路由（semantic-router）做「按语义查表」。本质还是 registry，只是 dict 换成了带网络和向量检索的索引。

### Factory（工厂）→ dict 分发 / `singledispatch`

GoF 的工厂是为了「不用 `new` 具体类、由一个方法决定造谁」。Python 里类本身就是可调用对象，「按 key 造对象」就是查个 dict：

```python
SHAPES = {"circle": Circle, "square": Square}   # 类是一等对象，直接当值
def make_shape(kind, **kw):
    return SHAPES[kind](**kw)                    # 查表 + 调用
```

而「按**类型**分派」（GoF 里要靠多态/双分派解决的）用 `functools.singledispatch`（见 ch04），它内部维护一张「类型 → 实现」的注册表，按第一个实参的类型沿 MRO 查找：

```python
from functools import singledispatch
from datetime import datetime

@singledispatch
def to_json(obj):                       # 兜底实现
    raise TypeError(f"can't encode {type(obj)}")

@to_json.register                       # 按注解的类型登记
def _(obj: datetime): return obj.isoformat()

@to_json.register
def _(obj: list): return [to_json(x) for x in obj]
```

`singledispatch` 其实就是 Factory/Registry 在「类型」维度上的标准库化。

### Observer（观察者）→ callback 列表 / `weakref`

GoF 要 `Subject` 维护 `Observer` 接口列表。Python 里 observer 就是个 callable，subject 存一个列表挨个调：

```python
class Signal:
    def __init__(self):
        self._subs = []
    def connect(self, fn):  self._subs.append(fn)
    def emit(self, *a, **k):
        for fn in list(self._subs):     # 拷贝一份，回调里改订阅也不炸
            fn(*a, **k)

clicked = Signal()
clicked.connect(lambda x: print("got", x))
clicked.emit(42)                        # got 42
```

> **内幕陷阱**：强引用持有 observer 会**阻止它被 GC**（经典内存泄漏：UI 控件销毁了，subject 还攥着它的回调）。订阅者是对象时，用 `weakref.WeakSet` 存它们；是 bound method 时要用 `weakref.WeakMethod`（bound method 每次取属性都新建，普通 `weakref.ref` 会立刻失效）。这点机制见 ch16 的 weakref 段。

### Decorator（GoF 装饰器）vs Python 装饰器——别混

**这俩同名但不是一回事，是高频陷阱题。**

- **Python 装饰器**（`@d`）：**语法糖**，在 `def`/`class` 定义时执行一次，把名字替换成包装结果。是「定义期」的一次性改写。
- **GoF Decorator 模式**：**运行期**把一个对象包进另一个同接口的对象，逐层叠加行为，可动态组合。

GoF Decorator 在 Python 里通常用「包装类 + `__getattr__` 转发」实现：

```python
class UpperStream:                      # 包装任意有 write() 的流，叠加「转大写」
    def __init__(self, inner): self._inner = inner
    def write(self, s): self._inner.write(s.upper())
    def __getattr__(self, name):        # 其余方法透明转发给被包装对象
        return getattr(self._inner, name)

import sys
UpperStream(sys.stdout).write("hi\n")   # HI
```

> 一句话答面试：**Python 装饰器是「定义期换名字」，GoF Decorator 是「运行期套娃」；前者常用来实现后者，但不等价。**

### Adapter（适配器）→ duck typing 让它大半蒸发

GoF Adapter 把「接口不兼容的类」包一层翻译。Python 是 duck typing——只要长得像就能用，根本不要求实现某接口，于是大量 adapter 直接没必要：

```python
def dump(f):                 # 只要求「有 .write()」，不要求是某个类
    f.write("data")

dump(open("a.txt", "w"))     # 文件对象
import io; dump(io.StringIO())   # 内存流，零适配
```

只有当**方法名/签名真不一样**（第三方库要 `.send()`、你手里的对象只有 `.write()`）时，才写一层薄包装去翻译——这才是真 Adapter，而且通常十行内。

## 四、仍需的模式——Python 也省不掉

这些是**结构性/状态性**的真问题，跟语言有没有一等函数无关，Python 只是写得轻一点。

### State（状态机）→ enum + 转移表

「对象行为随内部状态变」是真实需求，Python 常用 enum + 一张转移表（数据驱动，比一堆 if 干净）：

```python
from enum import Enum, auto
class S(Enum):
    DRAFT = auto(); REVIEW = auto(); PUBLISHED = auto()

TRANSITIONS = {                         # (当前态, 事件) -> 新态
    (S.DRAFT,  "submit"):  S.REVIEW,
    (S.REVIEW, "approve"): S.PUBLISHED,
    (S.REVIEW, "reject"):  S.DRAFT,
}
def step(state, event):
    try:    return TRANSITIONS[(state, event)]
    except KeyError:
        raise ValueError(f"{event!r} not allowed in {state}")

step(S.DRAFT, "submit")                 # S.REVIEW
```

复杂工作流才上 `transitions` 库；多数场景这张表就够。

### Facade / Proxy → `__getattr__` 让 Proxy 变轻

Facade（门面）还是个「把一堆子系统包成一个简单接口」的类/模块，没有捷径——它本来就是组织代码，不是补语言缺陷。

Proxy（代理）则被 `__getattr__` 大大简化——拦截属性访问就能做懒加载、访问控制、远程转发：

```python
class Lazy:                             # 懒加载代理：第一次用到才真正构造
    def __init__(self, factory):
        self._factory, self._obj = factory, None
    def __getattr__(self, name):        # 只有访问真实属性时才触发
        if self._obj is None:
            self._obj = self._factory()
        return getattr(self._obj, name)

conn = Lazy(lambda: connect_db())       # 此刻不连库
conn.query("...")                       # 用到了，才真正 connect_db()
```

### 上下文管理器 = Python 原生的「获取—释放」模式

「拿到资源 → 用 → 保证释放」（C++ 的 RAII、Java 的 try-with-resources）在 Python 里被做成了语言协议 `with`（`__enter__`/`__exit__`，或 `@contextmanager`，见 ch07）。这不是 GoF 模式，但属于「Python 把模式提升成语言特性」的同类现象，值得并列记住。

## 五、收口地图：模式 → Python 原语

| GoF 模式 | 当年来补的缺陷 | Python 答案 | 命运 |
|----------|----------------|-------------|------|
| Strategy | 函数不能当值传 | 传函数 / `key=` | 消失 |
| Command | 同上 | callable / `partial` | 消失 |
| Template Method | 只能靠继承换步骤 | 传钩子函数（组合） | 消失 |
| Singleton | 控制唯一实例麻烦 | 模块即单例 | 消失 |
| Iterator | 遍历要手写对象 | 迭代协议 / 生成器 | 消失 |
| **Registry/Plugin** | 扩展要改派发代码 | dict+装饰器 / `__init_subclass__` / `entry_points` | 换形 ★ |
| Factory | 不想写死 `new` | dict 分发 / `singledispatch` | 换形 |
| Observer | 解耦事件通知 | callback 列表 + `weakref` | 换形 |
| Decorator(GoF) | 动态叠加行为 | 包装类 + `__getattr__` | 换形 |
| Adapter | 接口不兼容 | duck typing（多数蒸发） | 换形 |
| State | 行为随状态变 | enum + 转移表 | 仍需 |
| Facade/Proxy | 简化/代理访问 | 门面类 / `__getattr__` 代理 | 仍需 |

## Java/Go 对照框

| | Java / Go | Python |
|--|-----------|--------|
| 策略/命令 | 接口 + 实现类 + 实例（Java）；Go 可传函数 | 直接传函数，无需类 |
| 单例 | 私有构造 + `getInstance` + 双检锁 | 模块即单例（单进程内） |
| 工厂 | 工厂类/方法 + 多态 | dict 分发 / `singledispatch` |
| 插件注册 | SPI `ServiceLoader` + `META-INF/services`；Go `init()`+blank import | dict+装饰器 / `__init_subclass__` / `entry_points` |
| 依赖注入 | Spring 重量级容器 + `@Autowired` | 显式传参 / 工厂函数 / 启动期装配（见 ch20） |

最大认知差：Java 圈把模式当**架构基础设施**（容器、注解、反射满天飞）；Python 圈默认**显式 + 一等函数**，能用一个函数解决就不立一个类。面试被问「你会哪些设计模式」，高分答法不是背名字，而是：**「Python 里这几个模式已经被语言特性消化了——说说我会怎么用一等函数/装饰器/协议达到同样目的，以及哪几个（State、Registry 跨包）才真正需要显式实现。」**

## 章末面试卡

**Q1. 为什么说 Python 里很多 GoF 模式「不需要」了？**
因为半数 GoF 模式（Strategy/Command/Template Method/Observer…）的存在，是为了在「函数不是一等公民」的语言里把一段行为打包成对象来传递。Python 函数本身就是对象，能赋值/传参/返回，这层包装直接消失。要点是答出**根因**（一等函数 + duck typing + 协议 + 装饰器），而非罗列。

**Q2. 实现一个插件注册表，你有几种写法？怎么选？**
三种：① `dict`+装饰器（插件是函数、在本库内，最常用）；② `__init_subclass__`（插件是类、共享基类、带元数据）；③ `entry_points`（第三方跨 pip 包扩展，pytest/flake8 同款）。核心都是「依赖反转」：派发器只认注册表，插件反向登记，加插件不碰旧代码。

**Q3.（陷阱）Python 的 `@decorator` 和 GoF 的 Decorator 模式是一回事吗？**
不是。Python 装饰器是**定义期**的语法糖，执行一次、把名字替换成包装结果；GoF Decorator 是**运行期**把对象逐层包成同接口的对象、可动态组合。前者常被用来实现后者，但概念不同。

**Q4. 为什么模块天然是单例？这个「单例」有什么边界？**
模块首次 import 时执行一次，结果缓存进 `sys.modules`，后续 import 拿到同一对象。边界是**单进程**：`sys.modules` 每进程一份，多进程/多 worker 下每进程各有一份。跨进程真共享要靠 Redis/DB 等外部存储。

**Q5. 自动注册的插件没生效，最可能的原因是什么？**
插件模块**没被 import**——注册靠「模块顶层代码执行」这个副作用，没人 import 就不会执行，注册表是空的（等价于 Go 忘了 blank import）。解法：启动时用 `pkgutil.iter_modules` 扫描插件包并逐个 `import_module`，或改用 `entry_points` 让安装即可发现。

**Q6. `singledispatch` 按什么分派？能按多个参数吗？**
按**第一个实参的类型**，沿该类型的 MRO 在内部「类型→实现」注册表里查找（找不到走兜底）。只单分派；要按多个参数的类型组合分派，得用第三方 `multipledispatch` 或手写。它本质是 Factory/Registry 在类型维度的标准库化。

**Q7. Observer/回调最容易踩的坑是什么？**
强引用持有回调会**阻止订阅者被 GC**，造成泄漏（控件销毁了 subject 还攥着它）。对象订阅者用 `weakref.WeakSet`，bound method 用 `weakref.WeakMethod`（普通 `weakref.ref` 对 bound method 会立刻失效，因为 bound method 是临时对象）。
