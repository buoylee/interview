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

## TL;DR(三句话定位)

- **superpowers** = "**强制性方法论**":一整套从 brainstorm → plan → TDD → review 的工作流,靠 SessionStart hook + "1% 规则" 把 agent 卡死在流水线上,目标是放手让 agent 自动跑几小时
- **mattpocock-skills** = "**反框架的小工具集**":17 个手动调用的 slash command,作者明确反对 BMAD/Spec-Kit 那种"夺权",强调 "small, easy to adapt, composable"、 "make them your own"
- **agent-skills** = "**SDLC 标准化套装**":22 个 skill + 7 个 slash + 3 个 subagent,严格按 6 阶段 SDLC(DEFINE/PLAN/BUILD/VERIFY/REVIEW/SHIP)分组,边界最清晰、平台覆盖最广、最像团队基础设施

---

## 核心对比矩阵

| 维度 | superpowers | mattpocock-skills | agent-skills |
|---|---|---|---|
| **作者 / 背景** | Jesse Vincent / Prime Radiant | Matt Pocock(TS 圈知名教师) | Addy Osmani(Google Chrome DevRel) |
| **当前版本/标识** | v5.1.0 | 滚动主分支 | 滚动主分支 |
| **定位标语**(原文) | "complete software development methodology for your coding agents" | "My agent skills that I use every day to do real engineering - not vibe coding" | "Production-grade engineering skills for AI coding agents" |
| **skill 数** | 14 | 17 active(另 4 deprecated / 5 in-progress) | 22 |
| **slash command 数** | 0(skill 自身就是触发器) | 等于 skill 数(每个 skill 都是一个 slash command) | 7(`/spec /plan /build /test /review /code-simplify /ship`) |
| **subagent 数** | 0(v5 把 code-reviewer 收编进 skill) | 0 | **3**(code-reviewer / security-auditor / test-engineer) |
| **Hooks** | SessionStart(注入 using-superpowers) | **无** | SessionStart + simplify-ignore + sdd-cache(后两个是业务功能) |
| **References / 外置 checklist** | 有(每个 skill 自带 references/ 子文件) | 极少 | 5 份独立 checklist(testing/security/perf/a11y/orchestration,共 1,053 行) |
| **markdown 行数(skills/)** | ~7,054 | ~3,294 | ~6,216 |
| **触发模型** | **自动 + 强制门**:SessionStart 注入 + "1% 规则" + HARD-GATE | **手动**:全部靠 `/skill-name` | **混合**:slash + intent-mapping 自动 + 元 skill 调度 |
| **强制语句样本** | "If you think there is even a 1% chance a skill might apply, you ABSOLUTELY MUST invoke the skill" | 没有等价物 | "Determine if any skill applies (even 1% chance)"(同款措辞但靠 mapping 表执行) |
| **组织原则** | 流程方法论(SDD pipeline) | **失败模式驱动**(misalignment / verbosity / quality / mud-ball) | **6 阶段 SDLC** |
| **支持 harness 数** | 8(Claude Code / Codex CLI / Codex App / Factory Droid / Gemini CLI / OpenCode / Cursor / Copilot CLI) | 1(Claude Code) | 8+(Claude / Cursor / Gemini / Windsurf / OpenCode / Copilot / Kiro / 通用 MD) |
| **跨平台同步机制** | `.version-bump.json` + `scripts/sync-to-codex-plugin.sh` 一键改 6 文件 | 无(只有一份) | 每平台独立 setup 文档(`docs/*-setup.md`) |
| **AGENTS.md 与 CLAUDE.md 关系** | **symlink**(同一份内容) | 只有 CLAUDE.md(且偏组织规则) | **职责分工**(CLAUDE 给 CC 用户,AGENTS 给跨工具编排者) |
| **scope 控制** | 靠 v5 收编 agents、聚焦 14 个 skill | **`.out-of-scope/` + `deprecated/` 显式记录** | 22 skill 按 SDLC 阶段平均分布 |
| **PR 接受率** | 文档自报 **94% 拒收**("PRs that show no evidence of human involvement will be closed") | 未声明 | 未声明 |
| **核心独有能力** | brainstorming / writing-plans 强制门、subagent-driven-development | grill-me / grill-with-docs / CONTEXT.md 机制 | doubt-driven-development / `/ship` 并行 fan-out / 5 份 reference checklist |
| **分发** | Claude 官方插件市场 + Codex 官方市场 + 自家 superpowers-marketplace | 第三方 CLI(`npx skills@latest add ...`) | Claude 官方插件市场 + 各平台手工集成 |

