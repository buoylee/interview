# 01 · 接口底层:iface / eface / itab 与动态派发

> 这是本 track 的核心。「接口是两个字、靠 itab 函数表动态派发」——能在白板画出来,是资深信号。Go 接口和 Java 的最大差异:**隐式实现**(不写 `implements`)+ **结构是两个字**(不是对象头里的 klass 指针)。
>
> 桥接锚点:Java 接口靠对象头的 klass 指针 + 虚方法表(vtable)派发,且必须显式 `implements`;Go 接口值**自带** itab(类型 + 方法表),实现是隐式的(编译期检查的鸭子类型)。

---

## 1. 核心问题

```go
type Stringer interface{ String() string }
type User struct{ Name string }
func (u User) String() string { return u.Name }

var s Stringer = User{"alice"}    // 这一步在内存里发生了什么?
fmt.Println(s.String())           // s.String() 怎么找到 User.String 的?
```

- `s` 这个接口值在内存里**长什么样**?装了什么?
- `User` 没写 `implements Stringer`,凭什么能赋给它?编译器怎么检查?
- `s.String()` 是怎么**动态派发**到 `User.String` 的?有运行时开销吗?
- 把 `User{}` 装进接口,这个值放哪了?为什么常说「装接口会逃逸」?

---

## 2. 直觉理解

### 接口值 = 两个字:(类型信息, 数据指针)

一个接口值在内存里永远是**两个指针宽的字**:

```
┌──────────────┬──────────────┐
│  类型信息     │  数据指针      │
│ (itab / _type)│ (data)       │
└──────────────┴──────────────┘
```

- **第二个字 data**:指向真正的值(`User{"alice"}` 那份数据)。
- **第一个字**:看是哪种接口,分两种——
  - **空接口 `interface{}`/`any`** → 存 `*_type`(纯类型描述符),这种接口值叫 **eface**;
  - **非空接口**(带方法,如 `Stringer`)→ 存 `*itab`(类型描述符 + **方法函数表**),这种叫 **iface**。

一句话:**eface 记「是什么类型」,iface 还多记「这些方法的函数地址」**(因为非空接口要能调方法)。

### 动态派发 = 去 itab 的函数表里查地址再调

`s.String()` 不是直接调 `User.String`,而是:**从 itab 里取出 `String` 对应的函数指针,以 data 作接收者调用它**。这就是动态派发——和 Java vtable 同理,只是表挂在接口值的 itab 上,不是对象头里。

### 隐式实现 = 编译期帮你查「方法齐不齐」

`User` 不写 `implements`。编译器在 `var s Stringer = User{}` 这一刻检查:`User` 的方法集**是否包含** `Stringer` 要求的所有方法(这里 `String()`)。齐了就编译通过、生成 itab;缺一个就编译报错。所以 Go 接口是「**编译期检查的鸭子类型**」——像 Python 鸭子类型那样隐式,但错误在编译期就抓出来。

---

## 3. 原理深入

### 3.1 eface 与 iface 的结构(白板能画)

```go
// 空接口 interface{} / any —— 运行时等价
type eface struct {
    _type *_type           // 类型描述符:大小、对齐、kind、哈希、相等函数等
    data  unsafe.Pointer   // 指向实际数据
}

// 非空接口(带方法) —— 运行时等价
type iface struct {
    tab  *itab             // 含类型 + 方法表
    data unsafe.Pointer    // 指向实际数据
}
```

### 3.2 itab:接口与具体类型的「适配器 + 方法表」

```go
type itab struct {
    inter *interfacetype   // 接口类型(Stringer 要求哪些方法)
    _type *_type           // 具体类型(User)
    hash  uint32           // 类型哈希(type switch 用)
    fun   [1]uintptr       // ← 方法函数指针表(变长):实现该接口的各方法地址
}
```

- `fun` 是**关键**:它按接口方法顺序,存好 `User` 实现这些方法的**函数地址**。`s.String()` 就是 `tab.fun[0](data)`。
- `itab` 由 **(接口类型, 具体类型)** 唯一决定,运行时**全局缓存去重**:同样是 `(Stringer, User)` 的 itab 只生成一次,后续复用。所以装接口的常见路径不重复建表。
- `fun[0] == 0` 表示该类型**没实现**这个接口(type assert 失败时用)。

### 3.3 装值会拷贝、常会逃逸

```go
var s Stringer = User{"alice"}
```

data 是个**指针**,得指向某块内存。于是把 `User{"alice"}` 这个**值**装进接口时:

- 编译器需要一个地址放它 → 这个值通常被**搬到堆上**(逃逸),data 指向它;
- 即「**接口装值会拷贝一份并常逃逸到堆**」。这是热路径上 `any`/`interface{}` 参数(如 `fmt.Println(x)`)产生分配的根源。

**direct interface 优化**:如果装进接口的类型**本身就是单个指针**(`*T`、map、chan、func 这类「一个字宽且是指针」的类型),Go 直接把那个指针塞进 data 字,**不再额外分配**。所以 `var s Stringer = &User{}`(装指针)通常比 `var s Stringer = User{}`(装值)更省——前者无额外逃逸。

