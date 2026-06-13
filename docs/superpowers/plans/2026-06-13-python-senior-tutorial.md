# Python 资深工程师教程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在重构后的 `python/` 产出一套 17 章 + 面试卡 + README 的资深 Python 语言教程,面向 Java/Go 后端转 Python 面试者。

**Architecture:** 编号 Markdown 章节(`00-`…`16-`、`99-`),每章=导引 + 正文 + Java/Go 对照框 + 章末面试卡。吸收 `python/` 下 5 篇旧笔记后删除碎片。并发/性能/web 仅指针链接到已有目录,不重写。

**Tech Stack:** Markdown;代码示例用 Python 3.12/3.13;验证用临时 `.py` 脚本跑代码块(用完即删),不建 pytest 套件。

设计来源:`docs/superpowers/specs/2026-06-13-python-senior-tutorial-design.md`

---

## 文件结构

```
python/
  README.md                                    # 目录 + 阅读导航(Task 1)
  00-mental-model-and-setup.md                 # Task 2
  01-names-objects-memory.md                   # Task 3
  02-builtin-types-data-structures.md          # Task 4
  03-control-flow-comprehensions.md            # Task 5
  04-functions-closures-decorators.md          # Task 6
  05-oop-1-classes-protocols.md                # Task 7  (吸收 魔法方法.md / 类属性与实例属性.md)
  06-oop-2-inheritance-descriptors-metaclasses.md  # Task 8
  07-iterators-generators-context-managers.md  # Task 9
  08-exceptions.md                             # Task 10
  09-typing.md                                 # Task 11
  10-modules-packages-imports.md               # Task 12 (吸收 模块与导入.md)
  11-tooling-envs-packaging.md                 # Task 13
  12-testing.md                                # Task 14
  13-concurrency-bridge.md                     # Task 15 (并发-进程-线程-协程.md 要点 → 此处,深链 python-concurrency/)
  14-stdlib-and-ecosystem.md                   # Task 16 (吸收 常用库.md)
  15-cpython-internals-performance.md          # Task 17
  16-pythonic-idioms.md                        # Task 18
  99-interview-cards.md                        # Task 19
  (删除) 魔法方法.md 类属性与实例属性.md 模块与导入.md 常用库.md 并发-进程-线程-协程.md  # Task 20
```

旧笔记删除统一放到 Task 20(全部并入完成后再删,避免中途丢参考)。

---

## 每章任务通用流程(Chapter Task Procedure)

除 Task 1、Task 20 外,每个章节任务都执行下面 5 步。任务正文只列"本章必须覆盖的内容清单 + 必含示例 + 对照点 + 面试卡种子",不预写最终散文。

- [ ] **Step A — 写正文**:按"导引 → 正文(由浅入深)→ Java/Go 对照框 → 章末面试卡"模板,覆盖该任务列出的全部 must-cover 条目,且必须包含列出的"必含示例/陷阱"。
- [ ] **Step B — 验证代码块**:把本章所有可执行代码块(尤其"猜输出"答案)抄进 `/tmp/ch<NN>_check.py` 跑一遍,确认真实输出与文中声称一致。命令:`python3 /tmp/ch<NN>_check.py`。期望:无异常,输出与文中一致;不一致就改文中说法。
- [ ] **Step C — 清理**:`rm /tmp/ch<NN>_check.py`。
- [ ] **Step D — 校正交叉引用**:确认本章对其他章/`python-concurrency/`/`performance-tuning-roadmap/` 的链接路径真实存在。
- [ ] **Step E — 提交**:`git add python/<file>.md && git commit -m "python 教程:第 NN 章 <标题>"`。

> 验证用真实 `python3` 跑过的输出,不靠记忆——"猜输出" drill 写错答案是这套教程最丢人的 bug。

---

## Task 1: README 阅读导航

**Files:** Create `python/README.md`

