# 接口底层:iface / eface / itab 怎么动态派发

## 一句话回答

Go 的接口值永远是**两个字(指针宽)**:**非空接口** = `iface{ tab *itab, data unsafe.Pointer }`,**空接口 `any`** = `eface{ _type *_type, data unsafe.Pointer }`。`data` 指向实际值,`itab` 里含「接口类型 + 具体类型 + **方法函数指针表 fun**」。调 `s.M()` 就是从 `itab.fun` 取出 M 的函数地址、以 `data` 作接收者调用——这就是动态派发(≈ Java vtable,但表挂在接口值的 itab 上,且实现是**隐式**的)。

## 白板图

```
非空接口 iface:                    空接口 eface(any):
┌────────┬────────┐               ┌────────┬────────┐
│ *itab  │ data   │               │ *_type │ data   │
└───┬────┴───┬────┘               └────────┴───┬────┘
    │        └──→ 实际值                        └──→ 实际值
    └──→ itab{ inter(接口类型), _type(具体类型), hash, fun[]→各方法地址 }
```

## 关键点

- **eface vs iface**:`any` 不带方法,只需类型 + data(eface);带方法的接口要支持调方法,多一个 itab(含方法表)。
- **itab 全局缓存**:由 (接口类型, 具体类型) 唯一决定,运行时去重,`(Stringer, User)` 只建一次。
- **隐式实现**:不写 `implements`;编译器在赋值/传参处查「具体类型方法集 ⊇ 接口方法集」,覆盖即满足并生成 itab。编译期检查的鸭子类型。
- **装值会拷贝 + 逃逸**:`data` 是指针,装**值**进接口要把值搬到堆(逃逸);装**指针/map/chan/func**(单指针类型)走 direct interface 优化,直接塞 data 字、不额外分配 → 热路径优先装指针。

## 证据链接

- 正文:[`01 接口底层`](../01-interface-internals/README.md);值语义地基 [`00`](../00-values-layout/README.md)

## 易追问的延伸

- **接口 == nil 的条件?** 两个字都空。装 typed nil 指针→类型字段非空→非 nil(见 [typed nil 卡](q-typed-nil.md))。
- **动态派发有多贵?** 多一次间接 + 难内联,通常可忽略;超热小函数走接口会丢内联,可用泛型/具体类型。
- **怎么编译期断言某类型实现接口?** `var _ Stringer = (*User)(nil)`。
- **和 Java 区别?** Java 显式 implements + 对象头 klass→vtable;Go 隐式 + 接口值自带 itab + 两个字。
