# 99 · 面试卡 —— Go idiomatic 设计高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**组合而非继承、小接口而非大抽象、显式而非魔法、零值可用、为调用方设计。**

## 卡片索引(深题卡)

- [接口设计:小接口·消费方定义·接受接口返结构体](q-interface-design.md)
- [组合与依赖注入(wire vs 手动)](q-composition-di.md)
- [函数式选项](q-functional-options.md)
- [并发安全的 API 设计](q-concurrent-api.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| Go 接口该多大 | 尽量小(1-2 方法);越大越弱;io.Reader 典范;大接口拆小嵌入组合 | [00](../00-interface-design/README.md) |
| 接口由谁定义 | 消费方(谁用谁定义、只声明用到的方法);隐式实现解耦 | [00](../00-interface-design/README.md) |
| 接受接口返结构体 | 参数用接口=灵活可测;返结构体=不隐藏能力·易演进·免装箱 | [00](../00-interface-design/README.md) |
| 何时定义接口 | 出现第二实现/测试要替换时再抽;别造只有一个实现的接口 | [00](../00-interface-design/README.md) |
| 没继承怎么复用 | 组合:嵌入+方法提升;无多态重写,多态用接口 | [01](../01-composition-di/README.md) |
| Go 怎么 DI | 显式构造注入:依赖为接口字段,NewXxx 传入,main 组装根 | [01](../01-composition-di/README.md) |
| 手动 DI vs wire | 手动透明中小够用;wire 编译期生成装配代码(无运行时反射,区别 Spring) | [01](../01-composition-di/README.md) |
| 一点拷贝优于一点依赖 | 为小复用引大依赖不划算,宁可拷;警惕依赖膨胀 | [01](../01-composition-di/README.md) |
| 没默认参数怎么做可选配置 | 函数式选项:Option func(*config),WithX 返回闭包,NewX(必填,opts...) | [02](../02-functional-options/README.md) |
| 函数式选项 vs config struct | 真可选+明确默认、加选项不破兼容、可校验可读;代价样板多 | [02](../02-functional-options/README.md) |
| 必填参数怎么办 | 放位置参数(NewServer(addr, opts...)),别塞选项 | [02](../02-functional-options/README.md) |
| 何时别用函数式选项 | 配置≤2/内部小函数/无可选项→直接参数或 config struct | [02](../02-functional-options/README.md) |
| 类型该不该自己加锁 | 通用类型让调用方同步(文档写明);共享单例内部加锁;关键是文档化契约 | [03](../03-concurrent-api/README.md) |
| 能在库里开 goroutine 吗 | 不偷开;要开给控制权(ctx 可取消/Close)+ 自带 recover | [03](../03-concurrent-api/README.md) |
| 并发 API 铁律 | 零值可用/谁同步文档化/ctx 首参下传/含锁用指针不导出锁/别暴露 channel·Mutex/返 error 不 panic | [03](../03-concurrent-api/README.md) |
| 为什么别导出 Mutex/channel | 嵌 Mutex 暴露 Lock/Unlock;导出 channel 关闭责任外泄;用未导出字段封装 | [03](../03-concurrent-api/README.md) |

← 回 [`design` 索引](../README.md)
