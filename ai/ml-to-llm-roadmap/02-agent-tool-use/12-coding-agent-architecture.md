# Coding Agent 架构

## 这篇解决什么问题

前面已经讲过 Agent runtime、multi-agent 协作和 Agent eval。Coding agent 是这些能力在代码仓库里的落地形态：它不是“会写代码的聊天机器人”，而是 repo-aware、tool-using、test-driven 的工程执行者。

这篇解决的问题是：Cursor / Codex / Claude Code 这类 coding agent 大概怎么工作，为什么它必须先读 repo、选择文件、生成 patch、跑检查、做 review，并且保护用户正在修改的代码和 repo history。

## 学前检查

读这篇前，建议先理解：

- Agent runtime 如何控制循环、工具、状态和 trace：[Agent Runtime 工程](./06-agent-runtime-engineering.md)
- 多执行者如何分工、交接和裁决：[Multi-Agent 协作机制](./09-multi-agent-coordination.md)
- Agent eval 为什么要看 trajectory、tool-call 和 recovery：[Agent Eval 实战](./11-agent-eval-practice.md)

如果还不熟，可以先记住一句话：coding agent 的核心不是“生成代码”，而是“在真实 repo 约束下，用工具安全地修改代码并验证结果”。

## 概念为什么出现

普通聊天模型可以回答“这段代码怎么写”。但真实开发任务通常不是从空白文件开始，而是在一个已经有历史、约定、测试、未提交改动和多人协作的 repo 里发生。

直接让模型写一段代码会遇到几个问题：

- 缺 repo context：不知道项目结构、命名约定、依赖、测试方式和已有 helper。
- 缺 file selection：看不到相关文件，容易改错层次、重复实现或漏掉调用点。
- 缺 patch discipline：整文件重写会制造无关 diff，甚至覆盖用户改动。
- 缺 test loop：一次生成无法证明代码能构建、测试通过或修复了真实失败。
- 缺 review loop：模型可能满足表面需求，但留下边界条件、回归风险或风格问题。
- 缺 sandbox/permission：执行命令、访问网络、写文件和提交代码都需要明确边界。
- 缺 user-change protection：多人同时改 repo 时，agent 不能把不属于自己的 dirty changes 当成可覆盖对象。

Coding agent 出现，是因为软件工程任务需要一个“代码仓库里的受控执行循环”，而不是一个孤立的文本生成器。

## 最小心智模型

最小 coding agent loop 是：

```text
task -> inspect repo -> plan edits -> select files -> generate patch -> apply patch -> run checks -> debug/revise -> review -> commit/report
```

这个 loop 可以拆成这些组件：

| component | responsibility | failure mode |
|-----------|----------------|--------------|
| repo context/indexing | 建立 repo 结构、语言、依赖、入口、测试和最近改动的上下文 | 不理解项目边界，重复造轮子或改错模块 |
| file selection | 选择本次任务真正相关的文件、测试和配置 | 上下文太少会漏改，上下文太多会分散注意力 |
| planner | 把任务拆成可验证的编辑步骤、风险点和检查命令 | 直接开改导致需求漏项、顺序错误或改动扩散 |
| patch writer | 生成最小 diff，保留周边代码风格和用户已有内容 | 整文件重写、格式 churn、覆盖用户改动 |
| tool runner | 运行 `rg`、构建、测试、格式化、git 等工具并读取结果 | 只凭模型猜测，不知道真实失败和环境约束 |
| test loop | 根据检查失败定位原因、修正代码、重新运行验证 | 测试失败后盲目重试，或把失败当成“模型不行” |
| review loop | 用代码审查视角检查 bug、回归、边界、遗漏测试和无关 diff | 功能看似完成，但隐藏行为风险或维护成本 |
| compaction | 在长任务里压缩上下文，保留目标、决策、文件、失败和下一步 | 压缩后丢关键约束，后续修改偏离任务 |
| subagent delegation | 把独立调查、测试分析或审查交给受限 specialist | 子任务共享状态不清，结果冲突或越权修改 |
| sandbox/permission | 控制文件写入、命令执行、网络、敏感路径和提交动作 | 命令副作用过大，越权写入或泄露敏感信息 |

和普通 Agent 一样，模型负责提出下一步；coding agent runtime 负责给它 repo context、执行工具、应用 patch、收集 test loop 结果，并决定何时需要用户授权、review 或停止。

## 客服退款/工单 Agent 案例

运行案例还是客服退款/工单 Agent，但这里要对比 business-action agent 和 coding agent 的差异。

业务动作 Agent 处理的是用户业务状态。例如退款 Agent 会读取订单、查询支付、创建工单、发起审批或通知用户。它 mutate 的是业务系统：订单、退款、工单、通知、审批状态。核心风险是越权读取、重复写入、绕过审批、错误承诺和状态不一致。

Coding agent 处理的是源码仓库状态。例如用户说“修复退款工单创建超时后重复提交的问题”，coding agent 应该：

```text
inspect repo: 找到 ticket/refund/idempotency 相关代码和测试
plan edits: 确认需要补幂等键、超时分类和回归测试
select files: 只选择相关 service、runtime/test 文件
generate patch: 用最小 diff 修改逻辑和测试
apply patch: 避免整文件覆盖，保留用户未提交改动
run checks: 跑目标测试、必要时跑更大范围测试
debug/revise: 根据真实失败修补实现或测试
review: 检查重复写、错误重试、日志脱敏和无关 diff
commit/report: 只提交本任务文件，报告验证证据
```

