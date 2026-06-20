# 02 · string · []byte · rune:不可变、UTF-8、转换拷贝

> 中文/emoji 一进来,`len(s)` 给的数对不上、`s[i]` 取出来是乱码、`[]byte(s)` 莫名变慢——根因都是:**string 是不可变的 UTF-8 字节序列**,而 `len`/索引按**字节**、`range` 按**rune(码点)**。讲清这套,字符串题就稳了。
>
> 桥接锚点:Java `String` 也不可变,但内部是 UTF-16(`char`/`length()` 按 UTF-16 code unit);Go 是 **UTF-8 字节**。Go 的 `rune`(=int32)≈ Java 的 code point,`byte`(=uint8)≈ 一个 UTF-8 字节。

---

## 1. 核心问题

```go
s := "héllo世界"
fmt.Println(len(s))          // 多少?是 7 吗?
fmt.Println(s[1])            // 打印出 'é' 吗?
for i, c := range s { ... }  // i 连续 0,1,2...吗?c 是什么类型?
b := []byte(s); b[0] = 'H'   // 改得动 s 吗?这步有成本吗?
```

- `len(s)` 数的是字符数还是字节数?`s[i]` 取的是字符还是字节?
- string 为什么不能改(`s[0]='H'` 编译报错)?
- `[]byte(s)` / `string(b)` 转换为什么是**拷贝**?怎么零拷贝?

---

## 2. 直觉理解

### string = {指针, 长度} 两个字,只读的字节

```
s := "abc"
┌─────┬─────┐
│ ptr │ len │   ptr→只读字节 [a][b][c], len=3(字节数)
└─────┴─────┘
```

- string 是**不可变**的:底层字节只读,所以 `s[0]='x'` 编译就不让。
- 正因不可变,**多个 string 能安全共享同一份底层字节**(子串 `s[1:3]` 不拷贝),且能放心当 map key、并发读无锁。

### len 按字节,range 按 rune

UTF-8 是**变长编码**:ASCII 1 字节,`é` 2 字节,`世` 3 字节,emoji 4 字节。所以:

- `len("héllo世界")` = 1+2+1+1+1+3+3 = **12 字节**(不是 7 个字符)。
- `s[i]` 取**第 i 个字节**(类型 `byte`),对多字节字符就是半个,乱码。
- `for i, c := range s`:`c` 是 **rune**(int32,一个完整码点),`i` 是该字符的**起始字节下标**(所以 i 会跳:0,1,3,4,5,6,9...)。

记忆:**索引/len 是字节视角,range 是字符(rune)视角。** 要数字符个数用 `utf8.RuneCountInString(s)` 或 `len([]rune(s))`。

### rune 和 byte

- `byte` = `uint8`,一个字节。
- `rune` = `int32`,一个 Unicode 码点(字符)。`'A'`、`'世'` 都是 rune 字面量。

---

## 3. 原理深入

### 3.1 不可变带来的「转换必拷贝」

`string` 只读、`[]byte` 可写,语义冲突,所以互转**默认拷贝一份**:

```go
b := []byte(s)      // 拷贝 s 的字节到新的可写数组(否则改 b 就改了"不可变"的 s)
s2 := string(b)     // 再拷贝回只读区
```

- 大字符串 / 高频转换时,这是实打实的分配 + 拷贝开销。
- **编译器优化的免拷贝特例**(知道就好):`m[string(b)]`(用 []byte 查 string-key map)、`for range string(b)`、`string(b) == "literal"` 等场景编译器能证明不逃逸,**省掉拷贝**。

### 3.2 零拷贝转换(Go 1.20+ 的 unsafe.String / unsafe.Slice)

确实需要零拷贝(只读、且保证不改、生命周期可控)时:

```go
import "unsafe"
b := []byte{'h','i'}
s := unsafe.String(&b[0], len(b))      // 不拷贝,s 共享 b 的内存(1.20+)
p := unsafe.Slice(unsafe.StringData(s), len(s))  // string→[]byte 零拷贝
```

⚠️ 危险:零拷贝得来的 string 与 []byte 共享内存,**改了 []byte 就破坏了 string 的不可变假设**,会引发诡异 bug。只在性能热点、且能严格保证只读时用,平时老老实实拷贝。

### 3.3 拼接与 strings.Builder

```go
// ❌ 循环里 s += x:每次都新建字符串 + 拷贝全部历史,O(n²)
// ✅ strings.Builder:内部用可增长 []byte,最后一次成型,O(n)
var b strings.Builder
for _, x := range parts { b.WriteString(x) }
result := b.String()                    // 内部零拷贝转成 string
```

