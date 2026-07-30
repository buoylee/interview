# 索引（Indexing）

## 1. 核心问题

索引是「在不全表扫的前提下，快速定位行」的数据结构。本章解决三件事：
**(a)** 为什么 MySQL/InnoDB 用 B+ 树，不用其他结构；
**(b)** 怎么读懂一条 SQL 走没走索引、走的是哪个；
**(c)** 写 SQL 和建表时，怎样的索引设计才能跑得快。

## 2. 直觉理解

想像一本 1000 页的字典，没有索引你要从头翻；按拼音排序的目录是「一层索引」，能让你跳到大概页数；如果目录本身又有「字头索引」（A 在前 50 页，B 在 51-100…），就是「两层索引」。InnoDB 的 B+ 树就是这种**多层目录**，但有两个关键特点：

- **目录不是一本，是两本**：一本按主键排（叫聚簇索引，叶子节点直接存整行数据），其余的都是「指向主键的目录」（二级索引，叶子节点只存主键值，要回去聚簇索引再查一次，叫「回表」）
- **每一页 16KB**：所以三层 B+ 树能放下大约几千万行（具体数字见 Scenario 01）

## 3. 原理深入

### 3.1 为什么是 B+ 树

| 数据结构 | 问题 | B+ 树的回应 |
|---|---|---|
| 二叉树 / 红黑树 | 树太高，10^7 行要约 23 层 → 访问路径长 | B+ 树扇出大（一页 ≈ 1170 条目），3 层就够装千万级（见 Scenario 01） |
| Hash | 不支持范围、不支持排序 | B+ 树叶子节点按顺序串成链表 |
| B 树 | 内部节点也存数据 → 扇出小、范围查找要回上层 | B+ 树内部节点只存键，所有数据在叶子，扇出更大 + 范围扫描沿链表 |

这里常说的“3 层 B+ 树定位一行”表示最多访问 3 个索引页，**不等于固定发生 3 次磁盘 IO**。索引页命中 Buffer Pool 时只是内存访问；如果先走二级索引、查询列又没有被覆盖，还要再沿聚簇索引定位一次。

### 3.2 聚簇索引 vs 二级索引

- **聚簇索引**（clustered，又叫主键索引）：叶子节点 = 整行数据。InnoDB 每张表有且仅有一个聚簇索引。没显式主键时，InnoDB 选第一个非空 UNIQUE 列；都没有就用隐藏的 6 字节 `DB_ROW_ID`。
- **二级索引**（secondary，又叫非聚簇）：叶子节点 = 索引列值 + **主键值**。所以走二级索引拿不在索引里的列时，要再用主键去聚簇索引查一遍——这叫**回表**。
- 一句话区别：MyISAM 的二级索引叶子节点存的是「物理行地址」，InnoDB 存的是「主键值」。所以 InnoDB 的主键变更代价高，主键不要选会变的列。

### 3.3 联合索引 + 最左前缀

联合索引 `(a,b,c)` 按 a→b→c 排序。能走索引的条件（详见 Scenario 02）：

- `WHERE a=? AND b=? AND c=?` — 全用
- `WHERE a=? AND b=?` — 用 a,b
- `WHERE a=? AND c=?` — 只用 a，c 在 Server 层过滤（或 ICP 下推）
- `WHERE b=? AND c=?` — 通常全扫；8.0 在某些条件下会 **skip scan**

**WHERE 条件的书写顺序不影响最左前缀匹配**：对联合索引 `(a,b)`，在字段与参数类型匹配的前提下，`WHERE a=? AND b=?` 与 `WHERE b=? AND a=?` 都能用到 a、b。优化器按条件涉及的索引列生成访问路径，不会按 SQL 文本从左到右套索引；最左前缀限制的是**索引列顺序**以及查询是否提供这些列的条件，而不是 WHERE 中条件出现的顺序。只有 `WHERE b=?` 时仍然缺少最左列 a，不能因此直接用 `(a,b)` 做常规定位。

