# 03 · panic · recover · defer:Go 的「异常」机制与边界

> 00 章说 Go 把异常机制锁进了保险柜,这章打开保险柜看里面:`panic`/`recover` 怎么运作、`defer` 的求值与执行时机(面试最爱挖)、recover 为什么常常「没接住」、以及那条判据——**到底何时才该 panic**。
>
> 桥接锚点:`defer` ≈ Java 的 `finally` / try-with-resources(但更灵活);`panic`/`recover` ≈ `throw`/`catch`,但**只该用于程序 bug**,不是日常错误。

---

## 1. 核心问题

```go
func f() {
    for i := 0; i < 3; i++ {
        defer fmt.Println(i)        // 打印 0 1 2 还是 2 2 2?什么时候打印?
    }
    fmt.Println("body")
}
```

```go
func g() {
    if r := recover(); r != nil {   // 这样能接住 panic 吗?
        fmt.Println("recovered")
    }
    panic("boom")
}
```

- `defer` 的参数**什么时候求值**?函数体**什么时候执行**?多个 defer 什么顺序?
- `recover` 为什么经常「写了却没接住」?它必须放在哪?
- 何时该 `panic`,何时该 `return err`?(00 章给了判据,这里给机制依据)

---

## 2. 直觉理解

### defer = 一个后进先出的「待执行调用」栈

每遇到一个 `defer`,就把「这次调用」压进当前函数的一个栈;函数**返回前**(无论正常 return 还是 panic)逆序(LIFO)弹出执行。

关键拆成两个时刻:

- **参数在 `defer` 语句执行那一刻就求值并固定**;
- **函数体延到 return 前才跑**。

所以开头那题答案是 **2 1 0**:三个 `defer fmt.Println(i)` 在循环里把 `i` 的**当时值** 0、1、2 各自固定下来,函数结束时 LIFO 弹出 → 打印 2、1、0。(注意:这和「循环变量捕获」坑不同——那是闭包引用变量,见 [`concurrency/04-goroutine`](../../concurrency/04-goroutine/README.md);`defer f(i)` 是传参求值,固定的是值。)

### panic = 立刻开始「栈展开」,沿途跑 defer

`panic` 一触发:当前函数停在原地 → **逆序执行已压入的 defer** → 把 panic 交给调用者 → 调用者也跑自己的 defer……一路向上**展开(unwind)**,直到:① 某个 defer 里 `recover` 接住,展开停止;② 或抵达 goroutine 顶端,**整个进程崩溃**并打印栈。

### recover = 只有蹲在「defer 里」才接得住

`recover` 只有在**正在 panic 的 goroutine** 中、被一个**延迟函数直接调用**时,才返回那个 panic 值并止住展开。其它任何位置调用都返回 `nil`(等于没用)。开头 `g()` 的 recover 在**普通流程**里调用(不是 defer),所以接不住——panic 照样 crash。

---

## 3. 原理深入

### 3.1 defer 的三条铁律

```go
func demo() (result int) {        // 命名返回值
    result = 1
    defer func() { result++ }()   // defer 能改命名返回值!
    return result                 // 先把 result 设为 1,再跑 defer → result=2 → 真正返回 2
}
```

1. **参数求值时机 = defer 语句执行时**(不是函数返回时)。`defer log(time.Now())` 记的是注册那一刻的时间。
2. **执行顺序 = LIFO**(后注册先执行)。
3. **defer 能修改命名返回值**:`return x` 实际分两步——先给命名返回值赋值,**再跑 defer**,最后才真正返回。这是「defer-recover 把 panic 转成 error 返回」的基础(见 3.4)。

### 3.2 defer 的性能(版本敏感)

Go 1.13/1.14 做了 **open-coded defer** 优化:大多数「函数内 defer 数量固定、不在循环里」的场景,defer 几乎零开销(编译期展开,不走运行时 `_defer` 链表)。但**循环里的 defer**、数量不定的 defer 仍走较慢的堆分配路径——所以**别在长循环里 defer**(还会导致资源到函数结束才释放,见 5 节)。

### 3.3 panic/recover 机制细节

```go
func safeClose(c io.Closer) {
    defer func() {
        if r := recover(); r != nil {        // ✅ 在 defer 里直接调 recover
            log.Printf("recovered: %v", r)
        }
    }()
    c.Close()
}
```

- `recover` 必须在 **defer 函数内、且被该 defer 直接调用**。包一层普通函数再调 `recover` 也无效(不是「被延迟函数直接调用」)。
- **re-panic**:recover 后可以判断,不该处理的再 `panic(r)` 抛回去。
- **panic 值可以是任意类型**,但惯例传 `error` 或字符串。`recover()` 返回 `any`,常 `r.(error)` 或 `fmt.Errorf("%v", r)`。

### 3.4 边界处把 panic 转成 error(最有用的 recover 用法)

```go
func Parse(data []byte) (result *AST, err error) {   // 命名返回值 err
    defer func() {
        if r := recover(); r != nil {
            err = fmt.Errorf("parse panic: %v", r)   // 把 panic 翻译成 error 返回
        }
    }()
    return parseInternal(data), nil                  // 内部深层逻辑可以放心 panic 简化代码
}
```

标准库 `encoding/json`、`text/template` 内部就用这招:**内部用 panic 跳出深层递归,在包的公共边界 defer-recover 转回 error**,对外仍是「error 是值」的契约。靠的就是 3.1 的「defer 能改命名返回值」。