- [ ] **Step 1:** 写一页导航:教程定位(Java/Go 后端→资深 Python)、17 章顺序表(章号 + 一句话简介,与 spec 第 5 节一致)、推荐读法(线性通读 vs 按主题跳读)、与 `python-concurrency/`、`performance-tuning-roadmap/`、`fastapi-ops/` 的关系说明(并发/性能/web 深度在那些目录)。
- [ ] **Step 2:** 提交 `git add python/README.md && git commit -m "python 教程:README 阅读导航"`。
- (README 暂列全部 18 个文件名;后续章节产出即生效,无需回改。)

---

## Task 2: 第 00 章 — 心智模型与起步

**Files:** Create `python/00-mental-model-and-setup.md`(走通用流程,NN=00)

**Must-cover:**
- Python 设计哲学(`import this` 的 Zen 要点:可读性、显式优于隐式)。
- 执行模型:源码→字节码(`.pyc`/`__pycache__`)→ CPython 虚拟机解释;REPL;脚本 vs 模块。
- 实现版图:CPython / PyPy / 其他;本教程以 CPython 3.12/3.13 为准。
- **总纲心智**:"一切皆对象(有 id/type/value)+ 名字只是绑定"——后续 01 章展开,这里先建立直觉。
- 起步:装哪个版本、`python3 -m venv` 一句话起一个隔离环境(细节留到第 11 章)、怎么用本教程(配合临时脚本跑代码)。

**必含示例:** `id()`/`type()` 各看一次;一个 `.pyc` 缓存的观察(import 后出现 `__pycache__`)。
**对照点:** 与 JVM 字节码/JIT 的类比与差异(无强制编译步骤、默认无 JIT,3.13 起实验 JIT);与 `go build` 静态编译的对比。
**面试卡种子:** "Python 是解释还是编译型?"、".pyc 是什么"、"CPython/PyPy 区别"。

---

## Task 3: 第 01 章 — 名字、对象与内存模型

**Files:** Create `python/01-names-objects-memory.md`(NN=01)

**Must-cover:**
- 名字是引用绑定,不是盒子;赋值 = 绑定;一对象多名字(别名)。
- 可变 vs 不可变(int/str/tuple/frozenset 不可变;list/dict/set/对象可变)。
- `is`(身份)vs `==`(值);小整数缓存(-5~256)与字符串驻留是 CPython 实现细节,**值比较永远用 `==`**。
- 别名导致的就地修改可见性;`copy.copy` 浅拷贝 vs `copy.deepcopy` 深拷贝。
- 引用计数基础(`sys.getrefcount`)+ 循环引用为何需要分代 GC(此处入门,第 15 章深入)。

**必含示例(全部要跑验证):** `a=256;b=256;a is b`→True 与 `a=257;b=257;a is b`→可能 False;别名 `b=a;a.append` 影响 `b`;`[[0]*3]*3` 共享内层引用三行同变 + 正解 `[[0]*3 for _ in range(3)]`;浅 vs 深拷贝对嵌套 list 的差异。
**对照点:** Java 引用 vs 基本类型;`==` vs `.equals` 正好对应 Python `is` vs `==`;Go 值/指针语义。
**面试卡种子:** "`is` 和 `==` 区别"、"为什么 `a is b` 对 256 成立对 257 不一定"、"深浅拷贝"、猜输出:别名/`[[]]*n`。

---

## Task 4: 第 02 章 — 内置类型与数据结构

**Files:** Create `python/02-builtin-types-data-structures.md`(NN=02)