---

## 三家共同点(本质共识)

不管哲学多不一样,这三家在以下几点上**高度一致**——可以认为是 2026 年"agent skill"领域的事实标准:

1. **`SKILL.md` + YAML frontmatter** 作为 skill 的最小单元,frontmatter 至少有 `name` + `description`
2. **spec-before-code** 是公理 —— 三家都有自己的"先写设计/规格再写代码"的 skill(`brainstorming` / `grill-with-docs` / `spec-driven-development`)
3. **TDD 是默认姿势** —— 三家都把 test-driven-development 单列为 skill,且都强调 RED-GREEN-REFACTOR 顺序、反对 mock 滥用、要求 vertical slice
4. **用 description 字段做触发** —— 都靠 description 写一句"何时用我"让 agent / harness 自己决定调不调
5. **Anti-pattern / Red Flags 风格的反"偷懒"段** —— 三家都有"**Common Rationalizations**"或"**Red Flags**"风格的章节,把 agent 常见的合理化借口预先驳斥
6. **元 skill / 自指文档** —— 都有"教 agent 怎么用 skill 系统"的 meta 文档(`using-superpowers` / `setup-matt-pocock-skills` / `using-agent-skills`)
7. **流程上把 review 和 ship 分开** —— 都不把代码审查/调 review/合并/发布混为"一个动作"

---

## 三家关键差异(本质分歧)

| # | 议题 | superpowers | mattpocock-skills | agent-skills |
|---|---|---|---|---|
| 1 | **是否强制 agent 必须用 skill** | 是,SessionStart 注入 + 1% 规则 + HARD-GATE | 否,纯手动 | 中等,靠 intent-mapping + 元 skill |
| 2 | **目标使用模式** | "放手让 agent 自动跑几小时" | "我有自己流程,需要时手动调一个特定能力" | "团队里把 SDLC 阶段标准化下来" |
| 3 | **对小任务友好度** | 差(1 行修改也得过 brainstorm) | **好**(没人逼你调) | 差(SDLC 6 阶段假设) |
| 4 | **平台覆盖** | 8 个 | 1 个 | 8+ 个 |
| 5 | **subagent 哲学** | v5 主动**取消** agents 目录,改进 skill 内嵌 prompt | 不涉及 | **3 个独立 agent**,靠 `/ship` 并行 fan-out |
| 6 | **scope 哲学** | 把"全 SDLC 流程"做完整 | 显式拒绝小众功能(`.out-of-scope/`) | 把"高级工程师纪律"做完整 |
| 7 | **对用户控制权的态度** | 强制门最严,但承认"用户指令 > skill > 默认" | "Hack around with them. Make them your own." 最尊重用户 | 中等,SDLC 阶段建议性强但有 intent-mapping 自动化 |
| 8 | **AGENTS.md ⇆ CLAUDE.md 思路** | 同一份(symlink) | 只对 CC 写 | 区分受众分写两份 |
| 9 | **是否有"质疑自己"的 skill** | 间接(`receiving-code-review` 反对盲从) | 间接(`/grill-me` 反向拷问用户) | **直接**:`doubt-driven-development` 把"对自己的判断起疑"做成正式流程 |
| 10 | **品牌色彩** | "complete methodology"产品级 | 个人品牌(`/setup-matt-pocock-skills`) | 中性产品名("agent-skills") |

---

## 选型建议(场景 → 推荐)

### 场景 A:个人 / 小团队、想"放手让 agent 自动写几小时,自己只看结果"
**推荐 superpowers**。它是唯一一套真把"长时间无人值守"作为目标的方法论,SessionStart 强塞 + 1% 规则确保 agent 不会跳步,brainstorming/writing-plans 的 HARD-GATE 帮你在前期把 spec 钉死,后面 subagent-driven-development 才有"信赖基础"自动跑。代价是**小任务也要走完整流程**,Auto mode 才能勉强缓解。

### 场景 B:已经有自己的开发流程,只想给 agent 补几个特定能力
**推荐 mattpocock-skills**。每个 skill 都是独立 slash command,**不调就不发生**,完全不污染你的 system prompt。`/grill-me` 处理"对不齐意图"特别好用,`/grill-with-docs` 加 `CONTEXT.md` 是处理"agent 不懂你项目术语"的轻量解。但接受现实:agent 不会"自动调用",**要靠你养成"先 grill 再说"的习惯**。

