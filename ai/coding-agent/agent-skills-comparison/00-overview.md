# Agent Skills 三大仓库对比报告 — 总览

> 对比对象:
> - **superpowers** — `obra/superpowers` (Jesse Vincent),v5.1.0
> - **mattpocock-skills** — `mattpocock/skills` (Matt Pocock)
> - **agent-skills** — `addyosmani/agent-skills` (Addy Osmani)
>
> 深度细节:
> - [01-superpowers.md](./01-superpowers.md)
> - [02-mattpocock-skills.md](./02-mattpocock-skills.md)
> - [03-agent-skills.md](./03-agent-skills.md)

---

## TL;DR(更诚实的版本)

三家不是"三种独立设计",而是**两个流派**:

### 流派 A:**框架派**(superpowers + agent-skills)

共同信念:**"agent 不能 vibe coding,必须被强制走工程纪律"**。两家共享:
- spec 先于 code(都有 spec/brainstorming 类 skill)
- 强制 TDD(都把 TDD 单列为 skill)
- 描述驱动的 skill 自动触发("1% 规则"两边都有)
- Anti-pattern / Red Flags 表反 agent 偷懒
- 多平台官方插件(superpowers 支持 8、agent-skills 支持 8+)
- 元 skill 教 agent 怎么用 skill 系统

**差别只在工程实现层**(下面"框架派内部差异"那节细说)。

### 流派 B:**工具派**(mattpocock-skills)

不同信念:**"框架夺权,我只给你工具"**。明确反对 superpowers / agent-skills 这种"夺权"做法,17 个 skill 全靠用户手动 `/skill-name` 调用,没有 SessionStart 注入、没有 1% 规则、没有强制门。

> "These skills are designed to be small, easy to adapt, and composable. ... Hack around with them. Make them your own."
> —— `mattpocock/skills` `README.md`

---

## 真正的对比矩阵

| 维度 | superpowers | mattpocock-skills | agent-skills |
|---|---|---|---|
| **流派** | 框架派 | **工具派** | 框架派 |
| **作者 / 背景** | Jesse Vincent / Prime Radiant | Matt Pocock(TS 圈知名教师) | Addy Osmani(Google Chrome DevRel) |
| **当前版本/标识** | v5.1.0 | 滚动主分支 | 滚动主分支 |
| **定位标语**(原文) | "complete software development methodology for your coding agents" | "My agent skills that I use every day to do real engineering - not vibe coding" | "Production-grade engineering skills for AI coding agents" |
| **skill 数** | 14 | 17 active | 22 |
| **slash command 数** | 0(skill 自身就是触发器) | 17(每个 skill 一个) | **7**(`/spec /plan /build /test /review /code-simplify /ship`,作为 macro 入口) |
| **subagent 数** | 0(v5 故意取消) | 0 | **3**(code-reviewer / security-auditor / test-engineer,独立 context) |
| **Hooks** | 1 类(SessionStart 启动) | 0 | 3 类(SessionStart + **`sdd-cache` HTTP 缓存** + **`simplify-ignore` 代码段保护**) |
| **References / 外置 checklist** | 嵌入各 skill 内部 | 极少 | **5 份独立 checklist**(testing/security/perf/a11y/orchestration,共 1,053 行) |
| **markdown 行数(skills/)** | ~7,054 | ~3,294 | ~6,216 |
| **触发模型** | 自动 + SessionStart 注入 + 1% 规则 | 纯手动 | 自动(intent-mapping) + 手动 slash + 元 skill 调度 |
| **跨 skill 流转** | **agent 自动**(brainstorming 完成后自动调 writing-plans) | 不流转(每个 skill 独立) | **用户手动**(打完 `/spec` 不会自动进 `/plan`) |
| **BUILD 期 skill 细分** | 2(`tdd` + `systematic-debugging`,不分前后端) | 2(`/tdd` + `/diagnose`) | **7**(细分:incremental / TDD / context / source-driven / **doubt-driven** / **frontend-ui** / **api-design**) |
| **组织原则** | 流程方法论(skill chain) | 失败模式驱动(misalignment / verbosity / quality / mud-ball) | 6 阶段 SDLC(DEFINE/PLAN/BUILD/VERIFY/REVIEW/SHIP) |
| **支持 harness 数** | 8(Claude Code / Codex CLI / Codex App / Factory Droid / Gemini CLI / OpenCode / Cursor / Copilot CLI) | 1(Claude Code) | 8+(Claude / Cursor / Gemini / Windsurf / OpenCode / Copilot / Kiro / 通用 MD) |
| **跨平台维护** | `.version-bump.json` 集中改版 + sync-to-codex 镜像 | 无(只有一份) | 每平台独立 setup 文档(`docs/*-setup.md`) |
| **AGENTS.md 与 CLAUDE.md** | symlink(同一份) | 只 CLAUDE.md(且偏组织规则) | 分写(CLAUDE 给 CC 用户、AGENTS 给跨工具编排) |
| **scope 控制** | v5 收编 agents、聚焦 14 skill | **`.out-of-scope/` + `deprecated/` 显式记录** | 22 skill 按 SDLC 阶段平均分布 |
| **PR 接受率** | 自报 **94% 拒收** | 未声明 | 未声明 |
| **核心独有能力** | 单 agent 跨 skill **自动流转**、`subagent-driven-development` 长时段执行 | grill-me / grill-with-docs / CONTEXT.md 机制 | **真正的多角色独立审查**(`/ship` 并行 fan-out)、**doubt-driven-development**、**业务 hook(sdd-cache / simplify-ignore)**、**外置 checklist 库** |
| **分发** | Claude 官方插件市场 + Codex 官方市场 + 自家 marketplace | 第三方 CLI(`npx skills@latest add ...`) | Claude 官方插件市场 + 各平台手工集成 |

