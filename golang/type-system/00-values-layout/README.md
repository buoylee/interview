# 00 · 值、类型与内存布局

> 这是类型系统的地基。Go 默认是**值语义**:赋值、传参、返回都**拷贝一份**。理解这条,后面接口装值为什么会拷贝/逃逸、map 元素为什么不可寻址、`range` 为什么改不动原元素,才都串得起来。
>
> 桥接锚点:Java 把类型劈成两半——基本类型(`int`)是值、对象是引用;Python 一切皆引用。Go 反过来:**一切默认是值**,要共享才显式用指针(`*T`)。

---

## 1. 核心问题

```go
type Point struct{ X, Y int }
func move(p Point) { p.X = 100 }      // 改得动原来的吗?

func main() {
    a := Point{1, 2}
    b := a                            // b 是 a 的拷贝还是别名?
    move(a)                           // a.X 变了吗?
    fmt.Println(a.X)                  // 1 还是 100?
}
```

- 赋值 `b := a`、传参 `move(a)` 到底是**拷贝**还是**共享引用**?
- 那 slice/map 传进函数改了为什么**外面能看到**?它们不也是值吗?
- 哪些类型能用 `==` 比较,哪些一比就**编译报错**甚至 **panic**?

---

## 2. 直觉理解

### 默认值语义:赋值/传参/返回都拷贝

Go 里 `b := a`、`f(a)`、`return a` 一律**拷贝整个值**。上面那题:`move(a)` 拿到的是副本,`a.X` 仍是 **1**。要改原值就传指针:

```go
func move(p *Point) { p.X = 100 }     // 传 *Point,改的是原值
move(&a)                              // a.X 现在是 100
```

> 对照 Java:`move(point)` 传的是引用拷贝,函数内 `point.x = 100` **会**改到原对象(因为是同一个堆对象)。Go 传 `Point` 是**整个结构体拷贝**,改不到原值——这是 Java 程序员最容易栽的直觉差。

### 「引用类型」的真相:它们是**含指针的小header**

那为什么 slice/map 传进函数,里面改了外面看得到?因为 slice/map/chan 这些不是「整块数据」,而是一个**很小的 header,里面装着指向底层数据的指针**:

- `slice` = `{指针 ptr, 长度 len, 容量 cap}` 三个字;
- `map`/`chan` = 一个指向底层结构的指针;
- `string` = `{指针 ptr, 长度 len}` 两个字;
- `interface` = 两个字(下一章);
- 函数值、指针 = 一个指针。

传参时**拷贝的是这个 header**(很便宜),但 header 里的指针还指向**同一份底层数据**——所以通过它改元素,外面能看到。Go 没有「引用类型」这个语言概念,只有「**碰巧含指针的值类型**」。理解成「拷贝 header、共享底盘」最准。

```go
func fill(s []int) { s[0] = 99 }      // 改的是共享的底层数组 → 外面看得到
func grow(s []int) { s = append(s, 1) } // append 可能换底层数组 → 外面看不到!(s 是副本)
```

> `grow` 那行是经典坑:`append` 扩容会分配**新**底层数组,但 `s` 是 header 副本,重新指向新数组只影响副本。细节在 [`data-structures/` slice]。

---

## 3. 原理深入

### 3.1 零值可用(zero value)

Go 没有构造函数;每个类型有**确定的零值**,且语言哲学是**让零值直接可用**:

```go
var i int            // 0
var s string         // ""
var p *int           // nil
var sl []int         // nil,但能直接 append、len/range(见 05)
var m map[string]int // nil,能读不能写(见 05)
var mu sync.Mutex    // 零值就是已解锁、可用的锁,不用 New
var buf bytes.Buffer // 零值就能直接 Write
```

设计准则:**让类型的零值是有意义、可用的状态**(`sync.Mutex`、`bytes.Buffer` 是范本)。这条在 [`design/` 并发安全 API] 还会回来。

### 3.2 可比较性(comparability)——`==` 能不能用

`==` 不是所有类型都能用,规则要记牢(面试常考):

| 类型 | 可比较? | 说明 |
|---|---|---|
| 基本类型(数值/string/bool)、指针、channel | ✅ | 按值/按地址比 |
| **数组** | ✅(若元素可比较) | 逐元素比 |
| **struct** | ✅(若所有字段可比较) | 逐字段比 |
| interface | ✅ | 动态类型相同且值相等;**但若动态类型不可比较→运行时 panic** |
| **slice、map、func** | ❌ | 编译报错(只能和 `nil` 比) |