**范围条件决定能用几列构造索引区间**：对 `(a,b,c)`，`WHERE a=? AND b>? AND c=?` 通常由 a、b 决定扫描区间；遇到 b 的 `>` 后，不再用 c 缩小区间，但 c 仍可能通过 ICP 在索引页中提前过滤。不要把“不能继续定位”说成“后续列完全没用”。这条规则针对 `>`、`<`、`BETWEEN`、非前导通配的 `LIKE` 等范围运算；`IN (...)` 可被优化成多个等值范围，应以 `EXPLAIN` 为准。

**联合索引设计原则**：
1. **先看完整查询模式**：哪些查询必须复用这个索引、需要哪些最左前缀，以及是否还要支持 `ORDER BY` / `GROUP BY`。
2. **等值列通常放在范围列前**：让更多 key part 能参与区间定位；范围列之后的列主要承担 ICP、覆盖或排序等作用。
3. **区分度只是同等条件下的参考，不是“越高越靠前”的铁律**：如果查询总是同时对 a、b 做等值过滤，`(a,b)` 和 `(b,a)` 最终命中的行数相同；应根据其他查询能否复用左前缀、排序需求和索引宽度决定顺序。

### 3.4 覆盖索引

如果一条查询从该表需要的列（包括 `SELECT`、`WHERE`、`JOIN` 等涉及的列）都能从同一索引取得，就不需要回表。`SELECT name, age` 与 `SELECT age, name` 的书写顺序不影响是否覆盖，关键是列是否都在索引中；explain Extra 出现 `Using index`。代价：索引变胖、写入慢。详见 Scenario 03。

### 3.5 索引下推（ICP）

ICP 是 **Index Condition Pushdown（索引条件下推）**，MySQL 5.6+ 默认开启。要理解它，先要分清“下推”和“二级索引”是两个不同维度的概念。

#### 学习本节前，先抓住四个关键认知

1. **“使用索引”不只有一种含义。** 可以使用 B+ 树的有序性定位范围，也可以使用已经扫描到的索引条目里的列值做过滤。
2. **ICP 属于第二种。** 下推的 `name/age` 条件不是再做一次 `O(log N)` 的 B+ 树跳转查找，而是逐条读取当前二级索引条目中的值，执行 SQL 条件判断。
3. **所以“用了索引”和“缩小了扫描范围”可以同时一真一假。** `name/age` 确实使用了索引中持有的数据，但没有使用这两列的排列顺序来缩小扫描范围。
4. **ICP 主要省回表，不省这段索引扫描。** 扫描范围有 `M` 个条目时，ICP 仍可能检查 `M` 个条目；如果只有 `K` 个通过，就只让这 `K` 个条目回表。

这里的“过滤”是执行 `WHERE` 中的 **SQL 条件过滤**，不是应用程序的业务逻辑，也不是覆盖索引。

先用一句流程记住结果：**没有 ICP 是“二级索引条目 → 回表读完整行 → 返回 Server 判断”；有 ICP 是“二级索引条目 → 先判断下推条件 → 通过才回表”。**

#### “下推”到底推到哪里

MySQL 的 SQL 执行可以简化为两个逻辑层，两者通常都在同一个 `mysqld` 进程中：

```text
Server 层（Parser / Optimizer / Executor）
原本负责执行取回完整行后的剩余 WHERE 过滤
                  │
                  │ Handler API
                  ▼
InnoDB 存储引擎层
负责扫描 B+ 树、读页、回表、MVCC 和锁
```

ICP 的“下”是这个软件调用方向：

```text
Server 层中原本判断的部分 WHERE 条件
                         │
                         │ 优化器下推
                         ▼
InnoDB 扫描当前索引条目时判断
```

**二级索引并不在聚簇索引的“下层”。** 聚簇索引和二级索引都是 InnoDB 管理的 B+ 树；“聚簇 / 二级”描述数据怎样存，“Server / 存储引擎”才是这里的上下层边界。

