# 02 · 函数式选项(Functional Options)

> 构造函数想支持「一堆可选配置」,但 Go 没有默认参数、没有方法重载。社区惯用法是**函数式选项(functional options)**——`NewServer(addr, WithTimeout(5s), WithTLS(cfg))`。这是 Go 特有、面试高频的设计模式(Rob Pike / Dave Cheney 推广)。
>
> 桥接锚点:Java 用 Builder 模式(`.timeout(5).tls(cfg).build()`)或重载/可选参数;Go 没有重载/默认值,用函数式选项达到同样的「可选、可扩展、可读」。

---

## 1. 核心问题

```go
// 想支持很多可选配置,但 Go 没有默认参数、没有重载……
NewServer(addr)                                  // 全用默认
NewServer(addr, timeout, maxConn, tls, logger)   // ❌ 参数爆炸、全得传、顺序易错
```

- Go 没有默认参数 / 重载,怎么优雅地支持「可选配置」?
- 为什么不用 config struct 直接传?函数式选项好在哪?
- 这个模式怎么写?什么时候才值得用?

---

## 2. 直觉理解

### 把每个可选配置变成一个「改配置的函数」

```go
type Option func(*config)                        // 选项 = 一个修改 config 的函数

func WithTimeout(d time.Duration) Option {
    return func(c *config) { c.timeout = d }      // 闭包捕获参数,返回改配置的函数
}
func WithTLS(cfg *tls.Config) Option {
    return func(c *config) { c.tls = cfg }
}

func NewServer(addr string, opts ...Option) *Server {
    c := defaultConfig()                          // 先设默认
    for _, opt := range opts { opt(&c) }          // 逐个应用选项覆盖
    return &Server{addr: addr, cfg: c}
}
```

调用方按需传:

```go
NewServer(":8080")                               // 全默认
NewServer(":8080", WithTimeout(5*time.Second), WithTLS(cfg))   // 只配想配的
```

直觉:**每个选项是一个延迟执行的「配置修改器」,构造时依次应用在默认配置上**。

---

## 3. 原理深入

### 3.1 为什么比 config struct 好

直接传 config struct 也能可选:

```go
NewServer(addr, Config{Timeout: 5*time.Second})    // 也行,但……
```

函数式选项相比 config struct 的优势:

- **真正的可选 + 默认**:不传的选项保持默认;config struct 里没设的字段是零值,你分不清「想用零值」还是「忘了设」。
- **可扩展不破坏兼容**:加新选项 = 加一个 `WithXxx` 函数,**老调用代码不动**;给 config struct 加字段虽兼容,但区分不了默认。
- **可校验 / 可组合**:选项函数里能做校验、能组合多个设置、能有依赖逻辑。
- **可读**:`WithTimeout(5s)` 比 `Config{..., Timeout: 5s, ...}` 在长参数里更自解释。

代价:**更多样板**(每个选项一个函数)。所以不是所有构造都该用——见 3.3。

### 3.2 变体

- **Option 作为接口**(而非函数类型):`type Option interface{ apply(*config) }`——能携带状态、能在选项上加方法,但更重。多数用函数类型就够。
- **返回 error 的选项**:`type Option func(*config) error`,构造时校验失败可返错。
- **方法式选项**:`s.Option(WithX())` 运行时改配置(较少用)。

### 3.3 何时用、何时别用

**适合**:

- 配置项**多且大多可选**(服务器、客户端、连接池);
- 库要**长期演进**、不断加配置而不破坏调用方;
- 公共 API(对外库)。

**别用**(杀鸡用牛刀):

- 只有一两个参数 / 没有可选项 → 直接传参数。
- 内部小函数 → config struct 或直接参数更简单。
- 必填参数 → 放普通位置参数(`NewServer(addr, opts...)`,addr 必填、opts 可选),别塞进选项。

口诀:**必填走位置参数,可选走 functional options;配置少就别上这套样板。**

### 3.4 对照 Java Builder

| | Java Builder | Go functional options |
|---|---|---|
| 写法 | `.timeout(5).tls(c).build()` | `WithTimeout(5), WithTLS(c)` |
| 默认值 | builder 里设 | defaultConfig() 设 |
| 加配置 | builder 加方法 | 加一个 With 函数 |
| 必填 | build() 时校验 | 位置参数强制 |
| 额外类型 | 一个 Builder 类 | 一个 Option 类型 + 若干函数 |

两者解决同一问题(可选配置 + 可读 + 可扩展),Go 用闭包替代 Builder 对象。

---

## 4. 日常开发应用

- **构造函数签名**:`NewXxx(必填参数, opts ...Option)`——必填在前,可选用选项。
- **选项命名 `WithXxx`**:社区约定,一眼认出是选项。
- **`defaultConfig()` 设合理默认**,选项只覆盖想改的。
- **配置项少(≤2)就别用**,直接参数或 config struct。
- **对外库优先用它**(利于演进);内部代码按需。

---

## 5. 生产&调优实战

- **演进友好是最大生产价值**:库加配置只需加 `WithXxx`,所有现存调用代码零改动——对外 SDK/库尤其重要。
- **默认值要安全**:很多调用方只用默认;默认超时/连接数/缓冲区要设成生产安全值(别零值=无超时=隐患)。
- **选项校验**:用返回 error 的选项变体在构造时校验非法配置,早失败。
- **样板成本**:N 个选项 = N 个小函数;只在「可选项确实多 + 要演进」时值得,别为 2 个配置写一套。
- **可发现性**:IDE 里输入 `With` 能列出所有选项,比记 config 字段名友好——但要写好 doc 注释。

---

## 6. 面试高频考点

- **Go 没默认参数/重载,怎么做可选配置?** 函数式选项:`type Option func(*config)`,每个 `WithXxx` 返回一个改 config 的闭包,`NewXxx(必填, opts ...Option)` 在默认配置上依次应用。
- **比 config struct 好在哪?** 真正可选 + 明确默认(区分「设了零值」vs「没设」)、加选项不破坏兼容、可校验可组合、可读;代价是样板多。
- **怎么写?** `Option func(*config)` + `WithX` 返回闭包 + 构造里 `for _,o:=range opts{ o(&c) }`,先 `defaultConfig()`。
- **必填参数怎么办?** 放位置参数(`NewServer(addr, opts...)`),别塞进选项。
- **什么时候别用?** 配置少(≤2)、内部小函数、无可选项——直接传参/config struct。
- **和 Java Builder 关系?** 解决同一问题,Go 用闭包选项替代 Builder 对象。

---

## 7. 一句话总结

> **函数式选项是 Go 处理「可选配置」的惯用法**(因为 Go 无默认参数/重载):`type Option func(*config)`,每个 `WithXxx(...)` 返回一个修改 config 的闭包,构造函数 `NewXxx(必填参数, opts ...Option)` 先设 `defaultConfig()` 再依次 `opt(&c)` 应用。相比 config struct 的好处:真正可选 + 明确默认(能区分「设了零值」和「没设」)、加选项不破坏老调用、可校验可组合、可读;代价是每个选项一个函数的样板,所以**配置少就别用**、必填参数走位置参数。≈ Java Builder,但用闭包替代 Builder 对象;对外库尤其推荐(演进友好),默认值务必设成生产安全值。

← 上一章 [`01 组合与依赖注入`](../01-composition-di/README.md) ｜ 下一章 → [`03 并发安全的 API 设计`](../03-concurrent-api/README.md):设计一个会被并发使用的类型/库,该让谁负责加锁?能不能在库里偷偷开 goroutine?｜ 回 [`design` 索引](../README.md)
