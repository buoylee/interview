# 99 · 面试卡 —— Go 错误处理高频题速查

> 把全 track 高频考点压成「速答表(背诵用)」+「深题卡(讲清用,每张链回正文做证据)」。
>
> 总钥匙一句话:**error 是值,不是控制流。**

## 卡片索引(深题卡)

- [Go 为什么不用异常 / error vs panic](q-error-vs-exception.md)
- [`%w` 错误链与 `errors.Is`/`As` 怎么工作](q-wrap-is-as.md)
- [defer 求值/执行时机 + recover 为什么没接住](q-defer-recover.md)
- [何时该 panic、何时该 return err](q-when-panic.md)
- [并发错误:errgroup / errors.Join / goroutine panic](q-errgroup.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| error 是值还是异常 | 普通返回值 `(T,error)`,显式判断/上抛,不走异常控制流 | [00](../00-philosophy/README.md) |
| 为什么不用 try-catch | 把失败摆明面、消灭隐式跳转;Go2 `try` 提案被否决 | [00](../00-philosophy/README.md) |
| error vs panic 怎么选 | 调用方能应对的预期失败→error;程序bug/不可恢复→panic;公共API一律error | [00](../00-philosophy/README.md) |
| error 底层是什么 | 只有 `Error() string` 的普通接口;返错=返接口值,零异常开销(无栈轨迹抓取) | [00](../00-philosophy/README.md) |
| 三种错误风格 | sentinel(`Is`认类别)/typed(`As`取数据)/opaque(只`err!=nil`或断言行为);默认 opaque | [01](../01-error-values/README.md) |
| 哨兵为什么能认出 | 比的是**同一个包级变量的指针**;`errors.New` 每次返回新指针 | [01](../01-error-values/README.md) |
| typed nil 坑 | 返回具体类型 nil 指针赋给 error→接口非 nil;成功一律 `return nil`,函数返回类型用 error | [01](../01-error-values/README.md) |
| 为什么不能字符串匹配认错误 | 文案会变、穿不过包装层、是实现细节;用 `Is`/`As` | [01](../01-error-values/README.md) |
| `%w` vs `%v` | `%w` 保留链可 `Is`/`As`(暴露进契约);`%v` 切断链(跨边界翻译、不泄漏) | [02](../02-wrapping/README.md) |
| `errors.Is` 怎么走 | 沿链:`==target`? → 当前环自定义 `Is()`? → `Unwrap` 下一环;到 nil 未中则 false | [02](../02-wrapping/README.md) |
| Is vs As | Is 找「是不是某哨兵」(bool);As 找「能不能转某类型」并赋值取字段;Is配哨兵 As配类型 | [02](../02-wrapping/README.md) |
| 多重包装 | `errors.Join`/多 `%w`(1.20),`Unwrap() []error`,链变树,`Is`/`As` 递归 | [02](../02-wrapping/README.md) |
| `errors.As` target 要求 | 指向「实现 error 的类型/接口」的非 nil 指针,否则 panic | [02](../02-wrapping/README.md) |
| defer 参数何时求值 | defer 语句执行那刻即求值固定;函数体 LIFO 在 return 前跑 | [03](../03-panic-recover-defer/README.md) |
| defer 能改返回值吗 | 能改**命名返回值**;`return x`=先赋命名返回值→跑 defer→真返回 | [03](../03-panic-recover-defer/README.md) |
| for 循环里 defer | 参数逐次固定、LIFO 倒序;资源到函数结束才释放(别这么写) | [03](../03-panic-recover-defer/README.md) |
| recover 为什么没接住 | 必须在 **defer 函数里被直接调用** + 同一**正在 panic 的 goroutine** | [03](../03-panic-recover-defer/README.md) |
| panic→error 转换 | 命名返回值 + defer 里 recover 后给 err 赋值(json/template 内部用法) | [03](../03-panic-recover-defer/README.md) |
| 何时该 panic | 程序 bug/不可恢复/`MustXxx`/init 前置不满足;否则 error | [03](../03-panic-recover-defer/README.md) |
| goroutine panic 后果 | 没被**自己** recover→crash **整个进程**;别的 goroutine recover 不了 | [03](../03-panic-recover-defer/README.md)/[05](../05-concurrent-errors/README.md) |
| N 个 goroutine 错误怎么收 | 首错停用 `errgroup`;全收齐用 `errors.Join`;细粒度用 error channel | [05](../05-concurrent-errors/README.md) |
| errgroup vs WaitGroup | errgroup=WaitGroup+收首错+(WithContext)首错取消;默认只留一个错误 | [05](../05-concurrent-errors/README.md) |
| errgroup 兜 panic 吗 | 不兜,只收返回的 error;任务内 panic 照样 crash,需自己 recover | [05](../05-concurrent-errors/README.md) |
| 要不要又 log 又 return | 不要(handle once);中间层只加上下文上抛,日志在请求边界打**一次** | [04](../04-error-design/README.md) |
| API 该暴露什么错误 | 故意暴露的哨兵/类型/行为接口才是契约,数量尽量少;底层错误边界翻译掉 | [04](../04-error-design/README.md) |
| 怎么不泄漏内部错误 | 跨信任边界翻译成状态码+安全文案+稳定 error code,内部细节只进日志 | [04](../04-error-design/README.md) |
| 断言行为而非类型 | 优先暴露行为接口(`Temporary()`)让调用方断言,耦合最低 | [04](../04-error-design/README.md) |
| 错误带堆栈吗 | 标准库**不带**(故便宜);需要靠边界日志+trace 或 `pkg/errors` | [04](../04-error-design/README.md) |
| DAO 的 sql 错误冒泡到 controller | 不该;repo/service 边界翻译成领域错误,否则耦合实现(同 Java) | [04](../04-error-design/README.md) |

← 回 [`error-handling` 索引](../README.md)
