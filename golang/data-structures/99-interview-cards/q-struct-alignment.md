# struct 内存对齐与字段重排

## 一句话回答

struct 大小 **≠ 字段之和**,因为**内存对齐**:每个字段必须落在其大小的整数倍地址(int64/指针在 64 位平台要 8 字节对齐,int32 要 4,bool/byte 要 1),编译器在字段间插**填充(padding)**;整个 struct 的对齐 = 最大字段的对齐,**总大小向上取整到该对齐的倍数**。所以同样字段、不同声明顺序大小可能不同——**字段从大到小排(8→4→2→1)padding 最少**。

## 例子

```go
type A struct{ a bool; b int64; c bool }   // a[pad7]b c[pad7] = 24 字节
type B struct{ b int64; a bool; c bool }   // b a c[pad6]      = 16 字节
```

同样字段,B 省 8 字节。海量实例时差距放大(百万个 ×8B = 8MB)。

## 工具与应用

- `unsafe.Sizeof` / `Alignof` / `Offsetof`——编译期常量,验证布局。
- `fieldalignment -fix ./...`(golang.org/x/tools)自动重排字段省内存。
- **空 struct `struct{}` = 0 字节**:`map[K]struct{}` 当 set、`chan struct{}` 当信号。
- **map 把 key/value 分开存**正是为减少对齐 padding(分开紧排 vs 交错每个补齐)。

## 证据链接

- 正文:[`04 struct 对齐`](../04-struct-alignment/README.md);map 布局 [`01`](../01-map/README.md)

## 易追问的延伸

- **false sharing?** 不同核高频写的字段落同一 cache line(通常 64B)会互相使缓存失效;用 padding 撑到不同 line(高并发计数器/分片锁优化)。见 [`concurrency/06`](../../../concurrency/06-sync-memory-model/README.md)。
- **atomic 对齐坑?** 32 位平台 64 位 atomic 值要 8 字节对齐,否则 panic;常把它放 struct 开头。
- **要不要总是按大小排?** 海量/热点结构值得;少量对象按逻辑分组更可读,别过度优化。
- **和 Java 区别?** Java 布局由 JVM 定(`@Contended` 防伪共享);Go 按声明顺序排,字段顺序是你能控的优化点。
