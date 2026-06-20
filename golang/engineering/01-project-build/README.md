# 01 · 项目结构与构建:internal、build tags、embed、交叉编译

> 「你怎么组织一个 Go 项目?」是架构师面试常问的。Go 的关键是:**`internal/` 是编译器强制的可见性边界**(不是约定)、**build tags/文件名后缀**做多平台、**embed** 把资源打进单一二进制、**交叉编译**一条命令出各平台。
>
> 桥接锚点:Java 靠 `public`/`protected`/package-private + JPMS 管可见性、Maven 多模块管结构;Go 用**目录(`internal/`)+ 大小写**管可见性,结构更轻。Java 打 jar 要带依赖,Go 默认编出**单一静态二进制**。

---

## 1. 核心问题

- Go 项目该怎么分目录?有没有官方强制的 layout?
- `internal/` 这个目录名有什么魔力?和大小写导出有什么关系?
- 同一份代码要在 Linux/Windows/不同架构编译,怎么按平台切代码?
- 配置文件/模板怎么打进二进制,不用随程序带一堆文件?

---

## 2. 直觉理解

### 可见性有两层:大小写 + internal 目录

- **第一层(包内→包外):大小写**。标识符首字母大写 = 导出(public),小写 = 包私有。这是最基本的边界。
- **第二层(模块内的子树):`internal/` 目录**。放在 `internal/` 下的包,**只能被 `internal/` 父目录为根的子树**导入,外部模块**无法 import**——而且这是**编译器强制**的,不是文档约定。

```
github.com/me/app/
├── internal/
│   └── auth/          // 只有 github.com/me/app/... 内部能 import
└── pkg/
    └── client/        // 任何人都能 import(对外 API)
```

所以 `internal/` 是「**我想复用但不想成为公共 API**」的标准答案——比 Java 的 package-private 粒度更适合「整个子系统对外封闭、对内开放」。

### 没有官方强制 layout,但有社区惯例

Go 团队**不强制**目录结构(`golang-standards/project-layout` 是社区的、非官方)。常见惯例:

- `cmd/<appname>/main.go`:各可执行程序入口。
- `internal/`:私有实现(业务逻辑大多放这)。
- `pkg/`:想对外暴露的库代码(有争议,小项目可省)。
- 根目录:`go.mod`、README、主包。

原则:**扁平优先,按领域分包,别过早搞深层次目录**。

### 单一二进制 + 交叉编译

`go build` 默认编出**一个自包含的静态二进制**(纯 Go 时无需运行时/依赖库)——这是 Go 部署简单的核心优势(对比 Java 要 JVM + jar)。换平台只要改两个环境变量。

---

## 3. 原理深入

### 3.1 build constraints(build tags):按条件编译

两种方式让文件**只在特定条件下编译**:

**① 文件名后缀**(最简单):`foo_linux.go`、`foo_windows.go`、`foo_amd64.go`、`foo_linux_arm64.go`——编译器按 GOOS/GOARCH 自动只选匹配的。`xxx_test.go` 也是这套机制(只在测试时编)。

**② `//go:build` 指令**(1.17+ 新语法,放文件顶部、package 之前):

```go
//go:build linux && amd64
package foo
```

```go
//go:build integration        // 自定义 tag:go test -tags=integration 才编
package foo
```

> 旧语法 `// +build linux,amd64`(逗号=与、空格=或)已过时,新代码用 `//go:build`(布尔表达式更清晰);`gofmt` 会帮你同步两者。自定义 tag 常用于「集成测试」「特性开关」。

### 3.2 embed:把文件打进二进制(1.16+)

```go
import _ "embed"

//go:embed config.yaml
var configData []byte           // 单文件 → []byte 或 string

//go:embed templates/*.html static/*
var assets embed.FS             // 多文件/目录 → embed.FS(只读文件系统)
```

编译时把文件内容**嵌进二进制**,运行时不依赖外部文件。常用于:HTML 模板、静态资源、SQL 迁移脚本、默认配置——真正做到「一个二进制走天下」。

### 3.3 交叉编译

```bash
GOOS=linux  GOARCH=arm64 go build -o app-linux-arm64
GOOS=windows GOARCH=amd64 go build -o app.exe
go tool dist list            # 看支持的所有 GOOS/GOARCH 组合
```

纯 Go 代码交叉编译**零额外工具**(不像 C 要交叉工具链)。`go build` 还有构建缓存,增量编译快。

### 3.4 CGO 与静态二进制

```bash
CGO_ENABLED=0 go build       # 禁用 cgo → 纯静态二进制(无 libc 依赖)
```

