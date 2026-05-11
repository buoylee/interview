# Superpowers 深挖 (obra/superpowers)

> 三个仓库里**最重的那一个**。它把自己叫做 "complete software development methodology",而不是单纯的 skill 集。
> 仓库:<https://github.com/obra/superpowers>(本报告依据本地 v5.1.0 快照)

## 1. 速览

| 项 | 值 |
|---|---|
| 作者 | Jesse Vincent (jesse@fsck.com) / Prime Radiant |
| 当前版本 | v5.1.0(本地 commit `f2cbfbe`) |
| 许可 | 见 `LICENSE` |
| skill 数 | 14 |
| 总 markdown 行数(skills/) | ~7,054 |
| 支持 harness 数 | 8(Claude Code / Codex CLI / Codex App / Factory Droid / Gemini CLI / OpenCode / Cursor / GitHub Copilot CLI) |
| 是否带 hooks | 有(SessionStart) |
| 是否带 subagents | **没有独立 agents 目录**(v5 把原 `code-reviewer` agent 收编进了 skill 里的 prompt 模板) |

## 2. 设计哲学

`README.md` 开篇就把自己的定位讲透了:

> "Superpowers is a complete software development methodology for your coding agents, built on top of a set of composable skills and some initial instructions that make sure your agent uses them."
> —— `README.md`

注意"**complete methodology**"和"**make sure your agent uses them**"——后半句已经预告了这套东西的核心特征:**强制性**。

接下来这段把整个工作流的味道讲出来了:

> "It starts from the moment you fire up your coding agent. As soon as it sees that you're building something, it *doesn't* just jump into trying to write code. Instead, it steps back and asks you what you're really trying to do."
> —— `README.md`

> "It's not uncommon for Claude to be able to work autonomously for a couple hours at a time without deviating from the plan you put together."
> —— `README.md`

中文一句话总结这套哲学:**先问清楚再写,写之前先有 plan,plan 写好就放手让 agent 跑几个小时,跑完前必须验证;整个过程靠"硬性门"控制每一步,agent 没有跳步的自由**。

## 3. 方法论流水线

把 14 个 skill 摆到一条时间轴上,Superpowers 的实际形态是:

```
用户提需求
   │
   ▼
brainstorming           ← 必走:Socratic 提问 → 提案 → 设计 → 写 spec.md
   │
   ▼
writing-plans           ← 把 spec 拆成"junior 工程师能照做"的任务清单
   │
   ▼
using-git-worktrees     ← 起隔离工作区(可选,推荐)
   │
   ▼
subagent-driven-development  或  executing-plans
   │  (并行 / 串行两种执行模式)
   ▼
test-driven-development     ← 严格 RED-GREEN-REFACTOR
systematic-debugging        ← bug 出现时切到这里
   │
   ▼
verification-before-completion  ← "claim 完成"前必须跑命令
   │
   ▼
requesting-code-review      ← merge 前自我审查
receiving-code-review       ← 收到反馈后怎么处理
   │
   ▼
finishing-a-development-branch  ← merge / PR / cleanup
```

辅助 skill:`dispatching-parallel-agents`(并行 agent 编排)、`writing-skills`(怎么写新 skill)、`using-superpowers`(整套系统的"启动器")。

## 4. Skill 清单

> 共 14 个,description 字段为原文,用斜体标注的中文是简短解释。

