# MVS 最小版本选择(vs Maven/npm)+ 语义导入版本

## 一句话回答

Go 用 **MVS(Minimal Version Selection,最小版本选择)** 解析依赖:对每个模块,收集**所有**对它的版本要求,选其中**最高的那个「被要求版本」**——但**绝不主动拿没人要求的更新版本**。所以 `go.mod` 里的 require 不变,解析结果**永远一致、构建天然可复现**;「升级」是你显式 `go get` 改 go.mod 的动作,不会在构建时偷偷发生。这与 Maven「nearest-wins + 倾向较新」、npm「装最新兼容版 + 靠 lock 兜底」**截然相反**。

## 例子

```
你 require A v1.2;A require B v1.1;C require B v1.3
→ MVS 选 B v1.3(两要求里更高那个,满足两者);不会拿 B v1.4(没人要求)
```

## 为什么可复现

MVS 不主动求新 → go.mod 本身就是确定的构建清单,不需要 lock 文件防飘移。`go.sum` 不管选版本,只存**校验和**做完整性校验(防篡改,必须提交)。**版本由 go.mod 定,内容由 go.sum 验。**

## 语义导入版本(v2+)

主版本 ≥ 2 必须把 `/vN` 写进模块路径和导入路径(`github.com/foo/bar/v2`)。不同主版本被当**不同模块、可共存**,避免主版本冲突地狱。

## 证据链接

- 正文:[`00 modules 与依赖`](../00-modules/README.md)

## 易追问的延伸

- **怎么升级?** 显式 `go get foo@v1.5` 或 `go get -u`,再 `go mod tidy` + 测试。别把 `go get -u` 放进 CI(引入非确定升级)。
- **indirect?** 间接依赖(非直接 import),`go mod tidy` 维护;1.17+ 模块图裁剪加速解析。
- **和 Maven nearest-wins 的本质差?** Maven 按依赖树距离选、易冲突且倾向新;MVS 全局取最小可行版本、确定可复现。
- **供应链安全?** GOSUMDB 校验防篡改 + `govulncheck` 扫漏洞。
