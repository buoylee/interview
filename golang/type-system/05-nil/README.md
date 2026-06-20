# 05 · nil 的多张面孔

> `nil` 在 Go 里不是一个统一的「空」——它对不同类型含义不同,行为也不同。最坑的是 **typed nil**:一个「装了 nil 指针的接口」**不等于 nil**。这章把所有 nil 的面孔收口,很多在前面章节(接口两个字、值语义、错误处理)埋过伏笔。
>
> 桥接锚点:Java 只有一个 `null`,`obj == null` 永远直白。Go 的 nil 因为「接口是两个字」「不同类型零值不同」而有多副面孔——这是 Java 程序员最意外的地方。

---

## 1. 核心问题

```go
func getError() error {
    var e *MyError = nil      // 一个 nil 的具体指针
    return e                  // 返回它
}
func main() {
    err := getError()
    if err != nil {           // 居然进来了!为什么?
        fmt.Println("got error:", err)   // 但 err 又"是" nil...
    }
}
```

- 明明返回的是 `nil`,为什么 `err != nil` 成立?(typed nil)
- `nil` 的 map 能读吗?能写吗?`nil` 的 slice 能 append 吗?
- `nil` 的 channel 收发会怎样?`nil` 指针为什么有时还能调方法?

---

## 2. 直觉理解

### typed nil:接口是两个字,只有「都空」才 == nil

回忆 [`01`](../01-interface-internals/README.md):接口值 = **(类型, 数据指针)** 两个字。`err == nil` 当且仅当**两个字都为空**。

`return e`(`e` 是 `*MyError` 类型的 nil)装进 `error` 接口时:

```
err = ( 类型=*MyError , 数据=nil )
        ↑ 类型字段非空!         ↑ 数据是 nil
```

类型字段填了 `*MyError`,所以接口**不等于 nil**,尽管它装的指针是 nil。这就是 typed nil。

### 不同类型的 nil,能力天差地别

| nil 的类型 | 读 | 写/操作 |
|---|---|---|
| nil **slice** | ✅ `len`/`range`/`append` 都行 | append 会分配,完全可用 |
| nil **map** | ✅ 读返回零值 | ❌ **写 panic** |
| nil **channel** | ⚠️ 收发**永久阻塞** | close → panic |
| nil **func** | — | 调用 → panic |
| nil **pointer** | — | 解引用字段 panic;但**调方法可能不 panic**(见下) |
| nil **interface** | 真正的「空」 | 调方法 panic |

记不住就记:**nil slice 最友好(随便用),nil map 能读不能写,nil channel 会卡死,nil func/指针解引用会炸**。

---

## 3. 原理深入

### 3.1 typed nil 的根因与正确写法

根因就是「接口两个字、类型字段非空」。**正确做法:成功路径直接 `return nil`,函数返回类型写 `error`(接口),不要返回具体指针类型再隐式转换**:

```go
// ❌ 容易制造 typed nil
func do() error {
    var e *MyError
    if bad { e = &MyError{} }
    return e            // bad=false 时返回 typed nil,调用方 err!=nil 误判
}

// ✅ 显式判断,成功返回真 nil
func do() error {
    if bad { return &MyError{} }
    return nil          // 真正的 nil 接口
}
```

> 这条在 [`error-handling/01`](../../error-handling/01-error-values/README.md) 作为「错误风格的坑」点过,这里是机制完整版。`go vet` 的部分检查和静态分析工具能发现某些 typed nil 返回。

### 3.2 nil slice vs 空 slice

```go
var a []int          // nil slice:ptr=nil, len=0, cap=0
b := []int{}         // 空 slice:ptr 指向某个零长数组, len=0, cap=0
a == nil             // true
b == nil             // false
len(a) == len(b)     // 都是 0
a = append(a, 1)     // ✅ nil slice 能 append(会分配底层数组)
```

两者用起来几乎一样(都能 `len`/`range`/`append`),**惯例优先用 `var a []int`(nil slice)** 作零值。区别只在 `== nil` 和 JSON 序列化(nil → `null`,空 → `[]`)。

### 3.3 nil map 能读不能写

```go
var m map[string]int     // nil map
_ = m["x"]               // ✅ 读 → 返回零值 0
len(m)                   // ✅ 0
for range m {}           // ✅ 空循环
m["x"] = 1               // ❌ panic: assignment to entry in nil map
```

所以 map 必须 `make` 或字面量初始化才能写。读安全是个常被利用的特性(可选 map 不必初始化)。

### 3.4 nil channel:select 里的妙用

```go
var ch chan int      // nil channel
<-ch                 // 永久阻塞
ch <- 1              // 永久阻塞
close(ch)            // panic
```

