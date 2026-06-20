# 00 · 泛型基础:type parameters 与 constraints

> 泛型(Go 1.18)解决一个老问题:同一段逻辑要对很多类型成立,以前只能 `interface{}` + 类型断言(丢类型安全 + 装箱)或代码生成(啰嗦)。泛型让你**编译期参数化类型**,既通用又类型安全。本章讲怎么写;`01` 讲底层,`02` 讲何时用。
>
> 桥接锚点:Java `<T extends Comparable<T>>` ←→ Go `[T constraints.Ordered]`;但 Java 约束靠类继承层级,Go 约束是**接口 + 类型集(type set)**,且不擦除、不装箱值类型。

---

## 1. 核心问题

```go
// 泛型前:要么丢类型安全……
func Max(a, b interface{}) interface{} { ... }   // 调用方还得断言,装箱
// ……要么每个类型写一遍 MaxInt/MaxFloat/MaxString

// 泛型后:
func Max[T cmp.Ordered](a, b T) T {              // 一份代码,任意可排序类型,类型安全
    if a > b { return a }
    return b
}
Max(3, 5)            // T 推断为 int
Max("a", "b")        // T 推断为 string
```

- `[T cmp.Ordered]` 这个方括号在说什么?`T` 是什么?
- **约束(constraint)** 怎么写?`any`/`comparable`/`~int | ~float64` 都是什么?
- 调用时为什么不用写 `Max[int](3,5)`?(类型推断)

---

## 2. 直觉理解

### type parameter = 「类型也能当参数」

普通函数参数是「值」;泛型多了一类参数是「**类型**」,写在 `[]` 里:

```go
func Map[T, U any](s []T, f func(T) U) []U {     // T、U 是类型参数
    r := make([]U, len(s))
    for i, v := range s { r[i] = f(v) }
    return r
}
```

`T any` 读作「T 是任意类型」。调用时编译器把 `T`/`U` 替换成具体类型,生成类型安全的代码。

### constraint = 「这个类型参数能做什么」

类型参数不能为所欲为——你只能对它做「约束允许的操作」。约束**就是一个接口**,规定 T 必须满足什么:

- `any`(= `interface{}`):啥都行,但你也只能做「对任意类型都成立的事」(赋值、传递、放进容器),**不能 `+`、不能 `<`**。
- `comparable`:T 支持 `==`/`!=`(能当 map key、能比较);内置约束。
- **自定义约束 = 接口 + 类型集**:`interface{ ~int | ~int64 | ~float64 }` 说「T 的底层类型必须是这几个之一」——这样才能在泛型体里用 `<`、`+`。

口诀:**约束既限制 T,也赋予 T 能力**——你能对 T 做的,正是约束声明的那些。

---

## 3. 原理深入

### 3.1 约束里的类型集(type set)与 `~`

Go 1.18 给接口加了新能力:除了方法,还能写**类型元素**,定义一个「类型集合」:

```go
type Number interface {
    ~int | ~int8 | ~int64 | ~float32 | ~float64    // 联合:底层类型是这些之一
}
func Sum[T Number](xs []T) T { var s T; for _, x := range xs { s += x }; return s }
```

- `|` 是**联合**(union):T 可以是其中任一。
- `~int` 的 `~` 是**近似(approximation)**:不仅 `int`,还包括**底层类型是 int 的自定义类型**(如 `type Celsius int` 也满足 `~int`)。不写 `~`(只写 `int`)就只匹配 `int` 本身,不含 `Celsius`。

> 因为约束声明了 `~int|~float64`,编译器知道 T 支持 `+`/`<`,泛型体里才能用这些运算符。这是 Go 泛型「能对类型参数用运算符」的来源(Java 泛型做不到,只能调方法)。

### 3.2 约束也能要求方法

```go
type Stringer interface{ String() string }
func Join[T Stringer](xs []T) string { ... }    // T 必须有 String() 方法
```

约束可以**混合**方法和类型集。要方法时,本质和接口很像——这也引出 `02` 的取舍:**只调方法的话,用普通接口参数往往更合适**。

### 3.3 类型推断

```go
Max(3, 5)            // 不用写 Max[int],编译器从实参 3,5 推断 T=int
Map([]int{1,2}, strconv.Itoa)   // 推断 T=int, U=string
```

编译器能从实参类型推断类型参数,大多数情况不用显式写 `[T]`。推断不出来时(如返回类型才用到的 T)才需显式指定。

### 3.4 限制:方法不能有类型参数

