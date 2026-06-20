# 02 · 基准、模糊、集成测试

> 单元测试之外,Go 内置了三件资深工程师该会的:**benchmark**(量化性能 + 防回退)、**fuzzing**(自动找崩溃/边界输入,1.18)、**集成测试**(对真依赖,用 build tag + testcontainers 隔离)。外加 **coverage**。
>
> 桥接锚点:Java 要 JMH 做基准、jqwik 做属性测试、Testcontainers(Java 版同名)做集成;Go 这些**大多内置**(`go test -bench`/`-fuzz`/`-cover`),testcontainers-go 是社区库。

---

## 1. 核心问题

- 怎么量化一段代码多快、改完有没有变慢(防性能回退)?
- 怎么**自动**生成大量输入找崩溃/panic/边界 bug?
- 集成测试要连真 DB/Kafka,怎么在 CI 里可靠地起这些依赖、又不拖慢日常 `go test`?
- 覆盖率怎么看、看什么?

---

## 2. 直觉理解

### benchmark:让 `b.N` 自适应跑够久

```go
func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {      // 框架自动调大 N 直到测够时长,算出每次操作耗时
        Add(2, 3)
    }
}
```

```bash
go test -bench=. -benchmem        # 跑基准 + 报内存分配
# BenchmarkAdd-8   1000000000   0.3 ns/op   0 B/op   0 allocs/op
```

`b.N` 由框架**自适应**(从小到大跑到足够稳定),你只管循环 `b.N` 次。`-benchmem` 给 `B/op`(每次分配字节)和 `allocs/op`(每次分配次数)——优化逃逸/分配就盯这俩(见 [`data-structures/03`](../../data-structures/03-escape-analysis/README.md))。

### fuzzing:框架帮你造刁钻输入

```go
func FuzzParse(f *testing.F) {
    f.Add("valid input")                    // 种子语料
    f.Fuzz(func(t *testing.T, s string) {   // 框架自动变异 s,喂各种刁钻值
        _ = Parse(s)                        // 目标:别 panic / 满足某不变量
    })
}
```

```bash
go test -fuzz=FuzzParse                    # 持续生成输入找崩溃,失败语料存进 testdata
```

fuzzing 自动探索输入空间,擅长找 **panic、越界、解析器崩溃、不变量被破坏**。找到的崩溃输入会**存进 `testdata/fuzz/`**,之后当普通用例回归。

### 集成测试:真依赖,但隔离开

单元测试用 fake(快);集成测试连**真** DB/MQ(慢、真实)。用 **build tag 隔离**,平时 `go test` 不跑、CI 才跑:

```go
//go:build integration
package repo
```

真依赖用 **testcontainers-go** 在测试里**用 Docker 起一个真容器**(Postgres/Redis/Kafka),测完自动销毁——可靠、可重复,不污染环境。

---

## 3. 原理深入

### 3.1 benchmark 细节

```go
func BenchmarkX(b *testing.B) {
    setup()
    b.ResetTimer()              // 不把 setup 计入计时
    for i := 0; i < b.N; i++ { ... }
    b.ReportAllocs()           // 强制报分配(等价命令行 -benchmem)
}
b.RunParallel(...)             // 测并发吞吐
```

- `b.ResetTimer`/`b.StopTimer`/`b.StartTimer`:排除 setup/teardown 的计时。
- **benchstat**:跑多次 `-count=10` 后用 `benchstat old.txt new.txt` 做**统计显著性**对比(单次基准噪声大,别只跑一次下结论)。
- 防 dead-code 消除:把结果赋给包级变量,避免编译器优化掉被测代码。

### 3.2 fuzzing 机制

- `f.Add` 提供种子语料;`f.Fuzz` 的回调参数被框架**变异**(coverage-guided,按代码覆盖引导变异)。
- 支持的参数类型有限(基本类型、string、[]byte 等)。
- CI 里通常**限时跑**(`-fuzztime=30s`);找到的崩溃输入提交进 `testdata/fuzz/` 成为回归用例。
- 适合:解析器、编解码、输入校验、任何「不该 panic」的边界。

### 3.3 集成测试编排

- **build tag**(`//go:build integration`)+ CI `go test -tags=integration`:把慢测试和快单元测试分流(见 [`engineering/01`](../../engineering/01-project-build/README.md))。
- **testcontainers-go**:代码里声明要的容器,自动拉起 + 等就绪 + 测完销毁;比共享测试库/手工 docker-compose 更隔离、可并行。
- **TestMain** 做一次性起容器/迁移(见 [`00`](../00-unit-testing/README.md))。