**Must-cover:**
- 数值:int 任意精度、float(IEEE754,`0.1+0.2`)、`decimal`/`fraction` 何时用、`bool` 是 int 子类、`/` 总返 float vs `//` 地板除 vs 负数地板除符号、`%` 符号随除数。
- 文本与字节:`str`(Unicode 码点序列、不可变)vs `bytes`/`bytearray`;`encode`/`decode`;f-string;为什么 Java 的 String/byte[] 直觉会坑你。
- 序列:list / tuple / range 的差异与选型;切片(不越界、负索引、步长、切片赋值)。
- 映射与集合:dict(3.7+ 保序、视图对象、哈希要求)、set/frozenset;`dict.get`/`setdefault`/`defaultdict`。
- 复杂度速查(list 尾部 O(1) 头部 O(n)、dict/set 平均 O(1));dict/list 的过度分配扩容(内部,简述)。

**必含示例(跑验证):** `7/2`、`-7//2`、`-7%2`;`0.1+0.2`;`True+True`、`[1,2][True]`;切片越界返回 `[]` 而单索引越界报错;`dict` 保序;`d.get(k, default)`。
**对照点:** Java `int`/`BigInteger` vs Python 统一 int;Java `String` 编码 vs Python str/bytes 分离;Java `HashMap` 无序 vs Python dict 保序。
**面试卡种子:** "str 和 bytes 区别"、"`/` 和 `//`"、"dict 有序吗 / 怎么实现保序"、"bool 是 int 吗"。

---

## Task 5: 第 03 章 — 控制流、推导式、解包

**Files:** Create `python/03-control-flow-comprehensions.md`(NN=03)

**Must-cover:**
- 真值性(falsy:`0/0.0/""/[]/{}/()/None/False`);`if not lst` vs `if lst is None` 的区别。
- 链式比较 `1 < x < 10` 的真实语义;`and`/`or` 返回操作数(短路求值)。
- 循环:`for`/`while`、`else` 子句(无 `break` 才执行)、`enumerate`/`zip`、`break`/`continue`。
- `match` 结构化模式匹配(3.10+):字面量/序列/映射/类模式/守卫/通配。
- 推导式(list/dict/set/生成器);推导式变量不泄漏 vs `for` 变量泄漏(无块级作用域)。
- 海象 `:=`;解包(`a,*rest=...`、`*args`/`**kwargs` 在定义与调用点)。

**必含示例(跑验证):** `for...else` 查找命中/未命中;`0 or "x"`、`"a" and "b"`;`[i for i in range(3)]` 后 `i` 未定义而 `for j in...` 后 `j==2`;`match` 一个点;`a,*b=[1,2,3]`。
**对照点:** Java/Go 的 `{}` 块级作用域 vs Python 仅函数/推导式开作用域;Java switch vs `match`;三元 `a if c else b`。
**面试卡种子:** "什么是真值性"、"`and`/`or` 返回什么"、"推导式变量会泄漏吗"、"`for...else`"。

---

## Task 6: 第 04 章 — 函数:一等公民、闭包、装饰器

**Files:** Create `python/04-functions-closures-decorators.md`(NN=04)

**Must-cover:**
- 函数是对象(可赋值/传参/返回);`def` vs `lambda`。
- 参数体系:位置/关键字、默认值、`*args`/`**kwargs`、仅位置 `/`、仅关键字 `*`。
- **可变默认参数陷阱**(定义时求值一次)+ `None` 哨兵正解。
- 闭包:捕获的是变量绑定;**循环 lambda 延迟绑定**陷阱 + `lambda i=i` 快照;`nonlocal`。
- `functools`:`partial`、`wraps`、`lru_cache`、`reduce`、`singledispatch`。
- 装饰器:无参装饰器、带参装饰器(三层)、类装饰器、`@wraps` 为何必要;堆叠顺序。

**必含示例(跑验证):** 可变默认参数 `add(1)`→`[1]`、`add(2)`→`[1,2]` 与 `None` 正解;`funcs=[lambda:i for i in range(3)]` 全返 2 与默认参数修复;一个带参装饰器(如计时/重试)且 `@wraps` 保留 `__name__`。
**对照点:** Java 匿名类/lambda 与 final 捕获 vs Python 闭包延迟绑定;Java 注解 vs Python 装饰器(装饰器是真包装,注解是元数据)。
**面试卡种子:** 可变默认参数猜输出、闭包延迟绑定猜输出、"装饰器原理"、"`lru_cache` 做了什么"。

