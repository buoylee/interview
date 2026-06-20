# 99 · 面试卡 —— Go 工程化与工具链高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**MVS 让构建可复现、`internal/` 用目录强制边界、工具链开箱即用。**

## 卡片索引(深题卡)

- [MVS 最小版本选择(vs Maven/npm)+ 语义导入版本](q-mvs.md)
- [replace / vendor / workspace / go.sum](q-modules-tooling.md)
- [internal 可见性 + build tags + embed](q-internal-build.md)
- [工具链:vet / golangci-lint / race / generate](q-toolchain.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| Go 怎么选依赖版本 | MVS:取所有要求里被要求版本的最大值,绝不主动拿更新的 | [00](../00-modules/README.md) |
| MVS vs Maven/npm | Maven nearest+倾向新;npm 装最新+lock;Go 不主动求新,go.mod 本身可复现 | [00](../00-modules/README.md) |
| go.sum 是 lock 吗 | 不是;版本由 go.mod+MVS 定,go.sum 是校验和(防篡改),必须提交 | [00](../00-modules/README.md) |
| v2+ 为什么进路径 | 语义导入版本:不同主版本视为不同模块、可共存 | [00](../00-modules/README.md) |
| replace | 重定向某依赖(调试/fork),只对主模块生效 | [00](../00-modules/README.md) |
| vendor | go mod vendor 把依赖拷进仓库(离线/审计),-mod=vendor 构建 | [00](../00-modules/README.md) |
| workspace | go.work 多模块本地联合开发,不污染 go.mod(取代一堆 replace) | [00](../00-modules/README.md) |
| 怎么升级依赖 | 显式 go get foo@v / go get -u + go mod tidy;MVS 不自动升 | [00](../00-modules/README.md) |
| Go 项目 layout | 无官方强制;cmd/internal/pkg 惯例;扁平按领域分包 | [01](../01-project-build/README.md) |
| internal/ 特殊在 | 编译器强制:只能被父目录子树 import,外部模块不能;子系统封闭边界 | [01](../01-project-build/README.md) |
| 按平台编译 | 文件名后缀(foo_linux.go)或 //go:build 约束;自定义 tag 隔离集成测试 | [01](../01-project-build/README.md) |
| //go:build vs +build | 新语法布尔表达式更清晰(1.17+);gofmt 同步 | [01](../01-project-build/README.md) |
| embed | //go:embed 把文件/目录(embed.FS)编进二进制,运行时不依赖外部文件 | [01](../01-project-build/README.md) |
| 交叉编译 | GOOS=.. GOARCH=.. go build,纯 Go 零额外工具 | [01](../01-project-build/README.md) |
| CGO_ENABLED=0 | 出完全静态二进制,可进 scratch/distroless;代价用不了 cgo 库 | [01](../01-project-build/README.md) |
| 代码风格统一 | gofmt 官方唯一格式不可配置(无格式之争);goimports 管 import | [02](../02-toolchain/README.md) |
| go vet 查什么 | printf/copylocks/lostcancel/tag 错等正确性问题,保守高把握 | [02](../02-toolchain/README.md) |
| staticcheck vs golangci-lint | 前者强单体分析;后者聚合多 linter 的元工具,CI 主力 | [02](../02-toolchain/README.md) |
| 检测数据竞争 | go test -race,编译插桩+运行期 happens-before;动态、开销大不上生产 | [02](../02-toolchain/README.md) |
| go generate | 手动触发生成代码并提交(mock/stringer/protobuf),非构建一部分 | [02](../02-toolchain/README.md) |
| CI 怎么接 | fmt gate→vet→golangci-lint→test -race -cover→govulncheck | [02](../02-toolchain/README.md) |

← 回 [`engineering` 索引](../README.md)