`strings.Builder` 内部维护一个 `[]byte`,`String()` 用 unsafe 零拷贝返回(它能保证 builder 之后不再改),所以高效。大量拼接必用它(或 `bytes.Buffer`)。

### 3.4 子串共享与内存泄漏

`sub := huge[:10]`(string 切片)**共享** huge 的底层字节 → 持有 sub 会让整个 huge 的内存无法释放(同 slice 的子切片泄漏)。需要长期持有小子串就 `strings.Clone(sub)`(1.18+)拷出独立副本。

---

## 4. 日常开发应用

- **数字符个数**用 `utf8.RuneCountInString(s)`,别用 `len(s)`(那是字节)。
- **遍历字符**用 `for _, r := range s`(出 rune);**遍历字节**用 `for i:=0;i<len(s);i++`。
- **要按字符索引/反转**先 `[]rune(s)`(转成码点切片),处理完 `string(rs)`。
- **大量拼接**用 `strings.Builder`,别 `+=`。
- **频繁 string↔[]byte** 想清楚是否真要转;能用 `bytes.*` 或 `strings.*` 直接处理就别来回转。
- **零拷贝 `unsafe.String/Slice` 仅限热点 + 能保证只读**,否则别碰。

---

## 5. 生产&调优实战

- **`[]byte(s)`/`string(b)` 转换是隐藏分配热点**:HTTP/JSON 处理里高频转换会拉高 GC;profile 看到 `[]byte`/`string` 转换的分配,考虑减少转换次数或用零拷贝特例。
- **`+=` 拼接在循环里是 O(n²) 灾难**:大文本拼接务必 Builder。
- **子串持有大字符串 = 内存泄漏**:解析大响应只留一小段时 `strings.Clone`。
- **`[]rune(s)` 会分配且放大内存**(每字符 4 字节);只为数长度用 `utf8.RuneCountInString`,别 `len([]rune(s))`(后者多一次分配)。
- **string 比较是逐字节**:长 string 频繁 `==` 有成本,但通常先比 len/指针,可忽略。

---

## 6. 面试高频考点

- **string 底层?为什么不可变?** `{ptr, len}` 两个字、指向只读字节;不可变所以能安全共享、当 map key、并发读无锁、子串不拷贝。
- **`len(s)` 是字符数还是字节数?** **字节数**(UTF-8 变长)。数字符用 `utf8.RuneCountInString`。
- **`s[i]` 取什么?** 第 i 个**字节**(`byte`),多字节字符取出是半个。
- **`range` string 出什么?** `for i,c := range s`:`c` 是 **rune**(完整码点),`i` 是起始字节下标(会跳)。
- **byte vs rune?** byte=uint8(一字节);rune=int32(一个 Unicode 码点)。
- **`[]byte(s)` 为什么拷贝?怎么零拷贝?** string 只读、[]byte 可写,语义冲突故拷贝;`unsafe.String/Slice`(1.20+)可零拷贝但危险(共享内存破坏不可变)。编译器对 `m[string(b)]` 等特例免拷贝。
- **怎么高效拼接?** `strings.Builder`(内部 []byte,O(n));`+=` 在循环是 O(n²)。
- **和 Java String 区别?** 都不可变;Java 内部 UTF-16(`length()`/`charAt` 按 code unit),Go UTF-8 字节(`len`/索引按字节、range 按 rune)。

---

## 7. 一句话总结

> **string 是不可变的 UTF-8 字节序列,header 是 `{ptr, len}` 两个字。** 不可变 → 能安全共享、当 key、并发读无锁、子串零拷贝、但 `s[i]='x'` 非法。UTF-8 变长 → **`len`/`s[i]` 是字节视角**(`len` 是字节数、索引取一个 `byte`),**`range` 是字符视角**(出 `rune`=int32 码点 + 起始字节下标);数字符用 `utf8.RuneCountInString`。`string↔[]byte` 默认**拷贝**(只读 vs 可写的语义冲突),热点可用 `unsafe.String/Slice`(1.20)零拷贝但危险。拼接用 `strings.Builder`(O(n)),别循环 `+=`(O(n²));子串持有大串会内存泄漏,用 `strings.Clone`。

← 上一章 [`01 map`](../01-map/README.md) ｜ 下一章 → [`03 逃逸分析与栈堆`](../03-escape-analysis/README.md):前面反复说「会逃逸到堆」——到底什么决定一个值在栈上还是堆上?怎么用 `-gcflags=-m` 看。｜ 回 [`data-structures` 索引](../README.md)
