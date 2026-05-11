# Agent-skills 深挖 (addyosmani/agent-skills)

> 三个仓库里**最像"标准产品"**的那一个。它把整个 SDLC 的 6 个阶段直接做成 7 个 slash command,加 22 个 skill 加 3 个 subagent,边界最清晰、最适合团队/企业落地。
> 仓库:<https://github.com/addyosmani/agent-skills>(本报告依据本地快照,主分支顶部 commit `3ff4b51`)

## 1. 速览

| 项 | 值 |
|---|---|
| 作者 | Addy Osmani(Google Chrome DevRel,前端工程领域作者) |
| 当前 commit | `3ff4b51` "Merge pull request #159 from MiladZarour/codex/readme-skill-count-158" |
| 许可 | 见 `LICENSE` |
| skill 数 | **22**(按 SDLC 6 阶段分组 + 1 个 meta skill) |
| slash command 数 | **7**(`/spec /plan /build /test /review /code-simplify /ship`) |
| subagent 数 | **3**(`code-reviewer`、`security-auditor`、`test-engineer`) |
| 总 markdown 行数(skills/) | ~6,216 |
| references 行数 | ~1,053(5 份 checklist) |
| 支持 harness 数 | 8+(Claude Code / Cursor / Gemini CLI / Windsurf / OpenCode / Copilot / Kiro / 通用 Markdown) |
| 是否带 hooks | 有(SessionStart + 业务相关的 simplify-ignore / sdd-cache) |

## 2. 6 阶段 SDLC 模型

`README.md` 用一张 ASCII 图把整个仓库的"骨架"画出来了,这张图本身就是仓库的核心承诺:

```
  DEFINE          PLAN           BUILD          VERIFY         REVIEW          SHIP
 ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐
 │ Idea │ ───▶ │ Spec │ ───▶ │ Code │ ───▶ │ Test │ ───▶ │  QA  │ ───▶ │  Go  │
 │Refine│      │  PRD │      │ Impl │      │Debug │      │ Gate │      │ Live │
 └──────┘      └──────┘      └──────┘      └──────┘      └──────┘      └──────┘
  /spec          /plan          /build        /test         /review       /ship
```

`README.md` 的 mission statement:

> "Production-grade engineering skills for AI coding agents."
> —— `README.md`

> "Skills encode the workflows, quality gates, and best practices that senior engineers use when building software. These ones are packaged so AI agents follow them consistently across every phase of development."
> —— `README.md`

**这张图不是装饰**——22 个 skill 严格按 6 阶段分组、7 个 slash command 一对一覆盖关键阶段、`AGENTS.md` 里给出了"intent → skill → 阶段"的强制 mapping。是真"wired-in",不是 PPT 美工。

各阶段 skill 数:DEFINE 2 / PLAN 1 / BUILD 7 / VERIFY 2 / REVIEW 4 / SHIP 5 + Meta 1 = 22。

## 3. Slash Commands 详解

7 个命令分别定义在 `.claude/commands/*.md`(以及 `.gemini/commands/*.toml`),每个都直接调起对应 skill 流程。

| 命令 | 调起的 skill | 中文一句话 |
|---|---|---|
| `/spec` | spec-driven-development | 写 spec.md;问清 objective / tech stack / commands / project structure / code style / testing / boundaries 7 块 |
| `/plan` | planning-and-task-breakdown | 读 spec → 画依赖图 → vertical slice → 写带验收标准的 task 清单 → 落到 `tasks/plan.md` |
| `/build` | incremental-implementation + test-driven-development | 取下一个 pending task → RED 写失败 test → GREEN 实现 → run test → run build → commit → 标 done |
| `/test` | test-driven-development | 新 feature: 写 test → 实现;**修 bug:用 Prove-It pattern 先写出"复现 bug 的 test",再修** |
| `/review` | code-review-and-quality | 五维 review(correctness / readability / architecture / security / performance),输出按 Critical/Important/Suggestion 分级 |
| `/code-simplify` | code-simplification | 简化最近改动而不改行为(展开嵌套、拆长函数、消三元嵌套);每步都跑 test |
| `/ship` | shipping-and-launch | **并行 fan-out**:同时派 code-reviewer / security-auditor / test-engineer 三个 subagent,主 agent 合并出 go/no-go + rollback plan |

