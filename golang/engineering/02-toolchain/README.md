# 02 · 工具链:vet、staticcheck/golangci-lint、generate、race

> Go 的工具链「开箱即用」是它工程化的一大卖点:格式化、静态检查、竞态检测、代码生成都内置或一条命令。架构师面试会问「**团队该上哪些工具、怎么接 CI**」。本章给一份实用清单。
>
> 桥接锚点:Java 要拼 Checkstyle/SpotBugs/PMD/Maven 插件;Go 一个 `go vet` + `golangci-lint` + `go test -race` 基本覆盖,且格式由 `gofmt` **统一强制**(没有「大括号换不换行」之争)。

---

## 1. 核心问题

- 代码风格谁来统一?Go 有没有「格式之争」?
- `go vet` 和 `staticcheck`/`golangci-lint` 都查什么?有什么区别?
- 怎么自动发现并发数据竞争?`go generate` 又是干嘛的?
- 这些工具怎么接进 CI、形成团队规范?

---

## 2. 直觉理解

### 一张工具速览表

| 工具 | 干什么 | 何时跑 |
|---|---|---|
| **gofmt / goimports** | 统一格式 + 整理 import | 保存时 / 提交前 |
| **go vet** | 官方静态检查(printf、copylocks、lostcancel…) | 提交前 / CI |
| **staticcheck** | 更强的静态分析(死代码、bug 模式、简化建议) | CI |
| **golangci-lint** | **聚合**多个 linter 的元工具(含上面 + 几十个) | CI 主力 |
| **go test -race** | 运行期竞态检测 | 测试 / CI |
| **go generate** | 触发代码生成(mock/stringer/protobuf) | 手动 / 提交前 |
| **govulncheck** | 扫已知漏洞依赖 | CI |

### Go 没有格式之争

`gofmt` 是**官方唯一格式**,大家都用、不可配置风格——所以 Go 代码库风格高度一致,code review 不浪费在格式上。这是刻意的文化:「**有一种格式,就是 gofmt 的格式**」。

---

## 3. 原理深入

### 3.1 gofmt / goimports

```bash
gofmt -l -w .        # 列出并重写不合规文件
goimports -w .       # gofmt + 自动增删/排序 import
```

`goimports` 是 gofmt 超集,额外管 import。编辑器保存时自动跑是标配。

### 3.2 go vet:官方的「正确性」静态检查

`go vet` 查**容易出错但能编过**的问题:

- `printf` 格式串与参数不匹配(`%d` 配了 string);
- **copylocks**:拷贝了含 `sync.Mutex` 的结构体(见 [`type-system/02`](../../type-system/02-method-sets/README.md));
- **lostcancel**:`context` 的 cancel 没调用(见 [`concurrency/07`](../../concurrency/07-context/README.md));
- 结构体 tag 格式错、不可达代码、`%w` 误用等。

`go test` 默认会跑一部分 vet。它**保守**(只报高把握问题),所以补 staticcheck/golangci-lint。

### 3.3 staticcheck 与 golangci-lint

- **staticcheck**(honnef.co/go/tools):社区最强单体静态分析——死代码、冗余、bug 模式、可简化写法,误报低、价值高。
- **golangci-lint**:**元 linter**,并行跑一组 linter(vet、staticcheck、errcheck、ineffassign、gosec、revive…),一份 `.golangci.yml` 配置统一管。**团队 CI 用它当主力**:

```yaml
# .golangci.yml(节选)
linters:
  enable: [staticcheck, errcheck, govet, ineffassign, gosec]
```

```bash
golangci-lint run ./...
```

### 3.4 race detector

```bash
go test -race ./...      # 测试时插桩检测数据竞争
go build -race           # 构建带竞态检测的二进制(压测环境用)
```

原理:编译期插桩内存访问,运行期用 happens-before 算法检测「无同步的并发读写同一地址」(见 [`concurrency/06`](../../concurrency/06-sync-memory-model/README.md))。**只能发现实际执行到的竞争**(动态检测,非静态),所以要配合有并发覆盖的测试/压测。开销大(慢几倍、内存涨),只在测试/预发用,**别上生产**。

### 3.5 go generate

```go
//go:generate mockgen -source=repo.go -destination=mock_repo.go
//go:generate stringer -type=Color
```