```go
[3]int{1,2,3} == [3]int{1,2,3}   // ✅ true,数组可比
struct{X int}{1} == struct{X int}{1} // ✅
[]int{1} == []int{2}             // ❌ 编译错误:slice 不可比较
var a any = []int{1}
a == a                           // ⚠️ panic: 比较的动态类型 []int 不可比较
```

推论:**含 slice/map 字段的 struct 也不可比较**;想当 map 的 key 必须全字段可比较。要比较内容用 `reflect.DeepEqual`(慢)或自己写。

### 3.3 值的内存:就地存放,struct 是连续字段

一个 `Point{1,2}` 在内存里就是**两个连续的 int**(16 字节),没有对象头、没有指针间接(对比 Java 对象有 mark word + klass 指针 + 字段)。这让 Go 的 struct **数组/切片是紧密排布的**(cache 友好),也是它比 Java 对象省内存的原因之一。字段顺序影响大小(内存对齐),细节在 [`data-structures/` struct 对齐]。

> 这也解释了「接口装值会逃逸」(下一章):一个 `Point` 值要塞进接口,得先有个**指针**指向它,于是这个值往往被搬到堆上。

---

## 4. 日常开发应用

- **小结构体传值即可**(几个字段,拷贝便宜、还免逃逸、对并发更安全);**大结构体或要改原值才传指针**(`*T`)。别无脑全用指针——值传递常更快更安全。
- **方法接收者的值/指针选择**是同一问题的延伸,见 [`02-method-sets/`](../02-method-sets/README.md)。
- **想让类型「开箱即用」**:设计成零值可用(像 `sync.Mutex`),少逼调用方调 `New`。
- **当 map key / 用 `==`**:确保类型可比较(别含 slice/map 字段)。
- `range` 遍历拿到的是**元素副本**:`for _, v := range s { v.X = 1 }` 改不动原元素,要改用 `s[i].X = 1` 或 `for i := range s`。

---

## 5. 生产&调优实战

- **值拷贝的成本**:大 struct 频繁传值/`range` 会有拷贝开销;热路径上的大对象考虑传指针或用索引遍历。但**小值传值通常比指针快**(免逃逸、免 GC 扫描、cache 友好)——别迷信指针。
- **接口装值的隐性逃逸**:把值塞进 `any`/接口常导致它逃逸到堆(下一章),热路径上是分配热点;`go build -gcflags=-m` 能看到逃逸,细节见 [`data-structures/` 逃逸分析]。
- **`reflect.DeepEqual` 慎用在热路径**:它走反射、慢且会把 unexported 也比进去;能用 `==` 或手写比较就别用它。
- **拷贝带锁的 struct 是 bug**:`sync.Mutex` 等不可拷贝,值传递一个含锁的 struct 会复制锁状态;`go vet` 的 `copylocks` 会报。

---

## 6. 面试高频考点

- **Go 是值传递还是引用传递?** **只有值传递**。赋值/传参/返回都拷贝。slice/map/chan 之所以「像引用」,是因为它们是含指针的 header,拷贝 header 但共享底层数据。
- **传 slice 进函数改元素外面看得到,为什么 append 看不到?** 改元素动的是共享底层数组;append 扩容换了新数组,但函数内的 slice 是 header 副本,重指向只影响副本。
- **哪些类型不能 `==`?** slice、map、func(只能和 nil 比);含这些字段的 struct 也不行。数组、全可比较字段的 struct 可以。interface 可比但动态类型不可比时 panic。
- **零值可用是什么?** 类型零值即有效状态,免构造函数。范例 `sync.Mutex`、`bytes.Buffer`。设计自己的类型也应尽量零值可用。
- **和 Java 的值/引用区别?** Java 基本类型值、对象引用;Go 一切默认值,要共享显式用指针。Java 传对象能改到原对象,Go 传 struct 改不到(是拷贝)。
- **range 能改原元素吗?** 不能,`v` 是副本;用 `s[i]` 或索引。

---

## 7. 一句话总结

> **Go 只有值语义:赋值/传参/返回一律拷贝,要共享才显式用指针。** 所谓「引用类型」(slice/map/chan/string/interface/func)其实是**含指针的小 header**——拷贝 header 便宜、但共享底层数据,所以改元素外面看得到、append 扩容却看不到。`==` 只对可比较类型可用(slice/map/func 不行,含它们的 struct 也不行;interface 动态类型不可比会 panic)。设计上追求**零值可用**(`sync.Mutex` 范本)。和 Java「基本类型值 + 对象引用」相反,Go 默认一切是值——这是 Java 程序员最该校准的直觉。

下一章 → [`01 接口底层`](../01-interface-internals/README.md):值是怎么塞进接口的?接口值是哪两个字、itab 方法表怎么实现动态派发、为什么装值会逃逸。｜ 回 [`type-system` 索引](../README.md)
