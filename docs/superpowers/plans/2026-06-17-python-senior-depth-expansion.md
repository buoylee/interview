# Python 教程·资深度补强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `python/` 资深教程的 6 处缺口补齐到与全书一致的深度(Unicode 规范化、泛型变型、后 GIL 时代、async 协议、Python↔C 边界)。

**Architecture:** 5 处补丁进现有章节(ch02/ch09/ch13/ch15/ch07),1 处新开章(ch21)。每处沿用全书四件套:导引 → 正文(实测代码 + 行内注释)→ Java/Go 对照框加行 → 章末面试卡补 Q。能在 3.11 跑的代码先本机实测、核对输出再写进文档;需 3.13/3.14 的(后 GIL)标注「概念/面试向」。

**Tech Stack:** Markdown 教程文档;CPython 3.11(实测基线);标准库 `unicodedata`/`typing`/`asyncio`/`struct`/`array`/`ctypes`/`memoryview`。

**约定:** 仓库规则是「仅在用户许可时提交」。每个 Task 末尾的 commit 步骤在用户给 go-ahead 后执行(可逐章批准)。所有代码块的预期输出取自本机 3.11 实测(见各 Task 的验证步骤)。

---

## File Structure

| 文件 | 动作 | 责任 |
|------|------|------|
| `python/02-builtin-types-data-structures.md` | Modify(section 二 末尾,行 64–98 内,line 99 前) | 新增 `### Unicode 规范化` |
| `python/09-typing.md` | Modify(`### Self` 后 line 96–110,`## 四` line 111 前) | 新增 `### 变型:协变、逆变、不变` |
| `python/13-concurrency-bridge.md` | Modify(section 一 GIL 注记 + section 二 末尾) | 刷新 no-GIL 措辞 + 新增 `### 3.13+:两条新并行路径` |
| `python/15-cpython-internals-performance.md` | Modify(`### 未来` line 142–146 + 面试卡 Q6) | 刷新 free-threaded 状态到 3.14 |
| `python/07-iterators-generators-context-managers.md` | Modify(`### contextlib` 后 line 145–168,`## Java/Go` line 169 前) | 新增 `### 异步孪生` + 对照框行 + 面试卡 |
| `python/21-python-c-boundary.md` | Create | 新章:缓冲区协议/memoryview/struct/array/ctypes |
| `python/README.md` | Modify(目录表 line 41 后 + "与其他目录关系") | ch21 目录行 + 关系说明 |

交付顺序(增量、逐章可 review):Task 1 → 2 → 3 → 4 → 5。

---

## Task 1: #6 Unicode 规范化(ch02)

**Files:**
- Modify: `python/02-builtin-types-data-structures.md`(插入点:`## 二、文本与字节:str vs bytes` 章节末尾,即 line 99 `## 三、序列` 之前)

- [ ] **Step 1: 实测验证代码(doc 的「测试」)**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && python3 - <<'PY'
import unicodedata
a = "é"          # é 预组合(1 码位)
b = "é"         # e + 组合尖音符(2 码位)
print(a == b, len(a), len(b))
print(unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b))
print("ß".casefold() == "ss", "ß".lower())
PY
```
Expected 输出:
```
False 1 2
True
True ß
```

- [ ] **Step 2: 写入新小节**

在 line 99 `## 三、序列` 前插入(prose 要点 + 已验证代码):

要点必须讲到:① 同一个「字形」可有多种码位序列(预组合 NFC vs 分解 NFD),所以肉眼相同的字符串可能 `!=` 且 `len` 不同;② `unicodedata.normalize("NFC"/"NFD"/"NFKC"/"NFKD", s)`——NFC 合成最短、NFD 分解,NFK* 还会做兼容折叠(如全角→半角、`①`→`1`);③ 比较/去重/当 dict key 前先统一 normalize;④ `casefold()` 是比 `lower()` 更激进的大小写折叠,用于不区分大小写比较(`ß`→`ss`),`lower()` 不变;⑤ `len()` 数的是码位不是字形,emoji/组合字符会反直觉。

