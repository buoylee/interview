# 04 · 嵌入与组合:Go 没有继承,只有组合

> Go 故意**不要类继承**。复用靠**嵌入(embedding)**:把一个类型匿名放进另一个,它的字段和方法被「提升」到外层。看起来像继承,本质是**组合 + 自动转发**——**没有虚函数重写、没有多态覆盖**。这是和 Java 面向对象的根本分歧,面试常考。
>
> 桥接锚点:Java `class Dog extends Animal`(is-a 继承 + 可重写虚方法)←→ Go `struct Dog { Animal }`(has-a 组合 + 方法提升,无重写)。

---

## 1. 核心问题

```go
type Animal struct{ Name string }
func (a Animal) Speak() string { return a.Name + " makes a sound" }

type Dog struct {
    Animal          // 嵌入(匿名字段),不是 Animal field Animal
    Breed string
}

func main() {
    d := Dog{Animal{"Rex"}, "Lab"}
    fmt.Println(d.Name)       // 能直接访问?(Name 是 Animal 的)
    fmt.Println(d.Speak())    // 能直接调?调的是谁的 Speak?
}
```

- 嵌入和「普通字段」差在哪?`d.Name`/`d.Speak()` 为什么能直接用?
- 这是继承吗?如果 `Dog` 也定义一个 `Speak()`,是「重写」了 `Animal.Speak` 吗?
- 嵌入接口又是怎么回事(`io.ReadWriter`)?

---

## 2. 直觉理解

### 嵌入 = 匿名字段 + 自动提升

把类型名直接写进 struct(不给字段名)就是嵌入。嵌入类型的**字段和方法被「提升」**到外层,可以像外层自己的一样访问:

```go
d.Name          // 实际是 d.Animal.Name —— 提升后的简写
d.Speak()       // 实际是 d.Animal.Speak() —— 方法提升
```

本质:`Dog` **包含**一个 `Animal`(组合,has-a),编译器帮你把对 `Name`/`Speak` 的访问**自动转发**到内嵌的 `Animal`。**不是** `Dog` 「是一个」`Animal`(不是 is-a 继承)。

### 关键区别:没有虚函数重写,没有多态覆盖

如果 `Dog` 自己也定义 `Speak()`:

```go
func (d Dog) Speak() string { return d.Name + " barks" }
```

这叫**遮蔽(shadow)**,不是「重写(override)」。区别致命:

```go
var a Animal = d.Animal     // 把内嵌的 Animal 拿出来
a.Speak()                   // "Rex makes a sound" —— Animal 的,不是 Dog 的!
```

在 Java 里,`Animal a = dog; a.speak()` 会因虚函数动态派发到 `Dog.speak()`。**Go 没有这套**:`Animal` 类型的值就调 `Animal` 的方法,`Animal` 根本不知道 `Dog` 的存在。**Go 的多态只通过接口实现,不通过嵌入**。

一句话:**嵌入是为了复用代码(组合),接口是为了多态——两件事分开**。

---

## 3. 原理深入

### 3.1 方法提升让外层「自动满足接口」

嵌入最有用的效果:内嵌类型的方法被提升后,**外层也就满足了内嵌类型满足的接口**:

```go
type Stringer interface{ String() string }
type Base struct{}
func (Base) String() string { return "base" }

type Widget struct{ Base }          // 嵌入 Base
var s Stringer = Widget{}           // ✅ Widget 通过提升的 String() 满足了 Stringer
```

这是 Go 复用 + 满足接口的主力手法。标准库 `sync.Mutex` 常被嵌入,让外层直接有 `Lock`/`Unlock`。

### 3.2 嵌入接口 = 组合接口 / 包一层实现

```go
// 组合接口:io.ReadWriter 就是嵌两个接口
type ReadWriter interface {
    Reader            // 嵌入接口 = 要求实现 Reader 的方法
    Writer
}

// struct 嵌入接口:外层自动获得这些方法(转发给内嵌的接口值)
type LoggingReader struct {
    io.Reader         // 嵌一个接口值
}
func (r LoggingReader) Read(p []byte) (int, error) {
    log.Println("reading")
    return r.Reader.Read(p)      // 转发 + 加料(装饰器模式)
}
```

struct 嵌入**接口**是实现「装饰器 / 中间件」的常见招:外层默认转发给内嵌接口值,只重写想改的方法。

### 3.3 提升规则与二义性

- **浅层优先**:外层自己定义的字段/方法**遮蔽**内嵌的同名成员(上面 `Dog.Speak` 遮蔽 `Animal.Speak`)。
- **同层冲突要显式**:嵌入两个类型有**同名**方法/字段且在同一深度 → 提升被取消,直接 `d.X` **编译报错(ambiguous)**,必须 `d.A.X` / `d.B.X` 显式指定。
- **指针嵌入** `struct{ *Base }`:也提升方法,且共享同一个 Base;但内嵌指针为 nil 时调用提升方法会 panic。

