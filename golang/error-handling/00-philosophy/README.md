# 00 · 错误哲学：error 是值，不是控制流

> 这是整条 track 的地基。Go 与 Java/Python 在错误上的分歧不是 API 差异，是**哲学差异**：Java/Python 把错误当**异常（exception）**——抛出去、沿调用栈自动冒泡、由某个上层 catch；Go 把错误当**值（value）**——像 `int`、`string` 一样的普通返回值，就地判断、显式上抛。
>
> 桥接锚点：Java 的 `throw new IOException()` ←→ Go 的 `return err`。一个是「离开正常控制流、跳给上层」，一个是「正常控制流的一部分、留在原地」。

---

## 1. 核心问题

你在 Java 里读文件：

```java
String read(Path p) throws IOException {   // 失败 = 抛异常，签名上一个 throws
    return Files.readString(p);            // 出错自动沿栈冒泡，这里不写任何处理
}
```

同样的事 Go 里长这样：

```go
func read(p string) (string, error) {     // 失败 = 多返回一个 error 值
    b, err := os.ReadFile(p)
    if err != nil {
        return "", err                     // 出错必须显式 return，不会自己冒泡
    }
    return string(b), nil
}
```

三个问题，本章要回答：

- Go 为什么**故意不要** try-catch？把错误满世界 `if err != nil` 不是很啰嗦吗？
- 那 `panic`/`recover` 看起来不就是异常吗？它和 `error` 到底什么关系？
- 一个操作失败了，我**怎么判断**该 `return err` 还是该 `panic`？

---

## 2. 直觉理解

### error 是值：失败是「数据」，不是「事件」

Go 的核心立场：**失败是函数正常输出的一部分**。一个可能失败的函数，它的「结果」天然是「成功值 + 失败原因」二选一，所以签名就写成 `(T, error)`。调用方拿到的 `err` 是一个**普通的接口值**，你可以判断它、包装它、塞进 struct、传给 channel——它就是数据。

Java 的立场相反：失败是一个**事件（exception）**，它会**中断正常控制流**，沿调用栈往上「冒泡」，直到撞上一个 `catch`。中途的每一层函数都**看不见**它经过（除非自己 try）。

一句话对照：

| | Java/Python 异常 | Go error |
|---|---|---|
| 错误是什么 | 一个**事件**，中断控制流 | 一个**值**，是返回值的一部分 |
| 怎么传播 | 自动沿栈冒泡 | 手动 `return err`，一层层显式传 |
| 调用方 | 可以**不写** catch（unchecked 时静默穿透） | **必须**接住那个 `err`（编译器逼你处理返回值） |
| 控制流 | 隐式跳转（看代码看不出谁会抛） | 显式分支（`if err != nil` 写在脸上） |

### 「啰嗦」是故意的——把失败路径摆到明面

Java 里这段代码：

```java
a();    // 这三行里任何一行都可能抛异常跳走
b();    // 但你从代码上看不出来——控制流是隐形的
c();
```

Go 强迫你写成：

```go
if err := a(); err != nil { return err }
if err := b(); err != nil { return err }
if err := c(); err != nil { return err }
```

啰嗦，但**失败路径全部可见**：每一处可能出错的地方、出错后往哪走，都明明白白写在代码里，没有「隐形的跳转」。Go 的设计者（Rob Pike：*"Errors are values"*）认为：错误处理是程序的**主要逻辑**，不该被藏进一个看不见的控制流里。在大型服务里，「这行会不会抛、抛了谁接」的隐式跳转，正是难调试的根源。

### 那 panic 是什么？——Go 也有「异常」，但锁在保险柜里

Go 不是没有「类异常」机制：`panic` 会中断控制流、沿栈展开（unwind）、执行 defer，`recover` 能在 defer 里把它接住——**这套机制本身就是异常**。

关键区别在**用途约束**：

- `error`：**预期内**的失败（文件不存在、网络超时、参数非法）——是 API 契约的一部分，调用方应当处理。**99% 的失败走这条。**
- `panic`：**预期外**的失败（数组越界、空指针解引用、不该发生的状态）——通常是**程序 bug**，意味着「继续跑下去也没意义」。

所以 Go 的真实哲学不是「没有异常」，而是：**把异常机制（panic）从「日常错误处理」里赶出去，只留给「程序已经坏了」的场景。** Java 把两者混在一个 `Exception` 体系里（`IOException` 和 `NullPointerException` 都是异常）；Go 强行劈成两半——可预期的用值，不可预期的用 panic。