#### 先区分：索引定位与索引过滤

看到某个 `WHERE` 列出现在索引中，不能立刻只回答“用了索引”或“没用索引”。要连续问两个问题：

1. **能不能利用索引的有序性，确定扫描起点和终点？** 这是“索引定位”，能减少需要扫描的索引条目。
2. **如果不能定位，当前索引条目里有没有这个列值，可以在回表前判断？** 这是“索引过滤”，也就是 ICP 能做的事。

| 使用方式 | 使用了索引的什么 | 省掉什么 |
|---|---|---|
| 索引定位（access condition） | B+ 树中索引键的有序性 | 少扫描索引条目 |
| 索引过滤（pushed index condition） | 已经扫描到的索引条目中的列值 | 不匹配时少回表读取完整行 |

同一条查询可以同时使用这两种方式：前面的列负责定位，后面的列虽然不能继续定位，仍可以负责 ICP 过滤。

可以把它记成一句话：

> **索引访问条件负责“跳到哪里开始找”；ICP 条件负责“扫到这一条后，值不值得回表”。**

因此，“索引下推”本身不是再做一次利用 B+ 树有序性的 `O(log N)` 查找，而是对**已经进入扫描范围的二级索引条目逐条执行 SQL 条件判断**。不过，整条查询仍可能先用前导列完成 B+ 树定位：假设定位后要扫描 `M` 个索引条目，其中 `K` 个通过 ICP，那么可以把过程粗略理解成：

```text
先利用 city 定位 Taipei 区间：约 O(log N)
再顺序扫描这个区间：           检查 M 个二级索引条目
ICP 用 name/age 逐条过滤：       仍做 M 次轻量条件判断
真正按主键回表：                从最多 M 次降到 K 次
```

这里说的是帮助理解的成本模型，不是精确耗时公式；缓存命中、页布局等都会影响实际耗时。ICP 的核心收益是减少昂贵的回表和完整行传递，不是让 `name LIKE '%0%'` 突然获得按 B+ 树跳转定位的能力。这里也应称为“SQL 条件过滤”，不要和应用代码中的业务逻辑混为一谈。

#### 用具体索引条目看 `city / name / age` 各做什么

假设已有二级索引：

```sql
INDEX idx_city_name_age (city, name, age)
```

它的叶子条目按 `city → name → age` 依次排序，并携带主键。下面用几条简化数据表示这种顺序：

```text
city    | name  | age | 主键 id
--------|-------|-----|--------
Taipei  | Alice | 20  | 1
Taipei  | Alice | 35  | 2
Taipei  | Bob0  | 18  | 3
Taipei  | Bob0  | 40  | 4
Taipei  | Tom0  | 30  | 5
Tokyo   | Alice | 28  | 6
```

这里的重点不是示例名字，而是排序规则：先比较 `city`；`city` 相同时再比较 `name`；只有 `city` 和 `name` 都相同时，才按 `age` 排序。

查询：

```sql
SELECT *
FROM user_profile
WHERE city = 'Taipei'
  AND name LIKE '%0%'
  AND age > 25;
```

现在逐个看三个条件。

**第一步：`city='Taipei'` 用于索引定位。**

所有 Taipei 条目在 B+ 树中连续排列。InnoDB 可以直接定位到第一条 Taipei 记录，并在离开 Taipei 区间时停止，不需要扫描 Tokyo 等其他城市。

**第二步：`name LIKE '%0%'` 不能继续定位，但能用于索引过滤。**

前导 `%` 表示开头可以是任意内容。符合条件的 `name` 可能散落在 Taipei 区间的任何位置，因此无法提前算出一个连续的 `name` 起止范围。InnoDB 仍要扫描 Taipei 区间中的各个索引条目。

但是每个条目本来就存有 `name`。InnoDB 读到条目后，可以直接拿其中的 `name` 判断 `LIKE '%0%'`，不需要先按主键回表。