### 3.4 对照 Java 继承

| | Java 继承 | Go 嵌入 |
|---|---|---|
| 关系 | is-a(子类是父类) | has-a(组合) |
| 方法重写/多态 | ✅ 虚函数动态派发 | ❌ 无重写;多态只靠接口 |
| 向上转型 | `Animal a = dog` 仍调 Dog 方法 | 取出 `d.Animal` 调的是 Animal 方法 |
| 多继承 | 类不行,接口可 | struct 可嵌多个(冲突要显式) |
| `super.x()` | 有 | 用 `d.Animal.Speak()` 显式调内嵌的 |

---

## 4. 日常开发应用

- **组合复用**:把公共字段/行为抽成一个类型,嵌进多个 struct(如嵌 `BaseModel{ID, CreatedAt}`)。
- **嵌 `sync.Mutex`** 让类型直接有锁:`type Cache struct { sync.Mutex; m map[...] }`,但**用指针接收者**(别拷贝锁)。
- **装饰器/中间件**:嵌入接口 + 只重写想改的方法,其余自动转发。
- **不想暴露内嵌类型的全部方法**:别嵌入,改用**具名字段 + 显式转发**(嵌入会把内嵌的**所有**导出方法都提升出去,可能泄漏不想要的 API)。
- **多态用接口,不要试图用嵌入模拟继承重写**——会踩「取出内嵌值就调回父方法」的坑。

---

## 5. 生产&调优实战

- **嵌入会扩大公共 API 面**:嵌入一个类型 = 把它所有导出方法变成你的 API。嵌 `sync.Mutex`(导出 `Lock`/`Unlock`)会让外部能直接锁你的对象——常见做法是嵌**未导出**的或用具名字段封装。
- **嵌入接口值为 nil 会 panic**:`struct{ io.Reader }` 没初始化内嵌 Reader 就调 `Read` → nil 解引用 panic。要么保证注入,要么判空。
- **遮蔽导致的「调错方法」难查**:外层和内嵌同名方法,通过内嵌类型/接口调用时走的是内嵌的版本——重构时容易出微妙 bug。
- **JSON 等序列化受嵌入影响**:嵌入字段在 `encoding/json` 里默认**平铺**(promoted),输出层级和你想的可能不同;需要时用 tag 或具名字段控制。

---

## 6. 面试高频考点

- **Go 有继承吗?** 没有。用**嵌入**做组合复用,方法被提升,但**没有虚函数重写、没有多态覆盖**。多态只通过接口实现。
- **嵌入和继承的本质区别?** 嵌入是 has-a 组合 + 自动转发;继承是 is-a + 可重写虚方法。Go 里把内嵌值取出来调,走的是内嵌类型自己的方法(无动态派发到外层)。
- **嵌入怎么帮满足接口?** 内嵌类型的方法提升到外层,外层因此也满足内嵌类型满足的接口。
- **同名方法冲突怎么办?** 浅层(外层自定义)遮蔽深层;同深度两个嵌入类型同名 → ambiguous 编译错误,需显式 `d.A.X`。
- **嵌入接口有什么用?** 组合接口(`io.ReadWriter`);struct 嵌接口做装饰器(默认转发 + 重写部分方法)。
- **嵌入有什么坑?** 扩大公共 API 面(导出方法全提升)、内嵌接口/指针为 nil 调用 panic、遮蔽导致调错方法、序列化字段平铺。
- **`Dog` 遮蔽 `Speak` 后,`var a Animal = d.Animal; a.Speak()` 调谁?** 调 `Animal.Speak`——没有多态,这正是和 Java 的关键差别。

---

## 7. 一句话总结

> **Go 没有继承,只有嵌入(组合):把类型匿名放进 struct,其字段/方法被「提升」到外层、自动转发——这是 has-a 不是 is-a。** 关键差异:**没有虚函数重写、没有多态覆盖**,外层同名方法只是「遮蔽」,把内嵌值取出来调走的仍是内嵌自己的方法;**多态只能通过接口实现**。嵌入的威力在「方法提升让外层自动满足接口」和「嵌接口做装饰器转发」。坑:嵌入会把内嵌的导出方法全变成你的 API、内嵌接口/指针为 nil 调用会 panic、同深度同名会 ambiguous。记住:**嵌入为复用,接口为多态,两件事。**

← 上一章 [`03 类型断言`](../03-type-assertion/README.md) ｜ 下一章 → [`05 nil 的多张面孔`](../05-nil/README.md):收口——typed nil 为什么 `!= nil`、nil map/slice/channel/func 各自能干什么不能干什么、nil 指针居然能调方法。｜ 回 [`type-system` 索引](../README.md)
