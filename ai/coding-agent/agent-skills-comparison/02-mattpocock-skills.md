# Mattpocock/skills 深挖

> 三个仓库里**最轻、最克制**的那一个。作者明确说"我反对那种夺走你控制权的框架"。
> 仓库:<https://github.com/mattpocock/skills>(本报告依据本地快照 commit `9fecab9`)

## 1. 速览

| 项 | 值 |
|---|---|
| 作者 | Matt Pocock(TypeScript 圈知名教师,~60K newsletter 读者) |
| 当前 commit | `9fecab9` "Add review skill to facilitate two-axis code reviews" |
| 许可 | 见 `LICENSE` |
| skill 数(active) | 17(engineering 10 / productivity 3 / misc 4)|
| skill 数(全部状态) | 27(active 17 + in-progress 5 + personal 2 + deprecated 4)|
| 总 markdown 行数(skills/) | ~3,294 |
| 支持 harness 数 | 1(只针对 Claude Code 风格的 slash command) |
| 是否带 hooks | **没有** |
| 是否带 subagents | **没有** |
| 强制门 | **完全没有**,纯手动 slash 调用 |

## 2. 设计哲学

`README.md` 的第一句直接把整个仓库的"对抗对象"亮出来了:

> "Developing real applications is hard. Approaches like GSD, BMAD, and Spec-Kit try to help by owning the process. But while doing so, they take away your control and make bugs in the process hard to resolve. These skills are designed to be small, easy to adapt, and composable. They work with any model. They're based on decades of engineering experience. Hack around with them. Make them your own. Enjoy."
> —— `README.md`

中文一句话:**"框架夺权"是问题,我提供的是"小工具",你按需挑。**

副标题更直白:

> "My agent skills that I use every day to do real engineering - not vibe coding."
> —— `README.md`

"vibe coding"(凭感觉写)是这套 skill 想反对的另一面——但它的解法**不是上方法论**(那是 Superpowers 的路子),而是**给你几个高质量的小工具,逼你想清楚再动手**。

## 3. 失败模式驱动结构

整个仓库的组织方式特别像"看医生":先列出**症状**,再开**药方**(对应 skill)。`README.md` 列了 4 个 failure mode,每一个都配一句经典工程教科书引言:

| # | 症状 | 引用 | 解药(skill) |
|---|---|---|---|
| 1 | The Agent Didn't Do What I Want(对不齐意图) | David Thomas & Andrew Hunt, *Pragmatic Programmer*: "No-one knows exactly what they want" | `/grill-me`、`/grill-with-docs` |
| 2 | The Agent Is Way Too Verbose(术语缺失,啰嗦) | Eric Evans, *Domain-Driven Design*(ubiquitous language) | `/grill-with-docs` 抽 domain → 写 `CONTEXT.md` |
| 3 | The Code Doesn't Work(没测,跑不动) | *Pragmatic Programmer*(rate-limited feedback) | `/tdd`、`/diagnose` |
| 4 | We Built A Ball Of Mud(架构腐烂) | Kent Beck / John Ousterhout(模块设计) | `/to-prd`、`/zoom-out`、`/improve-codebase-architecture` |

这个结构说明了 Matt 的设计观:**skill 不是按 SDLC 阶段分的,而是按"agent 会出什么错"分的**。每个 skill 都是某个具体失败模式的对策。

## 4. Skill 清单

> 全部用 slash command 命名(对应 Claude Code `/skill-name`)。

### Engineering(10)

| Skill | 用途 |
|---|---|
| `diagnose` | 按系统化步骤诊断 bug,反对"凭直觉改" |
| `grill-with-docs` | grill-me 的增强版,顺带管理 `CONTEXT.md` 和 ADR |
| `improve-codebase-architecture` | 救泥球架构,带 DEEPENING/INTERFACE-DESIGN/LANGUAGE 子文档 |
| `prototype` | 写一次性原型(明确不要做工程化) |
| `setup-matt-pocock-skills` | 一次性 onboarding,问你 issue tracker / label / 文档目录 |
| `tdd` | RED-GREEN-REFACTOR,强调 vertical slicing |
| `to-issues` | 把对话/讨论拆成 issue tracker 里的 ticket |
| `to-prd` | 把 idea 转成 PRD,顺带过模块影响 |
| `triage` | 用 label 把新 issue 分类(用户在 setup 里告诉过它有哪些 label) |
| `zoom-out` | 强制 agent 跳出当前文件看全局 |

