# internal 可见性 + build tags + embed

## 一句话回答

Go 的可见性有两层:**大小写**(首字母大写=导出/public,小写=包私有)+ **`internal/` 目录**(编译器强制:`internal/` 下的包**只能被其父目录为根的子树** import,外部模块**无法导入**)。多平台编译靠 **build constraints**:文件名后缀(`foo_linux.go`/`foo_amd64.go`)或 `//go:build` 指令(布尔表达式,1.17+;自定义 tag 如 `-tags=integration` 隔离集成测试)。**embed**(`//go:embed` + `embed.FS`,1.16+)把文件/目录编进二进制,运行时不依赖外部文件。

## internal 示例

```
github.com/me/app/
├── internal/auth/    # 只有 github.com/me/app/... 内部能 import,外部模块不能
└── pkg/client/       # 任何人可 import(对外 API)
```

`internal/` 是「想复用但不想成为公共 API」的标准答案,也是大型库的**重构护城河**(外部依赖不了→你能放心改)。

## build tags / embed

```go
//go:build linux && amd64
package foo
```
```go
//go:embed templates/*.html
var assets embed.FS
```

## 证据链接

- 正文:[`01 项目结构与构建`](../01-project-build/README.md);copylocks 等 [`type-system/02`](../../../type-system/02-method-sets/README.md)

## 易追问的延伸

- **internal 是约定还是强制?** 编译器强制,违规直接编译报错。
- **Go 有官方项目 layout 吗?** 没有(project-layout 是社区的);cmd/internal/pkg 是惯例,扁平按领域分包。
- **`//go:build` vs `// +build`?** 新语法清晰、1.17+ 推荐;gofmt 同步两者。
- **交叉编译 + 静态二进制?** `GOOS/GOARCH go build` + `CGO_ENABLED=0` → 静态二进制进 scratch/distroless。
- **和 Java 可见性比?** Java public/protected/package-private + JPMS;Go 用大小写 + internal 目录,更轻。