---

## 3. 原理深入

### 3.1 error 只是一个普通接口

Go 里没有「异常类型」这种特殊东西。`error` 就是标准库里一个**最普通的接口**：

```go
type error interface {
    Error() string
}
```

任何实现了 `Error() string` 的类型都是一个 error。这意味着：

- `error` 值能被赋值、比较（`err == io.EOF`）、装进 struct、塞进 slice/channel、用 `==` 判断——因为它就是普通接口值。
- 「返回错误」在底层**没有任何特殊机制**：就是多压一个返回值到栈/寄存器上，和返回 `int` 零开销路径一样。对比异常：JVM 抛异常要**构造异常对象 + 抓取栈轨迹（fillInStackTrace，很贵）+ 栈展开找 handler**。Go 的 `return err` 没有这些。

> 这解释了为什么 Go 能在热路径上大量返回错误而不心疼性能——返回错误就是返回值，没有「异常开销」。

### 3.2 nil 是「没有错误」的约定

```go
func do() error {
    return nil          // nil = 成功，没有错误
}
if err := do(); err != nil { ... }   // 判 nil 就是判有没有错
```

`error` 是接口，它的零值是 `nil`。「成功」的惯例就是返回 `nil`。
⚠️ 这里埋着 Go 最经典的坑——**typed nil**：一个「装了 nil 指针的非空接口」`!= nil`。这个坑留到 [`type-system/` 的「nil 的多张面孔」] 专门拆，本章只需记住「`nil` 表示无错」这个约定。

### 3.3 panic/recover 的机制（与 error 划清界限）

```go
func mayPanic() {
    panic("boom")              // 中断控制流，开始沿栈展开
}
func safe() (err error) {
    defer func() {
        if r := recover(); r != nil {   // recover 只在 defer 里有效
            err = fmt.Errorf("recovered: %v", r)
        }
    }()
    mayPanic()
    return nil
}
```

- `panic` 触发后：当前函数停止，**逆序执行已注册的 defer**，然后把控制权交还给调用者，调用者同样执行 defer 再上抛……一路展开到 `recover` 接住，或到 goroutine 顶端**整个进程 crash**。
- `recover` **只有在 defer 函数里直接调用**才能截住 panic（机制细节在 [`03-panic-recover-defer/`](../03-panic-recover-defer/README.md)）。
- 注意上面 `recover` 把 panic **转成了 error 返回**——这是「跨边界」的常见手法：库内部可以用 panic 简化深层逻辑，但**不让 panic 越过包的公共边界**，在边界 defer-recover 转回 error。标准库 `encoding/json`、`fmt` 内部就这么干。

### 3.4 为什么 Go 2 没有加 try-catch（设计史，面试加分）

Go 团队认真提过给错误处理加语法糖：2018 的 `check/handle` 提案、2019 的 `try` 内置函数提案（`x := try(f())` 自动在出错时 return）。**两个都被否决/撤回了**。否决的核心理由：

- 它们会**把显式的错误检查重新变回隐式跳转**，违背「错误处理应当可见」的初衷；
- 让「错误在哪里被处理」变得不明显，社区压倒性反对。

结论：`if err != nil` 的啰嗦是**深思熟虑后保留的**，不是没来得及改。面试时能说出「try 提案被拒及原因」，是资深信号。

---

## 4. 日常开发应用

### 铁律一：错误是返回值，永远显式处理，别吞

```go
f, err := os.Open(name)
if err != nil {
    return fmt.Errorf("open config: %w", err)   // 加上下文再上抛（%w 见 02 章）
}
defer f.Close()
```

- **绝不 `_ = doSomething()` 把 error 丢掉**（除非你真的想忽略，且写明白）。`errcheck`/`go vet` 会抓未处理的 error。
- 上抛时**加上下文**（"open config:"），否则最上层只看到一句裸 `no such file`，不知道是谁、在哪、干什么时出的。

### 铁律二：error 作最后一个返回值

```go
func Fetch(ctx context.Context, id int) (*User, error)   // error 永远放最后
```

社区铁律：error 是最后一个返回值，名字就用 `err`。成功时其它返回值有效、err 为 nil；失败时**调用方不应假设其它返回值有效**（除个别有文档约定的，如 `io.Reader` 可能同时返回 n>0 和 err）。

### 铁律三：error vs panic 的判断公式

