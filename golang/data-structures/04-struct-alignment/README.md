# 04 · struct 内存对齐与布局

> 同样三个字段,换个声明顺序,一个 struct 可能是 24 字节也可能是 16 字节——差距来自**内存对齐(alignment)与填充(padding)**。这是「省内存 + 理解 cache」的资深题,也是 map 把 key/value 分开存、避免 false sharing 的底层原因。
>
> 桥接锚点:Java 对象也有对齐和 padding(对象按 8 字节对齐、`@Contended` 防 false sharing),但布局由 JVM 定、你管不着;Go 的 struct 字段**按你声明的顺序**排,所以**字段顺序是你能控制的优化点**。

---

## 1. 核心问题

```go
type A struct {
    a bool      // 1 字节
    b int64     // 8 字节
    c bool      // 1 字节
}
type B struct {
    b int64     // 8 字节
    a bool      // 1 字节
    c bool      // 1 字节
}
// unsafe.Sizeof(A{}) 和 unsafe.Sizeof(B{}) 一样吗?
```

- 三个字段总共 1+8+1=10 字节,为什么 `Sizeof` 不是 10?
- 为什么 `A` 和 `B` 字段一样、只是顺序不同,大小却可能不一样?
- 怎么排字段最省内存?

---

## 2. 直觉理解

### 对齐:每个类型要落在它大小的整数倍地址上

CPU 读内存按字长块来,**未对齐的访问慢甚至(某些平台)出错**。所以编译器要求:

- `int64`/`float64`/指针(64 位平台)要放在 **8 的倍数**地址;
- `int32` 放 4 的倍数;`int16` 放 2 的倍数;`bool`/`byte` 任意(对齐 1)。
- 整个 struct 的对齐 = 它**最大字段的对齐**;struct 大小要**向上取整到自身对齐的倍数**。

为了满足这些,编译器在字段间**插入填充字节(padding)**。

### 字段顺序决定 padding 多少

`A{a bool; b int64; c bool}` 的排布:

```
a(1) [pad 7] b(8) c(1) [pad 7]   → 24 字节
↑ a 后要填 7 字节,b 才能落到 8 的倍数;末尾再填 7 让总大小是 8 的倍数
```

`B{b int64; a bool; c bool}`:

```
b(8) a(1) c(1) [pad 6]           → 16 字节
↑ b 已对齐,a、c 紧挨,末尾填 6 凑成 8 的倍数
```

同样字段,`B` 省了 8 字节!**经验法则:字段按大小从大到小排(8→4→2→1),padding 最少。**

---

## 3. 原理深入

### 3.1 用 unsafe 三件套看布局

```go
unsafe.Sizeof(A{})        // 整个 struct 占多少字节(含 padding)
unsafe.Alignof(A{})       // 对齐要求(= 最大字段对齐)
unsafe.Offsetof(A{}.b)    // 某字段在 struct 内的偏移
```

这三个是编译期常量,讲对齐时直接拿来验证。

### 3.2 空 struct `struct{}`:零字节

`struct{}` 大小是 **0**。用途:

- `map[string]struct{}` 当**集合(set)**——value 不占空间。
- `chan struct{}` 当**纯信号**(只传「发生了」不传数据,见 [`concurrency`](../../concurrency/05-channel-select/README.md))。

> 细节:多个零大小字段/对象可能共享同一地址;`&struct{}{}` 合法但都指向同一个 runtime.zerobase。

### 3.3 为什么 map 把 key 和 value 分开存

回忆 [`01 map`](../01-map/README.md):bucket 里是 `key×8` 连续、再 `value×8` 连续,而不是 `(k,v)(k,v)...` 交错。原因正是对齐:`map[int8]int64` 若交错排,每个 int8 后要填 7 字节;**分开存则 8 个 int8 紧排、8 个 int64 紧排**,几乎无 padding。这是对齐知识在标准库里的真实应用。

### 3.4 false sharing(点到为止)