### Productivity(3)

| Skill | 用途 |
|---|---|
| `caveman` | 让 agent 输出极简短(对抗 verbosity) |
| `grill-me` | 拷问对话,把模糊需求逼成清晰需求,**最受欢迎的 skill** |
| `write-a-skill` | 写新 skill 的 meta-skill |

### Misc(4)

| Skill | 用途 |
|---|---|
| `git-guardrails-claude-code` | 给 Claude Code 加 git 保护(防止 force push 等) |
| `migrate-to-shoehorn` | 项目特定的迁移工具 |
| `scaffold-exercises` | 为教学搭练习脚手架 |
| `setup-pre-commit` | 配 pre-commit hook |

### 其他(不在 plugin.json 里)

- **deprecated/** 4 个:`design-an-interface`、`qa`、`request-refactor-plan`、`ubiquitous-language`(被 `/grill-with-docs` 合并掉了)
- **in-progress/** 5 个:`handoff`、`review`、`writing-beats`、`writing-fragments`、`writing-shape`
- **personal/** 2 个:`edit-article`、`obsidian-vault`(作者私用,不推广)

## 5. 核心 skill 解读

### 5.1 `/grill-me`(productivity/grill-me)

灵魂 skill。前面表里那句"No-one knows exactly what they want"对应的就是它。流程:**一次只问一个问题**,直到形成共识;能在代码里查到答案的就直接查,不要拷问用户。

它的 description:

> "Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree..."
> —— `skills/productivity/grill-me/SKILL.md`(frontmatter)

和 Superpowers `brainstorming` 有交集,但 `grill-me` 不强制产出 design doc、不强制走完整流水线,**只负责"问到位"这一件事**。

### 5.2 `/grill-with-docs`(engineering/grill-with-docs)

`grill-me` 的"工程师增强版":在拷问之外,**还要去找 / 更新 `CONTEXT.md`**。

`CONTEXT.md` 是什么?Matt 自己仓库里就有一份(`/Users/buoy/Development/gitrepo/skills/CONTEXT.md`),内容是这个仓库自己用的"领域字典":Issue tracker / Issue / Triage role 各是什么意思,哪些词被废弃了。`/grill-with-docs` 干的事就是**为用户的项目自动建/维护这份字典**——让 agent 以后不要再"用 20 个词去说 1 个词的事"(对应 failure mode #2)。

支持两种项目结构:
- 单 context:根目录一个 `CONTEXT.md`
- 多 context:根目录 `CONTEXT-MAP.md` + 各模块自己的 `CONTEXT.md`

### 5.3 `/tdd`(engineering/tdd)

和 Superpowers 的 TDD 思想一致,但**没有"1% 必须用 TDD"的强制**——你不调 `/tdd`,agent 就该写啥写啥。

特点:
- 显式反对"horizontal slicing"(把所有 test 一次写完再写实现)
- 强调 vertical slice:一次只完成"一个测试 → 一段实现"的最小循环
- 内置 `tests.md`、`mocking.md`、`deep-modules.md` 三个子文档讲底层原则

### 5.4 `CONTEXT.md` 机制

这不是 skill,但是整个体系的"基础设施"——`/grill-with-docs`、`/zoom-out`、`/triage`、`/to-prd` 都会读 / 写它。可以理解为**项目级的"短期记忆 + 术语表"**,把"agent 来回换 session 后还能保持术语一致"这件事用一个 markdown 文件解决。

## 6. 触发模型:零强制

**没有**任何"启动期注入 skill"、没有"1% 规则"、没有 SessionStart hook、没有 Red Flags 表。

skill 只通过 **`/skill-name`** 显式调用。这是非常自觉的设计选择——README 反复说:

> "Pick the skills you want, and which coding agents you want to install them on."
> "Hack around with them. Make them your own."
> —— `README.md`

唯一带"setup"性质的是 `/setup-matt-pocock-skills`,但它是**一次性 onboarding**(问你 issue tracker / label / 文档目录),不是每会话强制门。

## 7. Scope 管理:`.out-of-scope/` 与 `deprecated/`

这是这个仓库**最少见的优秀实践**——明确写出"我不做什么"。

### `.out-of-scope/`

3 个文件,公开记录"被请求但决定不做的事":

- **`mainstream-issue-trackers-only.md`**:`/setup-matt-pocock-skills` 只支持主流 issue tracker(GitHub、GitLab、Backlog.md)。"小众 tracker"明确不做,理由是维护成本。文件甚至点名了被拒掉的 issue(#99 dex tracker,~3 个月、~300 stars)
- **`question-limits.md`**:某次想给 grill 加上"最多问 N 个问题"的提议被拒
- **`setup-skill-verify-mode.md`**:某次想给 setup 加 verify 模式的提议被拒

### `deprecated/`

4 个被淘汰的 skill **保留代码不删**,README 里也保留链接,这样将来有人看 git 历史能找到来龙去脉:

- `design-an-interface`(并行 sub-agent 设计 UI)—— **方法被放弃**
- `qa`(交互式 bug 报告)—— 被其他流程替代
- `request-refactor-plan` —— 被合并
- `ubiquitous-language` —— 合并进 `/grill-with-docs`

这两个文件夹的存在告诉我们:**Matt 在主动控制"agent 工具的攻击面"**——不让 skill 数无限膨胀,这和 agent-skills 的 22 个 skill、Superpowers 的 14 个走的是不同的"丰俭"路线。

## 8. 分发与平台

### 安装方式

`README.md` 给的 30 秒入门:

> "1. Run the skills.sh installer:
> ```bash
> npx skills@latest add mattpocock/skills
> ```
> 2. Pick the skills you want, and which coding agents you want to install them on. **Make sure you select `/setup-matt-pocock-skills`**.
> 3. Run `/setup-matt-pocock-skills` in your agent."
> —— `README.md`

`skills@latest` 是一个**第三方 npm CLI**(skills.sh),不是 Claude 官方插件市场。这个工具是 Matt 自己运营的,有徽章 `https://skills.sh/b/mattpocock/skills`。

### 单平台

仓库本身只针对 Claude Code 风格的 slash command。没有 `.cursor-plugin/`、没有 `gemini-extension.json`,这点和 Superpowers / agent-skills 形成鲜明对比。这是**有意的克制**——多平台维护成本高,不在 Matt 的"做"清单里。

`scripts/` 只有两个 bash 脚本:`link-skills.sh`(把 active skill 软链到 `~/.claude/skills/`)和 `list-skills.sh`(列出 active skill)。

## 9. 个人风格观察

读完整个仓库,有几个观察:

1. **强烈的"教师"色彩**——每个 failure mode 都配一句经典书引言,REAMDE 的整体调性在教读者"为什么这么做",而不是"快用我"
2. **强烈的"作者品牌"**——newsletter 入口、skills.sh 个人 CLI、个人页跳转,都是 Matt Pocock 的扩展生态
3. **拒绝"夺权"** —— 没有 SessionStart 强塞、没有 Red Flags、没有 1% 规则;skill 是"你想用就用"
4. **scope 极度克制** —— `.out-of-scope/` 文档化"不做什么",deprecated/ 保留历史
5. **流程感弱** —— skill 之间几乎没有"必须按顺序走"的关系,你可以单独用 `/grill-me` 而不用 `/tdd`

## 10. 不足 / 风险

- **没有强制 → 容易被忽略**:agent 是否真的去调 `/grill-me` 完全靠用户主动打。"只要不调,grilling 就不发生",对自律差的用户帮助有限
- **单平台**:Cursor / Codex 用户没法直接用,要自己复制 SKILL.md
- **依赖第三方 CLI(skills@latest)**:不是 Claude 官方插件,生态稳定性次于 Superpowers / agent-skills
- **个人色彩重**:`/setup-matt-pocock-skills` 的命名就把品牌写死了;不易作为团队/公司基础设施
- **跨 session 一致性弱**:除了 `CONTEXT.md` 外没有"启动期 context 强化"机制——agent 换会话后,它不知道要去用 `/grill-me`
- **缺 review/security skill**:相比 agent-skills 的 5 个 review/ship 专门 skill,Matt 这套没有 security hardening、没有专门的 PR review skill(in-progress 里有个 `review`,但还没出炉)