---

## Task 7: 第 05 章 — OOP(一):类、属性、协议

**Files:** Create `python/05-oop-1-classes-protocols.md`(NN=05)
**吸收:** `python/魔法方法.md`、`python/类属性与实例属性.md`(把其有效内容并入本章)

**Must-cover:**
- 类与实例;`__init__` vs `__new__`(创建 vs 初始化);`self`。
- **类变量 vs 实例变量**(共享可变陷阱;`self.x=` 新建实例属性 vs 就地 mutate 共享)——来自旧笔记。
- 方法类型:实例方法 / `@classmethod` / `@staticmethod`;`@property`(getter/setter/deleter)。
- `__slots__`(省内存、禁动态属性)。
- 数据模型/dunder(来自旧笔记):`__repr__` vs `__str__`、`__len__`/`__getitem__`/`__contains__`/`__iter__`、`__eq__`+`__hash__` 契约(定义 `__eq__` 不定义 `__hash__` 变不可哈希)、运算符重载、`__call__`、`__enter__/__exit__` 预告。
- `dataclass`(`field`、`frozen`、`default_factory`)、`namedtuple`、`enum`。

**必含示例(跑验证):** 类变量 `tricks=[]` 被两个实例共享 + `__init__` 内 `self.tricks=[]` 正解;`@property`;`__eq__`+`__hash__`;`@dataclass` 一个。
**对照点:** Java static 字段 vs Python 类变量(都共享,但 Python 可变对象更易踩)、Java getter/setter vs `@property`、Java `equals/hashCode` 契约 vs `__eq__/__hash__`、Java record vs `@dataclass`。
**面试卡种子:** "类变量 vs 实例变量"(猜输出)、"`__new__` 和 `__init__`"、"`__str__` vs `__repr__`"、"`__eq__` 必须配 `__hash__` 吗"、"`__slots__` 作用"。

---

## Task 8: 第 06 章 — OOP(二):继承、描述符、元类

**Files:** Create `python/06-oop-2-inheritance-descriptors-metaclasses.md`(NN=06)

**Must-cover:**
- 继承、方法重写;**MRO 与 C3 线性化**(`Cls.__mro__`、菱形继承);`super()` 协作式多继承(不是"调父类",是按 MRO 走下一个)。
- 描述符协议(`__get__`/`__set__`/`__set_name__`):**`@property`/方法/`classmethod` 本质都是描述符**;data vs non-data descriptor 优先级。
- 属性拦截:`__getattr__`(找不到才触发)vs `__getattribute__`(每次都触发)vs `__setattr__`;`__getattr__` 实现代理/惰性。
- 元类:`type` 是类的类;`class` 语句怎么调用元类;`__init_subclass__`(轻量替代)、`__set_name__`;何时真需要元类(基本"你不需要")。
- ABC(`abc.ABC`/`@abstractmethod`)与 `Protocol` 结构化类型(鸭子类型的静态化)。

**必含示例(跑验证):** 菱形继承 `D.__mro__` + `super()` 链式调用顺序;一个最小描述符类;`__getattr__` 兜底;`__init_subclass__` 注册子类。
**对照点:** Java 单继承+接口 vs Python 多继承+MRO;Java 反射/字节码增强 vs Python 描述符/元类;Java 抽象类/接口 vs ABC/Protocol(名义 vs 结构化子类型)。
**面试卡种子:** "MRO 怎么算 / 菱形继承"、"`super()` 到底调谁"、"描述符是什么 / property 怎么实现的"、"`__getattr__` vs `__getattribute__`"、"什么时候用元类"。

---

## Task 9: 第 07 章 — 迭代器、生成器、上下文管理器