CPU 缓存以 **cache line(通常 64 字节)** 为单位。两个被不同 goroutine 高频写的字段若落在**同一 cache line**,会互相使对方缓存失效(false sharing),性能暴跌。解法:在字段间 padding 撑开到不同 cache line(`[64]byte` 填充)。这是高并发计数器/分片锁的优化点,深入见 [`concurrency/06`](../../concurrency/06-sync-memory-model/README.md) 与 perf-roadmap。

---

## 4. 日常开发应用

- **内存敏感 / 海量实例的 struct,字段从大到小排**(指针/int64 → int32 → int16 → bool/byte)。少量对象不必纠结。
- **set 用 `map[K]struct{}`**、信号用 `chan struct{}`,省内存。
- **拿不准布局就 `unsafe.Sizeof`/`Offsetof` 实测**,或用 `fieldalignment`(golang.org/x/tools)工具自动检查/修复字段顺序:
  ```bash
  fieldalignment -fix ./...      # 自动重排字段省内存
  ```
- **别为对齐牺牲可读性**:除非是高频/海量结构,字段按逻辑分组通常比按大小排更可维护。

---

## 5. 生产&调优实战

- **海量小 struct 的 padding 浪费会放大**:一个 struct 多 8 字节,放进百万元素的 slice 就是 8MB。内存敏感服务用 `fieldalignment` 扫一遍常有惊喜。
- **对齐影响 cache 命中**:紧凑的 struct 数组对 CPU cache 友好(顺序遍历快);臃肿的 padding 降低 cache 利用率。
- **false sharing 是高并发隐形杀手**:分片计数器、worker 本地状态数组,相邻元素被不同核高频写时,用 padding 隔到不同 cache line(或 `sync/atomic` 的对齐保证)。
- **atomic 对齐要求**:32 位平台上 `atomic` 操作 64 位值要求 8 字节对齐,否则 panic;把 64 位 atomic 字段放 struct 开头是常见保险做法。

---

## 6. 面试高频考点

- **为什么 struct 大小不等于字段之和?** 内存对齐:字段要落在其大小的整数倍地址,编译器插 padding;struct 大小向上取整到自身对齐(=最大字段对齐)的倍数。
- **字段顺序为什么影响大小?** 不同顺序产生的 padding 不同;从大到小排 padding 最少。给个例子能算出 24 vs 16。
- **怎么省内存?** 字段按对齐从大到小排;用 `unsafe.Sizeof` 验证、`fieldalignment -fix` 自动修。
- **空 struct 多大?有什么用?** 0 字节;`map[K]struct{}` 当 set、`chan struct{}` 当信号。
- **map 为什么 key/value 分开存?** 减少对齐 padding(分开紧排 vs 交错每个都补齐)。
- **false sharing 是什么?怎么解?** 不同核高频写的字段落同一 cache line(64B)互相失效;padding 撑到不同 line。
- **和 Java 区别?** Java 对象布局由 JVM 定(你管不着,`@Contended` 防伪共享);Go 按声明顺序排,字段顺序是你能控的优化点。

---

## 7. 一句话总结

> **struct 大小 ≠ 字段之和,因为内存对齐:每个字段要落在其大小的整数倍地址,编译器插 padding,struct 总大小向上取整到「最大字段对齐」的倍数。** 所以同样字段、不同顺序大小可能不同(`{bool,int64,bool}`=24,`{int64,bool,bool}`=16)——**字段从大到小排 padding 最少**,海量实例时省内存可观(用 `unsafe.Sizeof` 验证、`fieldalignment -fix` 自动修)。`struct{}` 是 0 字节(set/信号用)。对齐还解释了 map 为何 key/value 分开存,以及高并发下用 padding 隔开 cache line 防 false sharing。和 Java「布局由 JVM 定」不同,Go 字段顺序是你能掌控的优化点。

← 上一章 [`03 逃逸分析`](../03-escape-analysis/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):slice 扩容、map 内幕、string·rune、逃逸、对齐速查。｜ 回 [`data-structures` 索引](../README.md)
