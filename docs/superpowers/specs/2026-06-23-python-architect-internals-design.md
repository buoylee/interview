# Python 架构师内核层补完 Design

> 把 `python/` 教程从「资深生存线」抬到「架构师线」:能在白板上讲清 CPython 运行时的**源码级取舍**,而不只是心智模型。
> 关联前序 spec:`2026-06-13-python-senior-tutorial-design.md`(本教程的原始设计)。

## Context

`python/` 已有 **23 章(00–22)+ 99 面试卡 + README**,定位「资深工程师教程」,覆盖面很广(语言模型、类型系统、OOP、并发桥接、CPython 内部 ch15、Python↔C 边界 ch21、数据访问桥接 ch22)。README 已明确把三块深水区**指针出去**给别的 track,不在本 track 重写:并发深度→`python-concurrency/`、性能剖析→`performance-tuning-roadmap/`、数据访问→`python-data/`。

对全 23 章 + 卡做了一轮**架构师 bar 审计**(分四段并行读)。核心发现不是"缺 23 个零散深点",而是:

> **几乎每一章的"陷阱/行为"都踩在同一个没被讲透的底层上**——字节码与名字解析(`LOAD_FAST/GLOBAL/DEREF`)、code object、cell/帧、对象头与引用计数、属性查找算法、容器内部布局、GC、GIL 机制。这层目前只在 ch15 浅讲(188 行,心智模型级),别处全是"提到但不解释"(闭包说"捕获绑定"不讲 cell;property 说"是描述符"把协议 defer 掉;dict 说"紧凑布局"不讲索引表)。

这层正是把全书散落 gotcha 收敛成的**几条运行时原语**(「收口地图」)。所以补完主轴 = **先立内核脊柱,再把它的片段织回各章正文**。

## Problem

架构师级 Python 面试不止"猜输出",而是"解释内部机制 + 论证取舍"。当前深度接不住的典型追问:

- "白板画出 `obj.x` 的属性解析路径"(MRO + data/非 data 描述符 + `__getattr__` 兜底)
- "字节码执行循环里 GIL 在哪儿放?为什么 IO 密集多线程有用、CPU 密集没用?free-threading 怎么去锁?"
- "循环引用谁先析构?为什么不能靠 `__del__`?线上内存涨怎么从 refcount/循环/weakref 推?"
- "为什么推导式不泄漏变量、普通 for 泄漏?"(= code object + 名字编译)
- "零参 `super()` 怎么知道自己属于哪个类?"(= `__class__` cell)
- "compact dict 怎么省内存、dict 为什么从 3.7 变有序?"
- "都说动态类型慢,3.11 的自适应专门化改写了这个结论吗?"

现状这些要么没讲、要么停在"现象 + 一句话原因",学习者**知道现象、讲不出机制**。

## Goals

- 把 Layer A「运行时内核」立成一条**相邻双章脊柱**,作为「收口地图」**正经教**(底层进正文,不是塞进问答)。
- 把内核片段**织回各章首次出现处**(cell→ch04、属性查找→ch05/06、容器内部→ch02…),只写"这章 gotcha 的根因",机制本身引用脊柱、不重讲。
- 补两个真缺的**语言层**架构师新专题(库/API 设计、大库语言层治理)。
- 保持每章既有结构:**导引(为什么重要 / 一句话心智)→ 正文(由浅入深)→ Java/Go 对照框 → 章末面试卡**。
- 代码块全部可在 **CPython 3.11** 实跑;3.12+ / 3.13 / 3.14 的差异单独标注并给 3.11 等价。
- 升级 99 面试卡:从"senior trivia / 猜输出"补上"架构师白板:解释内部机制"那一层。

## Non-Goals(刻意排除,归别的 track,不重写)

审计 agent 还提了一批架构师向topic,但属于仓库已有 track,按「各 track 不重写、生态平衡」切出去,**spec 内明确点名出处**避免重复建设:

- 应用安全架构 / 密钥轮转生命周期 → `system-design/` · `engineering-handbook/`
- OTel 可观测性集成(logs/metrics/traces 三支柱)→ `observability/` · `logging/`
- 测试策略与质量门禁 at scale(金字塔、mutation、CI gates)→ `engineering-handbook/`
- 性能架构决策 / profiling 工具实操(火焰图、py-spy、cProfile)→ `performance-tuning-roadmap/`
- 数据访问深度(Session/池/N+1/迁移)→ `python-data/`(ch22 故意薄,**确认保留**)
- asyncio 事件循环调度 / worker / 任务队列实操 → `python-concurrency/`(ch13 只讲"怎么选")

> 边界判据:**语言 + 运行时 + 语言层架构** 留在本 track;**应用架构 / 运维 / 工具实操** 指针出去。GIL 的「机制」属运行时(留 ch16),GIL 下的「并发选型与实操」属 `python-concurrency/`(ch13 桥接)。

## Gap 审计(grounding,分三层)

### Layer A — 运行时内核(横切骨架,最高杠杆)

| | 原语 | 现状 | 架构师白板会问 | 落点 |
|--|--|--|--|--|
| A1 | code object + 名字编译成 `LOAD_FAST/GLOBAL/DEREF` | 几乎无 | 推导式为何不泄漏、`UnboundLocalError` 根因 | **脊柱 ch15** ← ch00/03/04 |
| A2 | 帧 + 求值栈 + eval 循环;生成器挂起=存帧 | "栈式+帧"一句 | `next()` 怎么从上次 yield 继续 | **脊柱 ch15** ← ch07 |
| A3 | cell/freevar 闭包;`__class__` cell 与零参 `super()` | 现象级 | `nonlocal` 改的是什么、零参 super 怎么定位自己 | **脊柱 ch15** ← ch04/06 |
| A4 | 对象头 + 引用计数生命周期(隐式 bump、`getrefcount` +1)、weakref | 浅 | 线上内存涨怎么从 refcount/循环/weakref 推 | **脊柱 ch16** ← ch01 |
| A5 | 分代 GC 标记-清除 + 晋升 + 阈值;`__del__` 循环顺序不定 | "三代/朝生暮死"一句 | 循环引用谁先析构、为什么别靠 `__del__` | **脊柱 ch16** |
| A6 | 属性查找完整算法(`__getattribute__`→MRO+data/非data 描述符→`__dict__`→`__getattr__`);`__slots__`=member descriptor;property 为何**必须**是 data 描述符 | 只给查找顺序 | 白板画 `obj.x` 解析路径 | **ch05/06 正文** |
| A7 | 容器内部:compact dict(索引表+entries+探测)、list 过度分配(~1.125×)、hash 随机化/SipHash、int 30-bit 数字 | "紧凑布局"一句 | compact dict 怎么省内存、dict 为何有序 | **ch02 正文** |
| A8 | 自适应专门化解释器(PEP 659 inline cache,3.11+)+ JIT(3.13/14)现状 | 几乎无 | specialization 改写"Python 慢"了吗 | **脊柱 ch15** |
| A9 | GIL 机制:eval breaker、何时放锁(IO/C 扩展 `Py_BEGIN_ALLOW_THREADS`)、`setswitchinterval`、free-threading 的 biased refcount(PEP 703) | 现象级 | 字节码循环里 GIL 在哪放、free-threading 怎么去锁 | **脊柱 ch16**(机制)↔ ch13(选型) |
| A10 | import 机制:`sys.meta_path` finder/loader、`.pyc` 失效(magic+hash/timestamp)、namespace pkg(PEP 420)、循环导入在 module dict 层真相 | 浅 | 走一遍深包导入解析、自定义 finder | **ch10 正文** |

### Layer B — 逐章「内部进正文」(A 的片段织回 + 章节专有深点)