代码块(逐字用已验证版本):
```python
import unicodedata
a = "é"          # 'é' 预组合:1 个码位 U+00E9
b = "é"         # 'é' 分解:'e' + 组合尖音符 U+0301,2 个码位
print(a == b)         # False —— 肉眼相同,码位不同
print(len(a), len(b)) # 1 2 —— len 数码位,不数字形

n = unicodedata.normalize
print(n("NFC", a) == n("NFC", b))   # True —— 先规范化再比

print("ß".casefold() == "ss")       # True —— casefold 比 lower 更激进
print("ß".lower())                  # 'ß' —— lower 不折叠
```
说明句:用户输入、文件名、跨系统数据先 `normalize("NFC", …)` 再比较/入库,否则会出现「搜不到、去重失败、`==` 为 False」的诡异 bug。

- [ ] **Step 3: 加 Java/Go 对照框一行**

在 `## Java/Go 对照框`(line 205 起)表格加一行:
```
| Unicode 规范化 | `java.text.Normalizer.normalize(s, NFC)` | `unicodedata.normalize("NFC", s)`;`casefold` ≈ 不区分大小写折叠 |
```

- [ ] **Step 4: 加章末面试卡一题**

在 `## 章末面试卡`(line 216 起)末尾加:
```
**Qx. 两个肉眼完全相同的字符串,`==` 却是 False,怎么回事?**
很可能是 Unicode 规范化不同——同一字形可由「预组合(NFC,1 码位)」或「分解(NFD,基字符+组合符,多码位)」表示,`==` 按码位比就不等,`len` 也不同。修法:比较/去重/做 key 前先 `unicodedata.normalize("NFC", s)` 统一。不区分大小写用 `casefold()`(比 `lower()` 更彻底,如 `ß`→`ss`)。
```

- [ ] **Step 5: 验证落地**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && grep -cE 'normalize|NFC|casefold' python/02-builtin-types-data-structures.md
```
Expected: ≥ 4

- [ ] **Step 6: Commit(用户 go-ahead 后)**

```bash
git add python/02-builtin-types-data-structures.md
git commit -m "python 教程:ch02 新增 Unicode 规范化小节(NFC/NFD、casefold、len 数码位)"
```

---

## Task 2: #5 泛型变型(ch09)

**Files:**
- Modify: `python/09-typing.md`(插入点:`### Self`(3.11+) 小节后 line 110、`## 四、进阶武器` line 111 之前)

- [ ] **Step 1: 实测验证(运行时不报错 + 变型概念靠注释)**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && python3 - <<'PY'
from typing import TypeVar, Generic, Sequence, Callable
T_co = TypeVar("T_co", covariant=True)
class ReadOnlyBox(Generic[T_co]):
    def __init__(self, v): self._v = v
    def get(self) -> T_co: return self._v
print(ReadOnlyBox(1).get())
PY
```
Expected 输出:`1`(运行时构造无误;变型是静态概念,mypy 行为以注释说明——本机无 mypy,沿用 ch09 既有「注释标 mypy 行为」写法)。

- [ ] **Step 2: 写入新小节 `### 变型:协变、逆变、不变`**

要点必须讲到:① 三种变型——不变(invariant,默认)、协变(covariant,子类型方向一致)、逆变(contravariant,方向相反);② **核心直觉**:可变容器必须不变——若 `list[Dog]` 能当 `list[Animal]`,调用方就能往里塞 `Cat`,破坏类型,所以 mypy 拒绝;③ 只读容器可协变——`Sequence[Dog]` 能当 `Sequence[Animal]`(只能读不能写,塞不进 Cat);④ 回调的参数位逆变——`Callable[[Animal], None]` 能当 `Callable[[Dog], None]`(能处理任意 Animal 的函数,必能处理 Dog);⑤ 旧式 `TypeVar("T_co", covariant=True)`/`contravariant=True` 显式声明;PEP 695 的 `class Box[T]`(3.12+)由检查器自动推断变型,无需手写。