`/ship` 是这套系统**最有特色**的一个——它不是"再走一遍 review",而是把三种角色当独立 reviewer **并发**跑(独立 context 防止串味),最后由主 agent 合并。

## 4. Skill 清单(全 22 个,按阶段分组)

### DEFINE(2)

| Skill | description(原文摘要) |
|---|---|
| `idea-refine` | "Refines ideas through structured divergent and convergent thinking. Use when you have a rough concept that needs exploration." |
| `spec-driven-development` | "Creates specs before coding. Use when starting a new project, feature, or significant change and no specification exists yet." |

### PLAN(1)

| Skill | description |
|---|---|
| `planning-and-task-breakdown` | "Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks." |

### BUILD(7,本仓最厚的一档)

| Skill | description |
|---|---|
| `incremental-implementation` | "Delivers changes incrementally. Use when implementing any feature or change that touches more than one file." |
| `test-driven-development` | "Drives development with tests. Use when implementing any logic, fixing any bug, or changing any behavior." |
| `context-engineering` | "Optimizes agent context setup. Use when starting a new session, when agent output quality degrades, when switching between tasks." |
| `source-driven-development` | "Grounds every implementation decision in official documentation. Use when you want authoritative, source-cited code." |
| `doubt-driven-development` | "Subjects every non-trivial decision to fresh-context adversarial review. Use when correctness matters more than speed..." |
| `frontend-ui-engineering` | "Builds production-quality UIs. Use when building or modifying user-facing interfaces." |
| `api-and-interface-design` | "Guides stable API and interface design. Use when designing APIs, module boundaries, or any public interface." |

### VERIFY(2)

| Skill | description |
|---|---|
| `browser-testing-with-devtools` | "Tests in real browsers. Use when building or debugging anything that runs in a browser." |
| `debugging-and-error-recovery` | "Guides systematic root-cause debugging. Use when tests fail, builds break, behavior doesn't match expectations." |

### REVIEW(4)

| Skill | description |
|---|---|
| `code-review-and-quality` | "Conducts multi-axis code review. Use before merging any change." |
| `code-simplification` | "Simplifies code for clarity. Use when refactoring code for clarity without changing behavior." |
| `security-and-hardening` | "Hardens code against vulnerabilities. Use when handling user input, authentication, data storage, or external integrations." |
| `performance-optimization` | "Optimizes application performance. Use when performance requirements exist or when you suspect performance regressions." |

### SHIP(5)

| Skill | description |
|---|---|
| `git-workflow-and-versioning` | "Structures git workflow practices. Use when making any code change." |
| `ci-cd-and-automation` | "Automates CI/CD pipeline setup. Use when setting up or modifying build and deployment pipelines." |
| `deprecation-and-migration` | "Manages deprecation and migration. Use when removing old systems, APIs, or features." |
| `documentation-and-adrs` | "Records decisions and documentation. Use when making architectural decisions, changing public APIs, shipping features." |
| `shipping-and-launch` | "Prepares production launches. Use when preparing to deploy to production." |

### Meta(1)

| Skill | description |
|---|---|
| `using-agent-skills` | "Discovers and invokes agent skills. Use when starting a session or when you need to discover which skill applies." |

## 5. 三个 Subagents

存在于 `agents/` 目录,每个都是一份独立 markdown,带自己的 frontmatter 和角色 system prompt。被 `/ship` 命令并行调用。

### 5.1 `code-reviewer.md`(97 行)

> "Senior code reviewer that evaluates changes across five dimensions — correctness, readability, architecture, security, and performance. Use for thorough code review before merge."
> —— `agents/code-reviewer.md`(frontmatter)

扮演 Staff Engineer。固定五维:
1. Correctness — 跟 spec 一致吗?边界处理了吗?test 够吗?
2. Readability — 别人看得懂吗?命名是否描述性?
3. Architecture — 跟现有模式一致吗?边界清吗?抽象层级对吗?
4. Security — 输入校验?secrets 安全?auth 校验?
5. Performance — N+1 查询?无界操作?不必要的 re-render?

输出按 Critical / Important / Suggestion 三档分级,带 `file:line` 引用。

### 5.2 `security-auditor.md`(101 行)

