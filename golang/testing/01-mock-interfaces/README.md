# 01 · mock 与接口:小接口 + 依赖注入做可测

> 要测一个依赖 DB / HTTP / 第三方的函数,不能真连。Go 的答案不是重型 mock 框架,而是**在消费方定义小接口 + 依赖注入**——把依赖换成测试用的 fake。这既是测试技巧,也是设计原则(和 [`design/`](../../design/) 互链)。
>
> 桥接锚点:Java 靠 Mockito 动态代理 mock 具体类/接口;Go 更偏**手写 fake 实现小接口** + DI,框架(gomock/testify)是辅助。Go 文化:**为测试而设计可注入的接口,而非为代码硬塞 mock**。

---

## 1. 核心问题

```go
func GetUserName(id int) (string, error) {
    db := openDB()                       // ❌ 硬依赖:测试时怎么不连真库?
    return db.QueryName(id)
}
```

- 怎么让这个函数在测试时**不连真数据库**?
- Go 没有 Mockito 那种「凭空 mock 一个类」,怎么造假?
- 手写 fake、gomock、testify/mock、sqlmock 各什么时候用?

---

## 2. 直觉理解

### 可测性 = 把依赖变成「可替换的接口参数」

把硬依赖改成**接口 + 注入**:

```go
type UserStore interface {                // 消费方定义的小接口(只要它用到的方法)
    QueryName(id int) (string, error)
}
func GetUserName(s UserStore, id int) (string, error) {   // 依赖注入
    return s.QueryName(id)
}
```

测试时传一个 **fake** 实现:

```go
type fakeStore struct{ name string; err error }
func (f fakeStore) QueryName(int) (string, error) { return f.name, f.err }

func TestGetUserName(t *testing.T) {
    got, _ := GetUserName(fakeStore{name: "alice"}, 1)
    if got != "alice" { t.Errorf("got %q", got) }
}
```

没有框架、没有反射——**fake 就是一个实现了接口的普通 struct**。这是 Go 测试的核心:**小接口 + DI**。

### 接口要小,且定义在消费方

回忆 [`type-system/01`](../../type-system/01-interface-internals/README.md):接口是隐式实现的。所以**接口应该小、定义在使用它的那一方**(消费方),只声明「我需要的那几个方法」。这样:

- mock 容易(只需实现少数方法);
- 不和庞大的真实类型耦合(真 DB 有几十个方法,你的接口只要一个 `QueryName`)。

口诀(也是 design track 的主题):**「接受接口,返回结构体」+「接口定义在消费方,越小越好」**。

---

## 3. 原理深入

### 3.1 fake vs mock vs stub

- **fake**:一个有**简化但真实行为**的实现(如内存版 store)。状态化、可复用,**最推荐**——测的是「行为/状态」。
- **stub**:返回写死的值,不关心调用。简单场景够用。
- **mock**:记录**交互**(被调了几次、用什么参数),断言「是否以正确参数调用了依赖」。交互式测试,易脆(过度耦合实现细节)。

Go 文化偏好 **fake/stub(状态式)** 而非 mock(交互式),因为后者容易写出「测试在复述实现」的脆弱测试。

### 3.2 工具:手写 vs gomock vs testify/mock

| 方式 | 何时用 |
|---|---|
| **手写 fake** | 接口小、行为简单——首选,零依赖、最清晰 |
| **gomock**(go.uber.org/mock)| 接口大/方法多、要严格断言调用次数和参数;`mockgen` 自动生成 |
| **testify/mock** | 喜欢 testify 生态、要灵活的 On/Return 设定 |
| **moq** | 生成轻量 fake(比 gomock 简洁) |

```go
//go:generate mockgen -source=store.go -destination=mock_store.go   // 自动生成 mock
```

准则:**接口小就手写 fake;方法多/要验证交互再上 gomock**。别一上来就 mock 框架。

### 3.3 httptest:测 HTTP server/client

```go
// 测 handler:用 ResponseRecorder,不起真服务器
func TestHandler(t *testing.T) {
    req := httptest.NewRequest("GET", "/users/1", nil)
    rec := httptest.NewRecorder()
    handler(rec, req)
    if rec.Code != 200 { t.Errorf("code=%d", rec.Code) }
}

// 测 client:起一个假的上游服务器
srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte(`{"name":"alice"}`))
}))
defer srv.Close()
client.BaseURL = srv.URL              // 把 client 指向假服务器
```