- 默认 `CGO_ENABLED=1`(用到 C 时),会动态链接 libc,且**交叉编译需要交叉 C 工具链**。
- 设 `CGO_ENABLED=0`:得到**完全静态**二进制,能塞进 `scratch`/`distroless` 空镜像(容器部署最爱)、交叉编译也更省心。代价:用不了依赖 cgo 的库(如某些 sqlite 驱动、net 的 cgo 解析器)。

### 3.5 build cache

`go build`/`go test` 结果按内容哈希缓存(`go env GOCACHE`),未变的包不重编、测试结果可复用(`go clean -cache` 清)。

---

## 4. 日常开发应用

- **业务实现放 `internal/`**:除非你在写给别人用的库,默认把代码放 `internal/`,杜绝外部误用、保留重构自由。
- **每个可执行程序一个 `cmd/<name>/`**:main 薄、逻辑在 internal。
- **平台相关代码用文件名后缀**(`xxx_linux.go`)分文件,别在一个文件里 `runtime.GOOS` 到处 if。
- **集成测试用 `//go:build integration`** tag 隔离,平时 `go test` 不跑、CI 里 `-tags=integration` 跑。
- **资源用 embed** 打进二进制,简化部署。
- **容器构建 `CGO_ENABLED=0`** 出静态二进制 + distroless/scratch 镜像。

---

## 5. 生产&调优实战

- **`internal/` 是重构护城河**:放 internal 的包外部依赖不了,你能放心改签名/拆分——这对大型代码库的可演进性极重要,架构上要主动用。
- **静态二进制 + 空镜像**:`CGO_ENABLED=0` + `FROM scratch`/`distroless` 得到几 MB、攻击面极小的镜像;但注意时区、CA 证书、DNS 解析(纯 Go resolver)等需显式处理。
- **交叉编译进 CI**:一条流水线出多平台产物,无需多套构建机。
- **build tag 管特性开关**:用 tag 编译出「带/不带某功能」的变体(如开源版/企业版),比运行时开关更彻底。
- **embed 注意体积**:大资源嵌进二进制会让它变大、占内存;超大静态资源考虑外置 + CDN。
- **可复现构建**:固定 Go 版本(toolchain 指令)、`-trimpath` 去掉本地路径、`-ldflags` 注入版本号,利于审计与缓存。

---

## 6. 面试高频考点

- **Go 项目怎么组织?有官方 layout 吗?** 无官方强制(project-layout 是社区的)。惯例:`cmd/` 入口、`internal/` 私有实现、`pkg/` 对外库;扁平优先按领域分包。
- **`internal/` 有什么特殊?** 编译器强制:`internal/` 下的包只能被其父目录为根的子树 import,外部模块无法导入——比大小写更粗粒度的边界,适合「子系统对内开放对外封闭」。
- **怎么按平台编译不同代码?** 文件名后缀(`foo_linux.go`/`foo_amd64.go`)或 `//go:build` 约束;自定义 tag(`-tags=integration`)隔离集成测试。
- **`//go:build` 和旧 `// +build` 区别?** 新语法布尔表达式更清晰,1.17+ 推荐;gofmt 会同步。
- **embed 是什么?** `//go:embed` 把文件/目录(`embed.FS`)编进二进制,运行时不依赖外部文件。
- **怎么交叉编译?** `GOOS=... GOARCH=... go build`,纯 Go 零额外工具。
- **CGO_ENABLED=0 有什么用?** 出完全静态二进制,可进 scratch/distroless 空镜像、交叉编译更省心;代价是用不了 cgo 依赖库。
- **和 Java 部署对比?** Java 要 JVM + jar;Go 默认单一静态二进制,部署极简。

---

## 7. 一句话总结

> **Go 工程结构的核心边界是 `internal/`——编译器强制:其下的包只能被父目录子树 import,外部无法导入**,这是比大小写更粗的「子系统封闭」边界,也是大型库的重构护城河;layout 无官方强制(cmd/internal/pkg 是惯例,扁平按领域分包)。多平台用**文件名后缀**(`foo_linux.go`)或 **`//go:build` 约束**(自定义 tag 隔离集成测试);**embed** 把资源编进二进制;**交叉编译**靠 `GOOS/GOARCH` 一条命令、纯 Go 零额外工具;**`CGO_ENABLED=0`** 出完全静态二进制塞进 scratch/distroless 空镜像。一切服务于 Go「单一自包含二进制、部署极简」的优势(对比 Java 的 JVM+jar)。

← 上一章 [`00 modules 与依赖`](../00-modules/README.md) ｜ 下一章 → [`02 工具链`](../02-toolchain/README.md):团队该上哪些工具——vet/staticcheck/golangci-lint 静态检查、go generate、race detector,以及怎么接进 CI。｜ 回 [`engineering` 索引](../README.md)