---

## 三家共同点(本质共识)

不管哲学多不一样,这三家在以下几点上**高度一致**——可以认为是 2026 年"agent skill"领域的事实标准:

1. **`SKILL.md` + YAML frontmatter** 作为 skill 的最小单元,frontmatter 至少有 `name` + `description`
2. **spec-before-code** 是公理 —— 三家都有"先写设计/规格再写代码"的 skill(`brainstorming` / `grill-with-docs` / `spec-driven-development`)
3. **TDD 是默认姿势** —— 三家都把 test-driven-development 单列为 skill,且都强调 RED-GREEN-REFACTOR 顺序
4. **用 description 字段做触发** —— 都靠 description 写一句"何时用我"让 agent / harness 自己决定调不调
5. **Anti-pattern / Red Flags 风格** —— 都有专门章节预先驳斥 agent 常见的合理化借口
6. **元 skill / 自指文档** —— 都有"教 agent 怎么用 skill 系统"的 meta 文档(`using-superpowers` / `setup-matt-pocock-skills` / `using-agent-skills`)
7. **review 和 ship 分开** —— 都不把代码审查/合并/发布混为"一个动作"

---

## 流派 B vs 流派 A:工具派 vs 框架派(本质分歧)

这是**真正的分水岭**——工具派(mattpocock)和框架派(superpowers + agent-skills)在以下几点上根本不同:

| # | 议题 | 工具派(mattpocock) | 框架派(superpowers / agent-skills) |
|---|---|---|---|
| 1 | **skill 是否会自动启用** | 否,纯手动 slash | 是,描述匹配 / SessionStart 注入 |
| 2 | **是否在 prompt 里强制 agent 走流程** | 否 | 是(1% 规则、Red Flags 表) |
| 3 | **目标用户** | 个人开发者、自律高 | 团队 / 想放手让 agent 干 |
| 4 | **对小任务友好度** | 高(不用就当没装) | 低(强制走流程) |
| 5 | **学习曲线** | 低(单 skill 即用) | 高(要理解整套方法论) |
| 6 | **scope 哲学** | 显式拒做(`.out-of-scope/`) | 力求覆盖完整流程 |
| 7 | **对 agent 自主性的态度** | 信任(让 agent 该咋写咋写) | 怀疑(假设 agent 会偷懒,用规则栓住) |

---

## 框架派内部差异:superpowers vs agent-skills

剥掉伪对立的"自动化程度"轴之后,**这两家的真实差别集中在 5 个工程实现点**:

### 1. 是否有真正独立 context 的 subagent

- **agent-skills**:**真有**——3 个独立 markdown 定义的 agent(`code-reviewer` / `security-auditor` / `test-engineer`)。`/ship` 命令**并行**起 3 个独立 context,主 agent 看不到它们内部思考,只收报告 → **真正的多视角审查**。
- **superpowers**:**没有**——v5 故意取消了 `agents/` 目录,把 review 角色全部并进 skill 内嵌的 prompt 模板。等于**还是同一个 agent 在切换心态**。

