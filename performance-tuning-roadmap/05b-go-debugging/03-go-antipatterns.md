# Go 常见性能反模式

## 概述

Go 语言的设计哲学追求简单和显式，但这并不意味着写出的代码天然就是高性能的。许多看似正确的写法在高并发或热路径上会带来严重的性能问题。本文整理了生产环境中最常见的 Go 性能反模式及其解决方案。

## 反模式一：过度使用 Channel

Go 的口号"不要通过共享内存来通信"被许多开发者过度解读，认为所有并发问题都应该用 channel 解决。

```go
// 反模式：用 channel 保护一个简单计数器
type Counter struct {
    ch chan int
}

func NewCounter() *Counter {
    c := &Counter{ch: make(chan int, 1)}
    c.ch <- 0
    return c
}

func (c *Counter) Increment() {
    v := <-c.ch
    c.ch <- v + 1
}

func (c *Counter) Get() int {
    v := <-c.ch
    c.ch <- v
    return v
}
```

这段代码功能正确，但 channel 操作涉及 goroutine 调度和内存拷贝，比 mutex 慢一个数量级。

```go
// 正确做法：简单共享状态用 mutex 或 atomic
type Counter struct {
    val atomic.Int64
}

func (c *Counter) Increment() { c.val.Add(1) }
func (c *Counter) Get() int64 { return c.val.Load() }
```

**判断标准**：如果你只是在保护一个共享变量的读写（没有数据传递语义），用 mutex 或 atomic。Channel 适用于 goroutine 间的数据传递和协调。

## 反模式二：Slice Append 内存泄漏

### 问题一：底层数组不释放

```go
// 从一个大 slice 中取一小部分
func getHeader(data []byte) []byte {
    return data[:10] // 返回的 slice 仍然引用整个底层数组
}
```

如果 `data` 是 10MB，`getHeader` 返回的 10 字节 slice 会导致整个 10MB 无法被 GC 回收。

```go
// 正确做法：拷贝一份
func getHeader(data []byte) []byte {
    header := make([]byte, 10)
    copy(header, data[:10])
    return header
}

// 或者使用 Go 1.21+ 的 bytes.Clone
func getHeader(data []byte) []byte {
    return bytes.Clone(data[:10])
}
```

### 问题二：append 后原 slice 元素的引用

```go
type User struct {
    Name string
    Data *LargeStruct
}

func filterUsers(users []*User) []*User {
    var result []*User
    for _, u := range users {
        if u.Name != "" {
            result = append(result, u)
        }
    }
    // 如果 users 有 1000 个元素，result 只有 10 个
    // 但 users 底层数组中被过滤掉的 990 个 User 对象不会被 GC
    // ——因为 users slice 本身还在作用域中
    return result
}
```

在长期存活的数据结构中，这个问题尤其严重。解决方案：过滤后将不需要的位置设为 nil。

## 反模式三：defer 在热路径上的开销

Go 1.14 之前，每个 defer 调用会在堆上分配一个 defer 结构体，代价约 50-100ns。Go 1.14 进行了开放编码优化（open-coded defers），将简单 defer 内联化，开销降到接近零。

但有些情况下 defer 仍然无法内联：
- 在循环中使用 defer
- defer 闭包捕获了过多的变量
- 函数有超过 8 个 defer

```go
// 热路径上避免不必要的 defer
func hotPathBad(mu *sync.Mutex) {
    mu.Lock()
    defer mu.Unlock() // 有少量开销
    // 很短的临界区
    counter++
}

// 如果临界区极短且调用频率极高
func hotPathGood(mu *sync.Mutex) {
    mu.Lock()
    counter++
    mu.Unlock() // 手动 unlock，零开销
}
```

**实际建议**：除非 benchmark 证明 defer 是瓶颈（每秒千万次调用级别），否则优先使用 defer 以保证安全性。过早优化 defer 是得不偿失的。

## 反模式四：string 和 []byte 频繁转换

Go 中 string 是不可变的，`[]byte` 是可变的。二者转换必须拷贝内存：

```go
func processData(data []byte) string {
    s := string(data)       // 拷贝一次
    result := process(s)
    b := []byte(result)     // 又拷贝一次
    return string(b)        // 再拷贝一次
}
```

优化方案：

```go
// 方案一：统一使用 []byte 或 string，减少转换
func processData(data []byte) []byte {
    // 全程用 []byte 操作
    return processBytes(data)
}

// 方案二：使用 unsafe 零拷贝转换（Go 1.20+）
import "unsafe"

func bytesToString(b []byte) string {
    return unsafe.String(unsafe.SliceData(b), len(b))
}

func stringToBytes(s string) []byte {
    return unsafe.Slice(unsafe.StringData(s), len(s))
}
```

**unsafe 方案的风险**：转换后的 `[]byte` 不能被修改，否则会违反 string 的不可变性约定，导致未定义行为。仅在你能保证不修改的场景下使用。

Go 编译器在某些场景下会自动优化掉拷贝：
- `map[string(b)]` — 用 `[]byte` 查 string key 的 map 时不拷贝
- `for range string(b)` — range 遍历时不拷贝
- `"prefix" + string(b)` — 字符串拼接时可能优化

## 反模式五：interface{}/any 装箱开销

将值类型赋给 interface{} 时会发生"装箱"（boxing）：

