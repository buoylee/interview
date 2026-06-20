# 类型断言与 type switch 底层

## 一句话回答

类型断言 `x.(T)` 把值从接口里取回:**单返回值** `s := x.(T)` 失败直接 **panic**;**comma-ok** `s, ok := x.(T)` 失败给零值 + `ok=false`、不 panic——**来源不确定一律用 comma-ok**。底层:断言成**具体类型**是比类型描述符 `_type` 指针是否相等(一次指针比较,极快);断言成**接口类型**是查/建 itab 看动态类型是否实现该接口(略贵)。type switch 是其多路版,编译器用类型 hash 分桶 + 精确比对高效分发。

## 两种断言的底层差异

```go
i.(int)        // 比 i 的类型字段 == int 的 _type?(指针比较)
i.(io.Reader)  // i 的动态类型实现了 Reader 吗?→ 查 (io.Reader, 动态类型) 的 itab
```

- 具体类型:类型描述符全局唯一,断言 = 一次指针比较。
- 接口类型:可能要查 itab 表 / 算方法集,`fun[0]==0` 表示没实现。

## type switch

```go
switch v := i.(type) {
case string:        // v 是 string
case int, int64:    // 多类型 case:v 仍是原接口类型(any)
case io.Reader:     // 也能 case 接口
default:            // v 是原接口类型
}
```

编译器常用 `_type.hash`/`itab.hash` 先分桶,避免线性比 N 次。

## 证据链接

- 正文:[`03 类型断言`](../03-type-assertion/README.md);itab 见 [`01`](../01-interface-internals/README.md)

## 易追问的延伸

- **断言失败一定 panic 吗?** 不一定,comma-ok 不 panic。
- **和 `errors.As` 关系?** `As` = 沿错误链逐环做类型断言并赋值(见 [`error-handling/02`](../../../error-handling/02-wrapping/README.md))。
- **type switch case 顺序要紧吗?** 多数场景编译器已 hash 优化;但接口 case 会匹配多个动态类型,放前面可能抢走本想进具体分支的值——注意语义。
- **`any` + 大量断言是坏味道?** 是,能在编译期约束就用泛型(generics track),断言留给真异构场景。
- **和 Java 比?** `x.(T)`≈`(T)x`+`instanceof`;comma-ok 提供「安全试探不抛异常」,Java 要先 `instanceof` 再强转。
