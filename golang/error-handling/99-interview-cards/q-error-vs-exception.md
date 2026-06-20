# Go 为什么不用异常 / error vs panic

## 一句话回答

Go 的哲学是 **error 是值,不是控制流**:可能失败的函数把错误当**普通返回值**(`(T, error)`)交出来,靠 `if err != nil` 显式判断、`return err` 显式上抛——把失败路径全摆到明面,消灭异常那种「看代码看不出谁会抛、抛了跳哪」的隐式控制流。Go **并非没有异常**:`panic`/`recover` 就是异常机制(中断+栈展开+defer),但被**刻意约束**只用于「程序 bug / 不可恢复状态」,日常的、调用方能应对的失败一律用 error。

## 为什么是「值」而不是「异常」

- **失败可见**:`a(); b(); c()` 在 Java 里任一行都可能抛异常跳走、代码上看不出;Go 强制 `if err != nil { return err }`,失败路径写在脸上。
- **零开销**:返回 error 就是多返一个接口值;抛异常要构造对象 + 抓栈轨迹(贵)+ 栈展开找 handler。
- **强制处理**:编译器逼你接住返回值,不像 unchecked 异常能静默穿透。
- **设计史**:Go 2 的 `check/handle`、`try` 提案都被**否决**——因为会把显式检查变回隐式跳转。`if err != nil` 的啰嗦是刻意保留的。

## error vs panic 判据

| 这个失败… | 用 |
|---|---|
| 调用方能合理应对 / 预期内(文件不存在、超时、校验失败、订单不存在) | **error** |
| 程序 bug / 不该发生(越界、解引用 nil、漏 case) | **panic** |
| `MustXxx`(参数是写死常量)、init/main 前置不满足 | **panic** / `log.Fatal` |
| 库的公共 API 边界 | 一律 **error**(内部要 panic 也在边界 recover 转 error) |

口诀:**能合理应对的 → error,只能改代码才能修的 → panic。**

## 对照 Java/Python

- Java checked 异常也强制处理,但靠类型系统 + 自动冒泡,`throws` 污染签名、催生 `catch(Exception e){}` 吞异常;Go 用「返回值 + 编译器逼你接住」达到强制,完全显式无冒泡。
- Java 的 `RuntimeException`(unchecked)≈ Go 的 panic 用途——程序 bug。
- Python `try/except` 同 Java,默认所有异常 unchecked。

## 证据链接

- 正文:[`00 错误哲学`](../00-philosophy/README.md)

## 易追问的延伸

- **panic 在生产什么风险?** 没 recover 的 panic 杀**整个进程**;goroutine 的 panic 别的协程 recover 不了 → 服务端用 recover 中间件兜单请求。见 [`03`](../03-panic-recover-defer/README.md)/[`05`](../05-concurrent-errors/README.md)。
- **error 性能真比异常好?** 是——无栈轨迹抓取、无展开,所以 Go 能在热路径大量返回 error 不心疼。
- **那 `if err != nil` 不烦吗?** 烦,但 Go 团队权衡后认为「错误处理是主逻辑、该可见」,否决了语法糖。
