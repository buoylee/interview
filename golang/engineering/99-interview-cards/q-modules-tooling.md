# replace / vendor / workspace / go.sum

## 一句话回答

三件配套工具各管一摊:**`replace`** 把某依赖路径/版本**重定向**到另一个(本地路径或 fork,用于调试/打补丁,**只对主模块生效**、不传染给引用者);**`vendor`**(`go mod vendor`)把所有依赖源码**拷进 `vendor/` 目录**,用 `-mod=vendor` 构建(离线/审计/不信任代理,代价是仓库膨胀);**`workspace`**(`go.work`,1.18)用于**多模块本地联合开发**,一个 `go.work` 列出本地模块目录、**不污染各自 go.mod**(取代以前一堆 `replace ../x`)。`go.sum` 是**校验和**文件(不是 lock),做依赖完整性校验。

## 各自定位

| 工具 | 解决什么 | 注意 |
|---|---|---|
| `replace` | 调试/fork/临时补丁某依赖 | 只对主模块生效;发布前清理 |
| `vendor` | 离线/隔离/审计构建 | 仓库变大;升级要重新 vendor |
| `go.work` | 多模块本地联调 | 不提交进发布(本地开发用) |
| `go.sum` | 防依赖被篡改 | **必须提交**;CI `-mod=readonly` |

## 证据链接

- 正文:[`00 modules 与依赖`](../00-modules/README.md)

## 易追问的延伸

- **replace 会影响下游吗?** 不会,只对主模块;协作者引用你的库时你的 replace 不生效。
- **vendor 何时值得?** 监管/离线环境、要审计全部依赖源码、不信任公共代理。
- **go.work 和 replace 区别?** go.work 是本地开发态的多模块联合、不动 go.mod;replace 写在 go.mod 里会留痕。
- **常用命令?** `go mod tidy`(整理)、`go mod why`(谁引入的)、`go mod graph`(依赖图)、`go mod download`。
