# 00 · modules 与依赖:MVS、go.sum、replace/vendor/workspace

> 依赖管理是架构师面试的硬考点,而 Go 的 **MVS(最小版本选择)** 和你熟悉的 Maven/npm **截然相反**——它选**满足约束的最小版本**而非最新,从而构建天然可复现。讲清 MVS,这章就赢一半。
>
> 桥接锚点:Maven「nearest-wins + 倾向较新」、npm「装最新兼容版 + lock 文件兜底」←→ Go「MVS 选最小可行版本,go.mod 本身就确定、go.sum 只做校验」。

---

## 1. 核心问题

```
你的模块 require A v1.2.0
A 又 require B v1.1.0
另一个依赖 C require B v1.3.0
→ 最终用哪个版本的 B?
```

- Go 怎么解析这张依赖图、选哪个版本?和 Maven/npm 一样选最新吗?
- `go.sum` 是 lock 文件吗?没有它能可复现吗?
- `replace`/`vendor`/`workspace` 各解决什么问题?

---

## 2. 直觉理解

### MVS:选「满足所有要求的最小版本」

Go 的算法叫 **Minimal Version Selection**。规则反直觉但简单:对每个依赖,收集**所有**模块对它的版本要求,选其中**最高的那个「被要求的版本」**——但**绝不超过**任何人的要求去拿更新的。

上面那题:B 被要求 v1.1.0 和 v1.3.0 → MVS 选 **v1.3.0**(两个要求里更高的那个,刚好满足两者)。它**不会**去拿 v1.4.0(没人要求)。

对比:

| | 选版本策略 |
|---|---|
| **Maven** | nearest-wins(依赖树最近的赢)+ 倾向较新,易冲突 |
| **npm** | 装满足范围的**最新**版,靠 lock 文件锁定 |
| **Go MVS** | 选**满足所有要求的最小版本**(被要求版本的最大值);不主动求新 |

### 为什么这设计能「可复现」

因为 MVS **不主动拿更新版本**:只要 go.mod 里的 require 不变,今天和一年后解析出的版本**完全一样**——`go.mod` 本身就是确定的构建清单,不需要额外的 lock 文件来「锁住飘移」。「想升级」是你**显式** `go get` 改 go.mod 的动作,而不是构建时自动发生。这是 Go「确定性优先」哲学的体现。

### go.sum 不是 lock,是「校验和」

既然 go.mod + MVS 已经确定了版本,`go.sum` 不负责选版本——它存每个依赖的**加密校验和**,用于**完整性校验**(防止依赖内容被篡改/镜像投毒)。下次拉取时比对 hash,不一致就报错。所以:**版本由 go.mod 定,内容由 go.sum 验**。

---

## 3. 原理深入

### 3.1 go.mod 的构成

```go.mod
module github.com/me/app      // 模块路径(= 导入前缀)
go 1.22                       // 语言版本(影响语法/行为)
toolchain go1.22.3            // (1.21+) 期望的 Go 工具链版本

require (
    github.com/foo/bar v1.4.0
    golang.org/x/sync v0.7.0  // indirect 表示间接依赖
)
replace github.com/foo/bar => ../bar-fork   // 重定向
exclude github.com/bad/dep v1.0.0           // 排除某版本
retract v1.3.0                              // 声明本模块某版本作废
```

### 3.2 语义版本 + 语义导入版本(v2+ 的坑)

Go 用 SemVer(`vMAJOR.MINOR.PATCH`),并强制**语义导入版本**:**主版本 ≥ 2 必须把 `/vN` 写进模块路径和导入路径**:

```go
require github.com/foo/bar/v2 v2.1.0       // 路径里有 /v2
import "github.com/foo/bar/v2"             // 导入也带 /v2
```

理由:不同主版本被当作**不同模块**,可以**共存**(你的依赖图里 v1 和 v2 同时存在不冲突)。这避免了 Java「diamond dependency 版本冲突地狱」的一大类问题。

### 3.3 indirect 与模块图裁剪

- `// indirect`:不是你直接 import、但依赖链需要的模块(`go mod tidy` 维护)。
- **模块图裁剪(graph pruning,1.17+)**:go.mod 记录足够的间接依赖,使解析只需加载相关模块的 go.mod,而非整个传递闭包——加快解析、缩小图。

### 3.4 replace / vendor / workspace 三件套

- **replace**:把某模块路径/版本**重定向**到另一个(本地路径或 fork)。用于:调试本地改的依赖、临时打补丁、私有 fork。`replace` 只在**主模块**生效(不传染给引用你的人)。
- **vendor**:`go mod vendor` 把所有依赖源码**拷进 `vendor/` 目录**,构建用 `-mod=vendor`。用于:离线/隔离构建、审计依赖、不信任代理。代价是仓库变大。
- **workspace**(1.18,`go.work`):多模块**本地联合开发**。以前要在每个 go.mod 写 `replace ../other` 互相指,现在一个 `go.work` 列出本地模块目录即可,**不污染 go.mod**:
  ```
  go work init ./app ./lib    // go.work 引用多个本地模块
  ```

