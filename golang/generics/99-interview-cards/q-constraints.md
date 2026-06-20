# 约束怎么写:type set、`~`、comparable

## 一句话回答

约束(constraint)**就是接口**——它既**限制**类型参数(T 必须满足),又**赋予**T 能力(泛型体里只能对 T 做约束声明的操作)。三类常用:`any`(=任意类型,只能做通用操作,不能 `+`/`<`);`comparable`(内置,支持 `==`/`!=`,能当 map key);**类型集约束**(接口里写类型元素,如 `interface{ ~int | ~float64 }`,声明后泛型体才能用 `+`/`<` 等运算符)。`~T` 的 `~` 是**近似元素**:匹配「底层类型是 T」的所有类型(含 `type Celsius int`),不只 T 本身;`|` 是**联合**。

## 例子

```go
type Number interface{ ~int | ~int64 | ~float64 }   // 类型集:底层是这些之一
func Sum[T Number](xs []T) T { var s T; for _, x := range xs { s += x }; return s }
//                                       ↑ 因为约束声明了数值类型集,才能用 +

func Keys[K comparable, V any](m map[K]V) []K { ... } // comparable 才能当 map key
```

- `~int`:含 `type ID int` 这种;只写 `int` 则不含。
- 约束也能要求**方法**(`interface{ String() string }`),还能混合方法 + 类型集。

## 证据链接

- 正文:[`00 泛型基础`](../00-basics/README.md);可比较性 [`type-system/00`](../../../type-system/00-values-layout/README.md)

## 易追问的延伸

- **为什么能对 T 用 `+`/`<`?** 因为类型集约束声明了 T 的底层类型范围,编译器知道这些类型支持该运算符(Java 泛型做不到,只能调方法)。
- **`comparable` 和 `any` 区别?** any 啥都行但只能做通用操作;comparable 多了 `==`(代价是不能用不可比较类型实例化)。
- **类型推断?** 编译器从实参推类型参数,`Sum([]int{...})` 不用写 `Sum[int]`。
- **和 Java `<T extends X>`?** Java 靠类继承层级 + 擦除 + 不能用运算符;Go 靠接口 + 类型集 + 能用运算符、不擦除。