```bash
go generate ./...        # 扫描 //go:generate 指令并执行
```

`go generate` **不是构建的一部分**——它是你手动触发、把生成的代码**提交进仓库**的机制。常用于:mock(mockgen)、枚举字符串(stringer)、protobuf(protoc-gen-go)、wire 依赖注入。生成的代码进版本库,构建时当普通代码编(见 [`generics/02`](../../generics/02-when-to-use/README.md):泛型替代了「为类型生成」,generate 留给「为元数据生成」)。

---

## 4. 日常开发应用

- **编辑器保存自动跑 `goimports`**:格式 + import 永远干净。
- **本地提交前**:`go vet ./...` + `golangci-lint run`(或 pre-commit hook)。
- **并发代码必跑 `-race`**:写并发就配能触发竞争的测试,`go test -race`。
- **mock/枚举用 `go generate`** 生成并提交,别手写样板。
- **统一 `.golangci.yml`** 进仓库,团队共享同一套规则。

---

## 5. 生产&调优实战

- **CI 流水线建议顺序**:`gofmt -l`(格式 gate,有差异就 fail)→ `go vet` → `golangci-lint run` → `go test -race -cover` → `govulncheck`。前面快的先跑、快速失败。
- **race 在 CI/预发跑,不上生产**:开销大;但 CI 的 `-race` 测试 + 压测能抓住绝大多数并发 bug(map 并发 fatal、data race)。
- **govulncheck 接 CI**:扫 go.sum 里的已知漏洞(Go 官方漏洞库),供应链安全基线(配合 [`00 modules`](../00-modules/README.md) 的 GOSUMDB)。
- **lint 规则渐进收紧**:老项目一次开全部 linter 会爆几千告警;先开核心(vet/staticcheck/errcheck),逐步加严,新代码严格、存量豁免。
- **生成代码标记**:生成文件带 `// Code generated ... DO NOT EDIT.` 头,lint/diff 工具会识别、不计入人工审查。

---

## 6. 面试高频考点

- **Go 怎么统一代码风格?** `gofmt` 官方唯一格式、不可配置——没有格式之争;`goimports` 额外管 import。
- **go vet 查什么?** 官方正确性静态检查:printf 不匹配、copylocks(拷贝锁)、lostcancel(漏 cancel)、tag 错等;保守、高把握。
- **staticcheck / golangci-lint 区别?** staticcheck 是强单体静态分析;golangci-lint 是**聚合多 linter 的元工具**,团队 CI 主力,一份配置统管。
- **怎么检测数据竞争?** `go test -race`/`go build -race`,编译期插桩 + 运行期 happens-before 检测;**动态检测**(只发现执行到的竞争),开销大、不上生产。
- **go generate 是构建的一部分吗?** 不是——手动触发生成代码并提交进仓库(mock/stringer/protobuf);构建时当普通代码。
- **团队该上哪些工具/CI 怎么接?** gofmt gate → vet → golangci-lint → test -race -cover → govulncheck。
- **和 Java 工具链对比?** Java 拼 Checkstyle/SpotBugs/PMD;Go 内置 fmt/vet/race + golangci-lint 基本覆盖,且格式强制统一。

---

## 7. 一句话总结

> **Go 工具链开箱即用且强制统一:`gofmt`(唯一官方格式,没有格式之争)+ `goimports`(管 import)、`go vet`(官方正确性检查:printf/copylocks/lostcancel)、`staticcheck`(强静态分析)、`golangci-lint`(聚合多 linter 的 CI 主力,一份 `.golangci.yml` 统管)、`go test -race`(编译插桩+运行期 happens-before 的动态竞态检测,开销大不上生产)、`go generate`(手动触发、生成代码提交进仓库,如 mock/stringer/protobuf)、`govulncheck`(扫已知漏洞)。** CI 顺序:fmt gate → vet → lint → test -race -cover → vulncheck。对比 Java 要拼一堆插件,Go 一套工具基本覆盖、风格还高度一致。

← 上一章 [`01 项目结构与构建`](../01-project-build/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):MVS、replace·vendor·workspace、internal·build tags、工具链速查。｜ 回 [`engineering` 索引](../README.md)
