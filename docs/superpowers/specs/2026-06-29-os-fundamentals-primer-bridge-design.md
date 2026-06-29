# Spec: 给 `performance-tuning-roadmap/00-os-fundamentals` 补 primer 引子 + 回链

> 日期:2026-06-29
> 触发:用户读 `00-os-fundamentals/01-cpu-architecture-scheduling.md` §5「中断与软中断」看不懂。

---

## 1. 诊断(为什么做这件事)

用户卡在 §5,但**内容其实早就写过了**,而且是「你视角/黑盒/砸实」三层风格,在两处:

- `linux/02-execution-primitives/README.md` 124–157 行「原语三:中断 IRQ」
- `metrics-decoder/01-cpu.md` 89–115 行「原語 B:中斷(hi/si)」

真正的问题不是内容缺失,是**接线缺失**:

1. `00-os-fundamentals` 是 2026-05-01 写的最早、最薄、「假设你已懂」的一层;上面两个 primer 是 6-26 / 6-29 才长出来的。
2. `00-os-fundamentals` **没有任何一条链接**指向后建的 primer 层(grep 验证:零个)。用户自然会卡在术语上、也不知道深挖去哪。
3. 连 primer 里都还差一句:`linux/02` 和 `metrics-decoder/01` 都讲了 top/bottom half,但**都没明说「软中断不是硬件触发的中断、它是内核的高优先级待办队列、名字会误导」**——这恰是最能解惑的一句。

按用户指示「**如果有重复就只补缺少的**」:缺的是 ① 薄引子 + 回链,② 那句破误解。**不重写已有原语。**

---

## 2. 目标

把 `00-os-fundamentals` 整章从「假设你懂」升级为「掉进术语时当场给 30 秒原语 + 指向深挖」,且**零内容重复**——深度仍只存在于 `linux/` primer 与 `metrics-decoder`,本章只做引子和接线。

---

## 3. 方案:两层处理(approach 1,已选)

对比过三种,选「头部框 + 针对性引子」:

| 方案 | 取舍 |
|---|---|
| **1 ✅采用** | 每篇一个「原语地图」头部框 + 只在真正掉进术语的小节加「你视角」引子。头部框解决发现性,引子只补卡点,不污染每节。最贴「只补缺的」。 |
| 2(否决) | 每个假设原语的小节都加引子。~40 个回调框,重复回链,正文臃肿。 |
| 3(否决) | 只加头部框/回链,不写引子。最省,但读到当场仍看不懂,得跳出去——没解决用户的卡点。 |

---

## 4. 两个组件的格式模板

### 组件 A —「原语地图」头部框(每篇顶部一个)

加在每篇 H1 标题 + 引言 blockquote 之后、第一个 `## 1.` 之前。格式:

```markdown
> **🧱 本篇假设你已懂这些底层原语,没把握先补:** <原语清单> → `<linux/0X-primitive>`;
> <这些指标怎么读> → `<metrics-decoder/0X>`
```

### 组件 B —「你视角」引子(只在触点小节)

加在目标小节 `##/###` 标题正下方,**原内容一字不动**。结构:

```markdown
> **你视角(30 秒):** <Java/Go 桥:你已经隐式用了什么、它背后其实靠这个原语>
>
> **一句破误解:**(可选,仅在有经典误解时)<把易混的点一句打掉>
```

并在该小节末尾加 1–2 条回链(沿用仓库已有 `→ ...: \`path\`` 约定):

```markdown
**→ 深挖黑盒**(<黑盒里发生什么>):`linux/0X-...`
**→ 这个指标怎么读**(<对应指标>):`metrics-decoder/0X`
```

### §5 中断的成稿(主角,直接定稿如下)