**这是最实质的差别**——决定了你的 review 是否会被"我刚才写代码的思路"污染。

### 2. BUILD 阶段的细分粒度

| | BUILD 期 skill |
|---|---|
| **superpowers** | 2 个,通用:`test-driven-development` + `systematic-debugging` |
| **agent-skills** | **7 个,按场景分**:`incremental-implementation` / `test-driven-development` / `context-engineering` / `source-driven-development` / `doubt-driven-development` / `frontend-ui-engineering` / `api-and-interface-design` |

如果你写**前端**——agent-skills 有专门的 `frontend-ui-engineering`;superpowers 就是"写代码 + TDD"。

如果你需要**对自己的判断起疑、独立 reviewer 反驳**——agent-skills 有 `doubt-driven-development`(本仓独有);superpowers 没有等价物。

### 3. References / 外置 checklist 层

- **agent-skills** 有 `references/` 目录,5 份独立 checklist(security / perf / a11y / testing / orchestration),共 1,053 行。**skill 文件保持薄,具体清单沉到 references**。
- **superpowers** 没有这个独立层。

意义:**OWASP 更新了,只改 `security-checklist.md` 一个文件**——所有用到 security 的 skill 自动引到新版。superpowers 改起来要找散落在多个 skill 的内嵌 checklist。

### 4. Hook 用途

| | hook 类型 |
|---|---|
| **superpowers** | 1 类:SessionStart(纯 lifecycle 触发器,只为注入 using-superpowers) |
| **agent-skills** | 3 类:SessionStart + **`sdd-cache`(给 WebFetch 加 HTTP 缓存层,带 ETag/Last-Modified)** + **`simplify-ignore`(把代码里 `/* simplify-ignore-start */` 标记的块遮罩成 hash,模型看不到,简化完再还原)** |

agent-skills 的后两个 hook 是**真业务功能**——这是仓库里**工程化最深**的部分,superpowers 完全没有这一层。

### 5. 跨"阶段边界"由谁推进

- **superpowers**:批了 brainstorming 的 design → **agent 自己**调 writing-plans → 批了 plan → **agent 自己**调 subagent-driven-development。**skill 之间的切换 agent 自己完成**(每个 skill 内部还是会问你)。
- **agent-skills**:打 `/spec` 跑完 → agent 停 → 你不打 `/plan`,系统不进 plan 阶段。**每个阶段都是显式命令**。

> ⚠️ **不要把这条理解成"自动 vs 手动"**——两家在 skill 内部都会反复找你确认,差别只在"跨 skill 这一步是 agent 自跳还是用户打命令"。整体的"无人值守时长"两边差不多。

---

## 决策树(更诚实的版本)

```
                          ┌───────────────────────────────┐
                          │ 你想要 framework 还是 toolset?│
                          └───────────────┬───────────────┘
                                          │
                ┌─────────────────────────┴─────────────────────────┐
                │ "我只想给 agent 补几个特定能力,                   │
                │  不要 SessionStart 注入也不要强制流程"            │
                ▼                                                   │
       ┌────────────────────┐                                       │
       │ mattpocock-skills  │                                       │
       │                    │                                       │
       │ 17 个手动 slash    │                                       │
       │ /grill-me 是杀手锏 │                                       │
       │ 个人项目首选       │                                       │
       └────────────────────┘                                       │
                                                                    │
                                  "我想要完整的工程纪律框架"        │
                                          ┌─────────────────────────┘
                                          ▼
                          ┌───────────────────────────────┐
                          │ 以下任一为"是"?               │
                          │  · 需要真独立 subagent         │
                          │    多角色审查(/ship 模式)    │
                          │  · 需要 BUILD 期细分          │
                          │    (前端 / API / 源驱动)     │
                          │  · 需要外置 security/perf      │
                          │    checklist 独立维护         │
                          │  · 需要业务 hook(WebFetch     │
                          │    缓存、代码段保护)         │
                          └───────────────┬───────────────┘
                                          │
                            是 ─────────┬─┴─────────── 否
                                        ▼              ▼
                              ┌─────────────────┐  ┌─────────────────┐
                              │  agent-skills   │  │   superpowers   │
                              │                 │  │                 │
                              │ 22 skill +      │  │ 14 skill,       │
                              │ 7 slash macro + │  │ 跨 skill 自动   │
                              │ 3 subagent +    │  │ 流转,           │
                              │ refs + hooks    │  │ 8 平台同步      │
                              └─────────────────┘  └─────────────────┘
```