**第三步：`age > 25` 也不能在本执行计划中继续定位，但能用于索引过滤。**

联合索引不是在整个 Taipei 区间内直接按 `age` 排序，而是**每个相同 `name` 的小组内部**才按 `age` 排序。由于前一列 `name` 没有被确定为一个可定位的等值或连续前缀，满足 `age > 25` 的条目会分散在 Alice、Bob0、Tom0 等多个 name 小组中，无法合并成一个连续的扫描区间。

但 `age` 同样存放在当前索引条目中，所以 InnoDB 仍可在回表前比较 `age > 25`。

三个条件的分工可以准确写成：

| 条件 | 能否缩小索引扫描范围 | 有没有使用索引 | 具体怎样使用 |
|---|---|---|---|
| `city = 'Taipei'` | 能 | 有 | 利用 B+ 树顺序定位 Taipei 的起止区间，属于索引访问条件 |
| `name LIKE '%0%'` | 不能 | 有 | 从每个索引条目读取 `name`，作为 ICP 条件判断是否值得回表 |
| `age > 25` | 不能 | 有 | 从每个索引条目读取 `age`，作为 ICP 条件判断是否值得回表 |

所以答案不是“`name/age` 没用到索引”，而是：

> `city` 使用索引的**有序性进行定位**；`name/age` 使用索引条目中**已经存储的列值进行 ICP 过滤**。前者减少扫描条目数，后者不减少扫描条目数，只减少回表次数。

#### ICP 开启后，五个示例条目怎样处理

InnoDB 已经利用 `city='Taipei'` 进入 Taipei 区间。接下来对每个条目，用条目中的 `name/age` 判断两个下推条件：

下表把两个条件的真假分别列出，只是为了展示每条索引记录为何被保留或淘汰；它不表示 MySQL 必然按表格中的列顺序计算条件。

| 扫到的二级索引条目 | `name LIKE '%0%'` | `age > 25` | InnoDB 下一步 |
|---|---:|---:|---|
| `Taipei, Alice, 20, id=1` | 否 | 否 | 跳到下一索引条目，不回表 |
| `Taipei, Alice, 35, id=2` | 否 | 是 | 跳到下一索引条目，不回表 |
| `Taipei, Bob0, 18, id=3` | 是 | 否 | 跳到下一索引条目，不回表 |
| `Taipei, Bob0, 40, id=4` | 是 | 是 | 用 `id=4` 回表读取完整行 |
| `Taipei, Tom0, 30, id=5` | 是 | 是 | 用 `id=5` 回表读取完整行 |

这五条都属于 `city='Taipei'` 的扫描范围，所以都要读取二级索引条目；但只有最后两条通过 ICP，需要访问聚簇索引完整行。

#### 怎样从 `EXPLAIN` 看出这三种分工

在本实验的执行计划中：

```text
key     = idx_city_name_age       整体选择了这个二级索引
key_len = 只覆盖 city 的长度       只有 city 参与索引定位
rows    = Taipei 区间的估算条目数  name/age 没有缩小这个区间
Extra   = Using index condition   name/age 作为 ICP 条件使用索引条目中的值
```

因此，`key_len` 没包含 `name/age`，不代表这两列完全没用；它只说明这两列没有参与本计划的索引定位。`Using index condition` 才是它们参与 ICP 过滤的证据。

如果查询再加上 `email LIKE '%@x.com'`，由于 `email` 不在当前索引条目中，InnoDB 不能在回表前判断；它就是残余条件，需要读取完整行后再由 Server Executor 判断。

#### 最关键的区别：判断发生在 `index_next()` 的里面还是外面

先纠正一个容易越想越乱的理解：**不能把它想成“平时由 Server 执行 `WHERE`；打开 ICP 后，InnoDB 又获得了一套独立的 SQL 解析器和执行器”。**

