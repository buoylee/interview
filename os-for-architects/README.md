# OS for 架构师 · 薄镜头（OS 原语 → 架构决策）

> **一句话定位**：把"看到 OS 原语 → 反射出架构决策"这个**资深 → 架构师的思维跃迁**，做成一张薄地图；每个决策点不展开，**指进深矿**。
>
> **它不是什么**：不是又一门 OS 课。机制怎么运作、容量公式怎么推、实验怎么跑 —— 那些深矿里都有，本课只负责"看到原语，反射出决策"，然后给你指针。

---

## 你为什么需要这一层

仓库里已经有两套 OS 内容，教的都是**资深 = 能答 = 反应式**：

- [`linux-handson/`](../linux-handson/) —— 机制·能排查·能讲清（出问题能解释）
- [`performance-tuning-roadmap/00-os-fundamentals/`](../performance-tuning-roadmap/00-os-fundamentals/) —— 资深性能机制深度

它们教你**出了问题怎么解释**。但架构师的差别在另一头：**写代码、定架构之前，用 OS 的约束反推设计决策** —— 这是**能设计 = 预判式**。这层的料散落在 `concurrency-capacity`、`performance-tuning-roadmap/11`、`/12`、`system-design` 里，**没有统一在"OS 原语"这个镜头下**。本课补这层镜头。

```
        os-for-architects   ← 本课：机制 → 设计决策（薄 · 全资源 · 横切）
              ▲ 坐在其上
        linux-handson       ← 机制 · 能答 · 能排查（含 lab）
              ▲
        00-os-fundamentals  ← 资深性能机制深度
```

---

## 防重复硬契约：和 `concurrency-capacity` 划清边界

最容易和本课混的是 [`concurrency-capacity/`](../concurrency-capacity/)。边界必须守住：

| | `concurrency-capacity` | **`os-for-architects`（本课）** |
|---|---|---|
| 形状 | 一根轴**挖到底** | 五种资源**各挖一铲** |
| 轴 | 容量/并发（单轴） | CPU/内存/存储/网络/隔离（全资源） |
| 深度 | 完整 Little 数学 + lab | 只教"反射" + 指针；**容量推导指向 cc** |
| 海拔 | 深而窄 | 薄而广 |

**本课的写作铁律**：凡涉及"完整推导 / 机制细节 / 可跑实验"，一律改为**一句反射 + 一个指针**，不在本课展开。

---

## 章节地图

| # | 章 | 对镜 `linux-handson` | 横指深矿（深决策） |
|---|---|---|---|
| [00](./00-the-lens/) | **镜头**：资深(能答) → 架构师(能设计) + 统一反射模板 | — | — |
| [01](./01-cpu-and-scheduling/) | 调度/CPU → **并发模型与容量** | 03 进程 | cc/01·02·04 |
| [02](./02-memory-and-paging/) | 虚存/内存 → **内存预算与缓存层** | 04 内存 | perf-11/01 · perf-12/01 · sd/06 |
| [03](./03-storage-io/) | 存储 IO → **持久化与引擎选型** | 05 IO | sd/06·07 · perf-11/04 |
| [04](./04-network-and-connections/) | 网络/连接 → **连接模型与容量** | 06 网络 | cc/05·07 · perf-11/02·03 · sd/04 |
| [05](./05-isolation-and-cgroups/) | 隔离/cgroup → **多租户与隔离设计** | 09 容器 | cc/06 · perf-12 · sd/08 |
| [06](./06-capstone-design/) | **综合**：一道设计题串起五条资源决策线 | — | → system-design-scenarios |
| [99](./99-interview-cards/) | **面试卡**："OS→设计"高频题（能答 → 能设计） | — | — |

> 缩写：`cc`=concurrency-capacity，`perf-11`=performance-tuning-roadmap/11-architecture，`perf-12`=…/12-container，`sd`=system-design。

---

## 怎么用本课

1. **先打地基**：看不懂 `us/sy/wa`、`RSS/Swap`、`await`、`TIME_WAIT` 这些字段本身？**别从本课硬啃** —— 先去 [`linux-handson/03→07`](../linux-handson/)（尤其 07 排查 playbook + stress-ng 实验，让数字在你眼前动起来），再回来。
2. **每个资源章统一 6 段**：盲点 → 原语→决策映射表（核心）→ 定量锚点 → 决策清单&反模式 → 指针 → 面试转化。
3. **顺指针下钻**：要机制细节，指针下指 `linux-handson` / `00-os-fundamentals`；要完整容量数学/深决策，横指 `cc` / `perf` / `sd`。
4. **收尾**：读 [06 综合](./06-capstone-design/) 走一次完整设计推演，[99 面试卡](./99-interview-cards/) 临考速记。

读完的标准：**对任意一个 OS 原语，你能反射出"它在设计期逼出哪个架构决策"，并能在面试里从『能答』答到『能设计』。**