- **ch02** 容器内部(A7)
- **ch03** 推导式=`MAKE_FUNCTION` code object / walrus 作用域 / match 编译
- **ch04** `__defaults__/__closure__`/cell、`functools.wraps`/`lru_cache`/`singledispatch` 内部
- **ch05/06** 属性查找算法 + 描述符协议调用 + `__set_name__` 时机 + 元类 `__prepare__`/三段式 + C3 算法(A6)
- **ch07** `gi_frame`/`yield from` 代理 / `with` 字节码与异常 unwinding
- **ch08** traceback 对象、`__cause__`/`__context__`/`__suppress_context__`、`except*` 过滤语义
- **ch09** `__class_getitem__`/`GenericAlias`、类型擦除边界、variance 由检查器而非运行时强制、PEP 695 翻译、`get_type_hints` 前向引用解析
- **ch10** import 内部(A10)
- **ch12** pytest assert 重写(AST/import hook)、fixture 依赖图、mock 内部
- **ch17(原)** pickle opcode VM(为什么不可能有"安全 pickle")+ 序列化选型 tradeoff
- **ch21(原)** buffer protocol strides/`Py_buffer`、稳定 ABI、C 扩展选型(Cython/pybind11/PyO3/ctypes/cffi)、扩展里放 GIL

### Layer C — 真缺的「语言层」架构师新专题(新增章)

- **C1 库 / 公开 API 设计**:版本与向后兼容、deprecation、`__all__`/单下划线契约、PEP 561 stub、自定义异常层次设计。
- **C2 大型代码库的语言层治理**:import 纪律与分层(下层不导上层)、循环导入的结构级规避、插件/扩展性(entry points + `importlib.metadata`)、内部 vs 公开 API 的物理隔离。

## Recommended Structure(混合脊柱)

### 脊柱:相邻双章

把现有 ch15(执行+内存混在一起,浅)拆深成**两章相邻脊柱**:

- **ch15 「CPython 执行模型」** —— A1/A2/A3/A8:字节码与 code object → 帧·求值栈·eval 循环 → 名字解析编译成三种 `LOAD` → cell/闭包/`__class__` → 自适应专门化(PEP 659)+ JIT 现状。
- **ch16 「对象模型·内存·GC·GIL 机制」(新增)** —— A4/A5/A9:对象头 → 引用计数生命周期 → weakref → 分代 GC 标记-清除 → `__slots__` member descriptor 机制 → GIL 放锁机制 → free-threading biased refcount。

旧 ch15 的内容**重分布不丢失**:执行相关→新 ch15;refcount/GC/`__slots__`/weakref/cached_property→新 ch16;"为什么慢"的四因现在由脊柱各处机制讲清,末尾在 ch16 收一节「为什么慢、怎么办(总纲)」串起四因 + 性能惯用法(numpy/局部变量/内置函数)。

### 编号方案(需你 spec review 拍板,最值得否决的一项)

新增 ch16 → 现有 16–22 顺移为 17–23(99 不变);两个新专题章 append 为 **24 库与公开 API 设计**、**25 大型代码库的语言层治理**。

- **成本**:重命名 7 个文件(旧 16–22)+ 更新 README 目录表 + 修所有交叉链接(章间 + 99 卡 + 可能仓库别处指向 `python/16..22` 的链接)。一次性机械操作,用 `grep` 全量核对。
- **收益**:脊柱两章相邻(15/16),读者可当一块「运行时全景」连读;符合「收口地图」。
- **备选(若你否决渐进)**:不插中间,内存章 append 为 ch23,脊柱不相邻(15 & 23)——churn 小但弱化"一条脊柱"。**推荐渐进(renumber)**。

### 织回各章的写法纪律

每个织回点只写「**这章 gotcha 的根因 + 一句指回脊柱**」,机制本身**不在被织章重讲**(避免重复 / 漂移)。例:ch04 闭包延迟绑定处补一句"根因是闭包变量存在 cell 里、捕获的是 cell 不是值,详见 [ch15 §cell](15…)",而 cell 的完整机制只在 ch15 讲。

## 交付计划(全量 spec,先落增量①)

依赖顺序:混合脊柱要求**脊柱先存在**(各章织回都引用它),故脊柱打头。

### 增量① 脊柱(先落地 → 见下「增量① 章节详纲」)

ch15 执行模型 + 新 ch16 内存/GC/GIL + 编号迁移(renumber 16–22→17–23)。这一刀拿下 P0 大头(A1–A5/A8/A9)。

### 增量② OOP 内部 + 容器内部

ch05/06 属性查找算法 + 描述符协议 + `super`/`__class__`/元类(A6);ch02 容器内部(A7)。第二道最高频白板题。

### 增量③ 其余织回

