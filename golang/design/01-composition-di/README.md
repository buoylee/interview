# 01 · 组合与依赖注入

> Go 没有继承(见 [`type-system/04`](../../type-system/04-embedding/README.md)),复用靠**组合**;没有 Spring 容器,依赖装配靠**显式构造注入**(手动或 wire 编译期生成)。本章讲怎么用这两样搭出可维护的结构。
>
> 桥接锚点:Java「继承复用 + Spring 运行时反射注入」←→ Go「组合复用 + 显式构造注入(无魔法)」。Go 文化反对运行时反射魔法,偏好编译期可见的装配。

---

## 1. 核心问题

- 没有继承,Go 怎么复用一段通用逻辑?
- 没有 `@Autowired`/Spring 容器,依赖怎么注入?手动传不累吗?
- 大项目几十个依赖,手动 new 一长串,有没有更好的办法?

---

## 2. 直觉理解

### 复用靠组合:嵌入 + 转发

```go
type BaseRepo struct{ db *sql.DB }
func (r BaseRepo) tx(fn func(*sql.Tx) error) error { ... }   // 通用事务逻辑

type UserRepo struct{ BaseRepo }       // 嵌入复用 tx()
type OrderRepo struct{ BaseRepo }      // 同样复用
```

嵌入让 `UserRepo`/`OrderRepo` 直接拥有 `BaseRepo` 的方法(方法提升,见 type-system/04)——这是组合复用。但记住:**没有多态重写**,要多态用接口。

### 依赖注入靠显式构造,而非容器魔法

Go 没有 Spring 那种「运行时扫描 + 反射注入」。依赖就是**通过构造函数显式传进去**:

```go
type Service struct {
    repo   UserStore       // 依赖是接口字段(可注入 fake)
    cache  Cache
    logger *slog.Logger
}
func NewService(repo UserStore, cache Cache, logger *slog.Logger) *Service {
    return &Service{repo: repo, cache: cache, logger: logger}   // 显式装配
}
```

在 `main` 里手动把依赖一层层 new 起来、传进去。**显式、可见、编译期检查**——没有「运行时找不到 bean」的惊喜。这是 Go「显式优于魔法」哲学的体现。

---

## 3. 原理深入

### 3.1 构造注入是 Go 的 DI 主力

- 依赖声明为**接口字段**(不是具体类型)→ 可注入真实现或 fake(可测,见 [`testing/01`](../../testing/01-mock-interfaces/README.md))。
- 构造函数 `NewXxx(deps...) *Xxx` 接收依赖、组装、返回(返回结构体,见 [`00`](../00-interface-design/README.md))。
- `main`(或一个 `wire` 文件)是**组装根(composition root)**:在这里把整棵依赖树 new 出来。

### 3.2 手动 DI vs wire

依赖多了,手动在 main 里 new 一长串确实繁琐。两条路:

- **手动 DI**:就是普通 Go 代码,一串 `NewX(NewY(NewZ()))`。小/中项目完全够用、最透明。
- **wire**(google/wire):**编译期**代码生成的 DI——你声明「provider 函数」,wire 生成装配代码。**关键:它生成的是普通 Go 代码,编译期完成,没有运行时反射**(和 Spring 的运行时容器本质不同)。依赖图大时减少样板。

```go
// wire.go(声明)→ wire 生成 wire_gen.go(真正的 New 调用链)
func InitService() *Service {
    wire.Build(NewService, NewUserRepo, NewCache, NewLogger)
    return nil   // 占位,wire 生成真实现
}
```

准则:**默认手动 DI(透明);依赖图大到样板难受了再上 wire**。绝大多数 Go 项目不需要 DI 框架。

### 3.3 「一点拷贝优于一点依赖」(Go proverb)

> *"A little copying is better than a little dependency."*

为了复用一个小函数而引入一个大依赖,常不划算——Go 文化宁可**拷几行代码**也不背一个依赖。这和 Java「能复用就抽公共库」的倾向不同,体现 Go 对依赖膨胀的警惕(也呼应 [`engineering/00`](../../engineering/00-modules/README.md) 的依赖管理)。

