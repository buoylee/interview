# 03 · 类型断言与 type switch

> 值装进接口后,怎么安全地取回具体类型、或判断它到底是什么?这就是类型断言 `x.(T)` 和 type switch。底层就是上一章 itab/`_type` 的比对。`errors.As`(错误那 track)本质也是沿链做接口断言。
>
> 桥接锚点:`x.(T)` ≈ Java 的 `(T) x` 强转 + `instanceof`;type switch ≈ `if (x instanceof A) ... else if (x instanceof B)`。但 Go 的 comma-ok 形式让你**不 panic 地试探**。

---

## 1. 核心问题

```go
var i any = "hello"
s := i.(string)        // 取回 string
n := i.(int)           // ❌ panic: interface conversion: interface {} is string, not int
n, ok := i.(int)       // ok=false,n=0,不 panic —— 区别在哪?
```

- `x.(T)` 两种写法(单返回值 vs comma-ok)有什么本质区别?何时 panic?
- 断言成**接口类型** `x.(SomeInterface)` 和断言成**具体类型** `x.(int)`,底层判断方式一样吗?
- type switch 怎么写、底层怎么高效分发?

---

## 2. 直觉理解

### 两种形式:会 panic 的 vs 安全试探的

```go
s := i.(string)         // 单返回值:断言失败直接 panic
s, ok := i.(string)     // comma-ok:失败时 ok=false、s 取零值,不 panic
```

铁律:**对来源不确定的接口值,永远用 comma-ok**;只有「我百分百确定它就是这个类型,错了就是 bug」才用单返回值(失败 panic 也合理)。

### 断言在问什么

- `x.(具体类型)`:问「接口里装的动态类型**正好是** `T` 吗?」——比 `_type` 是否相等。
- `x.(接口类型)`:问「接口里的动态类型**实现了** `I` 吗?」——查它有没有 `I` 要求的方法(能不能造出 itab)。

### type switch:一次比多个

```go
switch v := i.(type) {       // 注意是 i.(type),只能用在 switch 里
case string:
    fmt.Println("str", v)    // 这个分支里 v 是 string
case int, int64:
    fmt.Println("int", v)    // 多类型分支里 v 还是 any(原接口类型)
case io.Reader:
    v.Read(...)              // 也能 case 接口
default:
    fmt.Println("other")
}
```

---

## 3. 原理深入

### 3.1 断言成具体类型 = 比 `_type` 指针

`i.(int)` 在运行时:取出接口的类型字段(eface 的 `_type` / iface 的 `itab._type`),和目标类型 `int` 的 `_type` **比指针是否相等**。相等 → 成功,把 data 当 `int` 取出;不等 → comma-ok 给 `false`,单值形式 panic。

> 因为类型描述符全局唯一,比较就是**一次指针比较**,极快。

### 3.2 断言成接口类型 = 查/建 itab

`i.(io.Reader)`:要判断 `i` 的动态类型有没有实现 `io.Reader`。运行时查「(io.Reader, 动态类型)」的 itab:

- 已缓存且 `fun[0] != 0` → 实现了,成功,返回带新 itab 的接口值;
- 没实现(方法缺)→ 标记失败(`fun[0] == 0`),comma-ok 给 false。

所以**断言成接口比断言成具体类型略贵**(可能要查 itab 表 / 算方法集),但仍很快。

### 3.3 type switch 的底层

type switch 本质是一串类型比较,但编译器会优化:

- 对具体类型分支,比 `_type` 指针;
- 对接口分支,查 itab;
- 多分支时常用**类型 hash**(`itab.hash`/`_type.hash`)先快速分桶,再精确比对,避免线性比 N 次。

`v := i.(type)` 里的 `v`:在**单类型 case** 里是那个具体类型;在 **多类型 case / default** 里仍是原接口类型(`any`)。

### 3.4 和 `errors.As` 的关系

`errors.As(err, &target)` 就是**沿错误链对每一环做类型断言**(断言成 `target` 的类型),命中就赋值。理解了本章的断言,`errors.As` 的机制就是它的链式版(见 [`error-handling/02`](../../error-handling/02-wrapping/README.md))。

---

## 4. 日常开发应用

- **来源不确定一律 comma-ok**,别让断言 panic 掀翻流程:
  ```go
  if s, ok := v.(fmt.Stringer); ok { return s.String() }
  ```
- **type switch 做多态分发**:处理 `any`/AST 节点/事件类型时最常用。
- **断言接口而非具体类型**,降低耦合:`v.(io.Closer)` 比 `v.(*os.File)` 更通用(呼应 `error-handling/04` 断言行为而非类型)。
- **优先用泛型替代「`any` + 断言」**:能在编译期约束类型时,泛型更安全(见 generics track);断言是运行时手段,留给真异构场景。

---

## 5. 生产&调优实战

- **单值断言 panic 是线上事故源**:`v.(T)` 对外部/反序列化来的 `any` 直接断言,数据一变就 panic。**comma-ok + 兜底**。
- **断言不是免费的**:具体类型断言≈一次指针比较(便宜);接口断言可能查 itab(略贵)。超热路径上对海量元素反复断言,考虑结构化设计(泛型/具体类型)绕开。
- **type switch 顺序与命中率**:大多数场景编译器已优化为 hash 分发,不必手动按频率排;但语义上**接口 case 会匹配多个动态类型**,放前面可能「抢走」本想进具体分支的值——注意 case 顺序的语义。
- **`any` 满天飞是坏味道**:大量类型断言往往意味着该用泛型或重新设计接口。

---

## 6. 面试高频考点

- **`x.(T)` 两种形式区别?** 单返回值失败 **panic**;comma-ok(`v, ok := x.(T)`)失败 `ok=false`、`v` 零值、不 panic。不确定来源用 comma-ok。
- **断言具体类型 vs 接口类型,底层差异?** 具体类型:比 `_type` 指针是否相等(一次指针比较);接口类型:查/建 itab 看动态类型是否实现该接口(略贵)。
- **type switch 怎么高效分发?** 编译器用类型 hash 分桶 + 精确比对,避免线性 N 次比较;`v` 在单类型 case 是具体类型,多类型 case 是原接口类型。
- **断言失败一定 panic 吗?** 不一定——comma-ok 不 panic。
- **和 `errors.As` 关系?** `As` = 沿错误链逐环做类型断言并赋值。
- **和 Java 比?** `x.(T)`≈`(T)x`+`instanceof`;type switch≈`instanceof` 链;但 comma-ok 提供「安全试探不抛异常」,Java 要先 `instanceof` 再强转。

---

## 7. 一句话总结

> **类型断言 `x.(T)` 把值从接口里取回:单返回值失败 panic,comma-ok(`v,ok:=x.(T)`)失败给零值+false 不 panic——来源不确定一律用 comma-ok。** 底层:断言**具体类型**是比 `_type` 指针(一次指针比较,极快);断言**接口类型**是查/建 itab 看是否实现(略贵)。type switch 是其多路版,编译器用类型 hash 分桶高效分发。优先断言**接口/行为**而非具体类型以降耦合,能用泛型就别用「`any`+断言」。`errors.As` 就是它的错误链式版本。

← 上一章 [`02 方法集与接收者`](../02-method-sets/README.md) ｜ 下一章 → [`04 嵌入与组合`](../04-embedding/README.md):Go 没有继承,靠「嵌入」复用——方法怎么提升、它和 Java 继承的本质区别(没有虚函数重写)。｜ 回 [`type-system` 索引](../README.md)
