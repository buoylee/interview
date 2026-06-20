# 02 · 包装与检查:`%w` 错误链与 `errors.Is`/`As`

> 错误从底层一层层上抛,每层都想**加上下文**("query user: ...: connection refused")又**不丢底层错误**,好让最上层还能识别原始原因。Go 1.13 给的答案是**错误链(error chain)**:`%w` 把错误串成链,`errors.Is`/`As` 穿过整条链识别。这是面试白板高频题。
>
> 桥接锚点:错误链 ≈ Java 异常的 **cause 链**(`new IOException("...", cause)` + `getCause()`)。`errors.Unwrap` ≈ `getCause`,`errors.Is`/`As` ≈ 沿 cause 链找特定异常。

---

## 1. 核心问题

```go
// 三层调用,每层都想加自己的上下文
func repo() error    { return sql.ErrNoRows }
func service() error { /* 怎么加 "load user" 又保留 sql.ErrNoRows? */ }
func handler() error { /* 怎么让这里还能判断出"底层是 not found"? */ }
```

- 我 `fmt.Errorf("load user: %v", err)` 加了上下文,但底层 `sql.ErrNoRows` 被压成字符串、**认不出来了**。怎么办?
- 用了 `%w` 之后,`handler` 怎么穿过两层包装、识别出最底层是 `sql.ErrNoRows`?
- `errors.Is` 和 `errors.As` 到底怎么遍历这条链?有什么区别?

---

## 2. 直觉理解

### `%w` 把错误串成一条单向链表

`fmt.Errorf` 里用 `%w`(wrap)而不是 `%v`(value),返回的错误会**记住被包装的那个错误**,形成一条链:

```
handler 的错误  ──Unwrap()──▶  service 的错误  ──Unwrap()──▶  sql.ErrNoRows  ──Unwrap()──▶ nil
"handle req:"                  "load user:"                  "sql: no rows..."
```

每一环只加一句自己的上下文,`Error()` 打印时是拼起来的整条:
`"handle req: load user: sql: no rows in result set"`。

而 `errors.Is`/`As` 就是**沿着这条链一路 `Unwrap` 往下走**,逐环检查。

### `Is` 找「是不是某个错误」,`As` 找「能不能转成某类型」

- `errors.Is(err, target)`:链上**有没有某个环 == target**(找哨兵)。问的是「**是不是**这个错误」。
- `errors.As(err, &dst)`:链上**有没有某个环能赋给 dst 类型**,有就填进去(找类型 + 取数据)。问的是「**能不能当作**这种类型」。

口诀:**`Is` 配哨兵,`As` 配类型。** 对应 01 章的 sentinel / typed 两种风格。

---

## 3. 原理深入

### 3.1 `%w` 构造了什么

```go
err := fmt.Errorf("load user: %w", sql.ErrNoRows)
```

`fmt.Errorf` 见到 `%w`,返回一个内部类型(等价):

```go
type wrapError struct {
    msg string
    err error            // 记住被包装的错误
}
func (e *wrapError) Error() string { return e.msg }   // "load user: sql: no rows..."
func (e *wrapError) Unwrap() error { return e.err }   // ← 关键:暴露下一环
```

**`Unwrap() error` 方法就是「链」的本体**——任何实现了 `Unwrap() error` 的错误,都能被 `errors` 包沿链遍历。`%v` 则不生成 `Unwrap`,链就**断**在这里(这正是 04 章「跨边界用 `%v` 切断耦合」的机制)。

### 3.2 `errors.Is` 的算法(能默写是加分项)

```go
func Is(err, target error) bool {
    for {
        if err == target { return true }                 // ① 当前环 == target?
        if x, ok := err.(interface{ Is(error) bool }); ok && x.Is(target) {
            return true                                   // ② 当前环自定义了 Is() 且认账?
        }
        if err = errors.Unwrap(err); err == nil {        // ③ 走到下一环;到底了就没找到
            return false
        }
    }
}
```

三件事循环:**比相等 → 给错误一次自定义 `Is` 的机会 → Unwrap 到下一环**。所以 `Is(wrapped, sql.ErrNoRows)` 能穿过 `"load user:"` 这层找到底层哨兵。

> 第②步的用处:有的错误想让「一类」都匹配。例如 `os.ErrNotExist`——很多不同的底层错误都希望被 `Is(err, os.ErrNotExist)` 认出,就各自实现 `Is()` 方法表示「我算 not-exist」。

### 3.3 `errors.As` 的算法

```go
var pe *fs.PathError
if errors.As(err, &pe) {            // 沿链找第一个能赋给 *fs.PathError 的环
    fmt.Println(pe.Path)            // 取出结构化字段
}
```

`As` 沿链遍历,对每一环:**能不能赋值给 `*target` 指向的类型**(或该环有自定义 `As` 方法),能就填充并返回 true。
⚠️ `As` 的第二参**必须是指向「error 实现类型」的非 nil 指针**(这里是 `**fs.PathError`),否则**直接 panic**——这是常见低级错误。

### 3.4 多重包装与 `errors.Join`(Go 1.20+)

一个错误可以**同时包多个**底层错误,链从「链表」变成「树」:

```go
err := errors.Join(err1, err2)            // 聚合多个错误(任一非 nil)
err := fmt.Errorf("%w and %w", e1, e2)    // 1.20 起 %w 可出现多次
```

它们实现的是 `Unwrap() []error`(注意是切片)。`errors.Is`/`As` 在 1.20 后会**对每个分支递归遍历**(深度优先),所以树里任一环匹配都算命中。`errors.Join` 的 `Error()` 把各错误用换行拼接。