```go
func processAny(v interface{}) { /* ... */ }

func caller() {
    x := 42
    processAny(x) // int → interface{} 装箱：在堆上分配空间存储 int 值
}
```

装箱导致：
1. 堆分配（逃逸到堆）
2. 增加 GC 压力
3. 间接访问（通过指针）

```go
// 在热路径上，用具体类型代替 interface{}
// 反模式
func sum(values []interface{}) int64 {
    var total int64
    for _, v := range values {
        total += v.(int64) // 类型断言也有开销
    }
    return total
}

// 正确
func sum(values []int64) int64 {
    var total int64
    for _, v := range values {
        total += v
    }
    return total
}

// Go 1.18+：用泛型替代 interface{}
func Sum[T int | int64 | float64](values []T) T {
    var total T
    for _, v := range values {
        total += v
    }
    return total
}
```

## 反模式六：Map 删除 Key 后内存不释放

Go 的 map 只增不缩。删除 key 只是标记为空位，不会释放底层的 bucket 内存：

```go
func mapMemoryLeak() {
    m := make(map[int][]byte)

    // 插入 100 万个 key
    for i := 0; i < 1_000_000; i++ {
        m[i] = make([]byte, 1024) // 每个 value 1KB
    }
    // 此时 map 占用约 1GB+

    // 删除所有 key
    for i := 0; i < 1_000_000; i++ {
        delete(m, i)
    }
    // map 本身的 bucket 数组仍然是 100 万个 bucket 的大小
    // 虽然 value 的 1KB []byte 会被 GC，但 map 结构本身不缩

    runtime.GC()
    // 内存仍然很高
}
```

解决方案：

```go
// 定期重建 map
func rebuildMap(old map[int][]byte) map[int][]byte {
    newMap := make(map[int][]byte, len(old))
    for k, v := range old {
        newMap[k] = v
    }
    return newMap
    // old 不再被引用，下次 GC 会回收整个 bucket 数组
}

// 或者在业务层面定期重建缓存
type Cache struct {
    mu sync.RWMutex
    m  map[string]Value
}

func (c *Cache) Rebuild() {
    c.mu.Lock()
    defer c.mu.Unlock()
    newMap := make(map[string]Value, len(c.m))
    for k, v := range c.m {
        newMap[k] = v
    }
    c.m = newMap
}
```

## 反模式七：时间处理陷阱

```go
// time.Now() 有一定开销（系统调用级别，约 50-100ns）
// 在超高频调用的热路径上避免反复调用
func hotPath() {
    for i := 0; i < 1_000_000; i++ {
        start := time.Now() // 100 万次系统调用
        doTinyWork()
        elapsed := time.Since(start)
        recordMetric(elapsed)
    }
}

// 如果只需要单调时钟差值，可以批量处理
func hotPathOptimized() {
    start := time.Now()
    for i := 0; i < 1_000_000; i++ {
        doTinyWork()
    }
    elapsed := time.Since(start)
    recordMetric(elapsed / 1_000_000) // 平均值
}
```

另一个陷阱：`time.After` 在循环中使用会泄漏 Timer：

```go
// 反模式：每次循环创建新的 Timer，旧的 Timer 直到触发才会被 GC
for {
    select {
    case msg := <-ch:
        process(msg)
    case <-time.After(5 * time.Second): // 每次循环泄漏一个 Timer！
        fmt.Println("timeout")
    }
}

// 正确：复用 Timer
timer := time.NewTimer(5 * time.Second)
defer timer.Stop()
for {
    timer.Reset(5 * time.Second)
    select {
    case msg := <-ch:
        process(msg)
    case <-timer.C:
        fmt.Println("timeout")
    }
}
```

## 反模式八：并发 Map 使用不当

```go
// 会直接 panic: concurrent map writes
var m = make(map[string]int)

func handler(w http.ResponseWriter, r *http.Request) {
    key := r.URL.Path
    m[key]++ // 多个 goroutine 并发写 → panic
}
```

Go 运行时在检测到并发 map 写入时会直接 panic（不是数据竞争，是 fatal error，Race Detector 不需要就能触发）。这是 Go 团队有意为之的设计，避免静默的数据损坏。

修复方案参见前面 Race Detector 章节的 sync.RWMutex 或 sync.Map 方案。

## 性能反模式排查清单

```
代码审查时关注：
[ ] Channel 是否用于不需要数据传递语义的场景 → 改用 mutex/atomic
[ ] 大 slice 截取后是否拷贝了需要的部分
[ ] 热路径上是否有不必要的 string ↔ []byte 转换
[ ] interface{} 参数是否可以用具体类型或泛型替代
[ ] Map 在大量删除后是否定期重建
[ ] for-select 中是否使用了 time.After
[ ] 并发访问 map 是否有锁保护
[ ] HTTP response body 是否读完并 Close
```

## 小结

1. Channel 比 mutex 慢 10x+，简单共享状态保护用 mutex 或 atomic
2. 大 slice 截取后要 copy 或 Clone，避免底层数组无法回收
3. string/[]byte 转换尽量减少，热路径可用 unsafe 零拷贝（谨慎）
4. interface{} 装箱导致堆分配，热路径上用具体类型或泛型
5. Go map 只增不缩，大量删除后需要重建
6. for-select 中用 Timer.Reset 代替 time.After
7. 并发写 map 会直接 panic，必须加锁
