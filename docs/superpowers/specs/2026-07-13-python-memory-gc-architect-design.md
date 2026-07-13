# Python 内存管理/GC 面试内容补强到架构师级 — 设计

日期:2026-07-13
状态:已与用户对齐,待实现

## 背景与问题

体检结论:`python/16-objects-memory-gc-gil.md` 资深级达标(refcount、分代 GC、weakref、`__del__`、`__slots__`、GIL、free-threading),阅读流畅;但架构师级有四个缺口,且用户读完的留存只有「引用计数 + 分代 GC 兜循环」两点——深水区内容确实缺失:

1. **分配器层整个缺失**:pymalloc(arena/pool/block)、free list,全仓库零覆盖。最经典架构师题「对象都 del 了,RSS 为什么不降」整条链路断在中间。
2. **GC 生产调优缺**:gen2 全扫延迟尖峰、阈值调法、`gc.freeze()`+CoW、Instagram 关 GC 案例。
3. **PEP 683 immortal objects 没提**(3.12,refcount 叙事的现代尾巴,衔接 free-threading)。
4. **ch16 与 `performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md` 重叠**,无分工声明。

另一个校准洞察(用户 Java 背景):CPython 循环 GC 本来就浅(单线程、不并发、不搬移、不压缩的朴素 mark-sweep),深度不在收集器,而在**分配器 + refcount 的涟漪效应 + 生产调优**。这个「深度搬家了」的框架本身就是面试答案,要明写进正文。

## 改动清单

全部为文档改动,主文件 `python/16-objects-memory-gc-gil.md`,轻碰 3 个文件。

### 1. ch16 新增「§五 内存模型与分配:对象的一生」(~70-80 行)

插在现有 §四(分代 GC)之后、`__slots__` 之前;后续节号顺延(五→六…)。内容结构:

- **分层总图**(开头定调,代码块画层次):

  ```
  OS 虚拟内存
   └─ CPython 私有堆
       ├─ pymalloc: arena(256KB) → pool(4KB) → block   ← ≤512B 小对象
       └─ 直接 malloc                                   ← >512B 大对象
           └─ 对象层: 对象头 + free list 复用
               └─ 名字层: 引用绑定(ch01)
  ```

- **「一个对象的出生」走一遍**:`x = MyObj()` → `tp_alloc` → `PyObject_Malloc` → 判 ≤512B 走 pymalloc 找对应 size class 的 pool → 装对象头、refcount=1 → 名字绑定。
- **pymalloc 三层机制**:arena 向 OS 要 256KB;pool 4KB 按 size class 切;block 装对象。free list(float/list 等类型自留复用池)。
- **反 Java 直觉关键点**:三代**不是物理分区**——没有 eden/survivor,分代只是三条追踪链表,对象**从不搬家**;没有搬移 → 没有压缩 → 这正是 arena 碎片、RSS 不降的根因。
- **核心面试题:「del 了 RSS 为什么不降」三根因**:arena 高水位(一个活对象钉住整个 arena)、free list 不还、glibc malloc 本身不还 OS。
- **真机实测片段**:狂建对象 → del → 前后 RSS 对比,Docker python:3.11 实跑出真数字进正文(RSS 用 `resource.getrusage`)。
- **「泄漏还是碎片怎么判」**:指 `../performance-tuning-roadmap/06a-python-profiling/02-python-memory-analysis.md`(RSS vs tracemalloc 对照法已在那边)。
- 栈 vs 堆一行带过(对象全在堆,frame 也是堆对象)。

**不做**:obmalloc usedpools 位图等实现细节,越线。

### 2. ch16 §四末尾扩「生产视角:GC 什么时候成延迟元凶」(~30 行)

- gen2 全扫成本 = O(存活对象数),大堆(千万对象)一次可达百 ms 级 → P99 尖峰。
- 三手段:调大阈值 / `gc.freeze()`(fork 前移出扫描,防 CoW 写脏页——refcount 一动整页复制)/ 确定无环批处理 `gc.disable()`。
- Instagram 案例一段(gc.disable + freeze 省内存提容量)。**事实必须核实后写**,不确定的表述宁可弱化。

### 3. ch16 refcount 叙事尾加 PEP 683 immortal objects(~6-8 行)

None/True/False/小整数 3.12 起 refcount 冻结为特殊值不再增减 → CoW 友好,也是 free-threading 的前置件;与 §七(顺延后 §八)free-threading 衔接。

### 4. ch16 加「收口地图」框(~6 行)

位置:§四末尾(生产视角小节之后),作为 GC 话题的收束。明说:**Java GC 的深度在收集器(CMS/G1/ZGC、并发标记、停顿调优),Python 的深度在分配器和 refcount 的代价(GIL、CoW、immortal、free-threading)**。CPython 循环 GC 是朴素 mark-sweep,浅是设计使然。面试被问「Python GC 和 JVM GC 比」直接用。

### 5. 收尾同步

- ch16 章末面试卡 +3 张:「del 了 RSS 为什么不降」「GC 造成延迟尖峰怎么办」「immortal objects 是什么/为什么」。
- ch16「一句话心智」与 Java/Go 对照框按需微调(对象从不搬家/无压缩一行)。
- `python/99-interview-cards.md` 「并发/内部」节 +2 行速查(RSS 不降、GC 尖峰)。
- ch16 头部与 `06a/03-cpython-gc.md` 头部各加 2-3 行分工声明:ch16=机制教学,06a/03=排查视角+PyPy 差异。

## 验证方式

- 所有新代码片段在 Docker `python:3.11` 实跑,输出数字写进正文。
- 注意仓库已知陷阱:bash 跑采集脚本(zsh 不拆分变量)、docker exec 显式给 stdin。
- 事实核查:pymalloc 数字(512B 阈值、256KB arena、4KB pool)、PEP 683/779 版本号、Instagram 案例细节,写前对照官方文档/一手来源。

## 体例约束(沿用现有)

- 机制进正文教学,面试卡只做复习自检,不承载新知识。
- Java/Go 对照服务于桥接,不绑死 Java。
- 简体中文,与 python/ track 现有行文一致。
- 不新建文件,全部增量修改。

## 明确不做

- 不动 `python/01`(入门层够用)。
- 不给 06a/02 加新排查场景(已有 RSS vs tracemalloc 对照,§五 指过去即可)。
- 不覆盖 obmalloc 深层实现(usedpools、bitmap)。
- 不讲 PyPy 之外的其他实现 GC。
