# 08 · 异常与错误处理

> **为什么这章重要**:Python 的错误处理哲学和 Go(返回 error)、Java(受检异常)都不同——它**全用异常、且偏好"先做再说"(EAFP)**。理解异常层级、`try/except/else/finally` 的精确语义、异常链,以及 `finally` 吞 return 这类坑,是写出健壮代码和答好面试的基础。

## 一、异常层级

所有异常继承自 `BaseException`,日常你关心的几乎都在 `Exception` 这一支:

```
BaseException
├── SystemExit          # sys.exit() 触发
├── KeyboardInterrupt   # Ctrl-C
├── GeneratorExit
└── Exception           # ← 业务异常都在这下面
    ├── ValueError, TypeError, KeyError, IndexError, AttributeError ...
    ├── OSError (FileNotFoundError, ...)
    └── 你自定义的异常
```

**关键**:`except Exception` 不会捕获 `KeyboardInterrupt`/`SystemExit`(它们直接挂在 `BaseException` 下),所以 Ctrl-C 和 `sys.exit()` 能正常穿透你的 `try`。**永远别写 `except BaseException` 或裸 `except:`**——那会连 Ctrl-C 都吞掉。

自定义异常:建一个项目根异常,业务异常都继承它,这样调用方既能精确捕获也能"一网打尽":

```python
class AppError(Exception): pass
class NotFound(AppError): pass

try:
    raise NotFound("user 42")
except AppError as e:              # 父类能捕获子类
    print(type(e).__name__)        # NotFound
```

## 二、`try / except / else / finally` 的精确语义

```python
def run(fail):
    seq = []
    try:
        seq.append("try")
        if fail:
            raise ValueError("x")
    except ValueError:
        seq.append("except")       # 仅当 try 抛了匹配的异常
    else:
        seq.append("else")         # 仅当 try 完全没抛异常
    finally:
        seq.append("finally")      # 永远执行(正常/异常/return 都执行)
    return seq

print(run(False))   # ['try', 'else', 'finally']
print(run(True))    # ['try', 'except', 'finally']
```

- **`else`**:`try` 块没有异常时才跑。用途:把"可能抛异常的代码"和"成功后才做的事"分开,让 `try` 范围尽量小、意图更清晰。
- **`finally`**:**无论如何都执行**,包括 `try`/`except` 里有 `return`/`break`/`continue` 时。用于必清理的收尾(虽然资源清理更推荐 `with`)。

### 坑:`finally` 里的 `return` 会覆盖一切

```python
def tricky():
    try:
        return "try"
    finally:
        return "finally"      # 覆盖了 try 的返回值!

print(tricky())   # "finally"
```

`finally` 里的 `return`(或 `break`)会**吞掉** `try` 里的返回值,甚至吞掉正在传播的异常。所以**别在 `finally` 里写 `return`/`break`/`raise`**,除非你非常清楚自己在干什么。

### 捕获多种异常

```python
try:
    return int(x)
except (ValueError, TypeError) as e:    # 元组:一并捕获
    handle(e)
```

把多个异常放进元组一起捕获;多个 `except` 块按顺序匹配,**第一个匹配的胜出**,所以要把更具体的异常写在更通用的前面(否则永远轮不到具体的)。

## 三、异常链:`raise ... from ...`

捕获一个底层异常、包装成业务异常往上抛时,用 `raise X from e` 保留原始原因,便于排错:

```python
try:
    1 / 0
except ZeroDivisionError as e:
    raise RuntimeError("计算失败") from e

# 回溯里会显示:
# ZeroDivisionError: division by zero
# The above exception was the direct cause of the following exception:
# RuntimeError: 计算失败
```

- `raise X from e`:显式设置 `X.__cause__ = e`,打印"The above ... was the **direct cause**"。
- 若不写 `from`,在 `except` 中再抛新异常,Python 会自动设 `__context__`(隐式关联),打印"During handling ... **another exception** occurred"。
- `raise X from None`:抑制链,只显示 `X`(不想暴露底层细节时用)。

包装异常但保留链,既给了调用方干净的业务异常,又在日志里留住了根因——比 Go 的 `fmt.Errorf("%w", err)` 更结构化。

## 四、EAFP vs LBYL:Python 偏好"先做再说"

两种风格:

- **LBYL**(Look Before You Leap):先检查再操作。`if key in d: use(d[key])`。
- **EAFP**(Easier to Ask Forgiveness than Permission):直接做,出错再处理。`try: use(d[key]) except KeyError: ...`。

**Python 文化偏好 EAFP**,原因有二:(1) 避免检查与使用之间的竞态(检查通过后、使用前状态变了);(2) 在"正常路径几乎总成功"时更快(不为每次操作付检查开销)。