> 典型场景:并发 fan-out 收集多个 goroutine 的错误(见 [`05-concurrent-errors/`](../05-concurrent-errors/README.md))、或资源清理时 `defer` 里把多个 Close 错误 Join 起来。

### 3.5 对照 Java cause 链

| | Java | Go |
|---|---|---|
| 包装 | `new XxxException("msg", cause)` | `fmt.Errorf("msg: %w", err)` |
| 取下一环 | `Throwable.getCause()` | `errors.Unwrap(err)` |
| 沿链找特定异常 | 手写循环 `getCause()` + `instanceof` | `errors.Is` / `errors.As` |
| 多 cause | `addSuppressed()`(抑制异常) | `errors.Join` / 多重 `%w`(`Unwrap() []error`) |
| 堆栈 | 自动带 stack trace | **默认不带**(00/04 章) |

---

## 4. 日常开发应用

### 包装惯例

```go
// ✅ 上抛时加一段动宾上下文,用 %w 保留链
if err != nil {
    return fmt.Errorf("load user %d: %w", id, err)
}
```

- 想让调用方还能 `Is`/`As` 底层 → 用 **`%w`**;想故意切断(跨边界、不暴露内部)→ 用 **`%v`** 或返回新错误(04 章)。
- 上下文短句:小写、动宾、无句尾标点、不写 "failed to"(`%w` 用 `: ` 拼接,读起来才是干净的操作链)。

### 检查:Is 配哨兵,As 配类型

```go
if errors.Is(err, sql.ErrNoRows) { return ErrNotFound }   // 哨兵 → Is
var ve *ValidationError
if errors.As(err, &ve) { return badRequest(ve.Field) }    // 类型 → As
```

### 自定义 `Is`/`As`(进阶)

错误类型可实现 `Is(target error) bool` 或 `As(any) bool` 改写匹配逻辑。例如让带错误码的错误,只要码相同就算 `Is` 命中:

```go
func (e *APIError) Is(target error) bool {
    t, ok := target.(*APIError)
    return ok && t.Code == e.Code
}
```

---

## 5. 生产&调优实战

- **`Is`/`As` 是线性遍历链**:链很长时有成本,但通常可忽略;别在超热路径里对超长链反复 `As`。
- **包装层数适度**:每层加一段**新**上下文才有价值;无脑 `fmt.Errorf("error: %w")` 只会堆噪音(04 章「不重复包装」)。
- **`%w` 是契约暴露**:`%w` 把底层错误纳入你的链 = 承诺它可被调用方 `Is`/`As`;跨包/对外边界要想清楚是否该暴露,不想就 `%v`(04 章)。
- **`As` 目标写错会 panic**:务必传 `&dst`(指向实现 error 的类型的指针)。code review / 测试覆盖到。
- **`go vet` 帮查 `%w` 误用**:比如对非 error 用 `%w`、`Errorf` 没有 `%w` 却期望可 unwrap 等。

---

## 6. 面试高频考点

- **`%w` 和 `%v` 区别?** `%w` 生成带 `Unwrap()` 的包装错误、保留链、可被 `Is`/`As` 穿透;`%v` 只取文字、链断在此处。选择 = 要不要把底层错误暴露进契约。
- **`errors.Is` 怎么工作?** 沿链循环:当前环 `== target`?→ 给当前环自定义 `Is()` 一次机会 → `Unwrap` 到下一环;到 nil 还没中就 false。
- **`Is` 和 `As` 区别?** `Is` 找「链上有没有等于某哨兵」(返 bool);`As` 找「链上有没有可转成某类型的环」并把它**赋给目标变量**(能取字段)。哨兵用 Is,类型用 As。
- **画出 `%w` 错误链 + Is 遍历过程**(白板题):画三环单链 + Unwrap 箭头 + Is 逐环比对。
- **一个错误能包多个吗?** 能,`errors.Join` / 多重 `%w`(1.20),实现 `Unwrap() []error`,链变树,`Is`/`As` 对每个分支递归。
- **`errors.As(err, target)` 的 target 要求?** 必须是指向「实现 error 的类型」或接口的**非 nil 指针**,否则 panic。
- **和 Java cause 链对应?** `%w`↔`new Ex(msg,cause)`、`Unwrap`↔`getCause`、`Is`/`As`↔沿链 `instanceof`、`Join`↔`addSuppressed`。

---

## 7. 一句话总结

> **`%w` 把错误串成一条 `Unwrap()` 链(可加上下文又不丢底层),`%v` 则切断链。** `errors.Is(err, 哨兵)` 沿链找「是不是某错误」(还会给每环一次自定义 `Is` 机会),`errors.As(err, &类型)` 沿链找「能不能转成某类型」并取出字段——**Is 配哨兵、As 配类型**,对应上一章的 sentinel/typed。多重包装(`errors.Join`/多 `%w`,1.20)让链变树、`Is`/`As` 递归遍历。本质就是 Java 的 cause 链(`getCause`),只是 Go 用 `%w`+`Is`/`As` 标准化,且默认不带堆栈。

← 上一章 [`01 三种风格`](../01-error-values/README.md) ｜ 下一章 → [`03 panic·recover·defer`](../03-panic-recover-defer/README.md):error 之外那套「异常」机制——defer 的求值/执行时机、recover 为什么常常没接住、到底何时才该 panic。｜ 回 [`error-handling` 索引](../README.md)