### 3.4 组合模式:装饰器 / 中间件

嵌入接口 + 只重写部分方法 = 装饰器(见 type-system/04):

```go
type LoggingStore struct{ UserStore }       // 嵌入接口
func (s LoggingStore) QueryName(id int) (string, error) {
    log.Println("query", id)
    return s.UserStore.QueryName(id)        // 转发 + 加料
}
```

HTTP 中间件(`func(http.Handler) http.Handler`)是同一思想的函数版(见 [`service-design/`](../../service-design/))。

---

## 4. 日常开发应用

- **复用通用逻辑用嵌入**(BaseRepo/BaseModel),但要多态用接口。
- **依赖声明为接口字段 + 构造注入**:`NewXxx(deps...)`,依赖在 main 装配。
- **默认手动 DI**;依赖图大、样板痛了再 wire(编译期,无运行时反射)。
- **装饰器/中间件**用嵌入接口或函数包装。
- **警惕为小复用引大依赖**:小东西宁可拷。

---

## 5. 生产&调优实战

- **组装根集中在 main/wire**:依赖树只在一处装配,业务代码只声明「我要什么接口」,利于替换实现(测试/不同环境)。
- **显式 DI 的可维护性优势**:没有运行时容器,依赖关系编译期可见、IDE 可跳转、不会「启动时才发现注入失败」——对大团队是稳定性收益。
- **wire 的取舍**:省样板但加一层生成步骤 + 学习成本;团队小就别上。生成代码要提交(见 [`engineering/02`](../../engineering/02-toolchain/README.md))。
- **别滥用嵌入做"继承"**:嵌入会把内嵌类型的导出方法全提升成你的 API(见 type-system/04),可能泄漏不想要的方法;不想暴露就具名字段 + 显式转发。
- **依赖膨胀**:每个第三方依赖都是供应链/维护负担(漏洞、升级);「一点拷贝优于一点依赖」在生产是真实权衡。

---

## 6. 面试高频考点

- **没有继承怎么复用?** 组合:嵌入 + 方法提升(type-system/04);但无多态重写,多态用接口。
- **Go 怎么做依赖注入?** 显式构造注入:依赖声明为接口字段,`NewXxx(deps...)` 传入,main 做组装根。无 Spring 式运行时容器。
- **手动 DI vs wire?** 手动=普通代码、透明,中小项目够;wire=编译期生成装配代码(**无运行时反射**,区别于 Spring),依赖图大时减样板。默认手动。
- **wire 和 Spring 的本质区别?** wire 编译期生成普通 Go 代码、依赖编译期可见;Spring 运行时反射注入、可能运行时才报错。
- **「一点拷贝优于一点依赖」?** 为小复用引大依赖不划算,Go 宁可拷几行;警惕依赖膨胀。
- **装饰器怎么写?** 嵌入接口 + 重写部分方法转发;中间件是函数版。

---

## 7. 一句话总结

> **Go 没有继承,复用靠组合(嵌入 + 方法提升,但无多态重写——多态用接口);没有 Spring 容器,依赖装配靠显式构造注入**:依赖声明为**接口字段**(可注入 fake)、`NewXxx(deps...)` 传入、main 作组装根。依赖多时用 **wire**(编译期生成装配代码,**无运行时反射**,本质区别于 Spring),但默认手动 DI 更透明、中小项目够用。Go 文化「显式优于魔法、一点拷贝优于一点依赖」——警惕运行时反射魔法和依赖膨胀。装饰器/中间件 = 嵌入接口重写部分方法 / 函数包装。

← 上一章 [`00 接口设计哲学`](../00-interface-design/README.md) ｜ 下一章 → [`02 函数式选项`](../02-functional-options/README.md):构造函数参数太多、还想支持可选配置怎么办?Go 的惯用答案是函数式选项。｜ 回 [`design` 索引](../README.md)
