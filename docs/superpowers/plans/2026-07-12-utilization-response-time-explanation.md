# 利用率与响应时间非线性关系补充实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补足 M/M/1 中利用率与平均响应时间呈非线性关系的原因、推导和边界，并修正直接相关的不准确表述。

**Architecture:** 只修改现有性能定律文档。公式之后插入“直觉 + Little 定律推导 + 数值例子”，图表之后补模型边界，再同步修正工程启示与容量示例，使整章从数学模型到工程应用保持一致。

**Tech Stack:** Markdown、M/M/1 排队模型、Little 定律、Git 文本校验

## Global Constraints

- 保持现有章节的简洁、直觉优先风格。
- 不引入超出解释所需的排队论细节。
- 不将 M/M/1 单服务台模型直接等同于多核 CPU 或线程池。
- 70%–80% 只能表述为需要结合工作负载和 SLO 验证的经验余量，不能表述为普适定律或固定拐点。

---

### Task 1: 补足非线性原因并统一工程表述

**Files:**
- Modify: `performance-tuning-roadmap/01-methodology/04-performance-laws.md:197-275`

**Interfaces:**
- Consumes: 本文已有的 `λ`（到达率）、`μ`（服务率）、`ρ = λ / μ`（利用率）、`W`（平均停留时间）与 Little 定律 `L = λW`
- Produces: 新定义 `S = 1 / μ`（无排队时的平均服务时间），并推导 `W = S / (1 - ρ)`；后续倍率表和容量示例沿用该结论

- [x] **Step 1: 记录当前缺口和待修正文案**

Run:

```bash
rg -n 'CPU 80%|流量翻倍到 90%|排队论告诉我们 70%' performance-tuning-roadmap/01-methodology/04-performance-laws.md
```

Expected: 找到三处现有表述，分别位于倍率表引导语、工程启示和容量示例；正文尚无“为什么会非线性增长”或“模型边界”小节。

- [x] **Step 2: 在公式与倍率表之间加入原因、推导和例子**

在 `ρ = 利用率 = λ/μ` 的公式块之后加入：

````markdown
#### 为什么会非线性增长

先把无排队时的平均服务时间记为 `S = 1/μ`。当服务率 `μ` 固定、通过提高 `λ` 增加利用率时，平均服务时间 `S` 不变，变少的是系统用来消化随机积压的余量：

```
剩余处理能力 = μ - λ = μ(1 - ρ)
```

请求并不是均匀到达的。即使长期平均到达率小于服务率，短时间内也可能连续到达并形成队列。`ρ` 越高，服务器越难得空闲，消化同样一段积压所需的时间就越长。

还可以结合 Little 定律推导这个结果。在 M/M/1 假设下，泊松到达的 PASTA 性质让到达者平均看到 `L` 个请求，而指数服务时间的无记忆性让正在服务请求的平均剩余服务时间仍为 `S`；因此，完成这些请求再完成自身的平均时间为：

```
W = (L + 1)S
  = (λW + 1) / μ       # 代入 L = λW、S = 1/μ

μW = λW + 1
W  = 1 / (μ - λ)
   = 1 / [μ(1 - ρ)]
   = S / (1 - ρ)
```

关键在分母 `1 - ρ`：利用率越接近 100%，这个余量越接近零，平均响应时间便不是按利用率等比例增加，而是被倒数关系放大。

例如 `μ = 100 req/s`，无排队时 `S = 10ms`：

```
ρ = 80%：W = 10ms / (1 - 0.8) = 50ms
ρ = 90%：W = 10ms / (1 - 0.9) = 100ms
```

利用率只增加 10 个百分点，平均响应时间却翻倍。
````

将原来的倍率表引导语改为：

```markdown
所以，在符合 M/M/1 假设的单瓶颈系统中，利用率达到 80% 时，平均响应时间已经是无排队时的 5 倍：
```

- [x] **Step 3: 在图表与工程启示之间补充模型边界**

在响应时间曲线代码块之后加入：

```markdown
> **模型边界**：上述精确倍率成立于 M/M/1 的假设——泊松到达、指数服务时间、单服务台且系统处于稳态（`ρ < 1`）。多核 CPU、线程池通常需要 M/M/c 或更复杂的模型。对于允许请求进入等待队列且未通过拒绝、降级或背压限制队列的系统，仍会表现出“高利用率叠加流量或服务时间波动，导致排队快速增加”，但不存在对所有系统都适用的 80% 固定拐点。
```

- [x] **Step 4: 修正工程启示和容量示例**

将工程启示改为：

```markdown
- **不要让受排队影响的关键资源长期逼近 100% 利用率**。70-80% 常被用作初始容量目标，但应根据工作负载波动和延迟 SLO 验证
- 容量规划时要留 headroom（余量），不能按 100% 利用率来规划
- 这也是为什么“平时没问题，流量一涨就崩”——在 M/M/1 模型中，利用率从 60% 升到 90%（流量增加 50%），响应时间会从空闲时的 2.5 倍升到 10 倍；流量不是翻倍，响应时间却变成原来的 4 倍
```

将容量模型步骤 2 改为：

```markdown
2. **用 Little 定律检查并发数、吞吐量与延迟是否自洽**
```

将容量示例改为：

```markdown
- 简化假设：单实例有 100 个请求持续占用线程，且每个请求平均占用线程时间保持 50ms
- 据 Little 定律估算：`λ = L/W ≈ 100/0.05 = 2000 req/s`
- 实际最大吞吐量还受 CPU、I/O、锁竞争等瓶颈影响，须在目标负载下通过压测和延迟 SLO 验证
- 为排队和流量波动预留余量，这里仅用 70% 作为初步容量预算（不是 M/M/1 严格推导出的通用阈值）
- 所以单实例初步规划吞吐量 = 2000 × 0.7 = 1400 req/s
```

- [x] **Step 5: 校验结构、公式和旧表述已清理**

Run:

```bash
rg -n '为什么会非线性增长|PASTA|无记忆性|μ - λ = μ\(1 - ρ\)|W  = 1 / \(μ - λ\)|模型边界|流量增加 50%|检查并发数、吞吐量与延迟是否自洽|压测和延迟 SLO' performance-tuning-roadmap/01-methodology/04-performance-laws.md
```

Expected: 九种新增内容全部匹配。

Run:

```bash
rg -n 'CPU 80%|流量翻倍到 90%|排队论告诉我们 70%|计算理论吞吐量上限|单实例最大吞吐量（Little）' performance-tuning-roadmap/01-methodology/04-performance-laws.md
```

Expected: 无输出，退出码为 1。

Run:

```bash
git diff --check -- performance-tuning-roadmap/01-methodology/04-performance-laws.md
```

Expected: 无输出，退出码为 0。

- [x] **Step 6: 复读修改后的完整排队论与容量示例**

Run:

```bash
sed -n '180,325p' performance-tuning-roadmap/01-methodology/04-performance-laws.md
```

Expected: 阅读顺序为“模型定义 → 公式 → 原因与推导 → 倍率表与图 → 模型边界 → 工程启示 → 容量示例”，公式和例子相互一致，没有把 M/M/1 结论泛化为所有 CPU 或线程池的硬阈值。

- [x] **Step 7: 单独提交正文修改**

```bash
git add performance-tuning-roadmap/01-methodology/04-performance-laws.md
git commit -m "docs: explain nonlinear queueing latency"
```