**第一道分叉(框架 vs 工具)是真分水岭。**
**第二道分叉(superpowers vs agent-skills)是工程实现选择,差别更细。**

---

## 选型建议(场景 → 推荐)

### 场景 A:个人 / 小团队 / Side project,只想补特定能力
**推荐 mattpocock-skills**。`/grill-me` 处理"对不齐意图"特别好用,`/grill-with-docs` 加 `CONTEXT.md` 是处理"agent 不懂你项目术语"的轻量解。**不用就当没装**,完全不污染你的 system prompt。

### 场景 B:想要"完整工程框架",但**不需要**独立 subagent / 业务 hook / 外置 checklist 这些
**推荐 superpowers**。skill 之间 agent 自动流转,你只在每个 skill 内部回答问题——整体"打字次数"比 agent-skills 少;支持 8 平台,版本管理用 `.version-bump.json` 集中,工程上更"轻"。

### 场景 C:团队 / 生产代码,需要**真独立 subagent 多角色审查**(代码 / 安全 / 测试)
**只能选 agent-skills**。`/ship` 的并行 fan-out 是这个领域**唯一**可工程化落地的多角色 review 模式。superpowers v5 取消了这一层。

### 场景 D:写**前端 / API / 性能敏感代码**
**推荐 agent-skills**。BUILD 期 7 个细分 skill 里有 `frontend-ui-engineering` / `api-and-interface-design` / `performance-optimization` 等专门 skill,**superpowers 这里只是"写代码 + TDD"**。

### 场景 E:你的 agent 工作流**重度依赖 WebFetch**(查官方文档)
**推荐 agent-skills**。`sdd-cache` hook 给 WebFetch 加 HTTP 缓存层(ETag / Last-Modified),跨 session 复用——长期省 token、省时间。superpowers 没有等价机制。

### 场景 F:你想自己写一套企业内部 skill 库
- **学结构 / 模板**:看 superpowers 的 `writing-skills` skill + agent-skills 的 `docs/skill-anatomy.md`
- **学 hook 集成**:看 agent-skills 的 `hooks/sdd-cache-pre.sh` / `simplify-ignore.sh`(把"业务 hook"和"lifecycle hook"分离的最佳样本)
- **学 scope 控制**:看 mattpocock-skills 的 `.out-of-scope/`(明确"不做什么"的少见好实践)
- **学跨平台维护**:看 superpowers 的 `.version-bump.json` 中央化版本管理

---

## 数字事实汇总

| 事实 | superpowers | mattpocock-skills | agent-skills |
|---|---|---|---|
| skill 数(active) | 14 | 17 | 22 |
| skill 数(总,含 deprecated/in-progress) | 14 | 27 | 22 |
| skills/ 总 markdown 行数 | ~7,054 | ~3,294 | ~6,216 |
| slash command 数 | 0 | 17(每个 skill 一个) | 7(macro 入口) |
| subagent 数 | 0 | 0 | **3** |
| 独立 hook 数 | 1(SessionStart) | 0 | 7 文件(SessionStart + simplify-ignore + sdd-cache 三组) |
| references/ 文件数 | 嵌入各 skill | 极少 | **5(独立目录,共 1,053 行)** |
| docs/ setup 指南数 | 1+(opencode 单独) | 0 | 8 |
| 支持的 harness | 8 | 1 | 8+ |
| RELEASE-NOTES 行数 | 1,180 | — | — |
| 是否官方插件市场 | Claude + Codex 官方 + 自家 marketplace | 第三方 skills.sh | Claude 官方 + 各平台手工集成 |

---

## 最后一句话(修正版)

之前那版"superpowers 卖纪律 / mattpocock 卖工具 / agent-skills 卖工序"——**前后两个夸张了,只有"mattpocock 卖工具"立得住**。

**更准确的版本**:

> **superpowers 和 agent-skills 都在卖"工程纪律框架",mattpocock 在卖"高质量小工具"**。
>
> 在框架派里:**superpowers 押"流程的深度"**(单 agent 跨 skill 自动流转 + 跨平台同步),**agent-skills 押"分工的广度"**(独立 subagent + BUILD 期细分 skill + 外置 checklist + 业务 hook)。
>
> 两者目标一致(让 agent 不再 vibe coding),实现取舍不同,**没有"谁更强"——只有"哪种工程组织方式更贴你的场景"**。