**Files:** Create `python/07-iterators-generators-context-managers.md`(NN=07)

**Must-cover:**
- 可迭代 vs 迭代器(`__iter__`/`__next__`、`StopIteration`);`iter()`/`next()`。
- 生成器函数(`yield`)、生成器表达式、惰性求值与内存优势;`yield from` 委托;生成器的 `send`/`close`(简述,关联协程历史)。
- `itertools` 常用(`chain`/`islice`/`groupby`/`count`/`product`/`accumulate`)。
- 上下文管理器:`with` 协议(`__enter__`/`__exit__`、异常处理返回值)、`contextlib.contextmanager`、`ExitStack`、`suppress`。

**必含示例(跑验证):** 自定义迭代器类;生成器 vs list 的惰性(无限 `count` + `islice`);`@contextmanager` 写一个;`with` 中异常时 `__exit__` 被调用。
**对照点:** Java `Iterator`/`Iterable`、Java Stream 惰性 vs 生成器;Java try-with-resources vs `with`。
**面试卡种子:** "可迭代 vs 迭代器"、"生成器省内存为什么"、"`yield from`"、"`with` 原理 / 如何自定义"。

---

## Task 10: 第 08 章 — 异常与错误处理

**Files:** Create `python/08-exceptions.md`(NN=08)

**Must-cover:**
- 异常层级(`BaseException`/`Exception`/`KeyboardInterrupt`/`SystemExit`);自定义异常。
- `try/except/else/finally` 语义;多 `except`、元组捕获;`finally` 与 return 的交互。
- 异常链:`raise ... from ...`、`__cause__`/`__context__`;重新抛出。
- **EAFP vs LBYL** 惯用法(Python 偏 EAFP)。
- 异常组与 `except*`(3.11+,关联并发);`contextlib.suppress`;`warnings`;`assert` 用途与 `-O` 关闭。

**必含示例(跑验证):** `try/except/else/finally` 执行顺序;`raise X from e` 的链;`except (A, B)`;`suppress`。
**对照点:** Java 受检异常(checked)vs Python 全非受检;Java `try-finally` 资源管理 vs Python `with`;Go `error` 返回值 + `panic/recover` vs Python 异常。
**面试卡种子:** "EAFP vs LBYL"、"`else` 子句作用"、"异常链 `raise from`"、"Python 有受检异常吗"。

---

## Task 11: 第 09 章 — 类型系统与 typing

**Files:** Create `python/09-typing.md`(NN=09)

**Must-cover:**
- 动态 + 鸭子类型;渐进类型(类型注解不在运行时强制,靠 mypy/pyright 静态检查)。
- 基础注解:变量/参数/返回;`Optional`/`X | Y`(3.10+)、`Any`、`Union`。
- 泛型:`list[int]`、`TypeVar`、`Generic`、**PEP 695 `class Foo[T]` / `def f[T]()`**(3.12+)、`Self`(3.11+)。
- 进阶:`Protocol`(结构化)、`TypedDict`、`Literal`、`Final`、`@overload`、`ParamSpec`/`Concatenate`、`Annotated`、`Callable`。
- 工具:mypy / pyright 基本用法;`__annotations__`;`from __future__ import annotations` 与字符串注解;运行时类型(pydantic 预告)。

**必含示例(跑验证 + 可选 mypy 说明):** 一个泛型函数(PEP 695 语法);`Protocol` 定义一个结构化接口;`TypedDict`;`@overload` 形态。注:注解不影响运行时行为这一点要用示例点明(传错类型不报错)。
**对照点:** Java 泛型类型擦除 vs Python 注解也不在运行时生效(但机制不同:Java 编译期擦除,Python 本就不检查);Java 名义接口 vs `Protocol` 结构化;Go interface(结构化)≈ `Protocol`。
**面试卡种子:** "类型注解运行时生效吗"、"`Protocol` vs ABC"、"`Optional[X]` 是什么"、"鸭子类型"。

