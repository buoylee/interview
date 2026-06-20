# 何时该 panic、何时该 return err

## 一句话回答

判据一句话:**调用方能合理应对的、预期内的失败 → `return error`;程序 bug / 不该发生的状态 / 继续跑没意义 → `panic`。** 库的**公共 API 一律 error**,绝不 panic 到调用方头上;真要在内部用 panic 简化深层逻辑,也要在包边界 `recover` 转回 error。99% 的失败走 error,panic 是「保险柜里」的少数派。

## 判据表

| 场景 | 选择 | 为什么 |
|---|---|---|
| 文件不存在、网络超时、用户输入非法、订单不存在 | **error** | 预期内,调用方能处理 |
| 数组越界、解引用 nil、不可能的 switch 分支 | **panic** | 程序 bug,早崩早暴露 |
| `regexp.MustCompile` / `template.Must`(参数写死常量) | **panic** | 约定:错了就是程序员的错 |
| `init` / `main` 前置不满足(连不上 DB、配置缺失) | **panic** / `log.Fatal` | 启动不了就别启动 |
| 库的公共 API | **error** | 别 panic 到调用方;内部 panic 在边界转 error |

## 为什么不拿 panic 当控制流

- **性能**:panic/recover 要栈展开 + 跑 defer,比 `return err` 贵得多。
- **语义**:panic 是隐式跳转,违背「错误处理可见」(见 [`00`](../00-philosophy/README.md))。
- **风险**:goroutine 里没 recover 的 panic 会 **crash 整个进程**(见 [`05`](../05-concurrent-errors/README.md))。

## 内部 panic、边界转 error(标准库手法)

```go
func Parse(b []byte) (ast *AST, err error) {
    defer func() {
        if r := recover(); r != nil { err = fmt.Errorf("parse: %v", r) }
    }()
    return parseInternal(b), nil   // 内部深层递归可用 panic 跳出,边界 recover 转 error
}
```

`encoding/json`、`text/template` 内部就这么干——对外仍是「error 是值」的契约。

## 证据链接

- 正文:[`03 panic·recover·defer`](../03-panic-recover-defer/README.md) / [`00 错误哲学`](../00-philosophy/README.md)

## 易追问的延伸

- **服务端怎么防 panic 拖垮全局?** 请求入口装 recover 中间件,把单请求 panic 兜成 500 + 记栈(gin/grpc 内置)。
- **`MustXxx` 为什么可以 panic?** 它约定参数是编译期写死的,失败=程序员错,适合在包初始化时 panic 早暴露。
- **panic 的值该传什么?** 惯例传 error 或字符串;`recover()` 返 `any`,常 `fmt.Errorf("%v", r)` 转 error。
