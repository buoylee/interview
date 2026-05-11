# Design — Agent Skills 仓库对比报告

> 内部规划文档,定义最终交付的 4 份 md 各自写什么、为什么这么拆。
> 写完报告后此文件保留,作为后续修订的依据。

## 目标

帮助读者从 0 全方位理解 3 个主流 "Claude Code agent skills" 仓库的设计差异:
- `obra/superpowers` (Jesse Vincent, v5.1.0)
- `mattpocock/skills` (Matt Pocock)
- `addyosmani/agent-skills` (Addy Osmani)

读者画像:已经在用 Claude Code、想搞清楚"该装哪一套"或"该自己怎么写 skill"的工程师。

## 编写约定

- **正文中文,术语和原文保留英文**(skill name、frontmatter 字段、命令名都保留)。
- **引用原文用 markdown 引用块 + 注明出处文件**,例如:
  ```
  > "Skills encode the workflows, quality gates, and best practices..."
  > —— addyosmani/agent-skills `README.md`
  ```
- 数字事实(skill 数、行数、平台数)以 subagent 调研所得为准,文末汇总一张事实表。
- 不做主观高低评,但允许在"选型建议"中给场景化推荐。

## 文件清单与各文件骨架

### `00-overview.md` —— 总览与选型(目标 ~300 行)

1. **TL;DR 三句话** —— 一句话定位每个仓库
2. **核心对比矩阵** —— 一张大表覆盖以下维度,横轴 3 个仓库,纵轴:
   - 作者 / 版本 / 许可
   - 定位标语(原文引用)
   - skill 数 / 总行数
   - 支持平台数
   - 触发模型(自动 / 手动 / 混合)
   - 是否有强制门禁
   - 组织原则(方法论 / 失败模式 / SDLC 阶段)
   - 是否提供 subagents
   - 是否有 hooks
   - 安装方式
3. **三家共同点** —— 5-7 条本质共识(都用 frontmatter、都强调 spec-before-code、都内置 TDD…)
4. **三家关键差异** —— 5-7 条本质差异(强制 vs 可选、方法论 vs 工具集、单平台 vs 多平台…)
5. **选型建议** —— 4-6 个场景 → 推荐哪家(或哪些 skill 拼用)
   - "想要全自动方法论 / 长时间放手让 agent 干" → superpowers
   - "已有自己流程,只补特定能力" → mattpocock
   - "团队需要标准化 SDLC 阶段闸门" → agent-skills
   - "想自己写 skill 学结构" → 看 superpowers + agent-skills 的 SKILL.md 模板
6. **延伸阅读** —— 链接到 3 份深挖文件

### `01-superpowers.md` —— 深挖 obra/superpowers(目标 ~500 行)

1. 仓库速览(作者、版本、许可、首页链接)
2. **设计哲学** —— 引用 README + CLAUDE.md 关键段(complete methodology / 1% 规则 / 评论性 PR 政策)
3. **方法论流水线** —— brainstorm → writing-plans → executing-plans / subagent-driven → TDD → request-review → finishing-branch,每步配 1-2 句中文解释 + skill name
4. **Skill 清单** —— 全 14 个 skill 的表格(name / description 原文 / 一句中文释义)
5. **触发与强制机制** —— 重点写:
   - SessionStart hook 注入 `using-superpowers`
   - "1% 规则" 原文引用 + Red Flags 表节选
   - HARD-GATE 标签
   - CLAUDE.md 里 94% PR 拒收的政策
6. **结构特点** —— dot 图、checklist、references/ 子文件、anti-pattern table 模式
7. **跨平台与分发** —— 8 个 harness、`.version-bump.json` 集中改版、`scripts/sync-to-codex-plugin.sh` 自动镜像
8. **代表性 skill 拆解** —— `brainstorming` / `test-driven-development` / `using-superpowers` 各 1 段精读
9. **不足 / 风险** —— 流程重、强迫性强、对小任务过度

### `02-mattpocock-skills.md` —— 深挖 Matt Pocock(目标 ~400 行)

1. 仓库速览
2. **设计哲学** —— 引用 README:
   - 反 BMAD/GSD/Spec-Kit 那段原文
   - "small, easy to adapt, and composable"
   - "make them your own"
3. **失败模式驱动结构** —— 4 个 failure modes(misalignment / verbosity / quality / mud-ball)→ 对应 skill,引用 README 每段开头的引言(Pragmatic Programmer / DDD / Kent Beck …)
4. **Skill 清单** —— 17 active(分 engineering / productivity / misc),另列 4 deprecated 与 5 in-progress
5. **核心 skill 解读** —— `/grill-me`、`/grill-with-docs`、`/tdd`、`CONTEXT.md` 机制
6. **触发模型** —— 纯手动 slash,无强制层;`/setup-matt-pocock-skills` 一次性 onboarding
7. **scope 管理** —— `.out-of-scope/` 与 `deprecated/` 文件夹的设计意图(罕见的"明确不做")
8. **分发** —— `npx skills@latest add ...` 第三方 CLI、单 Claude Code 平台
9. **个人风格观察** —— 牛人个人技能集 vs 框架的差异

### `03-agent-skills.md` —— 深挖 addyosmani/agent-skills(目标 ~600 行)

1. 仓库速览
2. **6 阶段 SDLC 模型** —— ASCII 图原样保留 + 每阶段 skill 列表
3. **Slash Commands** —— `/spec /plan /build /test /review /code-simplify /ship` 每个 1 段精读
4. **Skill 清单** —— 全 22 个 skill 按阶段分组的大表
5. **三个 subagents** —— `code-reviewer` / `security-auditor` / `test-engineer` 各自 frontmatter + 职责 + 怎么被 `/ship` fan-out
6. **触发与强制** —— 混合模型(手动 slash + 自动 intent-mapping + `using-agent-skills` 元 skill)、对比 superpowers 的 1% 规则
7. **特色组件** ——
   - hooks: `simplify-ignore` / `sdd-cache` 的实现机制
   - references/: 5 份 checklist(testing/security/perf/a11y/orchestration)
   - CLAUDE.md vs AGENTS.md 分工
8. **代表性 skill 拆解** —— `spec-driven-development` / `doubt-driven-development`(独有)/ `test-driven-development`
9. **跨平台支持矩阵** —— 8+ 个 harness 的差异
10. **不足 / 风险** —— SDLC 模型对小任务过重、reference checklist 维护成本

## 信息源约定

所有事实/引用以已经收集到的 subagent 调研材料为准,如有原文存疑,**回到对应仓库的 README.md / CLAUDE.md / SKILL.md 现场核对再写**(不凭印象写)。

## 不在范围

- 不写"如何安装第几步"——读者去看各仓库 README
- 不评测"哪家 skill 更好用"——只描述设计差异并给场景建议
- 不复刻完整 skill 内容,只摘 frontmatter + 关键段
- 不涉及商业模式、社区健康度、贡献者数量等元数据

## 完成判据

- 4 份 md 都写完且符合骨架
- 至少 6 处直接引用原文(每个仓库 ≥2 处)
- 总览的对比矩阵能让读者 60 秒内分清 3 家定位
- 内部链接(总览 → 深挖)可点
- 所有声称的数字与已收集的 subagent 数据一致