代码块:
```python
from typing import TypeVar, Generic, Sequence, Callable

class Animal: ...
class Dog(Animal): ...

# ① 可变容器:不变(invariant)——mypy 会拒绝下面的赋值
dogs: list[Dog] = [Dog()]
def feed_all(xs: list[Animal]) -> None: xs.append(Animal())  # 它能塞 Animal 进去
# feed_all(dogs)        # mypy 标红:list 不变,否则 dogs 里会混进非 Dog

# ② 只读容器:协变(covariant)——Sequence 只读,放行
def names(xs: Sequence[Animal]) -> int: return len(xs)
names(dogs)             # mypy OK:Dog 是 Animal,只读不会塞坏

# ③ 回调参数位:逆变(contravariant)
handler: Callable[[Dog], None]
def on_animal(a: Animal) -> None: ...
handler = on_animal     # mypy OK:能处理任意 Animal 的函数,必能处理 Dog

# 自定义协变泛型:声明 covariant=True(只读才安全这么标)
T_co = TypeVar("T_co", covariant=True)
class ReadOnlyBox(Generic[T_co]):
    def __init__(self, v: T_co) -> None: self._v = v
    def get(self) -> T_co: return self._v
```
说明句:一句话记忆——**能写就不变,只读可协变,消费者(回调入参)逆变**。3.12+ 的 `class Box[T]` 语法让检查器自动推断,平时不用手写 `covariant=`。

- [ ] **Step 3: 加 Java/Go 对照框一行**

在 `## Java/Go 对照框`(line 210 起)表格加一行:
```
| 变型 | Java 通配符 `? extends T`(协变)/`? super T`(逆变) | `TypeVar(covariant=/contravariant=)`;3.12+ 自动推断;只读协变、可变不变 |
```

- [ ] **Step 4: 加章末面试卡一题**

在 `## 章末面试卡`(line 223 起)末尾加(编号接 Q7 之后为 Q8):
```
**Q8. `list[Dog]` 能传给接收 `list[Animal]` 的函数吗?为什么?**
不能。`list` 可变,是**不变(invariant)**的——若允许,函数可往里 `append` 一个 `Animal`(甚至 `Cat`),破坏 `list[Dog]` 的契约,mypy 因此拒绝。要协变就用**只读**类型 `Sequence[Animal]`(放行)。规律:能写就不变,只读可协变,回调入参逆变。3.12+ 泛型由检查器自动推断变型。
```

- [ ] **Step 5: 验证落地**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && grep -cE '协变|逆变|不变|covariant|contravariant' python/09-typing.md
```
Expected: ≥ 5

- [ ] **Step 6: Commit(用户 go-ahead 后)**

```bash
git add python/09-typing.md
git commit -m "python 教程:ch09 新增泛型变型小节(协变/逆变/不变 + 可变即不变直觉)"
```

---

## Task 3: #3+#4 后 GIL 时代(ch13 + ch15)

**Files:**
- Modify: `python/13-concurrency-bridge.md`(section 一 GIL 注记 line 16 区 + section 二 末尾 line 45 后、`## 三、async` 前)
- Modify: `python/15-cpython-internals-performance.md`(`### 未来:3.13 free-threaded + JIT` line 142–146 + 面试卡 Q6 line 183)

> **写入前事实核对(必做):** no-GIL/子解释器演进快,先用 context7/WebSearch 确认两点再下笔——(a) **PEP 779**:free-threaded 在 3.14 是否已转为「officially supported」(非实验);(b) **PEP 734**:子解释器标准库模块名是 `concurrent.interpreters` 且随 3.14 落地。措辞按核实结果写,版本标清。本任务无可在 3.11 实测的代码,全部标「概念/面试向」。

- [ ] **Step 1: 核对事实**

Run(任一):用 `mcp__plugin_context7_context7__query-docs` 查 CPython free-threading / PEP 779 / PEP 734,或 `WebSearch "PEP 779 free-threaded supported 3.14"` 与 `"PEP 734 concurrent.interpreters 3.14"`。记录确认结论再继续。

- [ ] **Step 2: 刷新 ch13 section 一 的 GIL 注记**

