# Python 资深工程师教程

写给**有扎实后端底子、要把 Python 用到资深水准**的人:7 年 Java/Go 后端 + 1 年全栈(JS/Python),目标是面试复习与查漏补缺。

不教"什么是变量、什么是循环"。教的是 **Python 特有的数据模型、惯用法、类型系统、工程链,以及关键行为背后的 CPython 内部机制**——让你知其所以然,并且接得住面试里"猜输出 / 解释陷阱 / 为什么"那类追问。每一章都会在反直觉处点出 **Java/Go → Python 的差异**,但不以对照为主线。

> **环境约定**:示例以 **CPython 3.11+** 为准,在 3.11 实测;凡是 3.12+ 才有的语法(如 PEP 695 泛型 `class Foo[T]`)会单独标注并给出可在 3.11 跑的等价写法。

## 怎么读

- **线性通读**(推荐第一遍):00 → 16 顺序读。00–01 建立"一切皆对象 + 名字即绑定"的总纲,后面所有"陷阱"都从这里长出来;跳过会反复卡。
- **按主题跳读**(复习/查漏):直接进对应章,每章自带"导引 + Java/Go 对照框 + 章末面试卡",可独立读。
- **面试前突击**:先扫 `99-interview-cards.md`,卡壳的知识点回到对应章补。

每章结构固定:**导引(为什么重要 / 一句话心智)→ 正文(由浅入深)→ Java/Go 对照框 → 章末面试卡(高频题 + 猜输出 + 一句话答法)**。代码块都能直接跑。

## 章节目录

| # | 章节 | 一句话 |
|---|------|--------|
| 00 | [心智模型与起步](00-mental-model-and-setup.md) | 执行模型、CPython、版本;"一切皆对象 + 名字即绑定"总纲 |
| 01 | [名字、对象与内存模型](01-names-objects-memory.md) | 名字是绑定不是盒子;`is`/`==`、可变性、深浅拷贝、引用计数 |
| 02 | [内置类型与数据结构](02-builtin-types-data-structures.md) | 数值/str-bytes/list-tuple-dict-set 选型与复杂度 |
| 03 | [控制流、推导式、解包](03-control-flow-comprehensions.md) | 真值性、链式比较、`match`、推导式作用域、解包 |
| 04 | [函数:一等公民、闭包、装饰器](04-functions-closures-decorators.md) | 可变默认参数、闭包延迟绑定、`functools`、装饰器 |
| 05 | [OOP(一):类、属性、协议](05-oop-1-classes-protocols.md) | 类变量陷阱、dunder、`property`、`__slots__`、`dataclass` |
| 06 | [OOP(二):继承、描述符、元类](06-oop-2-inheritance-descriptors-metaclasses.md) | MRO/C3、`super()`、描述符、元类、ABC/Protocol |
| 07 | [迭代器、生成器、上下文管理器](07-iterators-generators-context-managers.md) | 迭代协议、`yield`/`yield from`、`itertools`、`with` |
| 08 | [异常与错误处理](08-exceptions.md) | 异常链、EAFP vs LBYL、`except*`、`suppress` |
| 09 | [类型系统与 typing](09-typing.md) | 渐进类型、泛型、`Protocol`/`TypedDict`、mypy/pyright |
| 10 | [模块、包、导入系统](10-modules-packages-imports.md) | import 机制与缓存、循环导入、`__main__`、`__all__` |
| 11 | [工程化:环境、依赖、打包、工具链](11-tooling-envs-packaging.md) | venv、uv/poetry、`pyproject.toml`、ruff、打包 |
| 12 | [测试](12-testing.md) | pytest、fixture/parametrize、mock、coverage |
| 13 | [并发(桥接章)](13-concurrency-bridge.md) | GIL 心智、threading/multiprocessing/asyncio 怎么选 |
| 14 | [标准库与生态地图](14-stdlib-and-ecosystem.md) | collections/itertools/pathlib/logging… + 生态地图 |
| 15 | [CPython 内部与性能心智](15-cpython-internals-performance.md) | 字节码、引用计数 + 分代 GC、为什么慢、性能惯用法 |
| 16 | [Python 风格与惯用法](16-pythonic-idioms.md) | PEP 8/20、地道写法、反模式、全书陷阱总览 |
| 99 | [面试卡](99-interview-cards.md) | 各章高频题汇总 + 猜输出 drill 合集 |

## 与仓库其他目录的关系

这套教程聚焦**语言本身**。三块深水区不在这里重写,只在对应章用指针带你过去:

- **并发深度** → [`../python-concurrency/`](../python-concurrency/):GIL、threading、multiprocessing、asyncio、anyio、生产 worker/任务队列、调优。第 13 章只讲"怎么选",实操在那里。
- **性能剖析/调试** → [`../performance-tuning-roadmap/06a-python-profiling`](../performance-tuning-roadmap/06a-python-profiling)、[`06b-python-debugging`](../performance-tuning-roadmap/06b-python-debugging)。第 15 章讲内部机制与心智,工具实操在那里。
- **Web/服务可观测性** → [`../fastapi-ops/`](../fastapi-ops/):FastAPI 指标/追踪/日志/压测/调优。
