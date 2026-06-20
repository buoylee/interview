# 01 · net/http:server、client、连接池与超时

> Go 标准库自带**生产级** HTTP server 和 client,不用框架就能上。但有几个面试必考、生产必踩的坑:**client 要复用(自带连接池)、默认无超时、连接复用要 drain body**;server 端的**中间件、ServeMux(1.22 路由增强)、超时与优雅关闭**。
>
> 桥接锚点:Java `HttpServer`/Servlet + Spring MVC、`HttpClient`/RestTemplate + 连接池(HikariCP 是 DB 的);Go 的 `http.Client`/`http.Server` 把这些内置,但需要你正确配置超时和复用。

---

## 1. 核心问题

- 写个 HTTP 接口要不要框架?中间件(日志/认证)怎么加?
- `http.Get(url)` 这么方便,为什么生产代码不能直接用?
- 为什么「每次请求 new 一个 http.Client」是错的?连接池在哪?
- HTTP 调用为什么必须设超时、必须读完并关闭 body?

---

## 2. 直觉理解

### server:Handler 接口 + ServeMux 路由

```go
type Handler interface { ServeHTTP(w http.ResponseWriter, r *http.Request) }
```

一切处理器都实现 `ServeHTTP`。`http.HandlerFunc` 把普通函数适配成 Handler。路由用 `ServeMux`:

```go
mux := http.NewServeMux()
mux.HandleFunc("GET /users/{id}", getUser)    // Go 1.22:支持方法 + 路径参数!
http.ListenAndServe(":8080", mux)
```

> **Go 1.22 给 ServeMux 加了方法匹配和路径通配**(`GET /users/{id}`,`r.PathValue("id")` 取参)——以前要靠 gorilla/chi 的功能,现在标准库够用了。

### 中间件 = 包装 Handler 的函数

```go
func logging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        log.Println(r.Method, r.URL.Path)
        next.ServeHTTP(w, r)            // 调用下一层
    })
}
mux2 := logging(authMiddleware(mux))   // 层层包装(洋葱模型)
```

中间件就是 `func(http.Handler) http.Handler`——洋葱式包装(承接 [`design/01`](../../design/01-composition-di/README.md) 装饰器)。

### client:复用一个 Client,它自带连接池

```go
// ❌ 每次 new 一个 client / 用 http.DefaultClient(无超时)
// ✅ 复用一个配好超时的 client(它内部的 Transport 管连接池)
var client = &http.Client{Timeout: 10 * time.Second}
```

`http.Client` 内部的 `Transport` 维护 **keep-alive 连接池**。**复用同一个 client** 才能复用连接;每次 new 会丢失连接池、暴涨 TIME_WAIT。

---

## 3. 原理深入

### 3.1 client 的三大坑

**① 默认无超时**:`http.Get`/`http.DefaultClient` 的 `Timeout` 是 **0 = 永不超时**。下游卡住你就永久挂(goroutine 泄漏)。**必须**设 `Timeout` 或用 `http.NewRequestWithContext` + ctx 超时(见 [`concurrency/07`](../../concurrency/07-context/README.md))。

**② 必须读完并关闭 body 才能复用连接**:

```go
resp, err := client.Do(req)
if err != nil { return err }
defer resp.Body.Close()                       // 必须关
io.Copy(io.Discard, resp.Body)                // 读完(排空),否则连接不能复用
```

不读完 body,底层 TCP 连接**无法放回池子复用**,变成新建连接 → 连接泄漏 + 性能差。

**③ Transport 连接池要调**:

```go
t := &http.Transport{
    MaxIdleConns:        100,
    MaxIdleConnsPerHost: 10,          // 默认才 2!高并发同一下游会瓶颈
    IdleConnTimeout:     90 * time.Second,
}
client := &http.Client{Transport: t, Timeout: 10 * time.Second}
```

`MaxIdleConnsPerHost` 默认 **2**,高并发调同一服务会因连接不够而频繁新建——生产常需调大。

### 3.2 server 的超时与优雅关闭

```go
srv := &http.Server{
    Addr:         ":8080",
    Handler:      mux,
    ReadTimeout:  5 * time.Second,    // 防慢读攻击
    WriteTimeout: 10 * time.Second,
    IdleTimeout:  120 * time.Second,
}
go srv.ListenAndServe()
// 优雅关闭(见 service-design/00):
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(ctx)                     // 停止接新请求,等存量请求完成
```