| 这个失败…… | 用 | 例子 |
|---|---|---|
| 调用方**可能想处理 / 是预期内的** | `error` | 文件不存在、网络超时、用户输入非法、订单不存在 |
| 是**程序 bug / 不该发生的状态** | `panic` | 数组越界、解引用 nil、switch 漏了 case、初始化时配置缺失 |
| 在**库的公共 API 边界** | 一律 `error` | 别让你的库 panic 到调用方头上 |
| 在 `main`/初始化、继续跑无意义 | `panic` 或 `log.Fatal` | 连不上数据库就启动不了 |

一句口诀：**「调用方能合理应对的 → error；只有程序员改代码才能修的 → panic。」**

---

## 5. 生产&调优实战

- **panic 在生产 = 进程级风险**：一个没 recover 的 panic 会**杀掉整个进程**（不是一个线程）。尤其 **goroutine 里的 panic 无法被另一个 goroutine 的 recover 接住**——它会直接 crash 整个程序（细节见 [`05-concurrent-errors/`](../05-concurrent-errors/README.md)）。所以服务端框架（gin、gRPC）都在请求入口装了 recover 中间件，把单请求的 panic 兜成 500，不连累别的请求。
- **不要用 panic 做正常控制流**：性能上 panic/recover 比 `return err` 贵得多（要栈展开、跑 defer）；语义上也会让错误「隐形跳转」。`recover` 只用于：① 兜住边界处不可控的 panic；② 库内部 panic 转 error 的边界翻译。
- **error 是 API 契约**：你的函数返回什么错误，调用方就会依赖什么错误去判断（`errors.Is(err, ErrNotFound)`）。一旦发布，错误类型/哨兵就成了**兼容性的一部分**——随意改错误会破坏调用方（设计原则见 [`04-error-design/`](../04-error-design/README.md)）。
- **别让错误信息泄漏内部**：`return err` 把底层 SQL 错误原样冒泡到 HTTP 响应，会泄漏表结构/实现细节，也是安全问题。边界要做错误翻译（04 章）。

---

## 6. 面试高频考点

- **Go 为什么不用异常（try-catch）？** 哲学是「error 是值不是控制流」：失败是返回值的一部分，强制显式处理，把失败路径摆到明面，避免隐式跳转难调试。Rob Pike "errors are values"。
- **那 panic/recover 不就是异常吗？区别在哪？** 机制上确实是异常（中断+栈展开+defer）；但**用途被约束**——error 管预期内可处理的失败（99% 场景），panic 只留给程序 bug / 不可恢复状态。Go 把异常机制从日常错误处理里赶了出去。
- **error vs panic 怎么选？** 调用方能合理应对的预期失败 → error；程序 bug / 不该发生的状态 → panic；库公共边界一律 error。
- **和 Java checked exception 比？** Java checked 也强制处理，但靠类型系统 + 自动冒泡，且 `throws` 会污染签名、催生 `catch(Exception e){}` 吞异常；Go 用「返回值 + 编译器逼你接住返回值」达到类似强制，但完全显式、无冒泡。
- **`if err != nil` 太啰嗦，Go 为什么不改？** Go 2 的 `check/handle`、`try` 提案都被否决——因为它们会把显式检查变回隐式跳转，违背初衷。啰嗦是刻意保留的。
- **error 底层是什么？** 一个只有 `Error() string` 的普通接口；返回错误就是返回一个接口值，零异常开销（无栈轨迹抓取、无栈展开）。

---

## 7. 一句话总结

> **Go 的错误哲学：error 是值，不是控制流。** 失败是函数返回值的一部分（`(T, error)`），靠 `if err != nil` 显式判断、`return err` 显式上抛，把失败路径全摆到明面、消灭隐式跳转。Go 并非没有异常——`panic`/`recover` 就是异常机制，但被刻意**锁进保险柜**，只留给「程序 bug / 不可恢复」的场景；预期内、调用方能应对的失败一律用 error。判据一句话：**能合理应对的 → error，只能改代码才能修的 → panic。** `if err != nil` 的啰嗦是 Go 2 否决 try 提案后深思熟虑的保留，不是缺陷。

下一章 → [`01 error 接口与三种风格`](../01-error-values/README.md)：error 既然是普通接口值，那「怎么造、怎么让调用方识别」就有 sentinel / typed / opaque 三种风格，各有取舍。｜ 回 [`error-handling` 索引](../README.md)