```markdown
## 5. 中断与软中断

> **你视角(30 秒):** 你的 Java/Go 代码一条条顺序执行,它**不会**主动去看「网卡收到包了没」。CPU 怎么知道?两条路:① **轮询**——自己每隔一会问「好了没」,大多时候答案是「没」,纯浪费;② **中断**——平时不管,**硬件有事拉一根信号线主动打断 CPU**。系统几乎全用中断。所以「中断」= 硬件强行打断 CPU、处理完再回原处,跟你熟的 event callback 很像,不是 busy-wait。
>
> **一句破误解:** 下面的「软中断」**不是硬件触发的中断**,是内核自己的一条**高优先级待办队列**(NET_RX/TIMER…)。名字里的「中断」是历史包袱——读成「内核的延后处理任务」就通了。

### 硬中断
（原内容不动）

### 软中断（SoftIRQ）
（原内容不动）

**→ 深挖黑盒**(中断上下文为何不能睡眠、top/bottom half、IRQ vs syscall 本质):`linux/02-execution-primitives` 原语三
**→ 这俩指标怎么读**(`top` 的 `hi`/`si`、si 为何打满、RSS/RPS):`metrics-decoder/01-cpu` 原語 B
```

---

## 5. 整章触点地图(只动这些)

| 文件 | 头部框回链 | 加「你视角」引子的小节 |
|---|---|---|
| `01-cpu-architecture-scheduling.md` | linux/02 + metrics-decoder/01 | §3 用户/内核态、§4 上下文切换、**§5 中断**(主角+破误解,见上) |
| `02-memory-management.md` | linux/01 + metrics-decoder/02 | §1–3 虚拟内存/页表/缺页(合一个引子)、§5 OOM(→ os-for-architects/05) |
| `03-disk-io-filesystem.md` | linux/03 + metrics-decoder/03 | §3 Page Cache、§6 fsync |
| `04a-network-tcp-core.md` | metrics-decoder/04 | §2–4 握手/挥手/TIME_WAIT 的 SYN/Accept 两个队列(轻引子,一个即可) |
| `04b-network-socket-kernel.md` | linux/02·03 + metrics-decoder/01·04 | §1 Socket Buffer、§2 内核收包流程(接 §5 中断)、§4 RSS/RPS |
| `05-process-thread-coroutine.md` | linux/02·03·04 + linux-handson/03 | §1 进程/线程/协程、§3 信号(=软件中断)、§5 I/O 多路复用/epoll |

规模:**6 个头部框 + ~14 个你视角引子 + 2 处基线补句**。

---

## 6. 基线补句(无论范围都做)

把「软中断 ≠ 硬件中断、是内核的高优先级待办队列、名字会误导」这一句,补进已有的两处 top/bottom-half 讲解:

- `linux/02-execution-primitives/README.md`(原语三:中断 IRQ,bottom-half 段附近)
- `metrics-decoder/01-cpu.md`(原語 B:中斷,软中断段附近)

---

## 7. 明确不碰

- `01` §1/§2(cache 层级 / NUMA)——硬件事实,已讲清,只进头部框不加引子。
- 各篇「实用诊断命令速查」「要点总结」——命令/结论,不是卡人的原语。
- `linux/`、`metrics-decoder/`、`os-for-architects/` 的既有深度内容——只加上面那 2 句基线,不重写。
- `00-os-fundamentals/README.md`——本身是索引,不动(除非顺手在「学习顺序」表后加一行指向 primer 层,可选,低优先)。

---

## 8. 实现注意

- **相对路径**:触点文件在 `performance-tuning-roadmap/00-os-fundamentals/` 下,到仓库根的 primer 是 `../../linux/...`、`../../metrics-decoder/...`、`../../os-for-architects/...`。实现时逐条核对 `[文字](路径)` 能点开。
- **语言**:`00-os-fundamentals` 现有正文是简体,引子与回链用简体,保持一篇内一致(`metrics-decoder` 是繁体,回链里出现「原語 B」是它的原标题,照抄不改)。
- **风格**:引子用 `>` blockquote;「你视角」「一句破误解」「→ 深挖」这几个标记词保持一致,方便用户扫读。
- **不造假**:不新增需要真机输出的内容(本任务零实跑);引子是概念桥,不含伪造的命令输出。
- **并发 git add 陷阱**:本仓库常有并发 agent 跑 `git add -A`;stage+commit 用显式路径、同一次 Bash 调用原子完成。

---

## 9. 验收

- 读 `00-os-fundamentals` 任一篇,掉进术语的小节都有 30 秒「你视角」可读,且能一键跳到深挖。
- 全章无与 `linux/`/`metrics-decoder` 重复的深度段落(只有引子 + 回链)。
- §5 与 `linux/02`、`metrics-decoder/01` 三处都明说了「软中断 ≠ 硬件中断」。
- 所有新增链接可点开。