- SQL 文本、列名、`LIKE`、`>` 等表达式语义，始终先由 Server 层解析和理解。
- 优化器从 `WHERE` 中挑出只依赖当前索引列、允许下推的部分。
- Server 通过 Handler 的 `idx_cond_push()`，把这棵条件表达式交给 InnoDB。
- InnoDB 不重新解析 SQL 文本；它是在自己的索引扫描循环中，准备好索引列的值，然后触发这棵下推条件求值。

所以这里说“由 InnoDB 过滤”，精确含义是：**过滤动作被放进了 InnoDB 的取下一行循环；条件不通过时，InnoDB 自己继续读下一个索引条目，不回表，也不把这一候选行返回给 Server Executor。**

两种方式的边界如下：

| | 没有 ICP：Server 层过滤 | 有 ICP：InnoDB 扫描期间过滤 |
|---|---|---|
| 判断时手上有什么 | 已经回表得到的完整行 | 当前二级索引条目中的索引列 + 主键 |
| 判断发生在哪里 | Handler 返回一行之后，Executor 的循环中 | Handler 尚未返回时，InnoDB 的索引扫描循环中 |
| 条件不通过 | 完整行已经读过，只是 Server 丢弃它 | InnoDB 直接移动到下一索引条目，不回表 |
| 能判断什么 | 完整行上的残余条件 | 只依赖当前索引列且允许下推的条件 |
| 最大收益 | 没有省掉本次回表 | 省掉不匹配候选项的回表和完整行返回 |

可以把一次 Handler 取行请求想成下面两段概念伪代码。它不是 MySQL 源码逐字翻译，但调用边界与真实实现一致。

**没有 ICP：`index_next()` 内部先回表，Server 在调用返回后过滤**

```text
# InnoDB：处理一次 Handler 取行请求
secondary_entry = next_secondary_index_entry()
full_row = clustered_index_lookup(secondary_entry.primary_key)  # 已回表
fill_record_buffer(full_row)
return OK                                                        # 返回 Server

# Server Executor：Handler 已返回完整行
if where_condition(record_buffer):
    send_row()
else:
    request_next_row()
```

**有 ICP：`index_next()` 内部可能跳过很多条目，直到找到值得回表的一条**

```text
# InnoDB：仍在处理同一次 Handler 取行请求
while secondary_entry = next_secondary_index_entry():
    fill_icp_fields(record_buffer, secondary_entry)              # 只填判断所需索引列

    if not pushed_index_condition(record_buffer):
        continue                                                  # 不回表，也不返回 Server

    full_row = clustered_index_lookup(secondary_entry.primary_key)
    fill_record_buffer(full_row)
    return OK                                                     # 通过 ICP 后才返回 Server

# Server Executor：只检查未下推的残余条件
if residual_condition(record_buffer):
    send_row()
```

注意这里的 `record_buffer`：它是 Handler 调用约定使用的 MySQL 行缓冲。无 ICP 时，InnoDB 回表后把完整行填进去再返回；有 ICP 时，InnoDB 会先把**下推条件需要的索引列**填进去做提前判断，通过后才回表并补成完整行。

#### 源码层到底怎样交接条件

如果继续下钻一层，MySQL 8.0 的主线是：

```text
Server 优化器
  │  从 WHERE 中选出可下推部分（内部是 Item 条件树，不是 SQL 字符串）
  ▼
Handler: idx_cond_push(index_no, condition)
  │  InnoDB 保存这棵下推条件
  ▼
InnoDB: row_search_idx_cond_check(...)
  │  1. 从当前二级索引记录中取出判断所需字段
  │  2. 转成 MySQL record buffer 中的字段格式
  │  3. 调用 pushed_idx_cond->val_int() 求真假
  ├─ false → next index record（不回表）
  └─ true  → row_sel_get_clust_rec_for_mysql(...)（需要完整行时才回表）
```

因此，“谁处理”要分两个角度回答：

