# 20 · 编码面试工具箱

> **为什么这章重要**:很多面试有现场编码轮(LeetCode 风格)。Python 写算法的优势全在"用对内置武器"——`heapq` 做优先队列、`bisect` 二分、`deque` 滑窗、`Counter`/`defaultdict` 计数、`sorted(key=)` 多级排序。这章是一份"算法题里该伸手拿什么"的速查 + 复杂度备忘,直接服务编码轮。

## 一、`heapq`:优先队列 / Top-K

Python 只有**最小堆**,`heap[0]` 永远是最小值,操作 O(log n):

```python
import heapq
h = []
heapq.heappush(h, 5); heapq.heappush(h, 1); heapq.heappush(h, 3)
heapq.heappop(h)             # 1 —— 弹出最小
h[0]                         # 看堆顶不弹

heapq.heapify(lst)           # 原地把 list 变堆,O(n)

# Top-K 直接用现成函数
heapq.nlargest(2, [5, 1, 3, 2, 4])    # [5, 4]
heapq.nsmallest(2, [5, 1, 3, 2, 4])   # [1, 2]
```

**最大堆**:Python 没有,套路是**存负值**(或存 `(-priority, item)` 元组):

```python
maxh = []
heapq.heappush(maxh, -x)     # 推入相反数
largest = -heapq.heappop(maxh)   # 弹出再取反
```

典型题:Top-K 高频元素、合并 K 个有序链表、Dijkstra、数据流中位数(双堆)。

## 二、`bisect`:有序数组二分

对**已排序**列表做二分查找/插入,O(log n) 定位:

```python
import bisect
a = [1, 3, 5, 7]
bisect.bisect_left(a, 5)     # 2 —— 第一个 >=5 的位置(可作"≥x 的下标")
bisect.bisect_right(a, 5)    # 3 —— 第一个 >5 的位置
bisect.insort(a, 4)          # 保持有序地插入 → [1, 3, 4, 5, 7]
```

用途:在有序数组里找插入点、统计 `< x` 的个数(`bisect_left` 返回值就是)、最长递增子序列(LIS)的 O(n log n) 解法。

## 三、`deque`:队列 / 栈 / 滑动窗口

两端操作都 O(1)(`list` 头部是 O(n)),是 BFS、滑窗的标配:

```python
from collections import deque
dq = deque([1, 2, 3])
dq.append(4)        # 右进
dq.appendleft(0)    # 左进
dq.popleft()        # 左出(队列 FIFO)
dq.pop()            # 右出(栈 LIFO)

window = deque(maxlen=3)         # 定长:超长自动挤掉旧的
for i in range(5): window.append(i)
list(window)                     # [2, 3, 4] —— 天然滑动窗口
```

BFS 用 `deque` 做队列;单调队列(滑窗最大值)也靠它。

## 四、`Counter` / `defaultdict`:计数与分组

```python
from collections import Counter, defaultdict
c = Counter("aabbbc")
c.most_common(1)     # [('b', 3)] 最高频
c["z"]               # 0 —— 不存在返回 0,不 KeyError

groups = defaultdict(list)       # 分组:无需先判 key
for word in words:
    groups[word[0]].append(word)
```

字母异位词分组、频次统计、滑窗字符计数(`Counter` 还支持 `+`/`-`/`&` 运算)——这类题用 `Counter`/`defaultdict` 能省一大半代码。

## 五、排序:`sorted(key=)` 与多级排序

```python
data = [("Ann", 30), ("Bob", 25), ("Al", 30)]

# 多级排序:返回元组,按年龄降序、同龄按名字升序
sorted(data, key=lambda x: (-x[1], x[0]))   # [('Al',30), ('Ann',30), ('Bob',25)]

import operator
sorted(data, key=operator.itemgetter(1))     # 按第 2 项升序(比 lambda 略快)
```

- **`key` 函数**只算一次/元素(Schwartzian 变换),返回**元组**即可多级排序:数值升序直接用、降序用负号或 `reverse=True`。
- `sorted` 是**稳定排序**(相等元素保持原相对顺序),可分多次按不同 key 排实现复合优先级。
- `operator.itemgetter`/`attrgetter` 比 lambda 稍快且更声明式。

### `@total_ordering`:自定义对象的全套比较

只写 `__eq__` + 一个 `__lt__`,自动补齐 `>`/`>=`/`<=`:

```python
from functools import total_ordering
@total_ordering
class Version:
    def __init__(self, n): self.n = n
    def __eq__(self, o): return self.n == o.n
    def __lt__(self, o): return self.n < o.n

Version(1) < Version(2)      # True
Version(3) >= Version(2)     # True —— 自动推导出来的
```