`http.Server` 不设超时 = 慢客户端能耗尽连接(Slowloris)。`Shutdown(ctx)` 是优雅关闭(详见 [`service-design/00`](../../service-design/00-service-skeleton/README.md))。

### 3.3 request 的 context

每个 `*http.Request` 带一个 ctx(`r.Context()`):客户端断开/超时时它会被取消。把它**一路传给下游调用**(DB/RPC),实现取消穿透(见 [`concurrency/07`](../../concurrency/07-context/README.md))。

---

## 4. 日常开发应用

- **小服务标准库够用**(ServeMux 1.22 + 中间件);要更多再上 chi/gin/echo。
- **中间件**:`func(http.Handler) http.Handler` 洋葱包装(日志/认证/recover/限流)。recover 中间件必备(见 [`error-handling/03`](../../error-handling/03-panic-recover-defer/README.md))。
- **client 全局复用一个**(配好 Timeout + Transport),别每次 new、别用 DefaultClient。
- **每次请求**:`defer resp.Body.Close()` + 读完 body。
- **下游调用带 ctx**:`http.NewRequestWithContext(ctx, ...)`。
- **server 设三个超时** + 优雅关闭。

---

## 5. 生产&调优实战

- **无超时是头号生产事故**:client 不设 Timeout/ctx,一个慢下游能让你 goroutine 堆积到 OOM。**所有出站 HTTP 必须有超时**。
- **不 drain body = 连接泄漏**:监控里看到大量 TIME_WAIT / 连接数暴涨,常是没读完关 body。
- **MaxIdleConnsPerHost 默认 2 的瓶颈**:高 QPS 调同一下游务必调大,否则连接复用率低、延迟高。
- **server 超时防慢攻击**:ReadTimeout/WriteTimeout/IdleTimeout 防 Slowloris 耗尽连接。
- **优雅关闭**:K8s 滚动更新时 `Shutdown(ctx)` 让存量请求做完再退,避免 502(见 [`service-design/00`](../../service-design/00-service-skeleton/README.md))。
- **复用 client 的连接池**:全局单例 client,连接复用大幅降延迟和握手开销。

---

## 6. 面试高频考点

- **写 HTTP 服务要框架吗?中间件怎么写?** 标准库够用(1.22 ServeMux 支持 `GET /x/{id}`);中间件 = `func(http.Handler) http.Handler` 洋葱包装。
- **为什么不能用 http.Get/DefaultClient?** 默认 **Timeout=0 永不超时**,下游卡住就泄漏;要复用配好超时的 client。
- **http.Client 要复用吗?为什么?** 要——内部 Transport 管 keep-alive 连接池,复用 client 才复用连接;每次 new 丢池子、TIME_WAIT 暴涨。
- **为什么必须读完并 Close body?** 不读完 body,TCP 连接无法放回池子复用 → 连接泄漏 + 性能差。`defer Close()` + `io.Copy(io.Discard, body)`。
- **连接池怎么调?** Transport 的 `MaxIdleConnsPerHost`(默认 2,高并发要调大)、`MaxIdleConns`、`IdleConnTimeout`。
- **server 要设哪些超时?** ReadTimeout/WriteTimeout/IdleTimeout 防慢客户端耗尽连接;Shutdown(ctx) 优雅关闭。
- **request ctx 干嘛?** 客户端断开/超时会取消它,一路传下游实现取消穿透。

---

## 7. 一句话总结

> **net/http 自带生产级 server/client。server**:Handler 接口 + ServeMux(1.22 支持 `GET /x/{id}` 方法路由),中间件 = `func(http.Handler) http.Handler` 洋葱包装(recover 中间件必备),设 Read/Write/IdleTimeout 防慢攻击 + `Shutdown(ctx)` 优雅关闭。**client 三大坑**:① 默认 `Timeout=0` 永不超时(必须设超时/ctx,否则慢下游导致泄漏);② **复用同一个 client**(它内部 Transport 是 keep-alive 连接池,每次 new 丢池子);③ **必须读完并 Close body**(否则连接无法复用→泄漏);`MaxIdleConnsPerHost` 默认才 2,高并发要调大。出站调用带 ctx 实现取消穿透。

← 上一章 [`00 io 接口家族`](../00-io/README.md) ｜ 下一章 → [`02 encoding/json`](../02-encoding-json/README.md):struct tag、流式编解码、自定义 Marshaler,以及数字解析成 float64 的经典坑。｜ 回 [`stdlib` 索引](../README.md)