> 实用推论:大对象或热路径,优先**装指针**进接口,省一次拷贝 + 堆分配。

### 3.4 接口的 nil(预告 typed nil)

接口值 `== nil` **当且仅当两个字都为空**(类型和 data 都没设)。如果你把一个 `(*User)(nil)` 装进接口,类型字段填了 `*User`、data 是 nil——**接口非 nil**!这就是 typed nil 坑,完整版见 [`05-nil/`](../05-nil/README.md)。

### 3.5 对照 Java

| | Java 接口 | Go 接口 |
|---|---|---|
| 实现声明 | 显式 `implements` | **隐式**(编译期查方法集) |
| 方法表挂哪 | 对象头 klass 指针 → vtable | 接口值自带 `itab.fun` |
| 接口值 | 一个对象引用(一个字) | **两个字**(itab/_type + data) |
| 空接口 | `Object` | `any`(eface,只有 `_type`+data) |
| 装基本类型 | 装箱成 `Integer` 等 | 装值拷贝 + 常逃逸(无「箱」类型,但同样有分配) |

---

## 4. 日常开发应用

- **接口要小**:itab 只需覆盖接口声明的方法;接口越小,越多类型能隐式满足、越好测试。`io.Reader`(单方法)是典范。设计哲学见 [`design/` 小接口]。
- **热路径优先装指针**:`var w io.Writer = &buf` 比装值省分配(direct interface)。
- **`any` 参数有成本**:`func(args ...any)`(如日志)会让每个实参装箱逃逸;超热路径考虑具体类型重载或泛型(见 generics track)。
- **判断「某类型是否实现某接口」用编译期断言**:
  ```go
  var _ Stringer = (*User)(nil)   // 编译期检查 *User 实现 Stringer,不实现就编译失败
  ```

---

## 5. 生产&调优实战

- **接口装值是隐藏分配热点**:profile 里看到意外的堆分配,常是值被装进 `any`/接口。`go build -gcflags=-m` 看逃逸,改装指针或避免装箱。
- **动态派发的成本**:itab 查表调用比直接调用略贵(多一次间接 + 难内联),绝大多数场景可忽略;但超热小函数若通过接口调用,会丢失内联优化——必要时用具体类型或泛型。
- **itab 全局缓存有锁**:首次为某 `(接口, 类型)` 建 itab 走带锁的全局表;稳定后复用无锁。极端动态(海量不同类型装同一接口)才需在意。
- **接口比较的坑**:两个接口值 `==` 时若动态类型不可比较(如底层是 slice)会 **panic**(见 [`00`](../00-values-layout/README.md));把 `any` 当 map key 要小心。

---

## 6. 面试高频考点

- **接口在底层是什么?** 两个字:非空接口 = `iface{tab *itab, data}`;空接口 = `eface{_type, data}`。data 指向实际值,itab 含「接口类型 + 具体类型 + 方法函数表」。
- **eface 和 iface 区别?** eface 给 `interface{}`/`any`,只存类型 + data;iface 给带方法的接口,多存 itab(含方法表)以支持动态派发。
- **方法怎么动态派发?** `s.M()` = 从 `itab.fun` 取 M 的函数指针,以 data 作接收者调用。≈ Java vtable,但表挂在接口值上。
- **Go 接口为什么不用写 implements?** 隐式实现——编译器在赋值/传参处检查具体类型方法集是否覆盖接口方法,覆盖即满足,并生成(缓存)itab。编译期检查的鸭子类型。
- **装值进接口会发生什么?为什么逃逸?** 拷贝一份值,data 指向它,该值常被搬到堆(逃逸)。装指针/map/chan/func 走 direct interface 优化、不额外分配。
- **itab 会重复创建吗?** 不会,按 (接口类型, 具体类型) 全局缓存去重。
- **接口值什么时候 == nil?** 两个字都空才 nil;装了 typed nil 指针则非 nil(见 05)。

---

## 7. 一句话总结

> **接口值是两个字:非空接口 `iface = {itab, data}`,空接口 `eface = {_type, data}`。** data 指向实际值,`itab` 含「接口类型 + 具体类型 + **方法函数表 fun**」,`s.M()` 就是从 `fun` 取地址、以 data 作接收者调用——动态派发,≈ Java vtable 但表挂在接口值上、且实现是**隐式**的(编译期查方法集生成并全局缓存 itab)。装**值**进接口会拷贝且常逃逸到堆;装**指针/map/chan/func** 走 direct interface 优化、不额外分配(热路径优先装指针)。接口 `==nil` 要两个字都空——装了 typed nil 则非 nil(下章)。

← 上一章 [`00 值与内存布局`](../00-values-layout/README.md) ｜ 下一章 → [`02 方法集与接收者`](../02-method-sets/README.md):上面说「编译器查方法集」——那 `T` 和 `*T` 的方法集到底差在哪?为什么指针接收者的类型只有 `*T` 能满足接口?｜ 回 [`type-system` 索引](../README.md)
