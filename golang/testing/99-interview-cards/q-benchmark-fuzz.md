# benchmark、fuzzing、集成测试

## 一句话回答

三件内置利器:**benchmark**——`BenchmarkXxx(b *testing.B)` 循环 `b.N`(框架自适应跑到稳定)次,`go test -bench=. -benchmem` 看 `ns/op`·`B/op`·`allocs/op`,`b.ResetTimer` 排除 setup,**多次 `-count` + `benchstat` 做统计显著性**(别单次下结论);**fuzzing**(1.18)——`FuzzXxx(f *testing.F)` + `f.Add` 种子 + `f.Fuzz` 回调,coverage-guided 变异输入找 panic/越界/不变量破坏,崩溃语料存 `testdata/fuzz/` 当回归;**集成测试**——`//go:build integration` build tag 隔离慢测试 + **testcontainers-go** 用 Docker 起真依赖测完销毁。

## benchmark 要点

```go
func BenchmarkX(b *testing.B) {
    setup(); b.ResetTimer()
    for i := 0; i < b.N; i++ { Target() }
    b.ReportAllocs()
}
```

坑:没 ResetTimer 把 setup 算进去、结果被 dead-code 消除(赋值给包级变量防优化)、只跑一次被噪声骗。

## fuzz 要点

```go
func FuzzParse(f *testing.F) {
    f.Add("seed")
    f.Fuzz(func(t *testing.T, s string) { _ = Parse(s) })  // 目标:别 panic / 守不变量
}
// go test -fuzz=FuzzParse -fuzztime=30s
```

适合解析器/编解码/输入校验;CI 限时跑、崩溃语料入库。

## 集成 + coverage

- build tag 分流:日常 `go test` 跑单元(快),CI `-tags=integration` 跑集成(慢、真实)。
- testcontainers-go 起真 Postgres/Redis/Kafka,TestMain 一次性初始化。
- coverage:`-cover`/`-coverprofile` + `go tool cover -html`;`-coverpkg` 跨包;1.20+ 可测二进制覆盖。**参考非目标**。

## 证据链接

- 正文:[`02 基准·模糊·集成`](../02-benchmark-fuzz-integration/README.md);逃逸/分配 [`data-structures/03`](../../data-structures/03-escape-analysis/README.md);build tag [`engineering/01`](../../engineering/01-project-build/README.md)

## 易追问的延伸

- **CI 怎么分层?** 单元每次跑;集成合并前/夜间;fuzz/benchmark 夜间或当门禁(benchstat 显著变慢则 fail)。
- **覆盖率反模式?** 为冲数字写「调用不断言」的空测试,虚高无价值。
- **和 Java?** Java 用 JMH/jqwik/Testcontainers;Go 这些大多内置(-bench/-fuzz/-cover)。