让自定义对象能直接进 `sorted`/`heapq`/比较运算,而不必手写六个比较方法。

## 六、切片与字符串技巧

```python
"hello"[::-1]                    # 'olleh' 反转
s == s[::-1]                     # 回文判断
"-".join(["a", "b", "c"])        # 'a-b-c'(拼接用 join,别 += 循环)
list("abc")                      # ['a','b','c']
"a,b,c".split(",")               # ['a','b','c']
nums[i:j]                        # 子数组(注意是拷贝,O(k))
matrix = [[0]*n for _ in range(m)]   # 二维数组!别用 [[0]*n]*m(第 01 章共享坑)
```

注意点:字符串不可变,循环 `s += c` 是 O(n²),拼接用 `"".join(list)`;`for i, x in enumerate(arr)` 取下标;`zip(a, b)` 并行遍历;`a, b = b, a` 交换。

## 七、复杂度速查(选数据结构的依据)

| 操作 | list | dict/set | deque | heapq |
|------|------|----------|-------|-------|
| 索引访问 | O(1) | 键 O(1)平均 | 端点 O(1) | 堆顶 O(1) |
| 末尾增删 | O(1)摊销 | — | O(1) | push/pop O(log n) |
| 头部增删 | O(n) | — | O(1) | — |
| 成员判断 `in` | O(n) | O(1)平均 | O(n) | O(n) |
| 查最小/最大 | O(n) | O(n) | O(n) | 最小 O(1) |
| 有序插入 | O(n) | — | — | — |

选型口诀:**查重/去重/成员判断 → `set`/`dict`;两端操作/滑窗 → `deque`;Top-K/优先队列 → `heapq`;有序 + 二分 → `bisect`;计数分组 → `Counter`/`defaultdict`。**

## Java/Go 对照框

| 需求 | Java | Python |
|------|------|--------|
| 优先队列 | `PriorityQueue` | `heapq`(仅最小堆,最大堆存负值) |
| 双端队列 | `ArrayDeque` | `collections.deque` |
| 有序二分 | `Collections.binarySearch`/`TreeMap` | `bisect` |
| 计数 | `Map<K,Integer>` + merge | `Counter` |
| 多级排序 | `Comparator.comparing().thenComparing()` | `sorted(key=lambda x:(...))`,稳定排序 |
| 自定义比较 | `Comparable`/`Comparator` | `__lt__` + `@total_ordering` |

差异:Java 的 `PriorityQueue` 可传 `Comparator` 做最大堆,Python `heapq` 只能最小堆 → **记住"最大堆存负值"这个套路**,编码轮常用。

## 章末面试卡

**Q1. Python 怎么实现优先队列?最大堆怎么办?**
用 `heapq`(基于 list 的最小堆,`heappush`/`heappop` O(log n),`heap[0]` 是最小值)。Python 没有最大堆,套路是**存相反数**(`heappush(h, -x)`,弹出后取反)或存 `(-priority, item)` 元组。Top-K 直接用 `heapq.nlargest/nsmallest`。

**Q2. 在有序数组里二分查找/插入用什么?**
`bisect`:`bisect_left`(第一个 ≥x 的位置)、`bisect_right`(第一个 >x),`insort` 保持有序插入,均 O(log n) 定位。可用于找插入点、统计 `<x` 的个数、LIS。

**Q3. BFS / 滑动窗口用什么数据结构?为什么不用 list?**
用 `collections.deque`:两端 append/pop 都是 O(1),适合队列(BFS)和滑窗;`list.pop(0)` 是 O(n)。`deque(maxlen=k)` 还能自动维护定长滑窗。

**Q4. 怎么做多级排序(先按 A 升、再按 B 降)?**
`sorted(data, key=lambda x: (x.a, -x.b))`——`key` 返回元组按序比较,数值降序用负号或 `reverse`。Python 的 `sorted` 是**稳定排序**,也可分多趟按不同 key 排实现复合优先级。

**Q5. 让自定义对象支持排序/比较,最少写几个方法?**
用 `functools.total_ordering` 装饰类,只需实现 `__eq__` + 一个比较(如 `__lt__`),其余 `>`/`>=`/`<=` 自动补齐。这样对象能直接进 `sorted`/`heapq`。

**Q6. 为什么循环 `s += c` 拼字符串慢?怎么写?**
字符串不可变,每次 `+=` 都新建并复制整个字符串,总复杂度 O(n²)。应把片段收集到 list 再 `"".join(parts)`,O(n)。
