# 99 · 面试卡 —— Go 泛型高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**接口为行为(运行期),泛型为类型(编译期);实现是 GCShape stenciling + 字典。**

## 卡片索引(深题卡)

- [约束怎么写:type set、`~`、comparable](q-constraints.md)
- [底层实现:GCShape stenciling + 字典](q-gcshape.md)
- [泛型 vs 接口:怎么选](q-generics-vs-interface.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| 泛型解决什么 | 同逻辑多类型 + 编译期类型安全 + 免 interface{} 装箱/断言 | [00](../00-basics/README.md) |
| constraint 是什么 | 就是接口;既限制类型参数又赋予能力(只能做约束声明的操作) | [00](../00-basics/README.md) |
| any / comparable | any=任意(只能做通用操作);comparable=支持 ==(可当 key) | [00](../00-basics/README.md) |
| 类型集 / union / ~ | 接口里写类型元素;`|` 联合;`~int` 匹配底层类型是 int 的类型;声明后能用运算符 | [00](../00-basics/README.md) |
| 方法能有类型参数吗 | 不能(只能用所属类型的);要参数化用泛型函数 | [00](../00-basics/README.md) |
| 类型推断 | 编译器从实参推类型参数,多数不用写 [T] | [00](../00-basics/README.md) |
| 标准库泛型 | slices/maps/cmp + min/max/clear(1.21);cmp.Ordered 取代 x/exp/constraints | [00](../00-basics/README.md) |
| 泛型怎么实现/几份代码 | GCShape stenciling + 字典:按内存形状分组,**指针类型共享一份**,各值类型各一份 | [01](../01-implementation/README.md) |
| GCShape 是什么 | 内存布局(对 GC/运行时)相同的一组类型;所有指针同一个 GCShape | [01](../01-implementation/README.md) |
| 字典干嘛 | 隐藏参数,带具体类型 _type + 方法地址,让共享代码对不同类型行为正确 | [01](../01-implementation/README.md) |
| 和 C++/Java 区别 | C++ 完全单态化(膨胀);Java 擦除(装箱/丢类型);Go 折中(分组+字典,不装箱值类型) | [01](../01-implementation/README.md) |
| 泛型一定更快吗 | 不一定;调 T 方法走字典间接、难内联,可能比接口慢;纯值操作(免装箱)才通常更快 | [01](../01-implementation/README.md) |
| 泛型 vs 接口怎么选 | 接口为行为(运行期多态/异构);泛型为类型(容器/算法/免装箱) | [02](../02-when-to-use/README.md) |
| 一条硬判据 | 泛型体里只调类型参数的方法 → 改用接口(更简单) | [02](../02-when-to-use/README.md) |
| 什么时候别用泛型 | 只调方法/各类型实现不同/只有一个类型/反射更自然/伤可读性 | [02](../02-when-to-use/README.md) |
| 代码生成还有用吗 | 有:泛型替代"为类型重复",codegen 留给"为元数据/样板生成"(序列化/mock/方法) | [02](../02-when-to-use/README.md) |

← 回 [`generics` 索引](../README.md)
