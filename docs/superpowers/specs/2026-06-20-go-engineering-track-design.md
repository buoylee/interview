# Go 工程化与工具链 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/engineering/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）
> 性质：C 层(工程化与架构)第一条。

## 背景与目标

工程化是架构师面试的「软实力硬考点」:**go modules 怎么解析依赖(MVS 最小版本选择——和 Maven/npm 截然不同)**、**项目怎么分层(`internal/` 是编译器强制的可见性边界)**、**build tags/交叉编译/embed**、**工具链(vet/staticcheck/golangci-lint/race)**。用户从 Java(Maven/Gradle)来,MVS 与「nearest/latest wins」的对比是最大认知差。

目标:读完能讲清 MVS 为什么可复现、`internal/` 的强制可见性、build constraint 怎么做多平台、团队该上哪些工具。

## 核心设计决策

- **形式**：3 章,照搬已认可模板(7 段 + `99-interview-cards/`)。
- **主线钥匙 = 「Go 的工程化追求确定性与简单:MVS 让构建可复现、`internal/` 用目录强制边界、工具链开箱即用」**。
- **双向桥**：Maven/Gradle(pom、nearest/latest 解析、Central)、Java 可见性(package-private、JPMS)、Python(pip/poetry/venv)。重点对比 **MVS vs Maven nearest-wins/npm latest**。
- **底层内幕进正文**:MVS 算法(取所有要求里的最大「最小版本」、可复现)、语义导入版本(v2+ 进路径)、go.sum 是校验和非锁文件、replace/vendor/workspace 各自定位、`internal/` 编译器强制规则、build constraint 新语法 `//go:build` + 文件名后缀、embed.FS、CGO_ENABLED 与静态编译。
- **Go 版本**:1.22+;workspace 1.18、`//go:build` 1.17、embed 1.16、toolchain 指令 1.21。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-modules/` | modules 与依赖 | go.mod / 语义版本 + 语义导入版本(v2+)/ **MVS 最小版本选择** / go.sum 校验 / replace / vendor / workspace / tidy·get |
| `01-project-build/` | 项目结构与构建 | layout(cmd/internal/pkg)/ **`internal/` 编译器强制可见性** / build tags(`//go:build`)+ GOOS/GOARCH 后缀 / embed / 交叉编译 / CGO_ENABLED |
| `02-toolchain/` | 工具链 | go vet / staticcheck·golangci-lint / go generate / race detector / gofmt·goimports / pprof 集成 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡(MVS、replace·vendor·workspace、internal·build tags、工具链) |

## 已有素材的处理

- pprof/race 工具**机制**链接 `performance-tuning-roadmap/05a·05b` 与 [`concurrency/06`](-race),本 track `02` 只讲「工程上怎么用、CI 怎么接」,不重讲原理。
- 测试工具(go test/benchmark)归 [`testing/`](../testing/) track,本 track `02` 只点到 race 与 generate,详细测试链过去。
- 现有顶层 stub `base.md`(22 行,Go 设计/面试链接)后续并入 master 外部参考或本 track,本次先不动(下条 track 处理)。

## 交付节奏

1. 写本 spec。2. 骨架 README + 3 章目录。3. 写 00(modules,MVS 重头)确认,推进 01/02 + 面试卡。

## 验收标准

- 00 能讲清 MVS 怎么选版本、为什么可复现、和 Maven/npm 的区别,以及 v2+ 为什么要进导入路径。
- 01 能讲 `internal/` 的强制规则、build constraint 怎么做多平台、embed 用法。
- 02 能列出团队该上的工具(fmt/vet/golangci-lint/race)和 CI 接法。

## 非目标（YAGNI）

- 不重讲 pprof/trace/GC 原理(链 perf-roadmap)。
- 不展开 CI/CD 平台细节、不展开 Docker 构建(归 cloud-native/其它 track)。
- 不逐一讲每个 linter 规则。