> "Security engineer focused on vulnerability detection, threat modeling, and secure coding practices."
> —— `agents/security-auditor.md`(frontmatter)

扮演 Security Engineer。审 5 个面向:
1. Input Handling(注入向量、HTML 编码、文件上传、URL 重定向)
2. Authentication & Authorization(密码哈希算法、session cookie 属性、IDOR、rate limit)
3. Data Protection(secret 管理、PII、加密、敏感字段)
4. Infrastructure(CSP/HSTS、CORS、依赖 CVE、错误信息泛化、最小权限)
5. Third-Party Integrations(API key 存储、webhook 校验、SRI、OAuth PKCE+state)

### 5.3 `test-engineer.md`(95 行)

> "QA engineer specialized in test strategy, test writing, and coverage analysis."
> —— `agents/test-engineer.md`(frontmatter)

扮演 QA Engineer。专注:
- 写测试**之前**先看代码(public API、边界、已有 pattern)
- test level 选择(unit / integration / e2e 各自适合什么)
- Prove-It pattern 写复现 bug 的测试
- describe/it 的描述性命名
- 覆盖 happy path / edge cases / error paths / concurrency

### 调用方式

`/ship` 命令的实现里直接 fan-out 这三个 agent(独立 context、并行执行),主 agent 合并它们的报告做 go/no-go 决策。这是 agent-skills 仓库**唯一**正式背书的"多 persona 编排模式"——`references/orchestration-patterns.md` 里把它叫 **"parallel fan-out"** 并明确**禁止**"meta-orchestrator router"模式(persona 之间互相调用 → 角色串味)。

## 6. 触发与强制

### 混合模型

`README.md` 里这句很关键:

> "Skills also activate automatically based on what you're doing — designing an API triggers `api-and-interface-design`, building UI triggers `frontend-ui-engineering`, and so on."
> —— `README.md`

也就是说触发是 **3 通道并存**:
1. **手动**:7 个 slash command(用户主动打)
2. **自动 / intent-mapping**:agent 根据"任务意图"匹配 description 里的关键词(designing API → api-and-interface-design)
3. **元 skill 强制**:`using-agent-skills` 在 session 开始时帮 agent 把任务映射到对应 skill

### 与 Superpowers 的"1% 规则"对比

`AGENTS.md` 里同样有"even 1% chance"的措辞:

> "Determine if any skill applies (even 1% chance)."
> —— `AGENTS.md`

但和 Superpowers 不一样——agent-skills **把这个判断做成了可机械执行的 intent → skill mapping 表**,不是 LLM 概率猜。换句话说:Superpowers 的 1% 规则是"靠 agent 自己反思",agent-skills 的"1% 规则"更接近"靠模式匹配兜底"——前者像道德规则,后者像查表。

### `using-agent-skills` 元 skill

类似 Superpowers 的 `using-superpowers`,但不那么激进:

> "Maps incoming work to the right skill workflow and defines shared operating rules."
> —— `skills/using-agent-skills/SKILL.md`

它是**调度器**,Superpowers 那个是**宪法**。前者偏功能,后者偏纪律。

## 7. 特色组件

### 7.1 hooks/(7 个文件)

| 文件 | 作用 |
|---|---|
| `hooks.json` | hook 注册清单 |
| `session-start.sh` | session 开场注入 context |
| `session-start-test.sh` | 上面那个的测试脚本 |
| `simplify-ignore.sh` | `/code-simplify` 的 Pre/Post 工具 hook —— 把代码里 `/* simplify-ignore-start */` 标记的块**遮罩**成 `BLOCK_<hash>`,模型看不到,简化完再还原。**保护手工调优的代码不被"简化"掉**。 |
| `simplify-ignore-test.sh` | 测试 |
| `SIMPLIFY-IGNORE.md` | 文档:注解语法、崩溃恢复、已知限制 |
| `sdd-cache-pre.sh` / `sdd-cache-post.sh` / `SDD-CACHE.md` | 给 `source-driven-development` 用的 **HTTP 缓存层** —— Pre 阶段查本地 cache(带 `If-None-Match` / `If-Modified-Since`),命中 304 就直接返回缓存内容并阻止 WebFetch;Post 阶段把新抓到的内容存入 cache(带 ETag/Last-Modified)。**没有 TTL,新鲜度交给 origin 服务器** |

