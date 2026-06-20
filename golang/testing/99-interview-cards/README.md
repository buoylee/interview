# 99 · 面试卡 —— Go 测试工程高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**测试即普通代码;table-driven + 子测试是惯用法;可测性靠小接口 + DI;benchmark/fuzz/coverage 内置。**

## 卡片索引(深题卡)

- [table-driven、子测试、t.Parallel/Cleanup](q-table-driven.md)
- [mock 与接口:小接口 + DI 做可测](q-mock-interfaces.md)
- [benchmark、fuzzing、集成测试](q-benchmark-fuzz.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| Go 测试怎么写 | TestXxx(t *testing.T) + `if got!=want { t.Errorf }`;无 stdlib 断言库 | [00](../00-unit-testing/README.md) |
| 为什么没断言库 | 刻意避免 DSL 滥用;要省事用 testify(assert 继续/require 即停) | [00](../00-unit-testing/README.md) |
| table-driven | 用例表 + 循环 + t.Run 子测试;加 case 一行、失败精确定位、可单独跑 | [00](../00-unit-testing/README.md) |
| t.Error vs t.Fatal | Error 记录后继续;Fatal 立即停(只能测试 goroutine);前置用 Fatal 值断言用 Error | [00](../00-unit-testing/README.md) |
| t.Parallel 注意 | 并行、父返回后跑;1.22 前循环变量要 tc:=tc;需无共享状态 + -race | [00](../00-unit-testing/README.md) |
| t.Helper / t.Cleanup | Helper 让错误行号指向调用处;Cleanup 注册 LIFO 清理(可在辅助函数注册) | [00](../00-unit-testing/README.md) |
| golden file / testdata | 大输出存 testdata(工具链忽略该目录)+ -update 重生;结构体比较用 cmp.Diff | [00](../00-unit-testing/README.md) |
| 黑盒 vs 白盒测试 | package xxx_test(只测导出) vs 同包(测未导出) | [00](../00-unit-testing/README.md) |
| Go 怎么 mock | 消费方定义小接口 + DI,测试传 fake(普通 struct);不靠反射 | [01](../01-mock-interfaces/README.md) |
| 接口为什么小+消费方定义 | 隐式实现 + 只声明用到的方法 → mock 易、不耦合大类型;接受接口返结构体 | [01](../01-mock-interfaces/README.md) |
| fake vs stub vs mock | fake=简化真实行为(推荐);stub=写死返回;mock=断言交互(易脆);Go 偏 fake | [01](../01-mock-interfaces/README.md) |
| 手写 fake vs gomock | 接口小手写 fake;方法多/要验证调用次数用 gomock+mockgen | [01](../01-mock-interfaces/README.md) |
| 怎么测 HTTP | httptest:NewRecorder 测 handler、NewServer 起假上游测 client | [01](../01-mock-interfaces/README.md) |
| 怎么测 DB 不连真库 | sqlmock 在 database/sql 层拦截断言 SQL;真库留集成测试 | [01](../01-mock-interfaces/README.md) |
| benchmark / b.N | BenchmarkXxx 循环 b.N(框架自适应);-benchmem 看 B/op·allocs/op;ResetTimer 排除 setup | [02](../02-benchmark-fuzz-integration/README.md) |
| 可信比较性能 | 多次 -count + benchstat 显著性;别单次;防 dead-code 消除 | [02](../02-benchmark-fuzz-integration/README.md) |
| fuzzing | FuzzXxx(f)+f.Add 种子+f.Fuzz 回调;变异找 panic/边界;崩溃语料存 testdata/fuzz | [02](../02-benchmark-fuzz-integration/README.md) |
| 集成测试隔离 | //go:build integration 分流 + testcontainers 起真依赖;TestMain 初始化 | [02](../02-benchmark-fuzz-integration/README.md) |
| coverage 怎么看 | -cover/-coverprofile + cover -html;-coverpkg 跨包;是参考非目标 | [02](../02-benchmark-fuzz-integration/README.md) |

← 回 [`testing` 索引](../README.md)