`httptest` 是测 HTTP 的标准库利器:`NewRecorder` 测 handler、`NewServer` 测 client。

### 3.4 sqlmock:测 DB 层而不连真库

```go
db, mock, _ := sqlmock.New()                          // 假的 *sql.DB
mock.ExpectQuery("SELECT name").WithArgs(1).
    WillReturnRows(sqlmock.NewRows([]string{"name"}).AddRow("alice"))
```

`DATA-DOG/go-sqlmock` 在 `database/sql` 层拦截,断言 SQL + 返回假数据。适合测 repo 层的 SQL 逻辑而不依赖真库(真库交互留给集成测试,见 [`02`](../02-benchmark-fuzz-integration/README.md))。

---

## 4. 日常开发应用

- **依赖都通过接口注入**(构造函数/参数),别在函数里 `openDB()` 硬连。
- **接口定义在消费方、保持小**:只声明你用到的方法,mock 才轻松。
- **首选手写 fake**;接口大或要验证交互次数再 gomock + mockgen。
- **HTTP 用 httptest**(handler 用 Recorder、client 用 Server)。
- **DB 单元测试用 sqlmock**,真库交互放集成测试。
- **注入时钟/随机/UUID**(`Clock` 接口)让时间相关逻辑可测、不 flaky。

---

## 5. 生产&调优实战

- **可测性是设计产物,不是事后补**:难测往往意味着耦合太紧(硬依赖、大接口);重构成「小接口 + DI」既好测又好维护(和 [`design/`](../../design/) 同源)。
- **别过度 mock**:mock 一切会让测试变成「实现的复述」,改实现就崩。优先 fake(测状态/行为),mock 只在「交互本身是契约」时用(如「必须调一次支付」)。
- **mock 框架的脆弱性**:严格的 `ExpectQuery` 字符串匹配、调用次数断言,重构时大面积失败;权衡严格度。
- **接口爆炸**:为每个依赖造接口会增样板;只在「需要替换/测试边界」处抽接口,内部具体类型直接用。
- **集成 vs 单元的边界**:sqlmock/httptest 是单元测试(快、确定);真 DB/真 HTTP 用 testcontainers 的集成测试(慢、真实),两者都要、用 build tag 分开。

---

## 6. 面试高频考点

- **Go 怎么 mock 依赖?** 在**消费方定义小接口 + 依赖注入**,测试传 fake 实现(普通 struct);不靠反射/框架也能做。
- **接口为什么要小、定义在消费方?** 隐式实现 + 只声明用到的方法 → mock 容易、不耦合庞大真实类型。「接受接口返回结构体」。
- **fake / stub / mock 区别?** fake=简化真实行为(状态式,推荐);stub=写死返回值;mock=记录并断言交互(交互式,易脆)。Go 偏好 fake。
- **手写 fake vs gomock?** 接口小手写 fake(首选);方法多/要验证调用次数用 gomock + mockgen。
- **怎么测 HTTP?** httptest:`NewRecorder` 测 handler、`NewServer` 起假上游测 client。
- **怎么测 DB 层不连真库?** sqlmock 在 database/sql 层拦截断言 SQL;真库交互留集成测试。
- **和 Mockito 区别?** Mockito 动态代理 mock;Go 更偏手写 fake 实现小接口 + DI,框架辅助。

---

## 7. 一句话总结

> **Go 的可测性来自「在消费方定义小接口 + 依赖注入」**:把硬依赖(DB/HTTP/第三方)改成接口参数,测试时注入一个实现了该接口的 **fake**(普通 struct,零框架)。接口要**小、定义在使用方**(隐式实现 + 只声明用到的方法 → mock 轻松),即「接受接口返回结构体」。优先 **fake/stub(状态式)** 而非 mock(交互式,易脆);接口小就手写 fake,方法多/要验证交互再上 gomock + mockgen。HTTP 用 `httptest`(Recorder 测 handler、Server 测 client),DB 单元测试用 sqlmock(真库留集成测试)。可测性是设计产物——难测=耦合太紧。

← 上一章 [`00 单元测试基础`](../00-unit-testing/README.md) ｜ 下一章 → [`02 基准·模糊·集成`](../02-benchmark-fuzz-integration/README.md):怎么写 benchmark 测性能、用 fuzzing 自动找崩溃输入、用 testcontainers 跑真依赖的集成测试。｜ 回 [`testing` 索引](../README.md)