---

## Task 12: 第 10 章 — 模块、包、导入系统

**Files:** Create `python/10-modules-packages-imports.md`(NN=10)
**吸收:** `python/模块与导入.md`

**Must-cover:**
- 模块 vs 包;`__init__.py` 作用;命名空间包(无 `__init__.py`)。
- import 机制:finders/loaders、`sys.modules` 缓存(模块只执行一次)、`sys.path`、绝对 vs 相对导入。
- `__name__ == "__main__"` 惯用法;`python -m` 运行模块/包。
- 循环导入成因与规避;`__all__` 与 `from x import *`;重新导出。

**必含示例(跑验证):** 观察模块只执行一次(`sys.modules` 缓存);`if __name__=="__main__"`;一个小循环导入 + 拆解。
**对照点:** Java package/classpath、Go package/import path vs Python 模块缓存与 `sys.path`;Java 无循环依赖编译报错 vs Python 运行期才炸。
**面试卡种子:** "import 会执行几次"、"循环导入怎么解决"、"`if __name__=='__main__'` 为什么写"、"`__init__.py` 干啥"。

---

## Task 13: 第 11 章 — 工程化:环境、依赖、打包、工具链

**Files:** Create `python/11-tooling-envs-packaging.md`(NN=11)

**Must-cover:**
- 虚拟环境:为什么需要、`venv`、激活;全局/用户/项目级隔离。
- 依赖管理:`pip` + `requirements.txt` 的局限;现代方案 `uv`(推荐)/`poetry`/`pdm`;锁文件与可复现安装。
- `pyproject.toml`(PEP 621 元数据、构建后端)。
- 打包发布:sdist vs wheel、`build`、(简述 PyPI 发布)。
- 质量工具链:`ruff`(lint+format,取代 flake8/black/isort)、`mypy`、`pre-commit`。
- 项目布局:src layout vs flat;`__init__.py` 与可导入性。

**必含示例:** 一份最小可用 `pyproject.toml`;`uv` 起项目/装依赖的命令序列(命令展示,不强制跑);`ruff check`/`ruff format` 命令。
**对照点:** Maven/Gradle(`pom.xml`/依赖坐标 + 中央仓库)、Go modules(`go.mod`/`go.sum` 内建)vs Python 生态碎片化(无官方唯一方案,这是 Java/Go 人最迷路处);venv ≈ 没有,但概念上像隔离的依赖目录。
**面试卡种子:** "venv 解决什么"、"requirements.txt vs lock"、"wheel 是什么"、"uv/poetry/pip 区别"。

---

## Task 14: 第 12 章 — 测试

**Files:** Create `python/12-testing.md`(NN=12)

**Must-cover:**
- `pytest` 基础:测试发现规则、`assert` 重写、运行/选择(`-k`/`-m`/`::`)。
- fixture(作用域、`yield` 拆装、`conftest.py`、依赖注入);`parametrize`;mark/skip/xfail。
- mock:`unittest.mock`(`Mock`/`patch`/`MagicMock`)、`monkeypatch`、何时 mock 何时别 mock。
- 覆盖率 `coverage`/`pytest-cov`;属性测试 `hypothesis`(简述);`tox`/`nox` 多环境(简述)。

**必含示例(跑验证):** 一个 `pytest` 测试 + 一个 fixture + 一个 `parametrize`(写进临时 `test_*.py` 用 `pytest` 跑过);一个 `patch` 示例。
**对照点:** JUnit(`@Test`/`@BeforeEach`/`@ParameterizedTest`)、Mockito vs pytest fixture/parametrize、`unittest.mock`;Go `testing` + table-driven vs `parametrize`。
**面试卡种子:** "fixture 是什么 / 作用域"、"`parametrize`"、"什么时候该 mock"、"conftest.py 作用"。

---

## Task 15: 第 13 章 — 并发(桥接章)

