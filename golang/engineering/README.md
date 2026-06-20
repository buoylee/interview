# Go 工程化与工具链 —— 给 Java 后端的「可复现构建 + 目录即边界」

> C 层(工程化与架构)第一条。Go 的工程化哲学是**确定性 + 简单**:依赖解析用 **MVS(最小版本选择)**让构建可复现(和 Maven/npm 的「装最新」截然不同)、`internal/` 用**目录**强制可见性边界、工具链开箱即用。这些是架构师面试的「软实力硬考点」。
>
> 总钥匙:**MVS 让构建可复现、`internal/` 用目录强制边界、工具链(fmt/vet/lint/race)开箱即用。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-engineering-track-design.md`｜Go 版本基线 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` modules 与依赖(MVS 重头),`01` 项目结构与构建(`internal`/build tags/embed/交叉编译),`02` 工具链。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(Maven/Gradle、package-private、JPMS)、**Python**(pip/poetry/venv)。重点 **MVS vs Maven nearest-wins/npm latest**。
4. **想答面试**：去 `99-interview-cards/` 找卡。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-modules/`](00-modules/) | modules 与依赖 | go.mod / 语义版本 + v2+ 导入路径 / **MVS 最小版本选择** / go.sum / replace / vendor / workspace ← 从这开始 |
| [`01-project-build/`](01-project-build/) | 项目结构与构建 | layout / **`internal/` 强制可见性** / build tags `//go:build` + GOOS/GOARCH / embed / 交叉编译 / CGO |
| [`02-toolchain/`](02-toolchain/) | 工具链 | go vet / staticcheck·golangci-lint / go generate / race detector / gofmt·goimports |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-engineering-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-modules | ✅ | go.mod / 语义导入版本 / **MVS** / go.sum / replace·vendor·workspace |
| 01-project-build | ✅ | layout / **internal 强制可见性** / build tags / embed / 交叉编译 / CGO |
| 02-toolchain | ✅ | gofmt / vet / staticcheck·golangci-lint / race / generate / govulncheck |
| 99-interview-cards | ✅ | 速答表(22 条) + 4 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- pprof/trace/race **机制** → `performance-tuning-roadmap/05a-go-profiling/`、`05b-go-debugging/`、[`concurrency/06`](../concurrency/06-sync-memory-model/README.md)(本 track 只讲工程上怎么接)
- 测试工具(go test/benchmark)→ [`testing/`](../testing/)(待建)
- `java/` — Maven/Gradle 依赖管理对标锚点

← 回 [`golang/` master 索引](../README.md)
