# table-driven、子测试、t.Parallel/Cleanup

## 一句话回答

Go 测试就是普通代码:`TestXxx(t *testing.T)` + `if got != want { t.Errorf(...) }`(**标准库刻意不带断言库**,嫌啰嗦用 testify)。最核心的惯用法是 **table-driven**:一张用例表(`[]struct{name; input; want}`)+ 循环 + `t.Run(tc.name, ...)` 子测试——加 case 只加一行、失败时精确定位、还能单独跑 `go test -run TestX/case`。

## 关键 API

```go
for _, tc := range tests {
    t.Run(tc.name, func(t *testing.T) {
        t.Parallel()                 // 并行(1.22 前循环变量要 tc:=tc)
        if got := F(tc.in); got != tc.want { t.Errorf("...") }
    })
}
```

- **`t.Error`(继续)vs `t.Fatal`(立即停,只能在测试 goroutine 调)**:前置条件用 Fatal,值断言用 Error。
- **`t.Parallel`**:标记并行、父返回后一起跑;需无共享状态 + `-race`;1.22 前要 `tc := tc` 拷贝循环变量。
- **`t.Helper()`**:让失败行号指向**调用处**(抽断言辅助函数必加)。
- **`t.Cleanup(fn)`**:注册 LIFO 清理,可在辅助函数里注册、对齐子测试生命周期(优于散落的 defer);配 `t.TempDir()`/`t.Setenv()`。
- **golden file**:大输出存 `testdata/`(工具链忽略该目录)+ `-update` 重生;结构体比较用 `google/go-cmp` 的 `cmp.Diff`。

## 证据链接

- 正文:[`00 单元测试基础`](../00-unit-testing/README.md);循环变量 [`type-system`/concurrency 04]

## 易追问的延伸

- **为什么 Go 不内置断言库?** 避免断言 DSL 滥用;`if` + 清晰错误信息更直接。
- **TestMain?** 包级 setup/teardown 入口(`m.Run()`),集成测试起容器用。
- **黑盒 vs 白盒?** `package xxx_test` 只测导出 API;同包能测未导出。
- **和 JUnit?** table-driven ≈ `@ParameterizedTest`,但更显式零依赖;Go 无 `@BeforeEach`(用 Cleanup/TestMain/辅助函数)。