**Files:** Create `python/13-concurrency-bridge.md`(NN=13)
**吸收:** `python/并发-进程-线程-协程.md` 的"选型心智"要点(深度内容交给 `python-concurrency/`)

**Must-cover:**
- **GIL 心智**:为什么多线程跑不满多核 CPU;CPU 密集 vs IO 密集;3.13 free-threaded 方向(预告)。
- 三条路怎么选:`threading`(IO 密集/阻塞调用)、`multiprocessing`(CPU 密集/绕开 GIL)、`asyncio`(海量 IO 并发/单线程协作);决策树。
- sync/async "函数着色"问题;`async`/`await` 一句话心智。
- **深度指针**:每条路的实操、陷阱、生产用法链接到 `python-concurrency/`(列出对应子目录:`01-foundations-gil`、`02-threading`、`03-multiprocessing`、`04-asyncio-core` 等)。

**必含示例:** 一个最小决策表(任务类型 → 选谁);`asyncio` 一个 `async def` + `await` 极简示例(跑验证)。
**对照点:** Java 线程真并行(无 GIL)+ 线程池/`CompletableFuture`、Go goroutine + channel vs Python GIL 约束下的取舍。
**面试卡种子:** "GIL 是什么 / 影响"、"threading vs multiprocessing vs asyncio 怎么选"、"async 为什么会传染"。
**链接验证:** 确认 `python-concurrency/` 各子目录路径存在(Step D)。

---

## Task 16: 第 14 章 — 标准库与生态地图

**Files:** Create `python/14-stdlib-and-ecosystem.md`(NN=14)
**吸收:** `python/常用库.md`

**Must-cover:**
- 标准库"电池":`collections`(`Counter`/`defaultdict`/`deque`/`namedtuple`)、`itertools`、`functools`、`datetime`/`zoneinfo`、`pathlib`、`os`/`sys`/`subprocess`、`json`、`logging`(配置心智)、`re`、`dataclasses`、`enum`、`typing`。
- 生态地图(一句话定位,不深讲):pydantic、httpx/requests、FastAPI、SQLAlchemy、numpy/pandas;资深 Python 工程师"该伸手拿哪个"。

**必含示例(跑验证):** `Counter`/`defaultdict`/`deque` 各一;`pathlib` 路径操作;`logging` 最小配置。
**对照点:** Java 标准库/Guava vs Python "batteries included";Java `java.time` vs `datetime`/`zoneinfo`;Java `java.nio.file.Path` vs `pathlib`。
**面试卡种子:** "`defaultdict`/`Counter` 用途"、"`deque` vs list"、"`pathlib` 比 os.path 好在哪"、"logging 怎么配"。

---

## Task 17: 第 15 章 — CPython 内部与性能心智

**Files:** Create `python/15-cpython-internals-performance.md`(NN=15)

**Must-cover:**
- 字节码与 `dis`:看一段函数的字节码;eval 循环/帧对象简述。
- 对象模型内部:`PyObject` 头(refcount + type 指针);引用计数如何工作;**分代 GC**(循环引用回收、三代、`gc` 模块)。
- 内存:pymalloc/arena/对象池;`__slots__` 省内存原理;`sys.getsizeof`。
- 性能:为什么 Python 慢、慢在哪;性能惯用法(局部变量、内置函数/C 实现、避免热点循环属性查找);C 扩展/Cython/numpy 向量化;3.13 free-threaded + 实验 JIT 方向。
- **深度指针**:性能剖析/调试实操链接到 `performance-tuning-roadmap/06a-python-profiling`、`06b-python-debugging`。

**必含示例(跑验证):** `dis.dis(fn)` 看字节码;`sys.getsizeof` 比较带/不带 `__slots__` 的对象;`gc.get_count` 或循环引用被回收的观察。
**对照点:** JVM 字节码 + JIT + 分代 GC(标记-清除/复制)vs CPython refcount + 循环 GC;Go GC(并发标记清除,无 refcount)。
**面试卡种子:** "Python 内存怎么管 / 引用计数 + GC"、"循环引用会泄漏吗"、"为什么 Python 慢"、"`__slots__` 为什么省内存"、"GIL 和 GC 关系"。

