# typed nil:接口为什么 `!= nil`

## 一句话回答

接口值是**两个字 (类型, 数据指针)**,`== nil` 当且仅当**两个字都为空**。把一个**具体类型的 nil 指针**(如 `(*MyError)(nil)`)装进接口时,**类型字段被填上 `*MyError`**、数据是 nil——于是接口 **`!= nil`**,尽管它装的指针是 nil。这就是 typed nil 坑,最常见于「函数返回具体错误类型而非 `error`」。根治:**成功路径直接 `return nil`,函数返回类型写接口(`error`)**。

## 复现与根因

```go
func getError() error {
    var e *MyError = nil
    return e              // 装进 error 接口:(类型=*MyError, 数据=nil) → 非 nil!
}
err := getError()
err != nil               // true(误判成"有错误")
```

```
err = ( *MyError , nil )
        ↑ 非空     ↑ 是 nil
两个字没都空 → 接口 != nil
```

## 正确写法

```go
func do() error {
    if bad { return &MyError{} }
    return nil           // 真正的 nil 接口
}
```

不要「声明具体指针变量 → 赋值/不赋值 → return 它」;成功就显式 `return nil`。

## 证据链接

- 正文:[`05 nil 的多张面孔`](../05-nil/README.md);接口两个字见 [`01`](../01-interface-internals/README.md);错误风格场景 [`error-handling/01`](../../../error-handling/01-error-values/README.md)

## 易追问的延伸

- **其它 nil 的面孔?** nil slice 可 append(惯用零值);nil map 能读不能写(写 panic);nil channel 收发永久阻塞;nil 指针能调方法(只要不解引用接收者)。
- **怎么检测 typed nil?** 统一「返回接口 + 成功 return nil」从源头杜绝;部分静态分析能发现返回具体指针类型的隐患。
- **和 Java null 区别?** Java 单一 null、`==null` 直白;Go 因「接口两字」产生 typed nil 这种反直觉情况。
- **判 slice 空别用 ==nil?** 对,用 `len(s)==0`(同时覆盖 nil 和空 slice)。
