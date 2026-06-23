# 15 · CPython 执行模型

> **为什么这章重要**:前面 14 章讲了无数"猜输出 / 为什么"的陷阱——闭包延迟绑定、`UnboundLocalError`、推导式不泄漏变量、零参 `super()` 怎么定位自己、生成器怎么"记住"上次位置。这些**全踩在同一层底座上**:你的代码先被编译成 **code object**,再由一个**栈式解释器**在**帧**上逐条执行,而名字在**编译期**就被分类成了局部/全局/闭包三种取法。这章把这层底座讲透——它是「**收口地图**」:学会它,前面那些散落的 gotcha 收敛成几条运行时原语,面试里再深的"为什么"追问你都接得住。
>
> **本章是脊柱上半段(执行)**,下半段(对象/内存/GC/GIL)在[第 16 章](16-objects-memory-gc-gil.md)。性能剖析的实操(火焰图、py-spy、cProfile)在 [`../performance-tuning-roadmap/06a-python-profiling`](../performance-tuning-roadmap/06a-python-profiling)。
>
> 环境:CPython **3.11.8** 实测;字节码随版本变化较大,3.12/3.13 的差异会单独标注。

## 一句话心智

**源码 → 编译成 code object(含字节码)→ 栈式解释器在帧上跑 eval 循环。名字不是运行时才查的——编译器早就把每个名字定成了 `LOAD_FAST`(局部)/ `LOAD_GLOBAL`(全局)/ `LOAD_DEREF`(闭包)三选一。**

## 一、从源码到 code object

Python 不是逐行解释源码文本。`def` / `class` / 模块在**导入或定义时**先被编译成一个 **code object**——一个不可变对象,装着字节码和它需要的全部静态信息。函数的 code object 挂在 `__code__` 上:

```python
def f(a, b):
    c = a + b * 2
    return c

co = f.__code__
co.co_varnames   # ('a', 'b', 'c')   —— 局部变量名(参数 + 函数体内赋值的)
co.co_consts     # (None, 2)         —— 用到的常量字面量
co.co_names      # ()                —— 引用的全局/属性名(这里没有)
co.co_code       # b'...'            —— 字节码本身(一串 (opcode, arg) 字节对)
```

关键认知:**`a`、`b`、`c` 在编译期就被收进了 `co_varnames`**,编译器据此给每个名字分配一个**槽位编号**。运行时取 `a` 不是去查字典,而是 `LOAD_FAST 0`——按下标读一个数组。这就是为什么函数局部变量访问快(见 §3)。

编译期还做了**常量折叠**等轻量优化(`2 * 3` 在编译时就算成 `6`),但 CPython 的编译器有意保守,不做激进的跨语句优化——重活留给运行时的解释器(见 §6)。

> 不同 code object 的层级:模块有自己的 code object,里面 `LOAD_CONST` 出函数的 code object 再 `MAKE_FUNCTION` 把它和闭包/默认值绑成函数对象。推导式、`lambda`、生成器各自也是独立的 code object——这正是"推导式自带一层作用域"的实现根(见 §3)。

## 二、栈式解释器:求值栈 + eval 循环 + 帧

CPython 是一台**基于栈的虚拟机**。`dis` 模块把字节码反汇编出来看:

```python
import dis
dis.dis(f)
```
```
              0 RESUME                   0      # 3.11 引入:协程/生成器恢复点,普通函数也有
              2 LOAD_FAST                0 (a)  # 把局部 a 压上求值栈
              4 LOAD_FAST                1 (b)  # 把 b 压栈
              6 LOAD_CONST               1 (2)  # 把常量 2 压栈
              8 BINARY_OP                5 (*)  # 弹 b、2,算 b*2,压回
             12 BINARY_OP                0 (+)  # 弹 a、(b*2),算和,压回
             16 STORE_FAST               2 (c)  # 弹栈顶存进局部槽位 c
             18 LOAD_FAST                2 (c)
             20 RETURN_VALUE                    # 返回栈顶
```
（左列是字节码偏移,与函数写在文件第几行无关——可复现;`dis` 实际还会在最左多一列源码行号。）

三个角色:

- **求值栈(value stack)**:操作数临时落脚的地方,指令在它上面压入/弹出。
- **eval 循环**:CPython 解释器核心是一个巨大的指令分发循环(`ceval.c` 里的 `_PyEval_EvalFrameDefault`),逐条取 opcode、跳到对应处理、改栈。所有 Python 代码最终都从这个循环里流过。
- **帧对象(frame)**:每次函数**调用**新建一个帧,保存这次调用的局部变量、求值栈、以及**指令指针** `f_lasti`(执行到第几条字节码)。帧用 `f_back` 串成链——这条链就是你在 traceback 里看到的调用栈。

```python
import inspect
def g():
    frame = inspect.currentframe()
    return frame.f_code.co_name, frame.f_back.f_code.co_name
g()   # ('g', '<module>')  —— 当前帧 + 上一帧(调用者)
```

记住这张图:**code object 是"剧本"(不可变、可共享),帧是"一次演出"(每次调用新建、装着这次的状态)**。同一个函数递归 10 层,就是同一个 code object 配 10 个帧。

## 三、名字编译成三种 LOAD(收口)

这是本章最高杠杆的一节。**Python 的名字解析发生在编译期,不是运行时**。编译器扫描每个作用域,把每个名字归成三类,生成三种不同的取指令:

```python
G = 10                       # 模块全局
def outer(p):                # p 被内层函数捕获
    def inner(q):            # q 是 inner 的局部
        return q + p + G     # q=局部, p=闭包变量, G=全局
    return inner

import dis
dis.dis(outer(1))
```
```
  0 COPY_FREE_VARS    1          # 把闭包变量(p)的 cell 拷进帧
  ...
  4 LOAD_FAST         0 (q)      # 局部 → 按数组下标取,最快
  6 LOAD_DEREF        1 (p)      # 闭包 → 从 cell 里取(见 §4)
  ...
 12 LOAD_GLOBAL       0 (G)      # 全局 → 查模块 dict,查不到再查 builtins
```

| 取法 | 用于 | 怎么取 | 成本 |
|--|--|--|--|
| `LOAD_FAST` | 函数局部(在 `co_varnames`) | 数组下标读 | 最快 |
| `LOAD_DEREF` | 闭包变量(外层函数的局部,被内层引用) | 从 cell 对象读 | 次之 |
| `LOAD_GLOBAL` | 模块全局 / 内置 | 查模块 `__dict__`,miss 再查 `builtins` | 最慢 |

**这一条规则收口了前面一堆 gotcha**:

- **`UnboundLocalError`**(第 [04 章](04-functions-closures-decorators.md)):函数里只要**有一处给名字赋值**,编译器就把它整段归为局部(进 `co_varnames`),于是赋值前的读取走 `LOAD_FAST` 一个还没绑定的槽位 → 报错。不是"运行到才发现",是编译期就定了性。
- **热循环把全局提成局部**(第 16 章性能惯用法):循环里反复 `LOAD_GLOBAL` 查 dict,把 `f = some.func` 提到循环外变成 `LOAD_FAST`,省掉每次的字典查找。
- **推导式不泄漏变量**(第 [03 章](03-control-flow-comprehensions.md)):列表推导式被编译成**独立的 code object**,像个隐藏函数被调用——它的循环变量是那个隐藏函数的局部,自然不漏到外面:

```python
def uses_comp(xs):
    return [i*i for i in xs]
dis.dis(uses_comp)
#   LOAD_CONST  (<code object <listcomp>>)   ← 推导式是独立 code object
#   MAKE_FUNCTION                             ← 包成函数
#   ...  CALL                                 ← 调用它,i 是它的局部,不泄漏
```

> **3.12 变化**:PEP 709 把列表/字典/集合推导式**内联**进了外层(不再 `MAKE_FUNCTION`+`CALL`,快了不少),但**作用域隔离的语义保留**——`i` 仍不泄漏。3.11 仍是独立 code object。

## 四、cell 与闭包

§3 说闭包变量走 `LOAD_DEREF` 从 **cell** 里取。cell 是什么?当外层函数的局部变量被内层函数引用(尤其会被 `nonlocal` 修改)时,CPython 不能把它当普通栈上的局部——内层函数可能在外层返回后还要读写它。于是这个变量被装进一个 **cell 对象**(一个单格的盒子),外层和内层共享这个 cell 的引用:

```python
def make_counter():
    n = 0
    def inc():
        nonlocal n      # 声明:我要改外层的 n
        n += 1
        return n
    return inc

c = make_counter()
c.__closure__                       # (<cell at 0x...: int object>,)
c.__closure__[0].cell_contents      # 0,然后
c(); c()
c.__closure__[0].cell_contents      # 2  —— 改的是 cell 里的内容
```

**这就是闭包延迟绑定陷阱的根**(第 04 章那个 `[f() for f in fns]` 全返回最后一个值):闭包捕获的是 **cell(盒子)本身,不是当时盒子里的值**。循环里所有内层函数共享同一个 cell,等你真去调用时,cell 里早就是循环结束后的最终值了。`nonlocal n; n += 1` 之所以能改到外层,也是因为它操作的是共享 cell,而不是新建一个局部绑定。

### `__class__` cell 与零参 `super()`

零参 `super()` 一直有点"魔法":它怎么知道"当前是哪个类、哪个实例"?答案也是 cell。**编译器发现方法体里用了 `super()`(或裸 `__class__`),就偷偷在方法里塞一个名为 `__class__` 的闭包变量(cell)**,绑定到"定义这个方法时所在的类":

```python
class Base:
    def who(self): return "base"
class Sub(Base):
    def who(self):
        return super().who() + "+sub"

Sub().who()                      # 'base+sub'
Sub.who.__code__.co_freevars     # ('__class__',)  ← 编译器塞的闭包变量
```

`super()` 零参等价于 `super(__class__, self)`:`__class__` 从 cell 拿(定义期就定死的类),`self` 从第一个参数拿。所以 `super()` 找的是 **MRO 里"当前类"之后的下一个类**,而不是 `self` 的直接父类——这正是协作式多继承的关键(MRO/C3 见第 [06 章](06-oop-2-inheritance-descriptors-metaclasses.md))。

## 五、生成器 = 可挂起的帧

普通函数调用:建帧 → 跑完 → 销毁帧。**生成器的不同点在于:它的帧不在 `yield` 处销毁,而是被挂起保存下来**。生成器对象 `gen.gi_frame` 就是那个被冻结的帧,`gi_code` 是它的 code object:

```python
def g():
    yield 1
    yield 2

gen = g()
gen.gi_frame.f_lasti     # 0   —— 还没开始,指令指针在起点
next(gen)                # 1
gen.gi_frame.f_lasti     # 8   —— 停在第一个 yield 处
next(gen)                # 2
gen.gi_frame.f_lasti     # 16  —— 推进到第二个 yield
```

`next()` 做的就是:**拿回这个挂起的帧,从 `f_lasti` 记录的位置继续跑 eval 循环,跑到下一个 `yield` 再把帧冻住、把值交出来**。这就是"生成器怎么记住上次位置"的全部真相——状态不在什么魔法里,就在那个保存下来的帧的局部变量和指令指针里。

由此还能理解几个操作(协议细节见第 [07 章](07-iterators-generators-context-managers.md)):

- `gen.throw(exc)`:在挂起点把一个异常**注入**进帧,就像 `yield` 那行抛了异常。
- `gen.close()`:在挂起点注入 `GeneratorExit`,触发帧里的 `finally` 清理后结束。
- `yield from sub`:不仅把迭代委托给 `sub`,还把 `send()`/`throw()` 透传给 `sub`、并接住 `sub` 的返回值——这正是 `asyncio` 早年用它搭协程的原因。

## 六、自适应专门化(PEP 659)+ JIT 现状

经典结论"Python 慢因为动态类型——每次 `a + b` 都要运行时查类型找 `__add__`"在 **3.11 之后需要打个折扣**。3.11 引入了**自适应专门化解释器**(adaptive specializing interpreter, PEP 659):

解释器**观察**每条字节码实际遇到的类型,跑热之后**把通用 opcode 原地换成专门版**(quickening)。比如通用的 `BINARY_OP +` 一旦总是看到两个 int,就换成 `BINARY_OP_ADD_INT`——跳过类型查找和方法分发,直接走整数相加的快路径:

```python
def add(a, b):
    return a + b
for _ in range(100):     # 跑热
    add(1, 2)

import dis
dis.dis(add, adaptive=True)   # adaptive=True 看专门化后的实际指令
#   RESUME_QUICK
#   LOAD_FAST__LOAD_FAST     ← 两条 LOAD_FAST 被合成一条超级指令
#   BINARY_OP_ADD_INT        ← 专门化成"整数加",省掉动态分发
#   RETURN_VALUE
```

