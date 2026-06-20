# defer 求值/执行时机 + recover 为什么没接住

## 一句话回答

`defer` 把「这次调用」压进当前函数的一个 **LIFO 栈**:**参数在 defer 语句执行那一刻就求值并固定**,**函数体延到 return 前才逆序执行**,且能**修改命名返回值**。`recover` 只有在**当前正在 panic 的 goroutine** 中、被一个**延迟函数直接调用**时才返回 panic 值并止住栈展开;放在普通流程里、包一层普通函数里、或在别的 goroutine 里调用,都返回 `nil`(等于没用)——这就是「写了 recover 却没接住」的原因。

## defer 三条铁律

```go
func demo() (result int) {
    result = 1
    defer func() { result++ }()   // ③ defer 能改命名返回值
    return result                 // return = 先把 result 赋值 → 跑 defer(result=2) → 真返回 2
}
```

1. **参数求值 = defer 语句处**(不是返回时):`defer log(time.Now())` 记的是注册那刻的时间。
2. **执行顺序 = LIFO**:`for i:=0;i<3;i++ { defer print(i) }` → 打印 `2 1 0`。
3. **可改命名返回值**:`return x` 分两步(赋命名返回值 → 跑 defer → 真返回)——这是 panic→error 转换的基础。

## recover 必须蹲在 defer 里

```go
func safe() (err error) {
    defer func() {                          // ✅ defer 函数里
        if r := recover(); r != nil {       // ✅ 被该 defer 直接调用
            err = fmt.Errorf("recovered: %v", r)   // 把 panic 转成 error 返回
        }
    }()
    mayPanic()
    return nil
}
```

- ❌ 普通流程里 `recover()`、❌ 在 defer 里再包一层普通函数调 `recover()`、❌ 在另一个 goroutine 里 `recover()`——都接不住。

## panic 流程

panic → 当前函数停 → 逆序跑已压入的 defer → 交给调用者(同样跑 defer)→ 一路**展开**,直到某 defer 里 recover 接住,**或**抵达 goroutine 顶端 **crash 整个进程**。

## 证据链接

- 正文:[`03 panic·recover·defer`](../03-panic-recover-defer/README.md)

## 易追问的延伸

- **`for` 循环里 defer 的坑?** 资源堆到函数结束才释放(句柄耗尽)+ 走慢路径;循环里要及时释放就显式调用或抽小函数。
- **recover 能接住别的 goroutine 的 panic 吗?** 不能——只对当前 goroutine 有效。每个 `go` 出去的协程要自带 recover,否则 crash 进程。见 [`05`](../05-concurrent-errors/README.md)。
- **defer 性能?** Go 1.14 open-coded defer 后,固定数量、非循环的 defer 近零开销;循环/不定数量走慢路径。
- **recover 能滥用吗?** 不能——无脑吞 panic 会掩盖真实 bug;recover 后要带 `debug.Stack()` 记录 + 上报。
- **defer ≈ Java 什么?** `finally` / try-with-resources,但更灵活(能改返回值、能 recover)。