### 3.5 常用命令

```bash
go get foo@v1.5.0        # 显式升级/降级某依赖(改 go.mod)
go get -u ./...          # 升级到较新的次/补丁版本
go mod tidy              # 补齐缺失 + 删除未用依赖,整理 go.mod/go.sum
go mod download         # 下载到模块缓存
go mod why github.com/x # 为什么需要这个依赖(谁引入的)
go mod graph            # 打印依赖图
```

GOPROXY(默认 proxy.golang.org)、GOSUMDB(校验和数据库 sum.golang.org)、GOPRIVATE(私有模块跳过代理/校验)。

---

## 4. 日常开发应用

- **加依赖**:直接 `import` 后 `go mod tidy`,或 `go get foo@version`。
- **升级要显式**:MVS 不会自动给你升;`go get -u` 或指定版本。升完跑测试 + `go mod tidy`。
- **本地联调多模块用 `go.work`**(别再手写一堆 `replace`)。
- **打补丁/调试依赖用 `replace`**(临时,合并前清掉)。
- **v2+ 库**:发布和引用都记得带 `/v2`。
- **私有模块**:设 `GOPRIVATE=git.company.com/*` 跳过公共代理和校验。

---

## 5. 生产&调优实战

- **构建可复现是 MVS 的最大生产价值**:CI 与本地、今天与明天解析出相同版本,无需「锁文件防飘移」。别用 `go get -u` 进 CI(那会引入非确定升级)。
- **`go.sum` 必须提交**:它是供应链安全的校验底座;CI 用 `GOFLAGS=-mod=readonly`(默认)防止构建偷偷改 go.mod/go.sum。
- **`replace` 别带进发布**:replace 只对主模块生效,但留在 go.mod 里会让协作者困惑;发布前清理。
- **vendor 用于强隔离/审计**:监管或离线环境把依赖 vendor 进仓库,构建不依赖外网;权衡是仓库膨胀 + 升级要重新 vendor。
- **依赖供应链**:GOSUMDB 校验防篡改;`govulncheck` 扫已知漏洞(Go 官方漏洞库),建议进 CI。

---

## 6. 面试高频考点

- **Go 怎么选依赖版本?和 Maven/npm 区别?** **MVS 最小版本选择**:取所有要求里「被要求版本的最大值」,绝不主动拿更新的。Maven nearest-wins+倾向新、npm 装最新+lock;Go 不主动求新,故 go.mod 本身可复现。
- **B 被要求 v1.1 和 v1.3,选哪个?** v1.3(两要求里更高那个,满足两者);不会拿 v1.4(没人要求)。
- **go.sum 是 lock 文件吗?** 不是。版本由 go.mod + MVS 确定;go.sum 是**校验和**,做完整性校验(防篡改),必须提交。
- **为什么 v2+ 要把 /vN 写进路径?** 语义导入版本:不同主版本视为不同模块、可共存,避免主版本冲突。
- **replace/vendor/workspace 区别?** replace 重定向某依赖(调试/fork,只对主模块);vendor 把依赖拷进仓库(离线/审计);workspace(go.work)多模块本地联合开发不污染 go.mod。
- **怎么升级依赖?** 显式 `go get foo@v` 或 `go get -u`,再 `go mod tidy` + 测试;MVS 不自动升。
- **indirect 是什么?** 间接依赖(非你直接 import),`go mod tidy` 维护。

---

## 7. 一句话总结

> **Go 依赖管理的核心是 MVS(最小版本选择):选「所有要求里被要求版本的最大值」,绝不主动拿更新的——所以 go.mod 本身就确定、构建天然可复现,升级是你显式 `go get` 的动作而非构建时自动发生**(与 Maven nearest-wins、npm 装最新+lock 截然不同)。`go.sum` 不是锁文件而是**校验和**(防篡改,必须提交);版本由 go.mod 定、内容由 go.sum 验。主版本 ≥2 要把 `/vN` 写进路径(语义导入版本,使多主版本共存)。三件套:`replace` 重定向依赖(调试/fork)、`vendor` 拷依赖进仓库(离线/审计)、`go.work` 多模块本地联合开发(不污染 go.mod)。

下一章 → [`01 项目结构与构建`](../01-project-build/README.md):代码怎么分层?`internal/` 为什么是编译器强制的边界?怎么用 build tags 做多平台、用 embed 把文件打进二进制。｜ 回 [`engineering` 索引](../README.md)
