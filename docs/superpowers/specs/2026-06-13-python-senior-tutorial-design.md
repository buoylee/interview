# Python 资深工程师教程 — 设计文档

- 日期:2026-06-13
- 状态:已通过 brainstorm,待写实现计划
- 位置:重构后的 `python/`

## 1. 目标

为有 **7 年 Java/Go 后端 + 1 年全栈(JS/Python)** 经验的工程师,提供一套**完整、可流畅阅读、覆盖到资深深度**的 Python 语言教程,用于面试复习与查漏补缺。读完应能:

- 掌握 Python **特有的数据模型、惯用法、类型系统、工程链**,而不是"用 Java 思维写 Python";
- 理解关键行为背后的 **CPython 内部机制**(引用计数/GC、描述符、MRO、元类、字节码),做到知其所以然;
- 接住面试里的"猜输出 / 解释陷阱 / 为什么"类追问。

## 2. 读者画像与前置

- 默认有扎实后端底子(OOP、数据结构、并发概念、系统)。**不教编程基础**(变量/循环是什么)。
- 对照锚点是 Java 与 Go:仅在"反直觉 / 易踩坑"处点出差异,不以对照作为章节主轴。

## 3. 设计决策(已对齐)

| 维度 | 决策 |
|------|------|
| 并发 | **桥接章 + 指针**:第 13 章只讲"何时选 threading/multiprocessing/asyncio"的心智,深度链接到已有的 `python-concurrency/`,不重复。 |
| 内部深度 | **资深含内部**:系统讲数据模型、引用计数/分代 GC、对象内存布局、描述符协议、MRO/C3、元类、字节码窥探、GIL 模型。 |
| 章节形态 | **教程正文 + 章末面试卡**:主体是可流畅阅读的叙述,章末附"高频题 + 猜输出 drill + Java/Go 对照"。 |
| 目录与旧笔记 | **重构 `python/`**:改为编号章节(00–16 + 99),把 5 篇旧笔记的好内容并入对应章后删除碎片文件。 |
| 篇幅 | **详尽展开**(对齐"全面/资深/流畅阅读");后续可按需精简。 |

## 4. 组织原则

以"语言主题由浅入深"为主线,把 "Java/Go → Python" 的对照编织进每一章。先建立"一切皆对象 + 名字即绑定"的总纲(00–01),再逐层展开类型→控制流→函数→OOP→迭代→异常→类型系统→模块→工程化→测试→并发→标准库→内部→风格。

## 5. 章节大纲(17 章 + 面试卡)

