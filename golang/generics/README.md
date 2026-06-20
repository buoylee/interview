# Go 泛型 —— 给 Java 后端的「不是擦除,也不是模板,而是 GCShape + 字典」

> 泛型(Go 1.18)让你写「对任意类型都成立、又有编译期类型安全」的代码,避免 `interface{}` 装箱。但它的底层实现很独特——**既不是 C++ 模板的完全单态化,也不是 Java 的类型擦除,而是 GCShape stenciling + 字典**,还带来「泛型有时比接口/手写更慢」的反直觉。这些都是资深面试点。
>
> 总钥匙:**接口为行为(运行期动态派发),泛型为类型(编译期参数化);Go 泛型用 GCShape 共享实例 + 字典传类型信息,在「代码膨胀」和「运行期开销」之间折中。**
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-generics-track-design.md`｜Go 版本基线 1.22+（泛型 1.18+）

## 怎么用这个 track

1. **按顺序读**：`00` 基础(怎么写约束/推断),`01` 底层(GCShape+字典,白板加分项),`02` 工程取舍(泛型 vs 接口 vs 代码生成)。
2. **每章固定 7 段**。
3. **双向桥**：对照 **Java**(类型擦除 / bounded wildcard / 装箱)、**C++**(模板单态化)、**Python**(鸭子类型)。
4. **想答面试**：去 `99-interview-cards/` 找卡。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-basics/`](00-basics/) | 泛型基础 | type parameters / constraints(any·comparable·union·`~`)/ 类型推断 / 限制 / slices·maps·cmp ← 从这开始 |
| [`01-implementation/`](01-implementation/) | **底层实现** | GCShape stenciling + 字典 / 对比 C++ 单态化与 Java 擦除 / 性能反直觉 |
| [`02-when-to-use/`](02-when-to-use/) | 工程取舍 | 泛型 vs 接口 vs 代码生成 / 「接口为行为,泛型为类型」/ 何时别用 |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-generics-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-basics | ✅ | type params / constraints(any·comparable·union·`~`)/ 类型推断 / slices·maps·cmp |
| 01-implementation | ✅ | GCShape stenciling + 字典 / 对比 C++ 单态化·Java 擦除 / 性能反直觉 |
| 02-when-to-use | ✅ | 接口为行为·泛型为类型 / 只调方法用接口 / vs codegen |
| 99-interview-cards | ✅ | 速答表(16 条) + 3 张深题卡 |

**本 track 全部完成。A 层(语言内核)四条主线全部交付。**

## 关联已有笔记（复用不重复）

- [`type-system/01`](../type-system/01-interface-internals/README.md) — 接口动态派发(本 track 反复对照「泛型编译期 vs 接口运行期」)
- [`type-system/00`](../type-system/00-values-layout/README.md) — 可比较性(`comparable` 约束)
- [`data-structures/03`](../data-structures/03-escape-analysis/README.md) — 装箱/逃逸(泛型避免 `interface{}` 装箱)
- `java/` — Java 泛型擦除,做对标锚点

← 回 [`golang/` master 索引](../README.md)
