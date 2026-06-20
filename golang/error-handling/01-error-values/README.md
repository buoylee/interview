# 01 · error 接口与三种风格：sentinel / typed / opaque

> 00 章说「error 是普通接口值」。既然是值,「怎么造一个错误、怎么让调用方识别它」就有固定的几种风格。资深面试常考:**你会用哪种风格、为什么**。本章把三种风格(哨兵 / 类型 / 不透明)讲透,04 章再谈在 API 边界怎么选。
>
> 桥接锚点:Java 靠**异常类的继承层级**(`catch (FileNotFoundException e)`)区分错误;Go 没有异常类层级,只能靠这三种「错误是值」的风格让调用方识别。

---

## 1. 核心问题

`func Get(id int) (*User, error)` 失败了。调用方想知道「是**没找到**(该返回 404)还是**数据库挂了**(该返回 500)」。可 `error` 只有一个 `Error() string`——总不能去 `strings.Contains(err.Error(), "not found")` 吧?那么:

- 我**造**一个错误有哪几种方式?`errors.New` / `fmt.Errorf` / 自定义类型,分别什么场景?
- 调用方怎么**可靠地识别**错误的种类,而不是去 match 字符串?
- 这几种风格各自把调用方**耦合**到什么程度?

---

## 2. 直觉理解

三种风格,按「调用方能拿到多少信息 / 被耦合多深」排:

| 风格 | 长什么样 | 调用方怎么认 | 给调用方的信息 |
|---|---|---|---|
| **sentinel 哨兵** | `var ErrNotFound = errors.New("not found")` | `errors.Is(err, ErrNotFound)` | 只有「是不是这一类」 |
| **typed 类型** | `type ValidationError struct{ Field string }` | `errors.As(err, &ve)` 取字段 | 「是这类」+ **结构化数据** |
| **opaque 不透明** | 只返回一个普通 error,**不导出**任何可匹配的东西 | 只能 `err != nil`,或断言**行为接口** | 「成功 or 失败」,最多一个能力问询 |

- **哨兵**像一个全局常量路标:大家都 `Is` 它。简单,但这个变量成了你的公共契约。
- **类型**像一个带字段的异常对象:`As` 出来能读 `.Field`/`.Code`/`.RetryAfter`。信息最足,耦合也最深。
- **不透明**是默认姿态:大多数错误调用方根本不需要区分种类,只要知道「失败了、带上下文上抛或记日志」即可——这种就别画蛇添足地导出哨兵/类型。

口诀:**默认 opaque;需要分类就 sentinel;需要带数据就 typed。** 导出的哨兵/类型越少,你的 API 契约越小越好维护(04 章详谈)。

---

## 3. 原理深入

### 3.1 error 接口与最朴素的实现

```go
type error interface { Error() string }
```

`errors.New` 返回的就是一个最小实现——一个**指针**:

```go
// 标准库等价实现
func New(text string) error { return &errorString{text} }
type errorString struct{ s string }
func (e *errorString) Error() string { return e.s }
```

⚠️ 注意是 `*errorString`(指针接收者)。这是哨兵能用 `==` 比较的关键——见下。

### 3.2 sentinel:为什么 `==` 能认出它

```go
var ErrNotFound = errors.New("not found")   // 包级变量,只 new 一次

func Get(id int) error { return ErrNotFound }   // 返回的就是这个变量本身

// 调用方
if errors.Is(err, ErrNotFound) { ... }   // 现代写法
if err == ErrNotFound { ... }            // 老写法(无包装时也成立)
```

`errors.New` 每次返回**新指针**,所以两个 `errors.New("x")` **永不相等**(指针不同)。哨兵之所以能被 `==`/`Is` 认出,是因为大家比的是**同一个包级变量的指针**,不是比文字。这也是为什么哨兵必须是**导出的包级变量**,而不是每次现造。

> 对照 Java:哨兵 ≈ 一个 `public static final` 的「标记异常实例」或一个 enum 错误码。但 Java 更常用**异常类型**区分,Go 哨兵是更轻的手段。

标准库哨兵例子:`io.EOF`、`sql.ErrNoRows`、`os.ErrNotExist`、`context.Canceled`。

### 3.3 typed:携带数据的错误,用 `As` 取字段

```go
type ValidationError struct {
    Field string
    Msg   string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s: %s", e.Field, e.Msg)
}

func validate(u *User) error {
    if u.Name == "" {
        return &ValidationError{Field: "name", Msg: "required"}
    }
    return nil
}

// 调用方:不是 match 字符串,而是 As 出类型读字段
var ve *ValidationError
if errors.As(err, &ve) {
    log.Printf("字段 %s 出错", ve.Field)   // 拿到结构化数据
}
```

用类型当错误时,**接收者一般用指针**(`*ValidationError`),`As` 的目标也写 `&ve`(即 `**ValidationError`)。

> 对照 Java:typed 错误 ≈ 自定义异常类带字段 `class ValidationException { String field; }`,`catch` 后读 `e.getField()`。Go 用 `errors.As` 取代 `catch (Type e)`。

### 3.4 opaque + 行为接口:不暴露类型,只问「能力」

