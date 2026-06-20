# Go 类型系统与接口 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/type-system/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）

## 背景与目标

类型系统是 Go 面试「黑盒内幕」考得最深的一块：**接口底层(iface/eface/itab/动态派发)**、**方法集与接收者(为什么 `*T` 能满足接口而 `T` 不能)**、**嵌入是组合不是继承**、**typed nil 陷阱**——每个都能往运行时结构里挖。用户从 Java（有 class 继承 + 虚函数表 + 装箱）来，正好用「Go 没有继承、接口是隐式 + 两个字 + itab 方法表」做对照。

目标：读完能在白板上画出 iface/eface 两个字 + itab 方法表、讲清动态派发、答出方法集规则与 typed nil 成因、说清「组合优于继承」在 Go 里怎么落地。

## 核心设计决策

- **形式**：6 章，照搬 `error-handling/` 已认可的模板（7 段 + `99-interview-cards/`）。
- **主线钥匙 = 「接口是两个字(类型/itab + 数据指针)，方法靠 itab 表动态派发；Go 用组合 + 隐式接口取代继承」**。
- **双向桥**：Java class 继承/虚表/`instanceof`/装箱 ←→ Go 嵌入/itab/类型断言/接口装值；Python 鸭子类型 ←→ Go 隐式接口（编译期检查的鸭子类型）。
- **底层内幕进正文**：eface 两字(`_type`+data)、iface 两字(`itab`+data)、itab 结构(接口类型+具体类型+方法函数指针表)与全局缓存、direct interface 优化（单指针类型直接塞 data 字）、接口装值会拷贝/逃逸、方法集规则的编译期含义、type assert 的 itab 比对。
- **Go 版本**：1.22+。`any` = `interface{}` 别名(1.18)；泛型与接口的取舍放 generics track，本 track 只点接口这一面。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-values-layout/` | 值、类型与内存布局 | 值语义(赋值/传参皆拷贝) / 零值可用 / 可比较性规则 / 「引用类型」其实是含指针的头 ← 立地基 |
| `01-interface-internals/` | 接口底层 | iface vs eface 两个字 / itab(方法表)与全局缓存 / 动态派发 / 接口装值的拷贝与逃逸 / direct interface |
| `02-method-sets/` | 方法集与接收者 | 值 vs 指针接收者 / `T` 与 `*T` 的方法集 / 为什么 `*T` 能满足接口 `T` 不能 / 可寻址性 / 一致性铁律 |
| `03-type-assertion/` | 类型断言与类型 switch | `x.(T)` comma-ok / 接口到接口断言 / type switch / 底层怎么比 itab/_type / 性能 |
| `04-embedding/` | 嵌入与组合 | struct/interface 嵌入 / 方法提升 / 组合 vs 继承(无虚函数重写) / 字段遮蔽与二义性 |
| `05-nil/` | nil 的多张面孔 | typed nil 接口陷阱 / nil map·slice·channel·func 各自语义 / nil 指针接收者居然能调 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡(iface/eface、方法集、嵌入 vs 继承、typed nil、类型断言) |

## 已有素材的处理

- typed nil 在 `error-handling/01` 与 `05` 点过，本 track 的 `05-nil` 是**完整版**，error-handling 反链过来。
- slice/map/string 的底层留给 `data-structures/` track，本 track `00` 只讲「它们是含指针的头、所以有引用语义」，不展开扩容/hmap。
- 现有顶层 stub `reflect.md` 的内容（反射）：本 track 不展开反射，仅在 `01` 提一句「反射基于 `_type`/itab」；reflect 细节按 umbrella 计划后续并入或单列，本次不处理。

## 交付节奏

1. 写本 track spec（本文件）。
2. 搭骨架：`type-system/README.md` + 6 章目录。
3. 写 00（地基）确认风格延续，逐章推进 01–05 + 面试卡。

## 验收标准

- 01 能在白板画 iface/eface 两字 + itab，讲清动态派发与接口装值逃逸。
- 02 能说清 `T`/`*T` 方法集差异与「为什么值接收者类型的值能进接口、指针接收者类型必须用 `*T`」。
- 04 能讲「Go 用嵌入做组合、没有继承/重写」与 Java 的本质差异。
- 05 能讲透 typed nil 成因（接口两字、类型字段非空）。

## 非目标（YAGNI）

- 不展开反射(reflect)全貌、不展开泛型(归 generics track)。
- 不展开 slice/map/string 底层(归 data-structures track)。
- 不逐行读 runtime/iface.go，深到「结构 + 动态派发 + 为什么」即可。