| Skill | description(原文) | 中文释义 |
|---|---|---|
| `using-superpowers` | "Use when starting any conversation - establishes how to find and use skills, requiring Skill tool invocation before ANY response including clarifying questions" | 启动器 + 强制门:每次会话开场都要先看一遍 |
| `brainstorming` | "You MUST use this before any creative work..." | 设计前的需求澄清,产出 spec.md |
| `writing-plans` | "Use when you have a spec or requirements for a multi-step task, before touching code" | 把 spec 拆成可执行任务清单 |
| `executing-plans` | "Use when you have a written implementation plan to execute in a separate session with review checkpoints" | 串行执行 plan,带评审点 |
| `subagent-driven-development` | "Use when executing implementation plans with independent tasks in the current session" | 把任务派给 subagent 并行干 |
| `dispatching-parallel-agents` | "Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies" | 并行编排原则 |
| `using-git-worktrees` | "Use when starting feature work that needs isolation from current workspace..." | 用 worktree 隔离工作区 |
| `test-driven-development` | "Use when implementing any feature or bugfix, before writing implementation code" | 严格 TDD |
| `systematic-debugging` | "Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes" | 系统化定位 bug,反对"凭直觉改" |
| `verification-before-completion` | "...requires running verification commands and confirming output before making any success claims; evidence before assertions always" | 声明完成前必须有"跑过命令"的证据 |
| `requesting-code-review` | "Use when completing tasks, implementing major features, or before merging to verify work meets requirements" | 自请代码审查 |
| `receiving-code-review` | "...requires technical rigor and verification, not performative agreement or blind implementation" | 收到 review 后不许"无脑同意",要技术性回应 |
| `finishing-a-development-branch` | "...presenting structured options for merge, PR, or cleanup" | 决定 merge / PR / 丢弃,清理收尾 |
| `writing-skills` | "Use when creating new skills, editing existing skills, or verifying skills work before deployment" | 元 skill:怎么写新 skill |

## 5. 触发与强制机制(全仓最硬核的部分)

### 5.1 SessionStart hook

`hooks/session-start` 是一个无扩展名 bash 脚本,在每个 session 开场被 harness 调用,**把整个 `using-superpowers/SKILL.md` 的内容塞进 context**(包在 `<EXTREMELY_IMPORTANT>` 标签里)。`hooks/hooks.json` 里 matcher 是 `"startup|clear|compact"`——也就是说**清屏、压缩 context 后还会再注入一次**,确保 agent 永远忘不掉这套规则。

### 5.2 "1% 规则"

`using-superpowers/SKILL.md` 里的核心强制语句(本会话开场你也看到了):

> "<EXTREMELY-IMPORTANT>
> If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.
>
> IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.
>
> This is not negotiable. This is not optional. You cannot rationalize your way out of this.
> </EXTREMELY-IMPORTANT>"
> —— `skills/using-superpowers/SKILL.md`

中文:**只要你觉得有 1% 可能某个 skill 适用,你必须调用它。这不是建议,是命令。**

### 5.3 Red Flags 表

`using-superpowers/SKILL.md` 里有一张"反合理化"表,把 agent 常见的偷懒理由全部点名:

| 想法(原文) | 现实(原文) |
|---|---|
| "This is just a simple question" | "Questions are tasks. Check for skills." |
| "I need more context first" | "Skill check comes BEFORE clarifying questions." |
| "Let me explore the codebase first" | "Skills tell you HOW to explore. Check first." |
| "I can check git/files quickly" | "Files lack conversation context. Check for skills." |
| "This doesn't need a formal skill" | "If a skill exists, use it." |
| "The skill is overkill" | "Simple things become complex. Use it." |
| "This feels productive" | "Undisciplined action wastes time. Skills prevent this." |

(完整 12 行)。这张表是为了**预防 agent 给自己找理由跳过 skill**——LLM 的"听上去合理"特性是这套强制系统主要要对抗的对手。

### 5.4 HARD-GATE 标签

部分 skill(如 `brainstorming`)在文档里直接打上 `<HARD-GATE>` 标签,行为表现为"必须用户显式 approve 才能继续",例如 brainstorming 里:

> "Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it."
> —— `skills/brainstorming/SKILL.md`

### 5.5 仓库本身的"PR 强制门"

`CLAUDE.md` 既给 agent 用,也给**贡献者**用。文档里直接威胁性地写:

> "PRs that show no evidence of human involvement will be closed. A human must review the complete proposed diff before submission."
> —— `CLAUDE.md`

并自报家门:**当前 94% 的 PR 拒收率**,内部把 agent 不假思索提的 PR 称为 "slop that's made of lies"。这是少见的"对自家工具用户也设置门槛"的做法。

## 6. 结构特点

打开任何一个 skill,你会看到这些**反复出现**的结构元素:

- **YAML frontmatter**(name + description),非常精简,无版本号、无 author 字段
- **流程图**用 Graphviz dot 写在 markdown 里(`brainstorming`、`tdd`、`using-superpowers` 都有),让 agent 把"决策树"显式跑一遍
- **Checklist 化任务**(用 TodoWrite 强制每步建 todo)
- **Anti-Pattern / Red Flags 表**(把 agent 容易跳的坑预先列出来)
- **References 子文件**(平台差异、prompt 模板、压力测试样本被切到独立文件,避免 SKILL.md 主体太长)
  - 例如 `using-superpowers/references/copilot-tools.md`、`brainstorming/visual-companion.md`、`subagent-driven-development/implementer-prompt.md`

## 7. 跨平台与分发

8 个 harness 各有一套 plugin manifest:

```
.claude-plugin/plugin.json           ← Claude Code
.claude-plugin/marketplace.json      ← Claude Code 市场元数据
.codex-plugin/plugin.json            ← OpenAI Codex
.cursor-plugin/plugin.json           ← Cursor
.opencode/INSTALL.md + plugins/      ← OpenCode
gemini-extension.json                ← Gemini CLI
```

**版本号同步靠 `.version-bump.json`**——一处定义,通过 `scripts/bump-version.sh` 一次性改 6 个文件。`scripts/sync-to-codex-plugin.sh`(15KB)负责把 superpowers 镜像同步到 OpenAI 官方 Codex 插件市场。

`RELEASE-NOTES.md` 1180 行,极详细,带每个平台的迁移说明。

`AGENTS.md` 是 `CLAUDE.md` 的 **symlink**,通过文件系统层确保给 Claude 和给其他 harness 的 agent 系统提示词永远一致。

## 8. 三个代表性 skill 拆解

### 8.1 `brainstorming/SKILL.md`(164 行 + 子文件)

**核心模式**:Socratic 提问。

- 一个 message 只问一个问题
- 偏好选择题(2-4 个 option)而不是开放题
- 必须先 explore 项目状态,再提问
- 提案阶段必须给出 2-3 个方案 + tradeoff
- 每个 section 提交一段后等用户确认
- 最后写 design doc,跑一遍"placeholder / 内部一致性 / 范围 / 歧义"4 项自检
- 终态唯一是调用 `writing-plans`(**禁止**直接跳到 `frontend-design` 等实现 skill)

**HARD-GATE**:用户没批 design 之前不准动手。

### 8.2 `test-driven-development/SKILL.md`(371 行)

中心思想:

> "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST."
> —— `skills/test-driven-development/SKILL.md`

强制 RED-GREEN-REFACTOR 三段循环。文档里反复点名几种"伪 TDD"——比如先写所有 test 再写实现(违反"小步走")、用 mock 替代真实依赖(掩盖集成问题)、async 测试里堆复杂度。

### 8.3 `using-superpowers/SKILL.md`(117 行 + references/)

整套系统的"宪法":

- 定义优先级:**用户指令 > Superpowers skill > 默认 system prompt**(罕见地承认"用户可以推翻 skill")
- 给出每个 harness 上"怎么调 skill"的 mapping(`Skill` 工具 in CC、`skill` 工具 in Copilot、`activate_skill` in Gemini)
- 12 行 Red Flags 反合理化表
- skill 优先级排序("先 process skill,再 implementation skill")

## 9. 不足 / 风险

- **流程开销大**:连"问个简单问题"都被强制走"先 brainstorm 再 plan"——对一次性脚本/小修改是过度设计。Auto mode 才能勉强缓解。
- **强迫性 prompt**(`<EXTREMELY-IMPORTANT>`、"YOU DO NOT HAVE A CHOICE")会污染 system prompt,可能与用户自己的 CLAUDE.md 规则打架。文档承认了这个优先级问题但只能靠 agent 自觉。
- **8 个 harness 维护成本极高**:每次改一个 skill 都要在 6 个 plugin manifest 上同步版本。`bump-version.sh` 解决"改版本号",但语义层面的兼容性还是要人工。
- **94% PR 拒收率**说明当前"agent 写 skill 升级 skill"的反馈环跑不顺——agent 提的 PR 被作者大量丢弃。这本身是一个"agent 系统能否自己进化"的悲观信号。
- **小团队 / 个人**用容易,但塞进有强约束(代码规范、CI/CD)的企业项目时,1% 规则可能产生大量"绕开"的对话——agent 一直停下来问。
