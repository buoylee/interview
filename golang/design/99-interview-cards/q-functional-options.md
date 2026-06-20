# 函数式选项(Functional Options)

## 一句话回答

Go 没有默认参数和方法重载,处理「可选配置」的惯用法是**函数式选项**:`type Option func(*config)`,每个 `WithXxx(...)` 返回一个修改 config 的**闭包**,构造函数 `NewXxx(必填参数, opts ...Option)` 先设 `defaultConfig()` 再依次 `opt(&c)` 应用。比起直接传 config struct 的好处:**真正可选 + 明确默认**(能区分「设了零值」vs「没设」)、**加选项不破坏老调用**、可校验可组合可读;代价是每个选项一个函数的样板。

## 模式

```go
type Option func(*config)
func WithTimeout(d time.Duration) Option { return func(c *config){ c.timeout = d } }

func NewServer(addr string, opts ...Option) *Server {
    c := defaultConfig()
    for _, opt := range opts { opt(&c) }
    return &Server{addr: addr, cfg: c}
}
NewServer(":8080", WithTimeout(5*time.Second))   // 必填位置参数 + 可选选项
```

## 何时用/别用

- **用**:配置多且大多可选、库要长期演进、对外 API。
- **别用**:配置 ≤2 / 内部小函数 / 无可选项 → 直接参数或 config struct。**必填参数走位置参数,别塞选项**。

## 证据链接

- 正文:[`02 函数式选项`](../02-functional-options/README.md)

## 易追问的延伸

- **vs Java Builder?** 解决同一问题,Go 用闭包选项替代 Builder 对象。
- **变体?** Option 作接口(可带状态)、返回 error 的选项(构造时校验)。
- **默认值注意?** 很多调用方只用默认,默认超时/连接数要设成生产安全值(别零值=无超时)。
- **命名约定?** `WithXxx`,IDE 输入 With 能列全部选项。