把现有「3.13 起有实验性 free-threaded(可关 GIL)构建,未来可能改变这一格局,但短期内生产仍以"有 GIL"为前提」改写为(按 Step 1 核实调整):
```
> 注意:GIL 是 **CPython 的实现细节**,不是 Python 语言规范(Jython 没有)。**3.13 引入实验性 free-threaded(可关 GIL)构建;3.14(2025-10)经 PEP 779 转为官方支持的构建变体**——真去 GIL、线程真并行。它仍是可选构建(默认发行版带 GIL),C 扩展需适配后才在该模式下安全,但「Python 多线程跑不满多核」这条结论正在被改写。见[第 15 章](15-cpython-internals-performance.md)。
```

- [ ] **Step 3: ch13 新增 `### 3.13+:两条新并行路径`(放 section 二 末尾,`## 三、async` 前)**

要点:除了「线程/进程/asyncio」老三样,3.13+ 多出两条真并行路径:
① **free-threaded 构建**(PEP 703/779):去掉 GIL,线程真并行;代价是单线程略慢、C 扩展需适配;适合 CPU 密集且依赖纯 Python/已适配扩展。
② **子解释器**(PEP 734,`concurrent.interpreters`,3.14 stdlib):一个进程内开多个互相隔离的解释器,**每个有自己的 GIL**,故能并行跑 CPU 任务;比多进程轻(共享进程、启动快),但对象不共享、需序列化传数据。
选型补充(接上文决策树):CPU 密集 + 能用 free-threaded → 线程;要隔离又嫌多进程重 → 子解释器;否则仍 `multiprocessing`;IO 密集照旧 asyncio。
代码示意(标 3.14+,不声称实测):
```python
# 3.14+，子解释器(PEP 734),示意不实测
from concurrent import interpreters
interp = interpreters.create()
interp.exec("print('hello from subinterpreter')")
```

- [ ] **Step 4: 刷新 ch15 `### 未来:3.13 free-threaded + JIT`(line 142)**

把「实验性…短期内生产仍以"有 GIL、无 JIT"为基线…面试提一句是加分项」更新为:JIT 在 3.13 起实验性(逐步成熟);free-threaded 经 PEP 779 在 3.14 转官方支持(仍是可选构建),「多线程跑不满多核」的传统结论开始被改写——给出「已落地但默认发行版仍带 GIL」的准确现状,而非「遥远的未来」。

- [ ] **Step 5: 刷新 ch15 面试卡 Q6(line 183 `**Q6. 听说过 3.13 的变化吗?**`)**

更新答案为:3.13 引入实验性 JIT 与实验性 free-threaded 构建;**3.14 经 PEP 779 把 free-threaded 转为官方支持的可选构建**,并把子解释器(PEP 734)纳入标准库(`concurrent.interpreters`)。影响:「Python 多线程跑不满多核」正在被改写,但默认发行版仍带 GIL,生产需确认构建与 C 扩展适配。

- [ ] **Step 6: 加 Java/Go 对照(ch13 对照框 line 111 起)**

在 free-threaded 相关行补一句:free-threaded 让 Python 线程更接近 Java 线程 / Go goroutine 的真并行模型(此前 CPU 并行只能靠多进程)。

- [ ] **Step 7: 验证落地**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && grep -cE 'PEP 779|PEP 734|子解释器|concurrent.interpreters|官方支持' python/13-concurrency-bridge.md python/15-cpython-internals-performance.md
```
Expected: ≥ 4(跨两文件)

- [ ] **Step 8: Commit(用户 go-ahead 后)**

```bash
git add python/13-concurrency-bridge.md python/15-cpython-internals-performance.md
git commit -m "python 教程:ch13/ch15 刷新后 GIL 时代(free-threaded 转官方支持 + 子解释器 PEP 734)"
```

---

## Task 4: #1 async 协议(ch07)

**Files:**
- Modify: `python/07-iterators-generators-context-managers.md`(插入点:`### contextlib`(line 145–168)之后、`## Java/Go 对照框` line 169 之前)