「永久阻塞」不是只有坏处:在 `select` 里**把某个 channel 置为 nil,可以动态「禁用」该分支**(nil 分支永不就绪),这是并发里的实用技巧(见 [`concurrency/05`](../../concurrency/05-channel-select/README.md))。

### 3.5 nil 指针居然能调方法

```go
type T struct{ x int }
func (t *T) Hello() string {
    if t == nil { return "nil receiver" }   // 方法里能判 t==nil
    return fmt.Sprint(t.x)
}
var p *T = nil
p.Hello()            // ✅ 返回 "nil receiver",不 panic!
```

为什么?**方法只是 `func Hello(t *T)`,接收者是个参数**(见 [`02`](../02-method-sets/README.md))。传一个 nil 指针进去完全合法,只要方法内部**不解引用** `t`(不访问 `t.x`)就不会 panic。所以 nil 指针能调方法,只是不能在方法里碰它的字段。这也让「nil 作为有效零值」的设计成为可能(如某些链表/树的空节点方法)。

---

## 4. 日常开发应用

- **成功就 `return nil`**,函数返回类型用接口(`error`),杜绝 typed nil。
- **slice 零值用 `var s []T`**(nil slice),直接 append;不必 `make` 除非要预分配 cap。
- **map 用前必 `make`/字面量**(要写的话);只读的可选 map 可以留 nil。
- **判空要分清**:判 slice 是否「无元素」用 `len(s)==0`(同时覆盖 nil 和空),别用 `s==nil`。
- **方法接收者可能为 nil 时**,在方法里先判 `if t == nil`,提供合理零值行为。

---

## 5. 生产&调优实战

- **typed nil 是经典线上 bug**:接口非 nil 但底层指针 nil,后续解引用又 panic,或错误判断把成功当失败。统一「返回接口 + 成功 return nil」根治。最常出现在:返回具体错误类型、把具体指针赋给接口、`interface{}` 包装。
- **nil map 写 panic**:从 JSON 反序列化/部分初始化拿到的 map 可能是 nil,写前确认已 make。
- **nil channel 永久阻塞 = goroutine 泄漏**:误用未初始化的 channel 会让 goroutine 卡死(NumGoroutine 涨),见 [`concurrency/04`](../../concurrency/04-goroutine/README.md)。但 select 里主动置 nil 禁用分支是合法技巧。
- **`len`/`cap`/`range` 对 nil slice/map 安全**,可大胆少写判空;但**写操作**和**channel 收发**对 nil 不安全。

---

## 6. 面试高频考点

- **typed nil 是什么/为什么 `err != nil`?** 接口是两个字(类型, 数据);返回一个具体类型的 nil 指针,类型字段非空 → 接口 != nil,尽管数据是 nil。根治:成功 `return nil`,函数返回接口类型。
- **nil map 能读能写吗?** 能读(返回零值)、`len`/`range` 安全;**写 panic**。
- **nil slice 能 append 吗?** 能,等价于空 slice 用;`var s []T` 是惯用零值。nil slice vs 空 slice 差别只在 `==nil` 和 JSON(`null` vs `[]`)。
- **nil channel 收发?** 永久阻塞;close panic。select 里置 nil 可动态禁用分支。
- **nil 指针能调方法吗?** 能,只要方法不解引用接收者(接收者是参数,传 nil 合法)。
- **怎么判 slice「空」?** `len(s)==0`(覆盖 nil 和空),别用 `s==nil`。
- **和 Java null 区别?** Java 只有一个 null、判断直白;Go 因「接口两个字 + 各类型零值不同」有多副面孔,typed nil 尤其反直觉。

---

## 7. 一句话总结

> **Go 的 nil 有多张面孔。最坑的 typed nil:接口是两个字(类型, 数据),把具体类型的 nil 指针装进接口,类型字段非空 → 接口 `!= nil`**——根治办法是成功路径 `return nil`、函数返回接口类型。其余各 nil:**nil slice 最友好**(`len`/`range`/`append` 都行,是惯用零值);**nil map 能读不能写**(写 panic);**nil channel 收发永久阻塞**(close panic,但 select 里置 nil 可禁用分支);**nil 指针能调方法**(接收者是参数,只要不解引用就不 panic)。判 slice 空用 `len(s)==0`。和 Java 单一 null 相比,这是 Go 类型系统(接口两字 + 零值各异)最该校准的直觉。

← 上一章 [`04 嵌入与组合`](../04-embedding/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):iface/eface、方法集、嵌入 vs 继承、typed nil、类型断言速查。｜ 回 [`type-system` 索引](../README.md)