### 场景 C:团队 / 企业项目,需要把 SDLC 阶段标准化、要 review/security/test 多角色协同
**推荐 agent-skills**。6 阶段 SDLC + 7 个 slash command 直接对标软件工程教科书的工作流;3 个 subagent + `/ship` 并行 fan-out 是所有仓库里**唯一**可工程化落地的"多角色 review";5 份 reference checklist(security/perf/a11y …)给团队提供共识基线。代价是学习曲线最陡、`/ship` token 成本最高。

### 场景 D:你想自己写一套企业内部的 skill 库
- **学结构 / 模板**:看 superpowers 的 `writing-skills` skill(它是 meta-skill,直接教你"skill 应该长什么样")+ agent-skills 的 `docs/skill-anatomy.md`(贡献者规范)
- **学 hook 集成**:看 agent-skills 的 `hooks/sdd-cache-pre.sh` / `simplify-ignore.sh`,这是把"业务 hook"和"lifecycle hook"分离的最佳样本
- **学 scope 控制**:看 mattpocock-skills 的 `.out-of-scope/` 写法,这是"明确不做什么"的少见好实践
- **学跨平台**:看 superpowers 的 `.version-bump.json` 中央化版本管理 + 8 个 plugin manifest

### 场景 E:你不确定要哪个,想"小步试"
**先装 mattpocock-skills**。零强制、单平台、装上去不用就当没装,先用 `/grill-me` 体验"agent 拷问你"的感觉。如果发现"我每次都得手动打 `/grill-me` 太麻烦",再上 superpowers(获得自动强制)或 agent-skills(获得 SDLC 闸门)。

---

## 一张图看决策

```
                    ┌────────────────────────┐
                    │  你想给 agent 装 skill │
                    └────────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    │ 你能容忍 SessionStart   │
                    │ 注入和强制 1% 规则吗?  │
                    └────────────┬────────────┘
                          能      │      不能
                ┌────────────────┴────────────────┐
                ▼                                 ▼
     ┌──────────────────────┐           ┌────────────────────┐
     │ 你想要 SDLC 阶段     │           │ 你想要"自由组合"  │
     │ 标准化(spec→ship)?│           │ 个人 / 项目用?    │
     └──────────┬───────────┘           └─────────┬──────────┘
                │                                 │
        是      │      否                         ▼
    ┌───────────┴──────────┐           ┌────────────────────┐
    ▼                      ▼           │  mattpocock-skills │
┌────────────┐    ┌──────────────┐     └────────────────────┘
│agent-skills│    │ superpowers  │
│            │    │              │
│22 skill +  │    │14 skill +    │
│7 slash +   │    │强制 SDD 流水 │
│3 agent     │    │8 平台覆盖    │
└────────────┘    └──────────────┘
```

---

## 数字事实汇总

| 事实 | superpowers | mattpocock-skills | agent-skills |
|---|---|---|---|
| skill 数(active) | 14 | 17 | 22 |
| skill 数(总,含 deprecated/in-progress) | 14 | 27 | 22 |
| skills/ 总 markdown 行数 | ~7,054 | ~3,294 | ~6,216 |
| slash command 数 | 0 | 17(每个 skill 一个) | 7 |
| subagent 数 | 0 | 0 | 3 |
| 独立 hook 数 | 1 类(SessionStart) | 0 | 7 文件(SessionStart + simplify-ignore + sdd-cache 三组) |
| references/ 文件数 | 嵌入各 skill | 极少 | 5(独立目录,共 1,053 行) |
| docs/ setup 指南数 | 1+(opencode 单独有) | 0 | 8 |
| 支持的 harness | 8 | 1 | 8+ |
| RELEASE-NOTES 行数 | 1,180 | — | — |
| 是否官方插件市场 | Claude + Codex 官方 + 自家 marketplace | 第三方 skills.sh | Claude + 各平台手工集成 |

---

## 最后一句话

如果你只能记住一句:

> **superpowers 卖的是"纪律",mattpocock-skills 卖的是"工具",agent-skills 卖的是"工序"。**

—— 三个仓库都在解决"如何让 LLM 不再 vibe coding"这个共同问题,但下注的方式截然不同:Superpowers 押"强制流水线",Pocock 押"高质量小工具 + 用户自律",Osmani 押"工业化的 SDLC pipeline"。