ch03/04(作用域/cell/defaults 字节码)+ ch07(生成器帧/with)+ ch10(import 内部 A10)+ ch09(typing 运行时真相)。

### 增量④ P2 + 新专题章

C1 库 API 设计(新 ch24)· C2 大库治理(新 ch25)· ch17→18 pickle VM · ch21→22 扩展选型 · ch08 异常内部 · ch12 测试内部。

> 每个增量落完后单独 commit;②③④ 各自落地前可再快速对齐细节(无需重走完整 brainstorm)。

## 增量① 章节详纲

### ch15 「CPython 执行模型」

- **导引(一句话心智)**:你的代码先编译成 **code object**,再被一个**栈式解释器**在**帧**上逐条执行;名字在**编译期**就被分类成 fast/global/deref。为什么重要:这是接住一切"猜输出/为什么"追问的底座。
- **§1 从源码到 code object**:编译产物;`co_code/co_consts/co_names/co_varnames/co_cellvars/co_freevars`;常量折叠/peephole 一提。Demo:`compile()` + `f.__code__.co_*`。
- **§2 栈式解释器:求值栈 + eval 循环 + 帧**:`dis` 一个函数逐条解释压/弹栈;帧 `f_locals/f_back/f_lasti`。Demo:`dis.dis(f)`、`inspect.currentframe()`。
- **§3 名字编译成三种 LOAD**:`LOAD_FAST`(函数局部=数组索引)vs `LOAD_GLOBAL`(模块/内置=dict 查)vs `LOAD_DEREF`(闭包=cell)。**收口**:`UnboundLocalError`、推导式不泄漏/for 泄漏、函数内访问快——同一根。Demo:三种 `dis` 对比。
- **§4 cell 与闭包**:freevar/cellvar、`cell_contents`、`nonlocal` 改 cell;`__class__` cell 与零参 `super()` 怎么工作。Demo:`f.__closure__[0].cell_contents`;super 的 `__class__`。
- **§5 生成器=可挂起的帧**:`gi_frame`/`gi_code`,`next` 恢复帧,`throw`/`close` 注入(机制根,与 ch07 呼应)。Demo:`gen.gi_frame.f_lasti` 随 `next` 变化。
- **§6 自适应专门化(PEP 659, 3.11+)+ JIT 现状**:quickening、inline cache、`BINARY_OP`→`BINARY_OP_ADD_INT` 等 specialization;adaptive。**重新作答**"动态类型慢"。3.13 实验 JIT、3.14 现状。Demo:`dis.dis(f, adaptive=True)`(跑过几次后)。
- **Java/Go 对照框**:JVM 字节码+分层 JIT(HotSpot)/ Go AOT 原生 / CPython 字节码+解释(3.11 specialization、3.13 实验 JIT)。code object ≈ Class 文件常量池+方法字节码。
- **章末面试卡**:三种 LOAD / `UnboundLocalError` 根因 / 零参 super 怎么定位自己 / 生成器怎么"记住"位置 / specialization 改写"Python 慢"了吗。

### ch16 「对象模型·内存·GC·GIL 机制」

