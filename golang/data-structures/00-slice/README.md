# 00 · slice 底层:三元组 header、扩容、别名坑

> slice 是 Go 最常用也最容易踩坑的类型。坑全来自一个事实:**slice 是个三元组 header(指针/长度/容量),多个 slice 可能共享同一个底层数组**。理解这点,扩容、别名、`append` 的迷惑行为全部解释得通。
>
> 桥接锚点:slice ≈ Java `ArrayList`(可变长 + 底层数组 + 扩容),但 slice 是**值**(header 拷贝)、且能**共享**底层数组开「窗口」(Java 没有这种 reslice 别名语义)。

---

## 1. 核心问题

```go
a := []int{1, 2, 3, 4, 5}
b := a[1:3]              // b 看到 [2,3];b 和 a 什么关系?
b[0] = 99               // a 变了吗?
b = append(b, 100)      // 这个 100 写到哪了?a[3] 被覆盖了吗?
fmt.Println(a, b)       // 输出什么?
```

- slice 在内存里是什么?`a[1:3]` 是拷贝还是共享?
- `append` 什么时候原地写、什么时候分配新数组?扩容扩多少?
- 为什么「函数里 append slice,外面看不到」?(承接 [`type-system/00`](../../type-system/00-values-layout/README.md))

---

## 2. 直觉理解

### slice = {指针, 长度, 容量} 三个字

```
a := []int{1,2,3,4,5}
┌─────┬─────┬─────┐
│ ptr │ len │ cap │   ptr→底层数组, len=5, cap=5
└──┬──┴─────┴─────┘
   └──→ [1][2][3][4][5]   ← 底层数组(真正的数据)
```

- **len**:当前有几个元素(能访问的范围)。
- **cap**:从 ptr 起底层数组还能放几个(扩容前的上限)。
- slice 本身只是这 3 个字;**数据在底层数组里**。

### 切片(reslice)= 开一个共享窗口

`b := a[1:3]` **不拷贝数据**,只是造一个新 header 指向**同一底层数组**的一段:

```
b: ptr→a[1], len=2, cap=4   (cap 从下标1到底层数组末尾=4)
a: ptr→a[0], len=5, cap=5
   底层数组: [1][2][3][4][5]   ← a、b 共享
```

所以 `b[0]=99` 会改到 `a[1]`(共享!)→ `a` 变成 `[1,99,3,4,5]`。

### append 的两种命运

`append(b, 100)`:b 的 len=2、cap=4,**还有空间** → 直接写到底层数组的下一格(即 `a[3]` 的位置),**覆盖 a[3]=4 变成 100**!这就是开头那题的坑:`a` 变成 `[1,99,3,100,5]`。

如果 append 时 **cap 已满** → 分配一个**新的、更大的**底层数组,拷贝过去,b 指向新数组,**从此和 a 脱钩**。

**一句话:append 在 cap 够时原地写(可能踩到别的 slice),cap 不够时另起新数组(脱钩)。** 这种「有时共享有时脱钩」的不确定性,是 slice 最大的坑。

---

## 3. 原理深入

### 3.1 扩容策略(面试高频,注意 1.18 变化)

`append` 触发扩容时,新 cap 怎么算:

- **Go 1.18 之前**:`cap < 1024` → 翻倍(×2);`cap ≥ 1024` → ×1.25。
- **Go 1.18 起**:阈值改为 **256**。`cap < 256` → 翻倍;`cap ≥ 256` → 平滑增长 `newcap += (newcap + 3*256) / 4`(约 1.25× 但过渡更平滑,避免在 1024 处突变)。

算出的「理想 cap」之后还会**按内存分配器的 size class 向上取整**(所以实测 cap 可能比公式值略大)。

> 记忆版:**小切片翻倍、大切片约 1.25 倍,阈值 1.18 后是 256**。别背死公式,讲清「小翻倍大缓增 + 按 size class 取整」即可。

### 3.2 三索引切片:控制 cap 防别名

`a[low:high:max]` 第三个数限定 cap = `max-low`:

```go
b := a[1:3:3]           // len=2, cap=2(而非到底层末尾)
b = append(b, 100)      // cap 已满 → 立刻分配新数组,不会踩 a[3]!
```

这是**切出一段给别人、又不让它 append 污染原数组**的标准防御手法(库代码常用)。

### 3.3 为什么「函数里 append 外面看不到」

```go
func grow(s []int) { s = append(s, 1) }   // s 是 header 副本
a := []int{1,2,3}
grow(a)                                     // a 不变!
```

