# net/http:client 连接池·超时·drain body

## 一句话回答

`net/http` 自带生产级 server/client。**client 三大坑**:① **默认 `Timeout=0` 永不超时**(`http.Get`/`DefaultClient` 危险,慢下游导致 goroutine 泄漏,必须设 Timeout 或用 ctx);② **复用同一个 client**(它内部 Transport 是 keep-alive 连接池,每次 new 丢池子、TIME_WAIT 暴涨);③ **必须读完并 Close body**(`defer resp.Body.Close()` + `io.Copy(io.Discard, body)`,否则连接无法放回池复用→泄漏)。`MaxIdleConnsPerHost` 默认才 **2**,高并发同一下游要调大。

## server 侧

```go
mux.HandleFunc("GET /users/{id}", h)    // 1.22:方法+路径参数,r.PathValue("id")
// 中间件 = func(http.Handler) http.Handler 洋葱包装(日志/认证/recover)
srv := &http.Server{ReadTimeout:..., WriteTimeout:..., IdleTimeout:...}  // 防慢攻击
srv.Shutdown(ctx)                       // 优雅关闭
```

## 证据链接

- 正文:[`01 net/http`](../01-net-http/README.md);ctx [`concurrency/07`](../../../concurrency/07-context/README.md);优雅关闭 [`service-design/00`](../../../service-design/00-service-skeleton/README.md)

## 易追问的延伸

- **为什么不读 body 就泄漏?** TCP 连接要 body 读完才能放回池复用,否则每次新建。
- **request ctx?** 客户端断开/超时会取消 `r.Context()`,一路传下游实现取消穿透。
- **要框架吗?** 1.22 ServeMux 已支持方法路由,小服务标准库够;复杂路由再上 chi/gin。
- **和 Java?** Java HttpClient + 连接池;Go 内建,但超时/复用/drain 要自己做对。
