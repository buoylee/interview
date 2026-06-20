# string · []byte · rune:不可变、UTF-8、转换拷贝

## 一句话回答

`string` 是**不可变的 UTF-8 字节序列**,header 是 `{ptr, len}` 两个字、指向只读字节。不可变 → 能安全共享、当 map key、并发读无锁、子串零拷贝,但 `s[i]='x'` 非法。UTF-8 是变长编码,所以 **`len(s)` 和 `s[i]` 是字节视角**(`len` 是字节数、索引取一个 `byte`),**`for i,c := range s` 是字符视角**(`c` 是 `rune`=int32 码点,`i` 是起始字节下标、会跳)。`string↔[]byte` 默认**拷贝**(只读 vs 可写语义冲突)。

## 字节 vs 字符

```go
s := "世界"
len(s)                        // 6(每个汉字 UTF-8 占 3 字节)
s[0]                          // 一个 byte(0xE4),不是 '世'
utf8.RuneCountInString(s)     // 2(字符数)
for i, c := range s {}        // i=0,c='世'; i=3,c='界'
```

- `byte` = uint8(一字节);`rune` = int32(一个 Unicode 码点)。
- 按字符处理先 `[]rune(s)`,完事 `string(rs)`。

## 转换与拷贝

- `[]byte(s)` / `string(b)` 默认**拷贝**(否则改 []byte 就破坏了 string 不可变)。
- 编译器免拷贝特例:`m[string(b)]`、`for range string(b)`、`string(b) == "x"`。
- 零拷贝:`unsafe.String`/`unsafe.Slice`(1.20+)——危险,仅热点 + 保证只读时用。
- 拼接用 `strings.Builder`(内部 []byte,O(n));循环 `+=` 是 O(n²)。

## 证据链接

- 正文:[`02 string·[]byte·rune`](../02-string-bytes-rune/README.md)

## 易追问的延伸

- **怎么数字符?** `utf8.RuneCountInString`(别 `len([]rune(s))`,后者多一次分配)。
- **子串泄漏?** `huge[:10]` 共享底层、持有它使 huge 不回收;`strings.Clone` 拷出。
- **Builder 为什么快?** 内部可增长 []byte,`String()` 用 unsafe 零拷贝返回(它保证之后不再改)。
- **和 Java String?** 都不可变;Java 内部 UTF-16(`length`/`charAt` 按 code unit),Go UTF-8(`len`/索引按字节、range 按 rune)。
