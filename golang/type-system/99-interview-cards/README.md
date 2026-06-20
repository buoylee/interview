# 99 · 面试卡 —— Go 类型系统与接口高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**接口 = 两个字(类型/itab + 数据指针),itab 方法表动态派发;Go 用组合 + 隐式接口取代继承。**

## 卡片索引(深题卡)

- [接口底层:iface / eface / itab 怎么动态派发](q-iface-eface.md)
- [方法集与接收者:为什么 `*T` 能满足接口而 `T` 不能](q-method-set-receiver.md)
- [类型断言与 type switch 底层](q-type-assertion.md)
- [嵌入 vs 继承:Go 为什么没有继承](q-embedding-vs-inheritance.md)
- [typed nil:接口为什么 `!= nil`](q-typed-nil.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| Go 是值传递还是引用传递 | 只有值传递;slice/map/chan 是含指针的 header,拷 header 共享底层 | [00](../00-values-layout/README.md) |
| 哪些类型不能 `==` | slice/map/func(及含它们的 struct);interface 动态类型不可比时 panic | [00](../00-values-layout/README.md) |
| 零值可用 | 类型零值即有效状态(`sync.Mutex`/`bytes.Buffer`),免构造函数 | [00](../00-values-layout/README.md) |
| 接口底层是什么 | 两个字:iface{itab,data} / eface{_type,data};data 指向值 | [01](../01-interface-internals/README.md) |
| eface vs iface | eface 给 any(只 _type+data);iface 给带方法接口(itab 含方法表) | [01](../01-interface-internals/README.md) |
| itab 里有什么 | 接口类型 + 具体类型 + 方法函数指针表 fun;按(接口,类型)全局缓存 | [01](../01-interface-internals/README.md) |
| 怎么动态派发 | s.M()=从 itab.fun 取函数指针,以 data 作接收者调;≈ Java vtable | [01](../01-interface-internals/README.md) |
| 为什么不用写 implements | 隐式:编译期查具体类型方法集是否覆盖接口方法,覆盖即满足 | [01](../01-interface-internals/README.md) |
| 装值进接口会怎样 | 拷贝一份 + 常逃逸到堆;装指针/map/chan/func 走 direct interface 不额外分配 | [01](../01-interface-internals/README.md) |
| 值 vs 指针接收者 | 值=操作拷贝(改不到原值/每次拷贝);指针=操作原值(能改/免拷) | [02](../02-method-sets/README.md) |
| T 和 *T 方法集 | T 只含值接收者方法;*T 含值+指针接收者(全部) | [02](../02-method-sets/README.md) |
| 为什么 *T 能满足接口 T 不能 | 接口要的是指针接收者方法,只在 *T 方法集里 | [02](../02-method-sets/README.md) |
| c.Inc() 能调但装接口不行 | 局部变量可寻址,编译器自动取址;接口里的值不可寻址 | [02](../02-method-sets/README.md) |
| map 元素能调指针方法吗 | 不能,map 元素不可寻址;取出改写回或用 map[K]*V | [02](../02-method-sets/README.md) |
| 接收者统一用哪种 | 有一个要指针就全用指针;只读小不可变才全用值(time.Time) | [02](../02-method-sets/README.md) |
| 值接收者 + 含锁 struct | 拷贝锁致互斥失效,go vet copylocks 报 | [02](../02-method-sets/README.md) |
| x.(T) 两种形式 | 单值失败 panic;comma-ok 失败给零值+false 不 panic | [03](../03-type-assertion/README.md) |
| 断言具体类型 vs 接口类型 | 具体=比 _type 指针(快);接口=查/建 itab 看是否实现(略贵) | [03](../03-type-assertion/README.md) |
| type switch 怎么分发 | 类型 hash 分桶 + 精确比对;v 在单类型 case 是具体类型 | [03](../03-type-assertion/README.md) |
| errors.As 本质 | 沿错误链逐环做类型断言并赋值 | [03](../03-type-assertion/README.md) |
| Go 有继承吗 | 没有;嵌入做组合 + 方法提升,无虚函数重写,多态只靠接口 | [04](../04-embedding/README.md) |
| 嵌入 vs 继承 | has-a 组合 + 自动转发 vs is-a + 可重写;取出内嵌值调走的是内嵌方法 | [04](../04-embedding/README.md) |
| 同名方法冲突 | 浅层遮蔽深层;同深度两嵌入同名→ambiguous 编译错,需显式 | [04](../04-embedding/README.md) |
| 嵌入接口 | 组合接口(io.ReadWriter);struct 嵌接口做装饰器转发 | [04](../04-embedding/README.md) |
| 嵌入的坑 | 扩大公共 API 面 / 内嵌接口为 nil 调用 panic / 序列化字段平铺 | [04](../04-embedding/README.md) |
| typed nil 为什么 != nil | 接口两字,具体类型 nil 指针→类型字段非空→接口非 nil | [05](../05-nil/README.md) |
| nil map 读写 | 能读(零值)、len/range 安全;写 panic | [05](../05-nil/README.md) |
| nil slice | 能 append/len/range,是惯用零值;vs 空 slice 仅差 ==nil 和 JSON | [05](../05-nil/README.md) |
| nil channel | 收发永久阻塞,close panic;select 里置 nil 禁用分支 | [05](../05-nil/README.md) |
| nil 指针能调方法吗 | 能,只要方法不解引用接收者(接收者是参数) | [05](../05-nil/README.md) |
| 怎么判 slice 空 | len(s)==0(覆盖 nil 和空),别用 s==nil | [05](../05-nil/README.md) |

← 回 [`type-system` 索引](../README.md)
