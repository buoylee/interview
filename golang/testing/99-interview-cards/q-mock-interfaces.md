# mock 与接口:小接口 + DI 做可测

## 一句话回答

Go 的可测性来自**「在消费方定义小接口 + 依赖注入」**:把硬依赖(DB/HTTP/第三方)改成接口参数,测试时注入一个实现了该接口的 **fake**(就是个普通 struct,零框架、零反射)。接口要**小、定义在使用它的那一方**——隐式实现 + 只声明用到的方法,所以 mock 轻松、不耦合庞大真实类型。这就是「接受接口,返回结构体」。

## 例子

```go
type UserStore interface{ QueryName(id int) (string, error) }   // 消费方小接口
func GetUserName(s UserStore, id int) (string, error) { return s.QueryName(id) }

type fakeStore struct{ name string }
func (f fakeStore) QueryName(int) (string, error) { return f.name, nil }
// 测试:GetUserName(fakeStore{name:"alice"}, 1)
```

## fake vs stub vs mock + 工具

- **fake**(简化真实行为,状态式)→ **首选**;**stub**(写死返回值);**mock**(断言交互次数/参数,易脆)。Go 偏 fake。
- **手写 fake**(接口小,首选)vs **gomock**(go.uber.org/mock,方法多/要验证交互,`mockgen` 生成)vs testify/mock。
- **httptest**:`NewRecorder` 测 handler、`NewServer` 起假上游测 client。
- **sqlmock**:在 `database/sql` 层拦截、断言 SQL,测 repo 不连真库。

## 证据链接

- 正文:[`01 mock 与接口`](../01-mock-interfaces/README.md);接口隐式实现 [`type-system/01`](../../type-system/01-interface-internals/README.md);设计哲学 [`design/`](../../design/)

## 易追问的延伸

- **别过度 mock**:mock 一切=测试复述实现,改实现就崩;优先 fake 测状态,mock 只在「交互本身是契约」时用。
- **可测性是设计产物**:难测=耦合太紧(硬依赖/大接口),重构成小接口+DI 既好测又好维护。
- **真库交互怎么测?** 集成测试(testcontainers + build tag),见 [`02`](../02-benchmark-fuzz-integration/README.md)。
- **和 Mockito?** Mockito 动态代理;Go 偏手写 fake 实现小接口 + DI,框架辅助。
