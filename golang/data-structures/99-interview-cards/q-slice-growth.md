# slice 扩容策略与共享底层数组的别名坑

## 一句话回答

slice 是三元组 header `{ptr, len, cap}`,数据在 **ptr 指向的底层数组**里;`a[i:j]` 这样的 reslice **不拷贝、共享同一底层数组**。`append` 在 **cap 够时原地写**(会覆盖共享该数组的其它 slice 的元素)、**cap 不够时分配新数组并与原数组脱钩**。扩容规则:**小切片翻倍、大切片约 1.25×**,阈值 Go 1.18 起是 **256**(之前 1024),算出后再**按内存 size class 向上取整**。因为传参/赋值拷贝的是 header 副本,`append` 必须 `s = append(s, x)` **接住返回值**。

## 别名坑示例

```go
a := []int{1,2,3,4,5}
b := a[1:3]          // 共享底层:b.len=2, b.cap=4
b[0] = 99            // a 变 [1,99,3,4,5](共享!)
b = append(b, 100)   // cap 够 → 写 a[3] → a 变 [1,99,3,100,5](覆盖!)
```

防御:三索引切片 `a[1:3:3]`(限定 cap=2,append 立刻另起新数组),或 `copy`/`slices.Clone` 出独立副本。

## 其它要点

- **函数里 append 外面看不到**:header 是副本,扩容后副本指新数组;须返回新 slice。
- **子切片持有大数组 = 内存泄漏**:`small := big[:10]` 让整个 big 不回收;copy 出来。
- **预分配**:`make([]T, 0, n)` 一次到位,避免反复 `growslice` + 拷贝。

## 证据链接

- 正文:[`00 slice`](../00-slice/README.md);header 概念 [`type-system/00`](../../../type-system/00-values-layout/README.md)

## 易追问的延伸

- **nil slice vs 空 slice?** 用法几乎一样(都能 append);差别仅 `==nil` 和 JSON(`null` vs `[]`);惯用零值是 nil slice。
- **`make([]T,5)` 和 `make([]T,0,5)`?** 前者 len=5(含零值),后者 len=0 cap=5(预分配空的)。
- **和 Java ArrayList?** 都底层数组+扩容;但 slice 是值 header、能 reslice 共享开窗口,ArrayList 无此别名语义。