不想让调用方耦合到你的具体类型,但又想让它判断「能不能重试」,就暴露**行为接口**而非类型:

```go
// 你的错误私有,但实现一个公开的行为
type temporaryError struct{ err error }
func (e *temporaryError) Error() string   { return e.err.Error() }
func (e *temporaryError) Temporary() bool  { return true }

// 调用方断言"行为",完全不知道你的具体类型(耦合最低)
var t interface{ Temporary() bool }
if errors.As(err, &t) && t.Temporary() { retry() }
```

标准库范例:`net.Error` 接口的 `Timeout() bool`。这就是 04 章「断言行为而非类型」的来源。

### 3.5 经典坑:typed nil ——返回「装了 nil 指针的接口」

```go
func do() error {
    var e *ValidationError = nil   // 一个 nil 的具体指针
    return e                       // ❌ 装进 error 接口后,接口 != nil !!
}
if do() != nil { /* 居然进来了 */ }   // 因为接口的"类型"字段非空(*ValidationError)
```

接口值 = (类型, 值) 两个字;只有**两个都为空**接口才 `== nil`。返回一个具体类型的 nil 指针,类型字段已经填了 `*ValidationError`,所以接口非 nil。**正确做法:成功就直接 `return nil`**,别返回一个 typed nil。机制全貌见 [`type-system/` 的「nil 的多张面孔」]。

---

## 4. 日常开发应用

- **绝大多数错误用 opaque**:`return fmt.Errorf("load config: %w", err)` 上抛即可,别为每个错误造哨兵/类型。
- **需要让调用方分类处理**→ 定义**少量**包级哨兵(`ErrNotFound`/`ErrConflict`),文档写明「调用方可 `Is` 这些」。
- **错误要带结构化数据**(字段名、错误码、重试间隔)→ 用 typed,调用方 `As` 出来读,**别让人去 parse `Error()` 字符串**。
- **不想被耦合具体类型**→ 暴露行为接口(`Temporary()`/`NotFound()`)。
- 哨兵命名 `ErrXxx`;错误类型命名 `XxxError`;`Error()` 文字小写、不带句尾标点(方便被 `%w` 拼接,见 02)。

---

## 5. 生产&调优实战

- **导出的哨兵/类型 = 长期契约**:一旦发布,调用方就 `Is`/`As` 它了,删改即破坏兼容(00 章)。所以**能不导出就不导出**,公共错误面尽量小。
- **哨兵的耦合代价**:`%w` 把 `sql.ErrNoRows` 透传出去,调用方 `Is(err, sql.ErrNoRows)`,你就再也换不了 `database/sql`——这正是 04 章要在边界**翻译**掉它的原因。
- **typed nil 在生产是隐藏 bug**:函数声明返回具体错误类型(`func() *MyErr`)再赋给 error,最容易踩。**统一让函数返回 `error` 而非具体指针类型**,从源头杜绝。
- **别用字符串匹配认错误**:`strings.Contains(err.Error(), "not found")` 一旦上游改文案就崩,且无法穿过包装层。永远用 `Is`/`As`。

---

## 6. 面试高频考点

- **Go 错误有哪几种风格?怎么选?** sentinel(`Is` 认类别)/ typed(`As` 取数据)/ opaque(只 `err!=nil` 或断言行为)。默认 opaque;要分类用哨兵;要带数据用类型;要低耦合用行为接口。导出越少越好。
- **哨兵为什么能用 `==`/`Is` 认出?** 它是**同一个包级变量的指针**;`errors.New` 每次返回新指针,所以比的是变量身份不是文字。
- **为什么不能用 `err.Error()` 字符串判断错误种类?** 文案会变、无法穿包装层、是实现细节不是契约。用 `Is`/`As`。
- **typed nil 坑是什么?** 返回一个具体类型的 nil 指针赋给 error 接口,接口非 nil(类型字段已填)。成功要直接 `return nil`,函数返回类型用 `error`。
- **和 Java 异常类层级比?** Java 靠异常类继承 + `catch (SubType e)` 区分;Go 无异常类,用哨兵/类型/行为接口三种「值」风格 + `Is`/`As` 区分。
- **`errors.New("x") == errors.New("x")`?** false——两个不同指针。哨兵必须共享同一变量。

---

## 7. 一句话总结

> **错误是值,识别错误有三种风格:sentinel(哨兵,`errors.Is` 认类别,靠共享同一包级变量指针)、typed(错误类型,`errors.As` 取结构化字段)、opaque(不透明,只判 `err!=nil` 或断言行为接口)。** 选择准则:默认 opaque,要分类用哨兵,要带数据用类型,要低耦合用行为接口;**导出的哨兵/类型越少,API 契约越小越好维护**。永远用 `Is`/`As` 而非字符串匹配认错误。坑:返回具体类型的 nil 指针会得到非 nil 的 error 接口(typed nil),成功一律 `return nil`。

← 上一章 [`00 错误哲学`](../00-philosophy/README.md) ｜ 下一章 → [`02 包装与检查`](../02-wrapping/README.md):错误要一层层上抛又不丢底层,靠 `%w` 串成错误链,`errors.Is`/`As` 穿过包装层识别。｜ 回 [`error-handling` 索引](../README.md)