- **表达式从哪里来**：来自 Server；Server 解析 `WHERE`，并生成、选择可下推的条件表达式。
- **谁控制何时过滤**：InnoDB；它在自己的二级索引扫描循环中准备索引值并触发求值，失败就自行跳过。
- **谁处理剩余条件**：Server Executor；InnoDB 返回完整行以后，再判断没有下推的 residual condition。

这也是为什么把 InnoDB 粗略理解成“只做 OS IO”会出错：InnoDB 除了读文件，还管理 B+ 树游标、Buffer Pool、MVCC、锁和回表；ICP 又让它在索引游标向前移动的过程中多做一次提前筛选。不过 InnoDB 仍不是通用 SQL 执行器：它只在扫描点触发 Server 交来的、当前索引足以提供数据的条件，并根据真假决定跳过还是回表。

#### 没有 ICP：先回表，再由 Server 过滤

```text
Server 层让 InnoDB 扫描 city='Taipei' 的区间
                         │
                         ▼
InnoDB 读取一个二级索引条目（city/name/age/id）
                         │
                         ▼
不在索引条目上判断 name/age，直接用 id 回表读取完整行
                         │
                         ▼
把完整行写入 record buffer，并通过 Handler 返回 Server 层
                         │
                         ▼
Server Executor 再判断 name/age，不符合就丢弃
```

如果 `city='Taipei'` 区间有 200 个索引条目，其中只有 80 个符合 `name/age`，没有 ICP 时仍需要约 200 次回表，然后 Server 再过滤到 80 行。

#### 有 ICP：InnoDB 先检查索引条件，通过才回表

优化器把仅依赖当前索引列的 `name/age` 条件通过 Handler 边界交给 InnoDB。InnoDB 读取当前二级索引条目后，先把判断所需的 `name/age` 写入 record buffer，并在扫描循环内触发下推条件求值：

```text
Server 层下发：
  索引访问区间 = city='Taipei'
  下推索引条件 = name LIKE '%0%' AND age > 25
                         │
                         ▼
InnoDB 扫描一个二级索引条目，并准备 name/age 的值
                         │
                         ├─ 条件不通过：跳到下一个索引条目，不回表
                         │
                         └─ 条件通过：用主键 id 回表读取完整行，再返回 Server
```

同样的数据分布下：

| | 检查的二级索引条目 | 读取完整行（回表） | 最终匹配 |
|---|---:|---:|---:|
| ICP 关 | 约 200 | 约 200 | 80 |
| ICP 开 | 约 200 | 约 80 | 80 |

因此 ICP **不会把 200 个索引条目缩小成 80 个**；它减少的是读取完整行和跨 Handler 边界传递的次数。`EXPLAIN Extra` 显示 `Using index condition` 表示实际使用了 ICP。

#### 为什么 InnoDB 的 ICP 用在二级索引

```text
聚簇索引叶子：已经是完整行
二级索引叶子：索引列 + 主键，要拿其他列还需回表
```

对 InnoDB，ICP 只用于二级索引。InnoDB 可以在回表前利用已有的索引列淘汰候选项，因而能省掉读取完整行的 IO。对聚簇索引，扫到叶子时完整行已经被读取，再做 ICP 无法节省这次读取。所以“二级索引”是 InnoDB 中 ICP 有收益的适用场所，不是“下推”这个名字的来源。

#### ICP 不等于覆盖索引

| | ICP | 覆盖索引 |
|---|---|---|
| 解决的问题 | 哪些候选索引条目值得回表 | 查询是否根本不需要回表 |
| 执行结果 | 条件通过后通常还要回表 | 所需列都在索引中，直接返回 |
| 常见 Extra | `Using index condition` | `Using index` |

记忆顺序：

```text
索引访问条件 → 决定扫哪一段索引
ICP 条件      → 决定扫到的索引条目是否值得回表
覆盖索引       → 决定通过过滤后是否根本不用回表
残余 WHERE     → 完整行返回后由 Server 层继续判断
```