传参拷贝的是 **header**(3 个字),函数内 `append` 若扩容,`s` 重新指向新数组——但这只是**副本的 ptr 变了**,外面的 `a` 还指旧数组。要让外面看到,得**返回新 slice**(`a = grow(a)`)或传 `*[]int`。这正是 `append` 的惯用法 `s = append(s, x)` 的由来:**必须接住返回值**。

### 3.4 copy 与 nil/空

```go
dst := make([]int, len(src))
n := copy(dst, src)         // 按 min(len(dst),len(src)) 拷贝,返回拷贝数;不共享
```

- `copy` 是**真拷贝**,切断共享。想「克隆一个 slice 不共享底层」就 `copy` 或 `slices.Clone`(1.21)。
- nil slice(`var s []int`)vs 空 slice(`[]int{}`):用法几乎一样(都能 append/len/range),区别仅在 `==nil` 和 JSON(`null` vs `[]`)。详见 [`type-system/05`](../../type-system/05-nil/README.md),惯用零值是 nil slice。

---

## 4. 日常开发应用

- **预知大小就 `make([]T, 0, n)` 预分配 cap**:避免 append 反复扩容拷贝(性能关键)。
- **`append` 必须接住返回值**:`s = append(s, x)`,永远。
- **切片给外部/长期持有,用三索引 `a[i:j:j]`** 防止对方 append 踩你的数组。
- **想要独立副本用 `copy`/`slices.Clone`**,别直接 `b := a[:]`(那是共享)。
- **大数组切一小段长期持有 = 内存泄漏**:小 slice 引用着大底层数组,整个大数组无法 GC。需要就 `copy` 出小的,放走大的。

```go
// ❌ 持有 small 会让整个 1e6 的底层数组活着
small := big[:10]
// ✅ 拷出来,big 可被回收
small := append([]int(nil), big[:10]...)   // 或 slices.Clone(big[:10])
```

---

## 5. 生产&调优实战

- **扩容拷贝是热路径分配点**:循环里无预分配地 append,会触发多次「分配新数组 + 拷贝旧数据」,profile 里表现为 `growslice` + GC 压力。预估 cap 一次到位。
- **别名 bug 难查**:两个 slice 共享底层数组,一处 append 在 cap 内改了另一处的数据,且是间歇性(取决于当时 cap)。给外部数据用三索引切片或 copy。
- **子切片持有大数组的内存泄漏**:常见于「解析大 buffer 后保留一小片」;务必 copy 出来。
- **`make` 的 len vs cap**:`make([]T, 5)` 是 len=5(含 5 个零值);要空的预分配是 `make([]T, 0, 5)`。写错会 append 出一堆前导零值。

---

## 6. 面试高频考点

- **slice 底层结构?** 三元组 header:`{ptr, len, cap}`;数据在 ptr 指向的底层数组。reslice 共享底层数组、不拷贝。
- **append 扩容多少?** 小翻倍、大约 1.25×;阈值 Go 1.18 起是 256(之前 1024);最后按 size class 取整。
- **为什么函数里 append 外面看不到?** 传的是 header 副本,扩容后副本指新数组,原 slice 不变;须 `s = append(...)` 接住返回值。
- **共享底层数组的坑?** `b:=a[1:3]; b[0]=x` 改到 a;`append(b,..)` 在 cap 内会覆盖 a 的后续元素。用三索引切片 `a[i:j:j]` 或 copy 隔离。
- **nil slice vs 空 slice?** 用法几乎一样(都能 append),差别在 `==nil` 和 JSON 序列化;惯用零值是 nil slice。
- **子切片导致内存泄漏?** 小 slice 引用大底层数组使其无法回收;copy 出独立副本。
- **和 Java ArrayList 区别?** 都是底层数组+扩容,但 slice 是值 header、能共享底层开窗口(reslice 别名);ArrayList 是对象引用、无此别名语义。

---

## 7. 一句话总结

> **slice 是三元组 header `{ptr, len, cap}`,数据在共享的底层数组里。** reslice(`a[i:j]`)只造新 header、共享底层,所以改元素互相可见;`append` 在 **cap 够时原地写**(可能覆盖别的 slice 的元素)、**cap 不够时另起新数组并脱钩**——扩容规则是「小翻倍、大约 1.25×,1.18 后阈值 256,再按 size class 取整」。因为传参是 header 副本,`append` 必须 `s = append(s, x)` 接住返回值。防别名用三索引切片 `a[i:j:j]` 或 `copy`;子切片长期持有大数组会内存泄漏,要 copy 出来。预知大小就 `make([]T, 0, n)` 预分配。

下一章 → [`01 map 底层`](../01-map/README.md):另一个主角——hmap/bmap 怎么组织、渐进式扩容、为什么遍历无序、为什么并发写直接 fatal。｜ 回 [`data-structures` 索引](../README.md)