```python
# LBYL —— 有竞态风险,且 d[key] 又查一遍
if "key" in d:
    v = d["key"]

# EAFP —— 地道
try:
    v = d["key"]
except KeyError:
    v = default
# 当然,这个具体例子直接 d.get("key", default) 更好
```

> 这点和 Java(也用异常,但文化上更 LBYL/防御式)、Go(根本不用异常,显式 `if err != nil`)都不同,面试常被问"EAFP 是什么、为什么 Pythonic"。

## 五、其他工具

### `contextlib.suppress`:优雅忽略指定异常

```python
from contextlib import suppress
with suppress(KeyError):       # 等价于 try/except KeyError: pass,但更短更清晰
    del d["maybe_missing"]
```

### 异常组与 `except*`(3.11+)

并发场景(`asyncio.TaskGroup`)里多个任务可能**同时**失败,需要一次抛一组异常。`ExceptionGroup` + `except*` 处理这种"一堆异常":

```python
try:
    raise ExceptionGroup("multi", [ValueError("a"), TypeError("b")])
except* ValueError as eg:
    print([str(x) for x in eg.exceptions])   # ['a']
except* TypeError as eg:
    print([str(x) for x in eg.exceptions])   # ['b']
```

`except*` 能从一个异常组里**挑出**匹配的子异常分别处理,其余继续传播。主要服务于结构化并发(第 13 章)。

### `assert`:只用于"绝不该发生"的内部断言

```python
def f(x):
    assert x > 0, "must be positive"   # 失败抛 AssertionError,带消息
    ...
```

`assert` 用于捕捉**程序员错误/不变量**,不是用来校验用户输入。**致命点**:用 `python -O` 运行时,所有 `assert` 会被**整个跳过**——所以绝不能用 `assert` 做安全检查或输入校验(生产可能关掉它)。

## Java/Go 对照框

| | Java | Go | Python |
|--|------|-----|--------|
| 机制 | 异常,分受检/非受检 | 返回 `error` 值,`panic/recover` 兜底 | 全用异常,无"受检" |
| 是否强制处理 | 受检异常编译期强制 | 靠约定显式检查 `err` | 不强制,文化偏 EAFP |
| 资源清理 | try-with-resources / finally | `defer` | `with` / `finally` |
| 包装根因 | `new X(e)` / `getCause()` | `fmt.Errorf("%w", err)` | `raise X from e`(`__cause__`) |
| 多异常 | `catch (A \| B e)` | — | `except (A, B)` / 异常组 `except*` |

Python 没有受检异常,意味着方法签名不告诉你它会抛什么——**靠文档和约定**。这更灵活但也更需要自律:在公共 API 文档里写清可能抛的异常。

## 章末面试卡

**Q1. `try/except/else/finally` 各自什么时候执行?**
`try` 跑主体;`except` 仅当 `try` 抛了匹配异常时跑;`else` 仅当 `try` **没有**异常时跑;`finally` **无论如何都跑**(包括有 `return`/`break` 或异常传播时)。`else` 用来把"成功后才做的事"移出 `try`,缩小 `try` 范围。

**Q2(猜输出).**
```python
def f():
    try:
        return 1
    finally:
        return 2
print(f())
```
`2`。`finally` 里的 `return` 会覆盖 `try` 的返回值(也会吞掉正在传播的异常)。所以别在 `finally` 里写 `return`/`raise`。

**Q3. `raise X from e` 有什么用?和不写 `from` 有何区别?**
`from e` 显式设置 `__cause__`,回溯里标记为"直接原因",用于把底层异常包装成业务异常同时保留根因。不写 `from` 而在 `except` 里抛新异常时,Python 自动设隐式的 `__context__`("处理中又发生了另一个异常")。`from None` 可抑制链。

**Q4. 什么是 EAFP?为什么说它更 Pythonic?**
EAFP = 先尝试操作、失败再用 `except` 处理(对比 LBYL 先检查再做)。更 Pythonic 因为:避免"检查—使用"之间的竞态,且在正常路径几乎总成功时不为每次操作付检查成本。

**Q5. 能用 `assert` 做参数/输入校验吗?**
不能。`assert` 只用于捕捉"绝不该发生"的内部不变量/程序员错误,而且 `python -O` 会把所有 `assert` 跳过。校验用户输入要用显式 `if ... raise ValueError(...)`。

**Q6. 为什么不要写裸 `except:` 或 `except BaseException`?**
它们会连 `KeyboardInterrupt`(Ctrl-C)和 `SystemExit`(`sys.exit()`)一起吞掉,让程序无法被正常中断/退出,还会掩盖意料外的错误。要兜底也应捕获 `Exception`,并且尽量精确匹配具体异常类型。