也就是说，退款 Agent 直接改变业务系统；coding agent 改变 source code。它必须保护三类东西：用户 edits、tests 和 repo history。覆盖用户改动、跳过测试或把 unrelated dirty files 一起提交，都是 coding agent 的生产事故。

## 工程控制点

- repo indexing：先建立项目索引，包括目录结构、语言栈、包管理器、测试入口、关键配置、README、已有约定和最近相关提交；不要把整个 repo 无差别塞进上下文。
- file selection：用 `rg`、文件树、引用关系、测试名和错误栈选择相关文件；优先读小而关键的上下文，再按证据扩展。
- planning：写清要改什么、不改什么、验证什么、风险在哪里；计划应该能映射到具体文件和检查命令。
- patch generation：生成局部 patch，保持现有风格、命名、导入顺序和格式；避免把无关格式化混进功能改动。
- apply patch：通过 patch 工具应用改动，让 diff 可审查、可回滚、可定位；不要用整文件覆盖来省事。
- test loop：先运行最能证明任务的检查，再根据失败信息 debug/revise；必要时扩大到相关单测、集成测试、lint 或 build。
- code review loop：完成后从审查者视角看 diff：有没有行为回归、边界遗漏、测试缺口、权限问题、并发问题、无关变更。
- context compaction：长任务压缩上下文时保留目标、用户约束、已读文件、已改文件、失败输出、验证命令、未解决问题和禁止事项。
- subagent delegation：只有当子任务独立、输入输出清楚、不会同时写同一文件时才拆；常见用途是并行调查、测试失败归因和独立 review。
- sandbox/permission：读写文件、执行命令、网络访问、安装依赖、删除文件和提交都要受 sandbox 与 permission 控制；高副作用命令要请求授权。
- avoiding overwrite of user changes：编辑前后检查 git status/diff，只修改指定文件；如果目标文件已有他人改动，要基于当前内容增量修改，不能恢复、重置或覆盖。
- commit hygiene：验证通过后只 `git add` 本任务文件，用清晰 commit message；不要把 `.obsidian/`、临时文件、unrelated dirty changes 或生成缓存带进提交。

这些控制点把 coding agent 从“能生成代码”升级成“能在协作 repo 中可靠交付改动”。

## 和应用/面试的连接

Cursor / Codex / Claude Code 这类 coding agent 大概怎么工作？

可以回答：它们先读取 repo context，利用搜索、文件读取、shell、patch、测试和 git 等工具形成一个受控 loop。模型根据任务和上下文规划修改，runtime 负责选择文件、执行工具、应用 patch、运行 checks、把失败 observation 喂回模型，并在 review 和 permission 边界内提交或报告结果。

Coding agent 为什么要读代码而不是直接改？

因为代码修改依赖局部上下文和项目约定。它要知道已有抽象、调用点、测试方式、类型约束、错误处理、风格和边界条件。直接改往往只满足题面，不满足 repo 的真实结构，容易重复实现、破坏 API、漏测试或引入无关 diff。

如何防止 coding agent 覆盖用户改动？

核心是把 user-change protection 做成流程约束：先看 git status，编辑前读取当前文件，使用局部 patch 而不是整文件覆盖，应用后检查 diff，只 stage 指定文件。如果目标文件存在非本任务改动，agent 要在其基础上增量修改；遇到冲突或无法区分归属时停下来询问，而不是 reset、restore 或重写。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| coding agent 只是会写代码的聊天机器人 | coding agent 是 repo-aware、tool-using、test-driven 的执行系统，重点是读 repo、改 patch、跑 checks 和保护协作状态 |
| 把整个 repo 塞进上下文最好 | 上下文越多不等于越准；更重要的是 repo indexing、file selection、引用证据和渐进读取 |
| 直接重写文件比 patch 更简单 | 重写会扩大 diff、覆盖用户改动、破坏 blame 和 review；patch discipline 才适合协作 repo |
| 测试失败说明模型不行 | 测试失败是 observation，应该进入 test loop，用失败信息定位需求理解、实现、环境或测试假设的问题 |
| subagent 越多越快 | subagent 会增加协调、上下文同步和冲突成本；只有独立、可验证、低共享状态的任务才适合拆 |

## 自测

1. repo context 应该包含哪些信息？为什么不能只把用户需求交给模型？
2. patch discipline 解决了哪些协作问题？为什么整文件覆盖风险更高？
3. test loop 中，检查失败后 agent 应该如何使用失败输出，而不是盲目重试？
4. context compaction 时至少要保留哪些信息，才能让后续步骤不偏离任务？
5. 如何设计流程来避免 coding agent 覆盖用户改动或提交无关文件？

## 回到主线

到这里，你应该能把 coding agent 理解成 Agent runtime 在代码仓库里的专门化：repo context 决定它看见什么，file selection 决定它改哪里，patch 和 test loop 决定它如何证明改动，review、sandbox、permission 和 commit hygiene 决定它能不能在多人协作里安全落地。

下一篇会把这些能力放到平台视角：如何把 runtime、tools、permissions、eval、observability 和多团队治理组合成可运营的 Agent 平台。

下一篇：[Agent Platform Case Study](./13-agent-platform-case-study.md)