### 3.5 何时该 panic(机制依据)

| 场景 | panic? | 为什么 |
|---|---|---|
| 程序 bug:越界、解引用 nil、不可能的 switch 分支 | ✅ panic | 继续跑没意义,早崩早暴露 |
| 包初始化/`init`、`main` 里前置条件不满足(配置缺失) | ✅ panic / `log.Fatal` | 启动不了就别启动 |
| `MustXxx` 构造函数(`regexp.MustCompile`、`template.Must`) | ✅ panic | 约定:参数是写死的常量,错了就是程序员的错 |
| 预期内失败(IO/网络/校验/找不到) | ❌ return error | 调用方能应对(00 章) |
| 库的公共 API | ❌ 一律 error | 别 panic 到调用方头上;真要 panic 也在边界 recover 转 error |

---

## 4. 日常开发应用

### defer 管清理(最常用)

```go
f, err := os.Open(name)
if err != nil { return err }
defer f.Close()                  // 紧跟在获取资源后写,保证释放

mu.Lock()
defer mu.Unlock()                // 锁的获取/释放配对,panic 也会解锁
```

- defer 紧跟资源获取写,**配对清晰**、panic 安全。
- ⚠️ 检查 `Close` 的错误(尤其写文件):`defer func(){ err = f.Close() }()` 配命名返回值,别让写缓冲未刷的错误被吞。

### 边界 recover 兜住请求(服务端)

```go
func recoverMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                log.Printf("panic: %v\n%s", rec, debug.Stack())   // 记 panic + 栈
                http.Error(w, "internal error", 500)              // 单请求兜成 500
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

把单个请求的 panic 兜成 500,不连累整个进程——gin/grpc 都内置这种中间件。

---

## 5. 生产&调优实战

- **别在循环里 defer**:资源会**堆到函数结束**才释放(连接/文件句柄耗尽),且走慢路径。循环里要及时释放就显式调用或抽成小函数。
- **recover 只兜「不可控的 panic」,别滥用**:用 recover 吞掉所有 panic 会**掩盖真实 bug**(空指针被悄悄咽下,问题更难查)。recover 后应**记录(带 `debug.Stack()`)+ 上报**,而非默默忽略。
- **recover 救不了别的 goroutine**:它只对**当前 goroutine** 的 panic 有效。你 `go func(){ panic() }()`,主协程的 recover **接不住**,整个进程 crash——所以**每个你 `go` 出去的 goroutine 都要自带 recover**(详见 [`05-concurrent-errors/`](../05-concurrent-errors/README.md))。
- **panic 比 return err 贵**:栈展开 + 跑 defer。别拿 panic 当控制流(00 章)。
- **`debug.Stack()` / `runtime/debug.SetPanicOnFault`** 用于诊断;生产 recover 中间件务必把栈打进日志,否则 panic 兜成 500 后丢了现场。

---

## 6. 面试高频考点

- **defer 参数何时求值?** defer **语句执行那一刻**就求值并固定;函数体延到 return 前 LIFO 执行。`defer f(x)` 固定的是当时的 x。
- **`for{ defer ... }` 输出顺序?** 参数逐次固定、LIFO 弹出,所以倒序(0,1,2 → 2,1,0);且资源到函数结束才释放(别这么写)。
- **defer 能改返回值吗?** 能改**命名返回值**——`return x` 是「先赋值命名返回值,再跑 defer,最后返回」。这是 panic→error 转换的基础。
- **recover 为什么常常没接住?** 它必须在 **defer 函数里被直接调用**,且在**同一个正在 panic 的 goroutine**。放普通流程里、包一层普通函数、或在别的 goroutine,都返回 nil。
- **怎么把 panic 转成 error?** 命名返回值 + defer 里 recover 后给 err 赋值(标准库 json/template 内部用法)。
- **recover 能接住别的 goroutine 的 panic 吗?** 不能。goroutine 的 panic 未被自己 recover 会 crash 整个进程——每个 go 出去的协程要自带 recover。
- **何时该 panic?** 程序 bug / 不可恢复状态 / `MustXxx` / init 前置不满足;预期失败和公共 API 一律 error。
- **defer ≈ Java 什么?** `finally` / try-with-resources,但更灵活(能改返回值、能 recover)。

---

## 7. 一句话总结

> **defer 是 LIFO 的待执行栈:参数在 defer 语句处即求值固定,函数体延到 return 前执行,且能修改命名返回值**(这是 panic→error 转换的基础)。**panic 触发栈展开、沿途跑 defer,直到某个 defer 里的 `recover` 接住、否则 crash 整个进程**;`recover` 只在**当前 panic 的 goroutine、defer 函数里被直接调用**时有效,救不了别的 goroutine。用途铁律:**panic 只给程序 bug / 不可恢复 / `MustXxx`,预期失败和公共 API 一律 error**;真要在内部用 panic,也要在包边界 recover 转回 error。recover 别滥用吞 bug,务必带 `debug.Stack()` 记录上报。

← 上一章 [`02 包装与检查`](../02-wrapping/README.md) ｜ 下一章 → [`05 并发中的错误`](../05-concurrent-errors/README.md):一个请求 fan-out 出 N 个 goroutine,错误怎么聚合、首错怎么取消其余、goroutine 里 panic 为什么会整进程 crash。｜ 回 [`error-handling` 索引](../README.md)
