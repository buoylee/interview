# 00 · 单元测试基础:table-driven、子测试、cleanup

> Go 的测试就是普通 Go 代码:一个 `TestXxx(t *testing.T)` 函数 + `if got != want { t.Errorf(...) }`。没有断言 DSL、没有注解。本章讲它的惯用法——**table-driven + 子测试**,以及 `t.Parallel`/`t.Helper`/`t.Cleanup` 这些细节。
>
> 桥接锚点:JUnit `@Test`/`@ParameterizedTest`/`@BeforeEach` + AssertJ 断言 ←→ Go `TestXxx` + table-driven + `if`。Go **刻意不内置断言库**——和 Java「断言无处不在」相反。

---

## 1. 核心问题

- Go 测试怎么写?为什么没有 `assertEquals`?那怎么断言?
- 一个函数要测十几组输入,难道写十几个 `TestXxx`?(table-driven)
- `t.Run`、`t.Parallel`、`t.Helper`、`t.Cleanup` 各干嘛?`t.Error` 和 `t.Fatal` 区别?

---

## 2. 直觉理解

### 测试就是代码,断言就是 if

```go
// add_test.go(和 add.go 同包,文件名 _test.go)
func TestAdd(t *testing.T) {
    got := Add(2, 3)
    if got != 5 {
        t.Errorf("Add(2,3) = %d, want 5", got)   // 不匹配就报错
    }
}
```

`go test ./...` 跑所有测试。**断言就是 `if 不符合预期 { t.Errorf }`**——Go 团队认为内置断言库会鼓励「断言 DSL 滥用」,普通 `if` + 清晰错误信息更直接。要省事可用第三方 `testify`(`assert`/`require`),但**标准库风格是手写 if**。

### table-driven:一张表测所有 case

惯用法不是写 N 个测试函数,而是**一张用例表 + 循环 + 子测试**:

```go
func TestAdd(t *testing.T) {
    tests := []struct {
        name     string
        a, b, want int
    }{
        {"positive", 2, 3, 5},
        {"zero", 0, 0, 0},
        {"negative", -1, -2, -3},
    }
    for _, tc := range tests {
        t.Run(tc.name, func(t *testing.T) {       // 每个 case 一个子测试
            if got := Add(tc.a, tc.b); got != tc.want {
                t.Errorf("Add(%d,%d) = %d, want %d", tc.a, tc.b, got, tc.want)
            }
        })
    }
}
```

好处:加 case 只加一行;`t.Run` 给每个 case 命名,失败时精确定位,还能单独跑 `go test -run TestAdd/negative`。这是 Go 测试**最核心的惯用法**(≈ JUnit `@ParameterizedTest`,但更显式、零依赖)。

---

## 3. 原理深入

### 3.1 t.Error vs t.Fatal

- `t.Error`/`t.Errorf`:记录失败但**继续**执行(能在一个测试里收集多个断言失败)。
- `t.Fatal`/`t.Fatalf`:记录失败并**立即停止**当前测试(`runtime.Goexit`)。⚠️ `t.Fatal` 只能在**测试 goroutine** 里调用——在子 goroutine 里调 `t.Fatal` 不会停测试(用 `t.Error` + return)。

准则:**前置条件不满足(err 非 nil、对象为 nil)用 `Fatal`(继续没意义);具体值断言用 `Error`(多收集几个)。**

### 3.2 子测试与 t.Parallel

```go
t.Run(tc.name, func(t *testing.T) {
    t.Parallel()                 // 标记此子测试可并行
    ...
})
```

- `t.Parallel()`:标记测试并行运行。同一父下所有标了 Parallel 的子测试,会**等父函数返回后一起并行跑**。
- ⚠️ **循环变量坑(Go 1.22 前)**:`tc` 是循环变量,1.22 前所有并行子测试闭包共享同一个 `tc`,跑起来全是最后一个 case——必须 `tc := tc` 拷贝。**Go 1.22 起循环变量每轮独立**,这个坑消失(但老代码/老版本仍要注意,见 [`concurrency/04`](../../concurrency/04-goroutine/README.md))。
- 并行能加速 IO 密集测试,但要确保各测试**无共享状态**;配合 `-race` 抓竞争。

### 3.3 t.Helper:让错误指向调用处

```go
func assertEqual(t *testing.T, got, want int) {
    t.Helper()                   // 标记为辅助函数
    if got != want { t.Errorf("got %d, want %d", got, want) }
}
```

`t.Helper()` 让失败的**行号报告在调用者**(而非辅助函数内部),抽取断言辅助函数时必加。

### 3.4 t.Cleanup vs defer

```go
func TestX(t *testing.T) {
    f := createTempFile(t)
    t.Cleanup(func() { os.Remove(f) })    // 测试结束时执行(LIFO)
}
```

`t.Cleanup` 注册清理,**测试(含子测试)结束后按 LIFO 执行**。比 `defer` 好在:能在**辅助函数里注册**(defer 只在当前函数作用域),且和子测试生命周期对齐。配套:`t.TempDir()`(自动清理的临时目录)、`t.Setenv()`(测试后自动还原环境变量)。