---

## Task 18: 第 16 章 — Python 风格与惯用法

**Files:** Create `python/16-pythonic-idioms.md`(NN=16)

**Must-cover:**
- PEP 8(命名/缩进/行宽)、PEP 20(Zen)落地;`ruff`/`black` 怎么帮你。
- 地道写法:解包交换、`enumerate`/`zip`、推导式 vs map/filter、`with` 管资源、EAFP、真值判断、`get`/`setdefault`、f-string、`pathlib`。
- **反模式合集("别把 Java 直译成 Python")**:无谓 getter/setter(用 property/直接属性)、`for i in range(len(x))`、可变默认参数、`type(x)==T` 而非 `isinstance`、过度类层级、用异常做控制流的边界、手动资源关闭不用 `with`。
- **陷阱总览**(汇总全书踩坑点,做成一页速查):可变默认参数、`[[]]*n`、闭包延迟绑定、类变量共享、`is` 比值、漏逗号隐式拼接、`for/while...else`、地板除符号。

**必含示例(跑验证):** 每类反模式给"反例 → 地道写法"对照;陷阱总览每条一行最小复现。
**对照点:** "Java 思维直译"清单 vs Pythonic 对应写法。
**面试卡种子:** "什么是 Pythonic"、"EAFP 例子"、整章陷阱合集即猜输出题库。

---

## Task 19: 第 99 章 — 面试卡

**Files:** Create `python/99-interview-cards.md`(NN=99)

**Must-cover:**
- 汇总各章"面试卡种子"为分主题速查(每条:问题 → 一句话答 → 关键词)。
- **"猜输出" drill 合集**:从 01/04/05 等章的陷阱抽 10–15 道,给输出与一句话解释(每道都跑验证)。
- Python 偏系统/设计类追问:GIL 与扩展性、内存模型、为什么选 Python/不选、类型系统取舍。

**必含示例(跑验证):** 所有"猜输出"题的答案用 `python3` 实测过。
**对照点:** 高频"Java/Go 选手转 Python 必被问"清单。
**(本任务走通用流程 A–E,验证尤其重要。)**

---

## Task 20: 清理旧碎片笔记

**Files:** Delete `python/魔法方法.md`、`python/类属性与实例属性.md`、`python/模块与导入.md`、`python/常用库.md`、`python/并发-进程-线程-协程.md`

- [ ] **Step 1:** 确认 05/10/14/13 章已分别吸收对应旧笔记的有效内容(逐一核对 must-cover 中"吸收"标记)。
- [ ] **Step 2:** `git rm python/魔法方法.md python/类属性与实例属性.md python/模块与导入.md python/常用库.md python/并发-进程-线程-协程.md`
- [ ] **Step 3:** `git commit -m "python 教程:清理已并入的旧碎片笔记"`

---

## Self-Review

**Spec coverage:** spec 第 5 节 17 章 + 99 + README → Task 1–19 一一对应;迁移计划(第 7 节)→ 各章"吸收"标记 + Task 20;边界(第 8 节)→ Task 15/17 用指针不重写;每章模板(第 6 节)→ 通用流程 Step A。覆盖完整,无缺口。

**Placeholder scan:** 各任务 must-cover/必含示例为具体条目与具体示例(非 "TODO/适当处理");通用流程把机械步骤抽出一次(DRY),内容清单逐任务给全。

**一致性:** 文件名在文件结构、各任务、README、Task 20 中保持一致(`NN-name.md`);旧笔记吸收去向(05/10/13/14)与 spec 第 7 节一致;验证脚本命名 `/tmp/ch<NN>_check.py` 统一。