完整开关对比见 [Scenario 04](scenarios/04-icp-on-off-comparison.md)，Server / Handler / InnoDB 的执行边界见 [ch04 §3.5](../04-execution-and-explain/README.md)。实现依据可对照 [MySQL 8.0 ICP 官方说明](https://dev.mysql.com/doc/refman/8.0/en/index-condition-pushdown-optimization.html)、[Handler `idx_cond_push()` 接口注释](https://dev.mysql.com/doc/dev/mysql-server/latest/sql_2handler_8h_source.html) 和 [InnoDB `row_search_idx_cond_check()` 源码](https://github.com/mysql/mysql-server/blob/8.0/storage/innobase/row/row0sel.cc)。

### 3.6 Multi-Range Read（MRR）

二级索引范围扫返回的主键是按二级索引顺序的，访问聚簇索引页可能很分散，未命中 Buffer Pool 时就会形成随机 IO。MRR 把主键先排序再批量回表，尽量把随机访问变得顺序。默认 `mrr_cost_based=on`，优化器只在估算划算时启用。

### 3.7 索引为什么会失效

“索引失效”是口语，排查时要拆成三种不同情况：

1. **不能用于定位**：索引列被转换、包在函数里，或缺少最左前缀，无法生成 `ref` / `range` 访问路径。
2. **只用到部分 key part**：例如 `(a,b,c)` 只由 a、b 定位，c 仍可能用于 ICP 或覆盖；这不是整个索引都失效。
3. **索引可用但优化器没选**：小表、返回比例高或回表成本高时，全表扫成本更低；这是成本选择，不是索引结构失效。

- **隐式类型转换发生在列侧**：`WHERE varchar_col = 100` 会按数值比较，字符串列无法直接按原索引值定位（Scenario 05）。不要反推成“类型不同一定失效”：`WHERE int_col = '100'` 常可先转换常量，保留索引定位能力
- **对列做函数 / 表达式**：`WHERE DATE(t)='2026-01-01'` —— 普通 t 索引无法直接定位，8.0.13+ 可建匹配表达式的函数索引
- **前导通配**：`LIKE '%abc'` 不能走 B+ 树，因为不知道从哪一页开始
- **OR 跨列**：不是必然失效；各分支有合适索引时可能走 Index Merge，某一分支没有可用索引时更容易退化为全扫。改写成 `UNION` / `UNION ALL` 前要先确认是否允许重复行，二者语义不同
- **数据量太小** / **预估代价不划算**：优化器可能选择全扫，看 `optimizer_trace` 里的 `cost_for_plan`；这属于上面的第三种情况

## 4. 日常开发应用

**建表时**
- 主键用自增 BIGINT（不要选 UUID 当主键 —— 随机插入导致页分裂频繁。详见 Scenario 01 的「为什么主键有序很重要」备注）
- 二级索引宁少勿多：每个二级索引在写入时都要维护，且占空间
- 联合索引顺序按 §3.3 两条原则定

**写 SQL 时**
- 写完每条非纯主键查询，本能反应是 `EXPLAIN` 一下（`make explain SQL="..."` 一键）
- 等值条件 + 比较条件混用时，**等值列优先**放索引前列；这说的是索引定义顺序，不是 WHERE 书写顺序
- WHERE 里不要对索引列本身做函数 / 类型转换（参考 §3.7）
- LIMIT 深翻页（`LIMIT 100000, 20`）改成 **延迟关联**：先在覆盖索引上拿到主键再回表
- 不要在 ORM 上盲信 — Hibernate / GORM / Sequelize 生成的 SQL 经常多 SELECT 字段、缺索引提示。打开 query log（`make general-log-on`）抓一次实际跑的 SQL 比对

## 5. 调优实战

**Case A：「这条 SQL 上线后慢了，看不出原因」**

1. `make slow` tail 慢查日志，找到 SQL
2. `make explain SQL="..."` 看 type / key / rows / Extra
3. 看到 `type=ALL` 或 `Using filesort` / `Using temporary` —— 分别检查访问路径、排序与临时结果原因，不能直接归结为“缺索引”
4. 如果走了索引但 rows 远大于实际返回行数 → 走了「不对的」索引；用 `force index` 试更优的
5. 都没问题但还是慢 → 看 `make innodb-status` 是否在等锁

**Case B：「联合索引有 5 列，新来的同事看不懂顺序怎么定」**

1. 列出所有用到这个索引的查询（grep 代码 + general log）
2. 每条查询写出 WHERE 的等值/范围列，以及 ORDER BY、GROUP BY、SELECT 所需列
3. 先安排高频查询可复用的最左前缀和排序需求，再把区分度作为同等候选之间的参考
4. 索引列超过 4-5 列就要警惕：可能是查询本身该拆，不是索引该长

**Case C：「explain 看起来 OK，但生产某次跑了 30s」**

→ 多半是数据分布偏斜（city='Taipei' 占 80% 数据时，优化器估算「这条 WHERE 能减 5%」就走错了）。用 `optimizer_trace` 找成本估算，必要时跑 `ANALYZE TABLE` 更新统计或用 hint 强制。

## 6. 面试高频考点

### 必考对比

| 维度 | 聚簇索引 | 二级索引 |
|---|---|---|
| 叶子节点存什么 | 整行数据 | 索引列值 + 主键值 |
| 一张表能有几个 | 1 | 多个 |
| 主键变更代价 | 高（数据物理重排） | 中（只动二级索引） |
| 是否需要回表 | 不需要 | SELECT 列超出索引列时需要 |

### "为什么选 B+ 树" — 三句话答法

1. 树高决定一次定位要访问多少个索引页。一页 16KB、扇出 1000+，3 层 B+ 树能装千万级；实际磁盘 IO 次数取决于这些页是否命中 Buffer Pool。
2. 叶子节点有序双向链表，**范围查询和排序都不用回到根**。
3. 内部节点只存键不存数据，比 B 树扇出更大，进一步压低树高。

### "RR（Repeatable Read，可重复读）隔离级别 + 联合索引能不能避免幻读" 类陷阱题
这里先把 RR 理解为“同一事务内重复读取应保持一致”的隔离级别；它如何通过 MVCC 和锁实现，见 ch05、ch06。

→ 见 06-locking 章和 05-mvcc-and-transaction 章。

### 易错点

- **索引选择性 ≠ 索引区分度高就一定好**：还要看是否覆盖热点查询
- **`type=index` 不等于 `type=range`**：前者是全索引扫描，后者只扫描有起止边界的索引区间
- **`Using index` 不等于 `Using index condition`**：前者是覆盖索引、不回表；后者是 ICP，过滤后仍可能回表
- **explain 的 rows 是估算**：不准也很正常，优化器是基于统计的，必要时 `ANALYZE TABLE`

## 7. 一句话总结

InnoDB 的索引是「按主键聚簇 + 多个二级索引指向主键」的 B+ 树。建表先想清楚主键，联合索引先按查询模式安排可复用的最左前缀，再考虑等值、范围、排序与覆盖需求，不能只凭区分度排序。写完 SQL 用 explain 区分“不能定位、只用部分 key part、可用但没被选”；`Using index` 表示覆盖索引，`Using index condition` 表示 ICP。详见 Scenarios 01-05。

## Scenarios

- [01 - B+ 树三层能放多少行](scenarios/01-bplus-tree-three-layers.md)
- [02 - 联合索引最左前缀失效](scenarios/02-leftmost-prefix-violation.md)
- [03 - 覆盖索引省回表](scenarios/03-covering-index-saves-roundtrip.md)
- [04 - 索引下推（ICP）开关前后对比](scenarios/04-icp-on-off-comparison.md)
- [05 - 隐式类型转换让索引失效](scenarios/05-implicit-type-conversion-kills-index.md)