### 3.5 TestMain:全局 setup/teardown

```go
func TestMain(m *testing.M) {
    setup()                  // 所有测试前(如起 DB 容器)
    code := m.Run()          // 跑所有测试
    teardown()
    os.Exit(code)
}
```

整个测试包的总入口,做一次性初始化(集成测试常用,见 [`02`](../02-benchmark-fuzz-integration/README.md))。

### 3.6 golden file:大输出对比

```go
golden := "testdata/output.golden"
if *update { os.WriteFile(golden, got, 0644) }   // go test -update 重新生成
want, _ := os.ReadFile(golden)
if !bytes.Equal(got, want) { t.Errorf("output mismatch") }
```

对「大块期望输出」(渲染结果、序列化)用 golden file 存进 `testdata/`(Go 工具链**忽略 testdata 目录**),`-update` flag 一键重生。比把大字符串写死在代码里清爽。比较结构体差异用 `google/go-cmp` 的 `cmp.Diff`(给可读 diff)。

---

## 4. 日常开发应用

- **默认 table-driven + `t.Run`**:几乎所有单元测试都这么写。
- **断言**:小项目手写 `if`;团队嫌啰嗦用 `testify`(`require` 失败即停 ≈ Fatal,`assert` 继续 ≈ Error)。对比结构体用 `cmp.Diff`。
- **前置用 Fatal、值断言用 Error**。
- **抽断言辅助函数加 `t.Helper()`**。
- **清理用 `t.Cleanup`/`t.TempDir`/`t.Setenv`**,别手写 defer 散落。
- **黑盒测试用 `package xxx_test`**(外部包视角,只测导出 API);白盒测试同包(能测未导出)。

---

## 5. 生产&调优实战

- **测试要确定、隔离、可并行**:不依赖全局状态/时钟/网络(用注入,见 [`01`](../01-mock-interfaces/README.md));`t.Parallel` + `-race` 在 CI 抓并发问题。
- **`-run`/`-count` 用法**:`go test -run TestX/case -v` 跑单 case;`-count=1` 禁用测试缓存(强制重跑)。
- **覆盖率别当 KPI**:`-cover` 看趋势可以,盲目追 100% 会催生无意义测试;重点覆盖核心逻辑和边界(见 [`02`](../02-benchmark-fuzz-integration/README.md))。
- **flaky 测试**:并行 + 共享状态/时序依赖是主因;`-race`、固定随机种子、注入时钟可治。
- **golden file 要 review**:`-update` 重生后必须人工 review diff,否则把 bug 当成新基线固化。

---

## 6. 面试高频考点

- **Go 测试怎么写?为什么没断言库?** `TestXxx(t *testing.T)` + `if got!=want { t.Errorf }`;Go 刻意不内置断言库(避免 DSL 滥用),要省事用 testify。
- **table-driven 是什么?** 用例表 + 循环 + `t.Run` 子测试;加 case 只加一行、失败精确定位、可单独跑。Go 最核心测试惯用法。
- **`t.Error` vs `t.Fatal`?** Error 记录后继续;Fatal 立即停(只能在测试 goroutine 调)。前置用 Fatal、值断言用 Error。
- **`t.Parallel` 注意?** 标记并行、父返回后一起跑;1.22 前循环变量要 `tc:=tc` 拷贝(1.22 修复);需无共享状态 + `-race`。
- **`t.Helper` / `t.Cleanup`?** Helper 让错误行号指向调用处;Cleanup 注册 LIFO 清理(可在辅助函数注册、对齐子测试生命周期)。
- **golden file / testdata?** 大输出存 `testdata/`(工具链忽略该目录)、`-update` 重生;结构体比较用 `cmp.Diff`。
- **黑盒 vs 白盒测试?** `package xxx_test`(只测导出 API)vs 同包(测未导出)。

---

## 7. 一句话总结

> **Go 测试就是普通代码:`TestXxx(t *testing.T)` + `if got!=want { t.Errorf }`,标准库刻意不带断言库(嫌啰嗦用 testify)。** 核心惯用法是 **table-driven**:用例表 + 循环 + `t.Run` 子测试(加 case 一行、失败精确定位、可单独跑)。要点:`t.Error`(继续)vs `t.Fatal`(立停,只在测试 goroutine);`t.Parallel`(并行,1.22 前循环变量要拷贝);`t.Helper`(错误指向调用处);`t.Cleanup`/`t.TempDir`/`t.Setenv`(自动清理);`TestMain`(包级 setup);大输出用 `testdata/` golden file + `-update`,结构体比较用 `cmp.Diff`。测试要确定、隔离、可并行 + `-race`。

下一章 → [`01 mock 与接口`](../01-mock-interfaces/README.md):要测一个依赖数据库/HTTP 的函数怎么办?Go 的答案是「小接口 + 依赖注入」——以及手写 fake vs gomock 的取舍。｜ 回 [`testing` 索引](../README.md)