机制要点:**inline cache**(把"上次见到的类型/方法"缓存在指令旁边)+ **超级指令**(把常见的指令对合并)。如果类型变了(guard 失败),会**退化**回通用版重新观察。这不是真正的 JIT(没编译成机器码),但在不改你代码的前提下显著提速了热路径。

- **真 JIT**:3.13 引入**实验性** copy-and-patch JIT,3.14 仍属实验/可选,默认不开,短期别指望。
- **不变的部分**:专门化帮的是"类型稳定的热循环";它**改变不了**"一切皆对象、有 GIL"这些更深的成本(见第 [16 章](16-objects-memory-gc-gil.md)"为什么慢"总账)。重数值计算该交给 numpy/C 扩展的,还是得交出去。

## Java/Go 对照框

| | Java(HotSpot) | Go | Python(CPython 3.11+) |
|--|--|--|--|
| 编译产物 | 字节码(.class) | AOT 原生机器码 | 字节码(code object) |
| 执行 | 解释 + 分层 JIT 编译成机器码 | 直接跑机器码 | 栈式解释 + 自适应专门化(3.13 实验 JIT) |
| 名字解析 | 编译期静态绑定(含类型) | 编译期静态 | 编译期定 fast/global/deref,**但值是动态的** |
| code object ≈ | .class 常量池 + 方法字节码 | —— | `__code__`(`co_code`/`co_consts`/`co_varnames`…) |
| 闭包捕获 | 捕获 final/effectively-final 的**值** | 捕获**变量**(同 Python) | 捕获 **cell**(盒子),不是值 |

一句话:**三家都先编字节码(Go 直接到机器码),差别在"之后怎么执行"和"名字绑得多死"**。Python 把名字的"取法"在编译期定死(快),但"取到的值是什么类型"留到运行时(灵活,也是慢和专门化的来源)。

## 章末面试卡

**Q1. Python 的名字解析在什么时候发生?三种 LOAD 是什么?**
编译期。编译器扫描作用域,把每个名字定成 `LOAD_FAST`(函数局部,数组下标取,最快)/ `LOAD_DEREF`(闭包变量,从 cell 取)/ `LOAD_GLOBAL`(模块全局→builtins,查 dict,最慢)。运行时不再"决定走哪种",只是执行已定好的指令。

**Q2. 为什么会 `UnboundLocalError`?**
函数体内只要有一处给某名字赋值,编译器就把它**整段**归为局部(进 `co_varnames`),赋值前的读取走 `LOAD_FAST` 一个未绑定槽位 → 报错。是编译期定性,不是运行到才发现;想读外层同名变量要 `global`/`nonlocal`。

**Q3. 闭包延迟绑定陷阱(循环里建的函数全返回最后值)的根因?**
闭包捕获的是 **cell(盒子)本身,不是当时的值**。循环里所有内层函数共享同一个 cell,真正调用时 cell 里已是循环结束后的最终值。`nonlocal x; x+=1` 能改到外层也是因为操作的是共享 cell。

**Q4. 零参 `super()` 怎么知道"当前类"?**
编译器发现方法用了 `super()`,会在方法里塞一个名为 `__class__` 的闭包变量(cell),绑定到定义该方法时所在的类(`co_freevars` 里能看到 `__class__`)。`super()` ≈ `super(__class__, self)`,据此沿 MRO 找当前类之后的下一个类。

**Q5. 生成器怎么"记住"上次执行到哪?**
生成器的帧在 `yield` 处不销毁、被挂起保存(`gen.gi_frame`),局部变量和指令指针 `f_lasti` 都留在帧里。`next()` 拿回这个帧、从 `f_lasti` 继续跑到下一个 `yield`。`throw`/`close` 是在挂起点注入异常。

**Q6. 都说"动态类型让 Python 慢",3.11 之后还成立吗?**
部分被改写。3.11 的自适应专门化(PEP 659)会观察实际类型,把热路径的通用 opcode 换成专门版(如 `BINARY_OP_ADD_INT`)、合并超级指令,省掉动态分发——对类型稳定的热循环有效。但它改变不了"一切皆对象 + GIL"这些更深的成本(见第 16 章),也不是真 JIT(3.13 才有实验性 JIT)。
