# `%w` 错误链与 `errors.Is` / `errors.As` 怎么工作

## 一句话回答

`fmt.Errorf("ctx: %w", err)` 里的 **`%w`** 生成一个带 `Unwrap() error` 方法的包装错误,把错误串成一条**链**(可加上下文又不丢底层);`%v` 则不生成 `Unwrap`、链断在此处。**`errors.Is(err, 哨兵)`** 沿链逐环找「是不是某个错误」(返 bool),**`errors.As(err, &类型)`** 沿链逐环找「能不能转成某类型」并把那一环**赋给目标变量**(可取字段)。一句话:**Is 配哨兵,As 配类型**——对应 sentinel / typed 两种风格。

## 错误链长什么样

```
fmt.Errorf("handle: %w", ...) ─Unwrap()→ fmt.Errorf("load: %w", ...) ─Unwrap()→ sql.ErrNoRows ─→ nil
```

`Error()` 打印是拼接的:`"handle: load: sql: no rows in result set"`。`Unwrap() error` 方法就是「链」的本体。

## `errors.Is` 算法(能默写加分)

```go
for {
    if err == target { return true }                         // ① 当前环 == target?
    if x, ok := err.(interface{ Is(error) bool }); ok && x.Is(target) { return true }  // ② 自定义 Is()
    if err = errors.Unwrap(err); err == nil { return false } // ③ Unwrap 下一环;到底没中
}
```

第②步让一个错误能声明「我算某一类」(如各种底层错误都认 `os.ErrNotExist`)。

## `errors.As` 要点

```go
var pe *fs.PathError
if errors.As(err, &pe) { use(pe.Path) }    // 沿链找第一个可赋给 *fs.PathError 的环,取字段
```

⚠️ 第二参必须是**指向「实现 error 的类型/接口」的非 nil 指针**(这里 `**fs.PathError`),否则 **panic**。

## 多重包装(Go 1.20+)

`errors.Join(e1, e2)` 或 `fmt.Errorf("%w and %w", e1, e2)` → 实现 `Unwrap() []error`,链变**树**,`Is`/`As` 对每个分支**递归**遍历。

## `%w` vs `%v` 是契约决策

- `%w`:把底层错误纳入你的链 = **承诺**调用方可 `Is`/`As` 到它(暴露内部进契约)。
- `%v`:故意切断链 = 跨抽象/信任边界**翻译**、不泄漏内部耦合。详见 [`04 错误设计`](../04-error-design/README.md)。

## 对照 Java cause 链

`%w`↔`new Ex(msg, cause)`、`Unwrap`↔`getCause()`、`Is`/`As`↔沿 cause 链 `instanceof`、`Join`↔`addSuppressed`。区别:Go 错误默认**不带堆栈**。

## 证据链接

- 正文:[`02 包装与检查`](../02-wrapping/README.md);风格背景 [`01`](../01-error-values/README.md)

## 易追问的延伸

- **为什么不能 `strings.Contains(err.Error(), "not found")`?** 文案会变、穿不过包装层、是实现细节;用 `Is`/`As`。
- **自定义 `Is`/`As` 方法干嘛?** 改写匹配逻辑,比如「错误码相同就算 `Is` 命中」。
- **链很长有性能问题吗?** `Is`/`As` 是线性遍历,通常可忽略;别在超热路径对超长链狂 `As`。
