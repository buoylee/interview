# Go 类型系统与接口 —— 给 Java 后端的「没有继承,只有组合 + 两个字的接口」

> Go 没有 class、没有继承、没有虚函数重写。它用**值语义 + 隐式接口 + 嵌入组合**搭出一套和 Java 很不一样的类型系统。面试爱往底层挖:**接口是哪两个字、itab 怎么动态派发、`*T` 凭什么能满足接口而 `T` 不能、typed nil 怎么来的**。本 track 把这些讲到白板能画。
>
> 总钥匙:**接口值 = 两个字(类型信息 + 数据指针),方法靠 itab 函数表动态派发;Go 用「组合 + 隐式接口」取代「继承 + 虚表」。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-type-system-track-design.md`｜Go 版本基线 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` 立值语义/内存布局地基,`01` 是核心(接口两个字 + itab + 动态派发),`02` 方法集(面试最绕),`03` 类型断言,`04` 嵌入组合(对照 Java 继承),`05` nil 的多张面孔(收口 typed nil)。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
3. **双向桥**：每章对照 **Java**(class/继承/虚表/`instanceof`/装箱)与 **Python**(鸭子类型)。
4. **想答面试**：去 `99-interview-cards/` 找卡,链回正文做证据。

## 容易忘时先看这里

- [接口是哪两个字 / itab 怎么动态派发](01-interface-internals/README.md) — 白板高频题。
- [为什么 `*T` 能满足接口而 `T` 不能](02-method-sets/README.md) — 方法集规则,最容易答错。
- [typed nil:接口 != nil 的坑](05-nil/README.md) — 经典陷阱。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-values-layout/`](00-values-layout/) | 值、类型与内存布局 | 值语义(赋值/传参皆拷贝) / 零值可用 / 可比较性 / 「引用类型」是含指针的头 ← 从这开始 |
| [`01-interface-internals/`](01-interface-internals/) | **接口底层** | iface vs eface 两个字 / itab 方法表 / 动态派发 / 接口装值的拷贝逃逸 |
| [`02-method-sets/`](02-method-sets/) | 方法集与接收者 | 值 vs 指针接收者 / `T` 与 `*T` 方法集 / 为什么 `*T` 能满足接口 / 一致性铁律 |
| [`03-type-assertion/`](03-type-assertion/) | 类型断言与 type switch | `x.(T)` comma-ok / 接口到接口 / type switch / 底层比对 / 性能 |
| [`04-embedding/`](04-embedding/) | 嵌入与组合 | 方法提升 / 组合 vs 继承(无虚函数重写) / 字段遮蔽与二义性 |
| [`05-nil/`](05-nil/) | nil 的多张面孔 | typed nil 接口陷阱 / nil map·slice·channel·func 语义 / nil 指针接收者 |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-type-system-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-values-layout | ✅ | 值语义(皆拷贝)/零值可用/可比较性规则 |
| 01-interface-internals | ✅ | iface/eface 两字 / itab 方法表 / 动态派发 / 装值逃逸 |
| 02-method-sets | ✅ | 值vs指针接收者 / T·*T 方法集 / 可寻址性 / 一致性铁律 |
| 03-type-assertion | ✅ | comma-ok / 具体vs接口断言底层 / type switch / 与 errors.As |
| 04-embedding | ✅ | 方法提升 / 组合 vs 继承(无重写)/ 遮蔽与二义性 / 嵌接口装饰器 |
| 05-nil | ✅ | typed nil 成因 / nil map·slice·channel·func / nil 指针调方法 |
| 99-interview-cards | ✅ | 速答表(31 条) + 5 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- [`error-handling/01`](../error-handling/01-error-values/README.md) / [`05`](../error-handling/05-concurrent-errors/README.md) — typed nil 在错误场景点过,本 track `05` 是完整版
- slice/map/string 底层 → 见 [`data-structures/`](../data-structures/),本 track 只讲「它们是含指针的头」
- `java/` — Java 类型系统/继承/泛型,做对标锚点

← 回 [`golang/` master 索引](../README.md)