这两个 hook 都是**业务相关的真功能**,不是单纯的 lifecycle 触发器——这是 agent-skills 仓库工程化最深的部分。

### 7.2 references/(5 份 checklist,共 1,053 行)

| 文件 | 行数 | 内容 |
|---|---|---|
| `testing-patterns.md` | 236 | 测试结构、命名、mock、React/API/E2E 例子、anti-pattern |
| `security-checklist.md` | 134 | pre-commit 检查、auth、输入校验、headers、CORS、OWASP Top 10 |
| `performance-checklist.md` | 153 | Core Web Vitals 目标、前后端 checklist、测量命令 |
| `accessibility-checklist.md` | 160 | 键盘导航、screen reader、ARIA、测试工具 |
| `orchestration-patterns.md` | 370 | persona 组合规则、合法模式(parallel fan-out)、违规模式(meta-orchestrator router)、Claude Code 互操作、Agent Teams |

`references/` 这种**外部 checklist** 是 superpowers / mattpocock 都没有的设计——把"agent 可能需要查的固定知识"和"workflow"分离。skill 文件保持薄,具体清单沉到 references/。

### 7.3 docs/(8 份 setup 指南)

`cursor-setup.md` / `gemini-cli-setup.md` / `windsurf-setup.md` / `opencode-setup.md` / `copilot-setup.md` / `kiro-setup.md` / `getting-started.md` / `skill-anatomy.md`(后者是给贡献者写新 skill 用的格式规范)。这是仓库**多平台支持**的真实承载——8 个 harness 不是嘴上说说,每个都有独立文档。

### 7.4 CLAUDE.md vs AGENTS.md(职责分工)

| | CLAUDE.md | AGENTS.md |
|---|---|---|
| 受众 | Claude Code 用户、贡献者 | OpenCode 用户、跨工具编排者 |
| 内容 | 项目总览、skill 阶段分组、命名规范、贡献者指南 | agent 执行模型、intent → skill 映射、编排规则、persona 组合约束 |
| 关键规则 | "每个 skill 在 `skills/<name>/SKILL.md`" | "如果任务匹配 skill,你**必须**调用(even 1% chance)"、"persona 不能调用其他 persona" |
| 范畴 | 单工具集成 | 跨工具抽象层 |

**两份文件不是镜像,而是分工**。这点和 Superpowers(`AGENTS.md` 是 `CLAUDE.md` 的 symlink)思路完全相反——Superpowers 用 symlink 保证"对所有 harness 一份相同的指令";agent-skills 是"对不同 harness 给不同侧重的指令"。

## 8. 三个代表性 skill 拆解

### 8.1 `spec-driven-development/SKILL.md`(200 行)

frontmatter:
```yaml
name: spec-driven-development
description: Creates specs before coding. Use when starting a new project, feature, or significant change and no specification exists yet. Use when requirements are unclear, ambiguous, or only exist as a vague idea.
```

强制 4 阶段:**SPECIFY → PLAN → TASKS → IMPLEMENT**,每阶段必须人审才能进入下一阶段。spec 模板固定 7 块(Objective / Tech Stack / Commands / Project Structure / Code Style / Testing Strategy / Boundaries)。

特色:**"Common Rationalizations" 表**——把 agent 常见的偷懒理由列出来反驳:
- "I'll write the spec after I code it" → 那是文档,不是 spec
- "This is simple, I don't need a spec" → 简单任务也得有验收标准

### 8.2 `doubt-driven-development/SKILL.md`(243 行,本仓独有的"招牌"skill)

frontmatter:
```yaml
name: doubt-driven-development
description: Subjects every non-trivial decision to a fresh-context adversarial review before it stands. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high...
```

非常有意思的设计:**对每个非平凡决策做一次"反向论证"**。流程是 5 步循环:

```
CLAIM → EXTRACT → DOUBT → RECONCILE → STOP
```

具体做法:fork 出一个**新 context** 的 reviewer(避免被原 agent 的"已经想清楚"污染),给它一个**对抗式 prompt**——目标是找问题而不是确认。最多跑 3 个循环,findings 全是噪声就停。

