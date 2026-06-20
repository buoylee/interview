# Go 泛型 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/generics/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）

## 背景与目标

泛型(Go 1.18)是面试新热点,且**底层实现(GCShape stenciling + 字典)很独特**——既不是 C++ 模板的完全单态化,也不是 Java 的类型擦除,介于两者之间,还有「泛型有时比接口/手写更慢」的反直觉点。资深面试爱考:**约束怎么写(type set/`~`/comparable)、底层怎么实现、什么时候该用泛型而不是接口**。用户从 Java 泛型(擦除)来,正好对照。

目标:读完能解释 type parameters/constraints、能讲 GCShape stenciling+字典与 C++/Java 的区别、能答「泛型 vs 接口 vs 代码生成」的取舍。

## 核心设计决策

- **形式**：3 章(右配:泛型比 error/类型系统薄),照搬已认可模板(7 段 + `99-interview-cards/`)。
- **主线钥匙 = 「接口为行为(运行期动态派发),泛型为类型(编译期参数化 + GCShape 共享实例 + 字典传类型信息)」**。
- **双向桥**：Java 泛型擦除/bounded wildcard/装箱 ←→ Go GCShape stenciling(不擦除、不装箱值类型);C++ 模板完全单态化(代码膨胀)←→ Go 折中;Python 鸭子类型/typing。
- **底层内幕进正文**:type set 与 `~`、`comparable`、type inference、不能有参数化方法;GCShape 的定义(所有指针型共享一个 shape,各值类型独立)、字典作隐藏参数、为什么是「省代码但有间接成本」的折中、泛型方法调用走字典可能比单态化慢。
- **Go 版本**:1.18 泛型;`cmp.Ordered`、`slices`/`maps` 标准库、`min`/`max`/`clear` 内置 1.21;`constraints` 包在 `golang.org/x/exp`。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-basics/` | 泛型基础 | 为什么要泛型 / type parameters / constraints(any·comparable·union·`~`)/ 类型推断 / 限制(无参数化方法)/ slices·maps·cmp·min·max | 
| `01-implementation/` | 底层实现 | GCShape stenciling + 字典 / 对比 C++ 单态化与 Java 擦除 / 性能反直觉(字典间接、可能比接口慢) |
| `02-when-to-use/` | 工程取舍 | 泛型 vs 接口 vs 代码生成 / 「接口为行为,泛型为类型」/ 何时别用泛型 |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡(约束/GCShape/泛型 vs 接口) |

## 已有素材的处理

- 承接 [`type-system/01`](接口动态派发):本 track 反复对照「泛型编译期 vs 接口运行期」。
- 承接 [`data-structures/03`](逃逸/装箱):泛型避免 `interface{}` 装箱,本 track `01`/`02` 引用。
- `comparable` 约束与 [`type-system/00`](可比较性)互链。

## 交付节奏

1. 写本 spec。2. 骨架 README + 3 章目录。3. 写 00 确认,推进 01/02 + 面试卡。

## 验收标准

- 00 能写出一个带约束的泛型函数并解释 `~`、`comparable`、类型推断。
- 01 能讲 GCShape stenciling+字典是什么、和 C++/Java 的区别、为什么可能比预期慢。
- 02 能给出「这个场景该用泛型还是接口」的判据。

## 非目标（YAGNI）

- 不做泛型数据结构大全(点到通用容器即可)。
- 不逐行讲编译器实现,深到「GCShape+字典机制 + 取舍」即可。
- 不重讲接口底层(链 type-system)。