- **导引(一句话心智)**:每个对象背着**对象头**(refcount + 类型指针);内存靠**引用计数实时收 + 分代 GC 兜循环**;一把 **GIL** 决定同一时刻只有一个线程跑字节码——三件事独立又互相牵动。
- **§1 对象头与内存布局**:`PyObject`(`ob_refcnt`+`ob_type`)、变长 `ob_size`;为什么 `int` 不是 8 字节。Demo:`sys.getsizeof`。compact instance dict(3.11 key-sharing)一提,深入指 ch02。
- **§2 引用计数生命周期**:`Py_INCREF/DECREF` 时机;绑定/解绑/传参/循环变量的隐式 bump;`getrefcount` 自己 +1;归零立即回收。优(及时可预测)缺(循环引用)。Demo:`sys.getrefcount` 的 +1。
- **§3 weakref**:不加 refcount 的引用;`WeakValueDictionary` 缓存"活着才缓存"。Demo:`weakref.ref` 在 `del` 后失效。
- **§4 分代 GC**:为什么需要(收循环);标记-清除(根可达性);三代+晋升(熬过回收晋升);阈值 `(700,10,10)` 触发机制。`gc` 模块:`collect/get_count/get_threshold`。`__del__` 在循环里析构顺序不定 → 用 `with`。Demo:构造循环 + `gc.collect()>0`。
- **§5 `__slots__` 的机制**:为每个槽建 `member_descriptor`(C 级偏移存取),省掉 per-instance `__dict__`;与 `__dict__`/继承冲突;与 `cached_property` 不兼容。Demo:`type(C.x)` 是 `member_descriptor`。
- **§6 GIL 机制**:为什么有(保护 refcount 不被并发撕裂);eval 循环里每线程持锁跑字节码,**eval breaker** 周期请求让出(`sys.setswitchinterval` 默认 5ms);IO syscall / C 扩展 `Py_BEGIN_ALLOW_THREADS` 时**主动放锁** → 所以 IO 密集多线程有用、CPU 密集没用。Demo:两 CPU 线程 vs 一个的耗时对比。
- **§7 free-threading(PEP 703/779, 3.13t/3.14)**:去 GIL 靠 **biased reference counting**(owner 线程非原子 fast path + 他线程原子 fallback)+ 每对象锁;单线程 ~5–10% 开销;C 扩展要适配。子解释器(PEP 734)每解释器独立 GIL。现状:可选构建,默认仍带 GIL。
- **§8 为什么慢、怎么办(总纲)**:把四因(解释执行 → §1-§2/ch15§6、动态类型 → ch15§6、装箱 → §1、GIL → §6)串起;性能惯用法(numpy 向量化释 GIL、热循环局部变量、内置 C 函数、`set`/`dict` 成员判断、生成器)。剖析工具实操指 `performance-tuning-roadmap/`。
- **Java/Go 对照框**:内存回收(JVM 分代/并发 GC vs Go 并发标记清除 vs CPython 引用计数为主+分代兜)/ 多核(JVM 线程真并行 vs goroutine vs CPython GIL→多进程/free-threading)/ 对象头(都有头,Java 基本类型不装箱)。
- **章末面试卡**:怎么管内存 / 循环引用泄漏吗+`__del__` 可靠吗 / GIL 和 GC 一回事吗 / GIL 在字节码循环哪放锁、IO 为何能并行 / free-threading 怎么去 GIL / `setswitchinterval` 调什么。

## 约定与验证

- **结构纪律**:每章沿用「导引 → 正文(由浅入深)→ Java/Go 对照框 → 章末面试卡」;底层进正文教学,**面试卡只做复习自检**,不承载新知识。
- **代码可跑**:所有 demo 在 CPython 3.11.8 实跑过(`dis` 输出、`getsizeof`、`gc.collect()`、`getrefcount` +1、cell/closure 等)。涉及版本差异(specialization 的 `adaptive=`、free-threading、PEP 695)单独标注并给 3.11 等价或"仅说明"。
- **版本基线**:正文以 3.11 为准;3.12/3.13/3.14 增量(JIT、free-threaded、子解释器、PEP 695)作为「未来/可选构建」标注,生产提醒"默认仍带 GIL、需确认构建与 C 扩展适配"。
- **编号迁移验证**:renumber 后 `grep -rn "python/1[6-9]\|python/2[0-2]" .` 及章内相对链接全量核对,确保无死链;README 目录表更新。
- **不重写边界**:每个深点若属 Non-Goals 的 track,正文用一句指针带过,不展开。

## Risks / Open Questions

1. **编号迁移 churn**:renumber 16–22 是本 spec 唯一高风险机械操作。缓解:一次性 `git mv` + grep 核对死链;spec review 时你可改选 append 备选。
2. **脊柱章长度**:ch15/ch16 内容密;若单章超 ~450 行影响连读,§6/§7 可下沉为"深入"小节或再裁。落地时按行数体感调。
3. **织回 vs 重讲的漂移**:增量②③ 织回时,严格"只写根因 + 指回脊柱",避免与脊柱重复 / 说法不一致。
4. **free-threading / JIT 时效**:3.14 相关结论随版本演进,正文标注"现状(截至 3.14)"并给 PEP 号,便于后续更新。
