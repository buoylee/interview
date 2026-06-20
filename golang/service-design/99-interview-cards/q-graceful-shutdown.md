# 优雅关闭 + liveness/readiness

## 一句话回答

**优雅关闭**:`signal.NotifyContext(ctx, SIGTERM, SIGINT)` 把信号变成可取消的 ctx,`<-ctx.Done()` 后**先把 readiness 转失败**(从负载均衡摘流量)→ `srv.Shutdown(超时ctx)`(停止接新请求、等存量请求完成)→ cancel 后台 goroutine → 关连接池/flush 日志 → 退出。Shutdown **必须带超时**(< K8s 的 terminationGracePeriodSeconds,默认 30s),否则滚动发布掐断存量请求 → 502。**liveness vs readiness**:liveness=进程还活着吗(死了**重启**,只查自身别查 DB);readiness=能收流量吗(依赖没好/优雅关闭期间返失败,**摘流量但不重启**)。还活着 ≠ 能服务,所以要两个。

## 关键代码

```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
defer stop()
go srv.ListenAndServe()
<-ctx.Done()
sdCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(sdCtx)
```

## 证据链接

- 正文:[`00 服务骨架`](../00-service-skeleton/README.md);Shutdown [`stdlib/01`](../../stdlib/01-net-http/README.md);后台 goroutine 退出 [`design/03`](../../design/03-concurrent-api/README.md)/[`concurrency/08`](../../concurrency/08-patterns/README.md)

## 易追问的延伸

- **为什么先摘 readiness 再 Shutdown?** K8s 摘 endpoint 和 SIGTERM 不保证顺序;先 readiness 失败 + sleep 几秒等 LB 摘干净,避免在途请求打到正在关的实例。
- **liveness 能查 DB 吗?** 不该,DB 抖动会误杀重启;依赖检查放 readiness。
- **配置?** 12-factor 走 env、缺项启动 Fatal。
- **和 Spring?** Spring Boot actuator + graceful shutdown;Go 手搓更透明。