特色禁令:
- "persona 不能调 persona"(防角色串味)
- 跨模型升级判断:发现是 model-specific 错误时,主动问用户"要不要换个模型再审一次"
- **Red Flag:"doubt theater"** —— 跑了流程但 0 个 finding 被分类为可执行 → 你是在演戏,不是在质疑

这是 superpowers / mattpocock 都没有的"质量护栏"模式。

### 8.3 `test-driven-development/SKILL.md`(383 行,**本仓最厚**)

中心是**Prove-It Pattern**:bug 修复必须先写一个"复现 bug 的失败 test"。还教了:
- 测试金字塔(80% unit / 15% integration / 5% e2e)
- 测试规模(Small / Medium / Large 按资源约束分)
- DAMP over DRY(测试里描述性短语 > 共用 helper)
- 用 real implementation 优先于 mock
- AAA(Arrange-Act-Assert)
- 一堆 anti-pattern(测实现细节、flaky test、snapshot 滥用、过度 mock)及修法

浏览器测试**单独抽到** `browser-testing-with-devtools` —— 这是 agent-skills 的"边界感":每个 skill 范围窄、互不重叠。

## 9. 跨平台支持矩阵

`README.md` 给出 8 种安装路径:

| 平台 | 安装方式 |
|---|---|
| **Claude Code**(推荐) | `/plugin marketplace add addyosmani/agent-skills` + `/plugin install agent-skills@addy-agent-skills`,或 `claude --plugin-dir` 本地装 |
| **Cursor** | 复制 SKILL.md 到 `.cursor/rules/` 或引用整个 `skills/` 目录(`docs/cursor-setup.md`) |
| **Gemini CLI** | `gemini skills install https://github.com/addyosmani/agent-skills.git --path skills`,或加进 `GEMINI.md`(`docs/gemini-cli-setup.md`) |
| **Windsurf** | 加进 Windsurf rules 配置(`docs/windsurf-setup.md`) |
| **OpenCode** | 通过 `AGENTS.md` + `skill` 工具(`docs/opencode-setup.md`) |
| **GitHub Copilot** | agent 文件作为 Copilot persona,skill 内容放 `.github/copilot-instructions.md`(`docs/copilot-setup.md`) |
| **Kiro IDE / CLI** | 放 `.kiro/skills/`,带 Project / Global scope(`docs/kiro-setup.md`) |
| **Codex / 其他** | 纯 markdown 格式,任何接受 system prompt 的 agent 都能用 |

文件层面对应:
- `.claude-plugin/marketplace.json`(Claude)
- `.claude/commands/*.md`(Claude slash command)
- `.gemini/commands/*.toml`(Gemini)
- `.opencode/skills` → `../skills/`(OpenCode 用 symlink)

## 10. 不足 / 风险

- **6 阶段 SDLC 模型对小任务过重** —— 跑一个 30 行的 utility 脚本也得过 spec → plan → build → test → review → ship?显然不合适。文档没有"逃生通道"指引(你可以跳过 spec 直接 build,但 skill 里没明说)
- **22 个 skill 描述近似** —— `incremental-implementation` 和 `test-driven-development` 在 `/build` 流程里同时被调,边界容易模糊;agent 可能两个都"觉得有 1% 适用"
- **references/ checklist 维护成本** —— security/perf/a11y checklist 的有效期受技术栈/CVE 影响,没有版本号、没有 last-reviewed 日期,容易腐烂
- **`/ship` 的 fan-out 假设了 token 预算** —— 三个 subagent 并行跑,每个独立 context,token 成本 3x;小项目用着也许过头
- **多平台 → 测试矩阵爆炸** —— 8 个 harness 各有自己的边角行为,没看到 CI 矩阵(superpowers 有 `tests/` 多平台测试集)
- **元 skill `using-agent-skills` 比 superpowers 同位 skill 弱** —— 没有"1% rule"那种 prompt 强度,intent mapping 表也是 description 关键词匹配,真有歧义时 agent 会迷茫

## 总结一句话

**把"高级工程师该有的纪律"做成可执行的 SDLC pipeline**,工程边界最清晰、平台覆盖最广、组件最齐全(skill + slash + agent + hook + references + 多平台 docs);代价是更重的学习曲线和更多的运行成本。