| # | 文件 | 核心内容 | 吸收旧笔记 |
|---|------|----------|-----------|
| 00 | `00-mental-model-and-setup.md` | 设计哲学、执行模型(解释器/.pyc/REPL)、CPython vs 其他实现、版本格局(3.12/3.13)、"一切皆对象 + 名字即绑定"总纲、教程用法 | |
| 01 | `01-names-objects-memory.md` | 名字是绑定不是盒子、可变/不可变、别名与 `is`/`==`、小整数/字符串驻留、`copy`/`deepcopy`、引用计数 + 循环 GC 入门 | |
| 02 | `02-builtin-types-data-structures.md` | int 任意精度、`/` vs `//`、str/bytes/编码(Java 重点对照)、list/tuple/dict(有序+哈希)/set、选型与复杂度、dict/list 扩容内部 | |
| 03 | `03-control-flow-comprehensions.md` | 真值性、链式比较、`for/while...else`、`match` 模式匹配、各类推导式、海象 `:=`、解包与 `*args/**kwargs` | |
| 04 | `04-functions-closures-decorators.md` | 默认参数陷阱与求值时机、仅位置/仅关键字参数、闭包+延迟绑定+`nonlocal`、`functools`、装饰器(带参/类装饰器) | |
| 05 | `05-oop-1-classes-protocols.md` | 类变量 vs 实例变量陷阱、`__new__`/`__init__`、property、`__slots__`、数据模型/dunder、`__repr__/__eq__/__hash__` 契约、dataclass/enum | 魔法方法、类属性与实例属性 |
| 06 | `06-oop-2-inheritance-descriptors-metaclasses.md` | MRO/C3、`super()` 协作式多继承、描述符(property 的底层)、`__getattr__` 族、元类/`__init_subclass__`、ABC、Protocol 结构化类型 | |
| 07 | `07-iterators-generators-context-managers.md` | 迭代协议、`yield`/`yield from`、惰性求值、`itertools`、`with`/`contextlib` | |
| 08 | `08-exceptions.md` | 异常层级、`else/finally`、链式 `raise from`、EAFP vs LBYL、异常组 `except*`、Java 受检异常对照 | |
| 09 | `09-typing.md` | 鸭子类型+渐进类型、泛型(PEP 695 `class Foo[T]`)、`X\|Y`、Protocol、TypedDict、Literal、ParamSpec、mypy/pyright、Java 泛型擦除对照 | |
| 10 | `10-modules-packages-imports.md` | import 机制与 `sys.modules` 缓存、`__init__.py`、`__main__`、循环导入、命名空间包、`__all__` | 模块与导入 |
| 11 | `11-tooling-envs-packaging.md` | venv、pip、uv/poetry、pyproject.toml、依赖解析、wheel/sdist、ruff、pre-commit、src 布局(Java/Go 无对应,最易迷路) | |
| 12 | `12-testing.md` | pytest(fixture/parametrize/conftest)、mock/monkeypatch、coverage、hypothesis、tox/nox | |
| 13 | `13-concurrency-bridge.md` | GIL 心智、threading/multiprocessing/asyncio 何时选谁、sync/async 着色;深度链到 `python-concurrency/` | (并发-进程-线程-协程 由 python-concurrency/ 承接) |
| 14 | `14-stdlib-and-ecosystem.md` | collections/itertools/functools/datetime/pathlib/logging/re…;生态(pydantic/httpx/fastapi/sqlalchemy/numpy)速览 | 常用库 |
| 15 | `15-cpython-internals-performance.md` | `dis` 字节码、eval 循环/帧、引用计数+分代 GC、pymalloc/内存、为什么慢/哪里慢、3.13 free-threaded+JIT、性能惯用法;链到 performance-tuning-roadmap | |
| 16 | `16-pythonic-idioms.md` | PEP 8/20、EAFP、地道写法、反模式合集("别把 Java 直译成 Python")、陷阱总览 | |
| 99 | `99-interview-cards.md` | 高频问答、"猜输出" drill 合集、Python 系统设计类追问 | |

外加 `README.md`:作为目录/阅读导航(章节顺序 + 一句话简介 + 推荐读法),支撑"流畅阅读"。

## 6. 每章模板

固定结构:

1. **导引** — 为什么这章重要 / 一句话心智模型;
2. **正文** — 由浅入深、程序员视角;代码块力求可直接跑、能自验;
3. **Java/Go 对照框** — 只在反直觉处出现;
4. **章末面试卡** — 高频题 + 猜输出 drill + 一句话答法。

## 7. 目录迁移计划

新建编号文件;旧笔记内容并入后删除原碎片文件:

| 旧文件 | 去向 |
|--------|------|
| `python/魔法方法.md` | 并入 `05` 后删除 |
| `python/类属性与实例属性.md` | 并入 `05` 后删除 |
| `python/模块与导入.md` | 并入 `10` 后删除 |
| `python/常用库.md` | 并入 `14` 后删除 |
| `python/并发-进程-线程-协程.md` | 由 `python-concurrency/` 承接,`13` 桥接;并入要点后删除 |

## 8. 边界(明确不做)

- 不重写并发深度、Python 性能调优 handson、FastAPI/web 框架专题 —— 仅在 13/15 章用指针链接到 `python-concurrency/`、`performance-tuning-roadmap/`、`fastapi-ops/`。
- 不教编程基础。
- 不做可执行校验套件(本教程走"教程正文 + 面试卡",代码块可跑但不挂 pytest 断言;若日后需要,另起 spec)。

## 9. 成功标准

- 17 章 + 面试卡 + README 全部产出,可从头到尾流畅阅读;
- 每章含 Java/Go 对照与章末面试卡;
- 资深主题(描述符、MRO、元类、GC、字节码、typing 进阶)有"为什么"层面的讲解,不止 API 罗列;
- 5 篇旧笔记的有效内容已并入,碎片文件已清理。