### 3.4 coverage

```bash
go test -cover                              # 概览覆盖率
go test -coverprofile=cov.out ./...
go tool cover -html=cov.out                # 可视化哪些行没覆盖
go test -coverpkg=./... ...                # 跨包覆盖(集成测试覆盖被测包)
```

- Go 1.20+ 还支持**给 `go build` 的二进制收集覆盖率**(集成/E2E 场景对真实运行的二进制测覆盖)。
- 覆盖率是**参考**不是目标:看「核心逻辑/边界有没有覆盖」,别为数字写空测试。

---

## 4. 日常开发应用

- **性能敏感函数配 benchmark**:改动后 `-benchmem` + `benchstat` 对比,防回退。
- **解析/校验/编解码配 fuzz**:CI 限时跑,崩溃语料入库回归。
- **repo/外部依赖配集成测试**:build tag 隔离 + testcontainers,本地/CI 跑真依赖。
- **覆盖率看趋势**:核心包定个底线(如 70%),别全局强求高数字。
- **基准跑多次 `-count`** 再下结论,单次噪声大。

## 5. 生产&调优实战

- **CI 分层**:快单元测试每次跑;集成测试(`-tags=integration`)合并前/夜间跑;fuzz 定时/夜间限时跑;benchmark 在性能关键模块做回归门禁(benchstat 比对,显著变慢就 fail)。
- **benchmark 的坑**:没 `ResetTimer` 把 setup 算进去、结果被 dead-code 消除、只跑一次被噪声骗、跑在负载不稳的机器上。注意这些才有可信数字。
- **testcontainers 的代价**:起容器有秒级开销,集成测试天然慢;并行 + 复用容器、只在该跑时跑。
- **fuzz 语料维护**:崩溃语料进版本库当回归;定期重跑发现新路径。
- **覆盖率反模式**:为冲数字写「调用但不断言」的测试,虚高且无价值;盯有意义的分支覆盖。

## 6. 面试高频考点

- **怎么写 benchmark?`b.N` 是什么?** `BenchmarkXxx(b *testing.B)` 循环 `b.N` 次;`b.N` 框架自适应跑到稳定。`-benchmem` 看 `B/op`、`allocs/op`;`b.ResetTimer` 排除 setup。
- **怎么可信地比较性能?** 跑多次 `-count=10` + `benchstat` 做统计显著性,别只跑一次;防 dead-code 消除。
- **fuzzing 是什么/找什么?** `FuzzXxx(f *testing.F)` + `f.Add` 种子 + `f.Fuzz` 回调;coverage-guided 变异输入,找 panic/越界/不变量破坏;崩溃语料存 `testdata/fuzz/` 回归。
- **集成测试怎么隔离?** build tag(`//go:build integration`)分流 + testcontainers-go 用 Docker 起真依赖、测完销毁;TestMain 做一次性初始化。
- **覆盖率怎么看?** `-cover`/`-coverprofile` + `go tool cover -html`;`-coverpkg` 跨包;1.20+ 可测二进制覆盖。覆盖率是参考非目标。
- **单元 vs 集成测试边界?** 单元用 fake(快、确定);集成连真依赖(慢、真实),build tag 分开,都要。

## 7. 一句话总结

> **benchmark**:`BenchmarkXxx(b)` 循环 `b.N`(框架自适应)次,`-benchmem` 看 `B/op`·`allocs/op`,`b.ResetTimer` 排除 setup,多次 `-count` + **benchstat** 做显著性对比(别单次下结论)。**fuzzing**(1.18):`FuzzXxx(f)` + `f.Add` 种子 + `f.Fuzz` 回调,coverage-guided 变异找 panic/边界,崩溃语料存 `testdata/fuzz/` 回归。**集成测试**:`//go:build integration` 隔离慢测试 + **testcontainers-go** 用 Docker 起真依赖测完销毁、TestMain 一次性初始化。**coverage**:`-cover`/`-coverprofile` + `cover -html`,是参考非目标。CI 分层:单元每次跑、集成合并前跑、fuzz/benchmark 夜间或门禁跑。

← 上一章 [`01 mock 与接口`](../01-mock-interfaces/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):table-driven·parallel、mock·接口、benchmark·fuzz 速查。｜ 回 [`testing` 索引](../README.md)
