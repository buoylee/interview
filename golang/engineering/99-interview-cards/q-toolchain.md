# 工具链:vet / golangci-lint / race / generate

## 一句话回答

Go 工具链开箱即用且**格式强制统一**:**`gofmt`**(官方唯一格式、不可配置——没有格式之争)+ **`goimports`**(管 import);**`go vet`**(官方正确性静态检查:printf 不匹配、copylocks、lostcancel);**`staticcheck`**(更强的单体静态分析);**`golangci-lint`**(聚合多个 linter 的元工具,**团队 CI 主力**,一份 `.golangci.yml` 统管);**`go test -race`**(编译插桩 + 运行期 happens-before 的**动态**竞态检测,开销大、**不上生产**);**`go generate`**(手动触发生成代码并提交,如 mock/stringer/protobuf,**非构建一部分**);**`govulncheck`**(扫已知漏洞依赖)。

## CI 推荐顺序

```
gofmt -l(格式 gate)→ go vet → golangci-lint run → go test -race -cover → govulncheck
```

快的先跑、快速失败。

## 关键区分

- **vet vs golangci-lint**:vet 是官方、保守、高把握;golangci-lint 聚合 vet + staticcheck + errcheck + gosec… 是更全的 CI 主力。
- **race 是动态检测**:只能发现**实际执行到**的竞争,要配有并发覆盖的测试/压测;开销大(慢几倍)只在测试/预发。
- **generate 不是构建**:手动跑、产物提交进仓库,构建时当普通代码(泛型替代「为类型生成」,generate 留给「为元数据生成」)。

## 证据链接

- 正文:[`02 工具链`](../02-toolchain/README.md);race 原理 [`concurrency/06`](../../../concurrency/06-sync-memory-model/README.md);lostcancel [`concurrency/07`](../../../concurrency/07-context/README.md)

## 易追问的延伸

- **Go 为什么没有格式之争?** gofmt 是唯一官方格式、不可配置,文化即「有一种格式就是 gofmt 的」。
- **race 能上生产吗?** 不能,开销太大;CI/预发跑。
- **老项目一次开全 linter?** 会爆告警;先开核心(vet/staticcheck/errcheck)渐进收紧,新代码严、存量豁免。
- **govulncheck 干嘛?** 扫 go.sum 依赖的已知漏洞(Go 官方漏洞库),供应链安全基线。
- **和 Java 工具链比?** Java 拼 Checkstyle/SpotBugs/PMD;Go 一套内置 + golangci-lint 基本覆盖、风格统一。