```go
type Box[T any] struct{ v T }       // ✅ 类型可以有类型参数
func (b Box[T]) Get() T { return b.v }   // ✅ 方法可用所属类型的 T

func (b Box[T]) Map[U any](f func(T) U) U  // ❌ 方法不能自己引入新类型参数 U
```

**方法不能有自己的类型参数**(只能用所属类型的)。这是 Go 的刻意限制(和接口动态派发的兼容性有关)。要参数化就写成泛型**函数**。

### 3.5 标准库的泛型(1.21)

```go
import ("slices"; "maps"; "cmp")
slices.Sort(s)                    // 任意 cmp.Ordered 切片排序
slices.Contains(s, x)
slices.Index(s, x)
maps.Keys(m)                      // (1.21 返回 iterator,1.23 起配合 range)
cmp.Ordered                       // 标准库的"可排序"约束(取代 x/exp/constraints)
min(a, b); max(a, b); clear(m)    // 1.21 内置泛型函数
```

`constraints` 包(`Ordered`/`Integer`/`Float`)在 `golang.org/x/exp`,1.21 起常用的 `cmp.Ordered` 进了标准库。

---

## 4. 日常开发应用

- **通用容器/算法用泛型**:`Map`/`Filter`/`Reduce`、栈/队列/集合、`slices`/`maps` 工具——既通用又类型安全、无装箱。
- **约束优先用标准库**:`any`、`comparable`、`cmp.Ordered`,够用就别自造。
- **要运算符(`+`/`<`)就用类型集约束**(带 `~` 以覆盖自定义底层类型)。
- **类型推断能省则省**,只在推不出来时显式 `f[T](...)`。
- **要参数化的「方法」?改写成泛型函数**(方法不能带自己的类型参数)。

---

## 5. 生产&调优实战

- **泛型替代 `interface{}` 省装箱**:`[]any` 存值会逃逸装箱(见 [`data-structures/03`](../../data-structures/03-escape-analysis/README.md)),泛型 `[]T` 直接存值类型、无装箱——容器场景能降分配。
- **但泛型不总是更快**:泛型体通过**字典**间接调用类型参数的方法,可能比单态化/具体类型慢(细节 [`01`](../01-implementation/README.md))。性能敏感处要 benchmark,别假设泛型必快。
- **别过度泛型化**:约束写得花、类型参数一大堆会严重伤可读性。能用具体类型或简单接口解决就别上泛型(`02` 的判据)。
- **编译期错误更友好**:约束不满足在编译期报错(如对 `any` 的 T 用 `<`),比运行期断言失败安全。

---

## 6. 面试高频考点

- **泛型解决什么问题?** 同一逻辑对多类型成立,又要编译期类型安全 + 避免 `interface{}` 装箱/断言。
- **constraint 是什么?** 就是接口——既限制类型参数、又赋予它能力(只能做约束声明的操作)。`any`(任意)、`comparable`(可 ==)、类型集(可用运算符)。
- **`~int` 的 `~` 是什么?** 近似元素:匹配底层类型是 int 的所有类型(含 `type Celsius int`),不只 `int` 本身。
- **类型集/union 干嘛?** 让约束声明「T 是这几个底层类型之一」,从而泛型体能用 `+`/`<` 等运算符。
- **方法能有类型参数吗?** 不能(只能用所属类型的);要参数化用泛型函数。
- **和 Java 泛型区别?** Java 约束靠类继承(`<T extends X>`)+ 擦除 + 装箱、不能对 T 用运算符;Go 约束是接口+类型集、不擦除不装箱值类型、能用运算符。
- **类型推断?** 编译器从实参推类型参数,多数不用显式写 `[T]`。

---

## 7. 一句话总结

> **泛型 = 把「类型」也当参数(`func F[T Constraint](...)`),编译期参数化、既通用又类型安全、避免 `interface{}` 装箱。** 约束(constraint)就是接口,既**限制** T 又**赋予** T 能力——`any`(任意)、`comparable`(可 `==`)、**类型集**(`~int | ~float64`,`~` 匹配底层类型、`|` 是联合,声明后泛型体才能用 `+`/`<` 运算符)。类型推断让多数调用不用写 `[T]`;**方法不能有自己的类型参数**(用泛型函数)。和 Java 不同:Go 不擦除、不装箱值类型、能对类型参数用运算符。标准库 `slices`/`maps`/`cmp` + `min`/`max`/`clear`(1.21)开箱即用。

下一章 → [`01 底层实现`](../01-implementation/README.md):同一个泛型函数对 int、string、各种指针,编译器到底生成几份代码?GCShape stenciling + 字典是什么、为什么泛型有时反而更慢。｜ 回 [`generics` 索引](../README.md)