- [ ] **Step 1: 实测验证代码**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && python3 - <<'PY'
import asyncio
async def gen(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i * i
class AConn:
    async def __aenter__(self):
        print("open"); return self
    async def __aexit__(self, *exc):
        print("close"); return False
async def main():
    async with AConn():
        out = [x async for x in gen(3)]
    print("collected:", out)
asyncio.run(main())
PY
```
Expected 输出:
```
open
close
collected: [0, 1, 4]
```

- [ ] **Step 2: 写入新小节 `### 异步孪生:`async for` / `async with` 背后的协议`**

要点:同步三协议各有 async 孪生,**一一对应**——迭代:`__iter__`/`__next__` → `__aiter__`/`__anext__`(耗尽抛 `StopAsyncIteration`);上下文:`__enter__`/`__exit__` → `__aenter__`/`__aexit__`(返回 awaitable);生成器:`def`+`yield` → `async def`+`yield`(async 生成器,自动实现异步迭代协议)。语法:`async for`/`async with` 只能用在 `async def` 里,由事件循环驱动。`contextlib` 有 `@asynccontextmanager` 与 `aclosing`(对应同步的 `@contextmanager`/`closing`)。强调这是**语言协议**;并发「怎么选/怎么落地」仍指向[第 13 章](13-concurrency-bridge.md)与 `python-concurrency/`。

代码块(逐字用已验证版本):
```python
import asyncio

async def squares(n):                 # async 生成器:async def 体内 yield
    for i in range(n):
        await asyncio.sleep(0)        # 让出事件循环
        yield i * i                   # 自动实现 __aiter__/__anext__

class AConn:                          # 异步上下文管理器
    async def __aenter__(self):       # 对应同步 __enter__
        print("open"); return self
    async def __aexit__(self, *exc):  # 对应同步 __exit__
        print("close"); return False

async def main():
    async with AConn():               # async with → __aenter__/__aexit__
        out = [x async for x in squares(3)]   # async for → __aiter__/__anext__
    print(out)                        # [0, 1, 4]

asyncio.run(main())                   # 运行整个协程
```
说明句:async 孪生协议是「在 await 点能让出控制权」的迭代/资源管理;迭代耗尽抛 `StopAsyncIteration`;需要确保 async 生成器被关闭时用 `contextlib.aclosing(...)`。

- [ ] **Step 3: 加 Java/Go 对照框一行**

在 `## Java/Go 对照框`(line 169 起)表格加一行:
```
| 异步迭代/资源 | Java 响应式 `Flow`/`CompletableFuture` | `async for`(`__aiter__`/`__anext__`)、`async with`(`__aenter__`/`__aexit__`)、async 生成器;≈ Go `range` over channel |
```

- [ ] **Step 4: 加章末面试卡一题**

在 `## 章末面试卡`(line 180 起)末尾加:
```
**Qx. `async with` / `async for` 和同步版的区别?背后是哪些 dunder?**
它们是同步协议的异步孪生,一一对应:`async with` → `__aenter__`/`__aexit__`(返回 awaitable,由事件循环 await),`async for` → `__aiter__`/`__anext__`(耗尽抛 `StopAsyncIteration`),`async def`+`yield` 是 async 生成器。只能用在 `async def` 内,作用是「在 await 点让出控制权」。并发怎么选见第 13 章。
```

- [ ] **Step 5: 验证落地**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && grep -cE '__aenter__|__aiter__|async for|async with|StopAsyncIteration' python/07-iterators-generators-context-managers.md
```
Expected: ≥ 5

- [ ] **Step 6: Commit(用户 go-ahead 后)**

```bash
git add python/07-iterators-generators-context-managers.md
git commit -m "python 教程:ch07 新增 async 协议小节(async for/with、async 生成器、与同步协议一一对应)"
```

---

## Task 5: #2 Python↔C 边界(新开 ch21)+ README

**Files:**
- Create: `python/21-python-c-boundary.md`
- Modify: `python/README.md`(目录表 line 41 后加 ch21 行;"与其他目录关系" 加一行)

- [ ] **Step 1: 实测验证全部代码块**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && python3 - <<'PY'
import struct, array, sys, ctypes
from ctypes.util import find_library
buf = bytearray(b"abcdef"); mv = memoryview(buf); mv[0:3] = b"XYZ"
print(buf)
packed = struct.pack(">Ih", 1, -2); print(packed, struct.unpack(">Ih", packed))
arr = array.array("i", [1,2,3,1000]); print(arr.itemsize*len(arr), sys.getsizeof([1,2,3,1000]))
libc = ctypes.CDLL(find_library("c"))
libc.strlen.restype = ctypes.c_size_t; libc.strlen.argtypes = [ctypes.c_char_p]
print(libc.strlen(b"hello"), libc.abs(-7))
PY
```
Expected 输出:
```
bytearray(b'XYZdef')
b'\x00\x00\x00\x01\xff\xfe' (1, -2)
16 88
5 7
```

- [ ] **Step 2: 创建 `python/21-python-c-boundary.md`(完整章式样)**

结构与必含内容:

**导引**(`> **为什么这章重要**`):资深要懂 Python 与 C 之间这条边界——numpy/torch 的数组都活在这层;理解它才知道「为什么 `.numpy()` 常免拷贝」「为什么处理大二进制别用 `bytes` 切片」;以及如何用 `ctypes`/`cffi` 直接调原生库做 FFI。一句话心智:**CPython 对象大多是「带头的盒子」,但有一类对象愿意把一段连续内存暴露出来共享——这就是缓冲区协议,零拷贝与 C 互操作都建在它上面。**

**一、缓冲区协议(buffer protocol)**:解释它是 `bytes`/`bytearray`/`array`/`memoryview`/numpy 数组共享的底层契约——对象暴露「一段连续内存 + 形状/步长/类型」给消费者直接读写,无需拷贝。谁实现了它,谁就能被 `memoryview` 包、被 `np.asarray` 零拷贝接走。

**二、`memoryview`:零拷贝视图**(用已验证代码):
```python
buf = bytearray(b"abcdef")
mv = memoryview(buf)      # 不拷贝,view 指向 buf 的内存
mv[0:3] = b"XYZ"          # 改 view 即改底层
print(buf)                # bytearray(b'XYZdef')

big = bytes(10_000_000)
sub_copy = big[1:]        # bytes 切片:拷贝 ~10MB
sub_view = memoryview(big)[1:]   # memoryview 切片:零拷贝,只挪指针
```
要点:处理大缓冲(网络包、文件块、图像)时,`memoryview` 切片/传参不拷贝,`bytes` 切片会拷贝整段;`memoryview` 可读写(若底层可变)。

**三、`struct` 与 `array`**(用已验证代码):
```python
import struct, array, sys
packed = struct.pack(">Ih", 1, -2)        # 大端:uint32 + int16 → 6 字节
print(packed, struct.unpack(">Ih", packed))   # b'\x00\x00\x00\x01\xff\xfe' (1, -2)

arr = array.array("i", [1, 2, 3, 1000])   # 紧凑同质 int 数组
print(arr.itemsize * len(arr), sys.getsizeof([1, 2, 3, 1000]))   # 16  88
```
要点:`struct` 把 Python 值打包成定长二进制(协议/文件格式必备,格式字符 `>`/`<` 控字节序,`I/h/q/f` 控类型);`array` 是紧凑同质数值数组,内存远小于 `list`(list 是指针数组,每元素是完整对象)。

**四、`ctypes`:调 C 动态库**(用已验证代码):
```python
import ctypes
from ctypes.util import find_library

libc = ctypes.CDLL(find_library("c"))     # 跨平台定位 libc(mac: libSystem;linux: libc.so.6)
libc.strlen.restype = ctypes.c_size_t     # 声明返回类型
libc.strlen.argtypes = [ctypes.c_char_p]  # 声明参数类型
print(libc.strlen(b"hello"))              # 5
print(libc.abs(-7))                       # 7
```
要点:`ctypes` 无需编译即可调已有动态库,关键是**显式声明 `restype`/`argtypes`**(否则默认按 int 处理会出错);`cffi` 是更现代的替代(声明式、贴近 C 头文件,常配合编译,性能更好)——一句话对比即可,不展开。
平台注记:`find_library("c")` 在 macOS/Linux 行为略不同,但都能解析到 libc;`abs`/`strlen` 跨平台稳妥。

**五、收口 numpy/torch**:为什么 `tensor.numpy()` / `np.asarray(some_buffer)` 常常**免拷贝**——因为两边都实现缓冲区协议,共享同一段内存;何时**会**拷贝(类型/连续性不匹配、跨设备 CPU↔GPU)。numpy 代码标「示意,需装库」。

**Java/Go 对照框**:
```
| | Java / Go | Python |
|--|-----------|--------|
| 调原生库 | JNI(需胶水)/ cgo | `ctypes`/`cffi`(免编译直接调) |
| 直接内存/零拷贝 | `ByteBuffer.allocateDirect`、NIO | 缓冲区协议 + `memoryview` |
| 紧凑数值数组 | `int[]`(原生数组) | `array.array` / numpy(对比 `list` 的指针数组) |
| 二进制打包 | `ByteBuffer` put/get | `struct.pack`/`unpack` |
```

**章末面试卡**(≥3 题):
- `memoryview` 解决什么问题?(零拷贝处理大缓冲;`bytes` 切片拷贝,`memoryview` 切片只挪指针。)
- `list` 和 `array.array` 内存差别为何这么大?(list 是指针数组+每元素独立对象头;array 连续存原始值。)
- `ctypes` 用前为什么要设 `argtypes`/`restype`?(否则默认按 C int 处理指针/长返回值会出错或截断;`cffi` 是更现代的声明式替代。)

- [ ] **Step 3: README 目录表加 ch21 行**

在 `python/README.md` line 41(`| 20 | …工具箱… |`)之后插入:
```
| 21 | [Python↔C 边界](21-python-c-boundary.md) | 缓冲区协议、memoryview、struct/array、ctypes/cffi |
```

- [ ] **Step 4: README "与其他目录关系" 加一行**

在该小节列表末尾加:
```
- **零拷贝/二进制/FFI 的语言层** 就在本章(ch21);更深的**性能剖析与原生扩展工程化**仍指 [`../performance-tuning-roadmap/`](../performance-tuning-roadmap/)。
```

- [ ] **Step 5: 验证落地**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview && test -f python/21-python-c-boundary.md && grep -cE 'memoryview|缓冲区协议|ctypes|struct|array' python/21-python-c-boundary.md && grep -c '21-python-c-boundary' python/README.md
```
Expected: 文件存在;第一个计数 ≥ 6;第二个 ≥ 1

- [ ] **Step 6: Commit(用户 go-ahead 后)**

```bash
git add python/21-python-c-boundary.md python/README.md
git commit -m "python 教程:新增 ch21 Python↔C 边界(缓冲区协议/memoryview/struct/array/ctypes)"
```

---

## Self-Review(已对照 spec)

**Spec coverage:** #6→Task1、#5→Task2、#3+#4→Task3、#1→Task4、#2→Task5。6 处全覆盖,无遗漏。

**Placeholder scan:** 所有 3.11 可跑代码块均本机实测、输出已填实值(Task1/2/4/5 的 Expected 取自实跑);Task3 无可实测代码,已显式标「概念/面试向」并加事实核对 gate,非占位。Java/Go 对照行与面试卡题均写出实际文字,非「补充合适内容」。

**Type/命名一致性:** 各小节标题、dunder 名(`__aenter__`/`__aexit__`/`__aiter__`/`__anext__`)、`covariant=True`/`contravariant=True`、`concurrent.interpreters`、`memoryview`/`struct`/`array`/`ctypes` 在跨任务引用中一致。grep 验证步骤与各章实际新增关键词对齐。

**风格一致性:** 每个新增遵循全书四件套(导引/正文实测/对照框/面试卡);新章 ch21 走完整章式样;面试卡只复习、不承载正文未讲的新知识。
