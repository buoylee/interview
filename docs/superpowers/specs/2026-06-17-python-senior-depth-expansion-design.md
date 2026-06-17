# Python 教程·资深度补强 — 设计 spec

> 日期:2026-06-17 · 目标读者:7 年 Java/Go 后端转 Python,面试复习 + LLM/AI 方向
> 状态:已批准,待出实施计划(writing-plans)

## 1. 背景与目标

`python/` 已是 21 章的资深向教程(00–20 + 99,~4100 行),广度与既覆盖主题的深度都达到资深 bar(描述符/元类/MRO、`except*`/ExceptionGroup、GC+环+weakref、import 内幕、functools 家族、时区、pydantic、profiling/`dis`、打包/插件均到位)。

经 grep 全量审计,确认 **6 处缺口**:5 处完全缺失、1 处存在但过时。本 spec 把这 6 处补到与全书一致的资深深度。

**不在范围**(YAGNI):并发实操(留 `python-concurrency/`)、networking/sockets、web 框架细节;JIT 仅在 #3 顺带一句不展开(非语言特性)。

## 2. 全局约定(沿用现有风格,逐条遵守)

- **每个新增结构**:导引(一句话心智)→ 正文(由浅入深,实测代码 + 行内注释)→ 对应章 Java/Go 对照框加行 → 章末面试卡补 Q。
- **代码实测**:能在 CPython 3.11 跑的(#1/#2/#5/#6)必须本机实跑、核对输出后再写进文档。
- **跑不了的(#3/#4,需 3.13/3.14)**:明确标注「概念/面试向,无法在 3.11 实测」,与现有 PEP 695 的处理法一致(标版本 + 给心智,不假装实测)。
- **README**:目录表「一句话」按需补关键词;#2 新增 ch21 行 + "与其他目录关系" 加一行。
- **底层进正文**:底层内幕写进正文教学,面试卡只做复习自检,不承载新知识(用户既定偏好)。

## 3. 六处补强(逐项规格)

### #6 Unicode 规范化 — 进 ch02(`02-builtin-types-data-structures.md`)
- **位置**:str/bytes 小节内,新增 `### Unicode 规范化:看起来相等却 `!=``
- **内容**:NFC/NFD/NFKC/NFKD 四种范式;`unicodedata.normalize`;组合字符 vs 预组合字符导致 `"é" != "é"` 的猜输出;`casefold()` vs `lower()`(大小写折叠用于不区分大小写比较);`len()` 数的是码位(code point)不是字形(grapheme),emoji/组合字符会反直觉。
- **实测例**:`unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b)`;两种 "é" 的 `len`/`==` 对比。
- **Java/Go 对照**:Java `java.text.Normalizer.normalize(...)`;Go `golang.org/x/text/unicode/norm`。
- **面试卡 Q**:为什么两个肉眼相同的字符串 `==` 为 False?怎么修?(答:可能是 NFC/NFD 不同;先 `normalize` 再比。)
- **版本**:3.11 可实测。

### #5 泛型变型 variance — 进 ch09(`09-typing.md`)
- **位置**:泛型部分(三、泛型),`Self` 之后或 `TypeVar` 小节内,新增 `### 变型:协变、逆变、不变`
- **内容**:不变(invariant,默认)/协变(covariant)/逆变(contravariant)定义;`TypeVar("T_co", covariant=True)` / `TypeVar("T_contra", contravariant=True)`;**核心直觉**:可变容器必须不变(为什么 `list[Dog]` 不能传给 `list[Animal]` —— 否则能往里塞 Cat),只读容器可协变(`Sequence[Dog]` 可当 `Sequence[Animal]`);回调参数位逆变;一句话点出 PEP 695 的 `class Foo[T]` 默认推断变型(3.12+)。
- **实测例**:用 mypy 思路构造 `list` 不变 vs `Sequence` 协变的对比(运行时不报错,注释标"mypy 会标红/放行");`Callable[[Animal], None]` 可当 `Callable[[Dog], None]`(逆变)。
- **Java/Go 对照**:Java 通配符 `? extends T`(协变)/`? super T`(逆变);Go 无声明变型。
- **面试卡 Q**:`list[Dog]` 能传给接收 `list[Animal]` 的函数吗?为什么?(答:不能,list 可变即不变;改用 `Sequence[Animal]` 可协变。)
- **版本**:3.11 可实测(旧式 `TypeVar` 显式 variance);PEP 695 默认变型标 3.12+。

### #3 + #4 「后 GIL 时代」刷新 — 改 ch13 + ch15
- **ch13(`13-concurrency-bridge.md`)**:
  - 把现有 no-GIL 注记从"实验性/未来/短期内生产仍以有 GIL 为基线"**改写为当前状态**:3.13 引入实验性 free-threaded 构建;**3.14(2025-10)经 PEP 779 转为官方支持**(不再是实验性)。
  - 新增小节 `### 3.13+ 的两条新并行路径`:① free-threaded 构建(真去 GIL,线程真并行,代价是单线程稍慢 + C 扩展需适配);② 子解释器(PEP 734,`concurrent.interpreters`,3.14 标准库;每解释器独立 GIL,进程内隔离,比多进程轻)。给**选型心智**:IO 密集→asyncio;CPU 密集且能用 free-threaded→线程;需隔离且不想付多进程开销→子解释器;否则仍 multiprocessing。
- **ch15(`15-cpython-internals-performance.md`)**:把"未来:3.13 free-threaded + JIT"小节状态刷新到 3.14;更新面试卡 Q6 的措辞(从"听说过吗/加分项"升级为"已落地,会怎样改变多线程结论")。
- **Java/Go 对照**:补一句 free-threaded 让 Python 线程更接近 Java 线程/Go goroutine 的真并行模型。
- **版本**:**概念/面试向,标注无法在 3.11 实测**;凡给代码(如 `from concurrent import interpreters`)标 3.14+ 且不声称实测。

### #1 async 协议 — 进 ch07(`07-iterators-generators-context-managers.md`)
- **位置**:章末正文(同步三协议讲完后),新增 `### 异步孪生:`async for`/`async with` 背后的协议`
- **内容**:与同步协议一一对应——`__aiter__`/`__anext__`(对 `__iter__`/`__next__`)、`__aenter__`/`__aexit__`(对 `__enter__`/`__exit__`)、async 生成器(`async def` 函数体里 `yield`)、`async for` / `async with` 语法、`StopAsyncIteration`、`contextlib.aclosing`;强调这些是**语言协议**,运行时由事件循环驱动;并发"怎么选"仍指向 ch13 / `python-concurrency/`。
- **实测例**:一个最小 async 生成器 + `async for` 消费,用 `asyncio.run(main())` 跑;一个 `async with` 自定义异步上下文管理器。
- **Java/Go 对照框**:加一行——async 协议 vs Java `CompletableFuture`/响应式、Go channel/`range` over channel。
- **面试卡 Q**:`async with` 和 `with` 的区别?背后是哪两个 dunder?(答:`__aenter__`/`__aexit__`,返回 awaitable,由事件循环 await。)
- **版本**:3.11 可实测。

### #2 Python↔C 边界 — 新开 ch21(`21-python-c-boundary.md`)
- **位置**:插在 ch20 与 ch99 之间;完整章式样(导引 → 正文 → Java/Go 对照框 → 章末面试卡)。
- **内容大纲**:
  1. **导引**:为什么资深要懂这条边界——numpy/torch 都活在这;零拷贝;FFI 调原生库。
  2. **缓冲区协议(buffer protocol)**:bytes/bytearray/`array`/`memoryview`/numpy 共享的底层契约(对象暴露一段连续内存)。
  3. **`memoryview`**:零拷贝切片,改一处动全身;与 `bytes` 切片(拷贝)实测对比(`sys.getsizeof` / id / 修改可见性)。
  4. **`struct`**:打包/解包二进制(网络协议、文件格式);`array`:紧凑同质数值数组(对比 list 的指针数组)。
  5. **`ctypes`**:加载 C 动态库、声明签名、调函数的最小例;`cffi` 一句话对比(更现代,声明式)。
  6. **收口 numpy/torch**:为什么 `tensor.numpy()` / `np.asarray(buf)` 常常免拷贝(共享缓冲区);何时会拷贝。
  7. **Java/Go 对照框**:JNI / `ByteBuffer.allocateDirect` / cgo。
  8. **面试卡**:memoryview 解决什么问题?ctypes vs cffi?为什么 list 比 array 占内存大?
- **实测**:`memoryview`/`struct`/`array`/`ctypes`(调 libc 如 `strlen`/`abs`)全部 3.11 标准库可实测;numpy 例若需装库则标"示意"。
- **README**:目录表加 `| 21 | [Python↔C 边界](21-python-c-boundary.md) | 缓冲区协议、memoryview、struct/array、ctypes/cffi |`;"与其他目录关系"加一行(零拷贝/性能深水仍指 performance-tuning-roadmap)。
- **版本**:3.11 可实测。

## 4. 交付顺序(增量,逐章可 review)

最便宜 → 结构 → 最大,每步本机实跑后交付,便于逐项审阅:

1. **#6** Unicode(ch02)
2. **#5** 变型(ch09)
3. **#3+#4** 后 GIL 时代(ch13 + ch15)
4. **#1** async 协议(ch07)
5. **#2** ch21 Python↔C(新章)

## 5. 成功标准(验收)

- [ ] 6 处缺口全部补齐,风格与既有章节一致(导引/正文/对照框/面试卡四件套)。
- [ ] #1/#2/#5/#6 的所有新增代码块在本机 CPython 3.11 实跑通过,文档内输出与实跑一致。
- [ ] #3/#4 的版本依赖明确标注「3.13/3.14,概念/面试向,非 3.11 实测」,不声称实测。
- [ ] README 目录表更新(ch21 新行 + ch02/07/09/13/15 关键词按需补)。
- [ ] 每处新增的面试卡 Q 落到位,且只做复习、不承载正文未讲的新知识。
- [ ] grep 复测:`memoryview`/`ctypes`/`变型|covariant`/`NFC|normalize`/`async for|__aenter__`/`子解释器|concurrent.interpreters` 均能命中对应新章节。

## 6. 风险与取舍

- **3.13/3.14 事实准确性**:no-GIL/子解释器演进快,写入前以 PEP 779(free-threaded 官方支持)、PEP 734(子解释器 stdlib)为准,措辞标清版本,避免把"实验/官方"说反。
- **ch07 体量**:加 async 协议后接近 ~300 行,仍可控;若过长则把面试卡 drill 精简,不拆章。
- **ctypes 实测可移植性**:libc 函数名/加载方式 macOS 与 Linux 略不同,例子选跨平台稳妥的(如 `ctypes.CDLL` 经 `ctypes.util.find_library("c")`),并注明平台差异。
