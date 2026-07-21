# Claude Code 机制学习轨道

这是一条面向面试的机制学习轨道。它要教会你的不是“记住 Claude Code 有哪些文件”，而是用一套稳定模型解释：一个 coding agent 如何组织模型可见信息、接收模型意图、控制机器效果、记录观察，并据此继续一个任务。

当前入口是 [00：一次完整的 Agent Turn](00-one-agent-turn.md)。读完它，应该能先画出完整闭环，再把后续源码证据放回正确节点。

## 刻意排除什么

- 这不是覆盖所有命令、UI、Plugin、Bridge 和完整 agent 产品面的 Claude Code 百科全书。
- 这不是“从零做一个 agent”的实现教程，也不以复制产品为目标。
- 这不是逐行源码导览。源码只在机制结论需要证据时出现，不能代替因果解释。
- 适配器、集成方式和历史实现变体不进入主阅读路径；它们只能在核心机制成立后作为附录或历史材料阅读。

## 一句话主线

> 一次 agent turn 如何把用户意图转换成安全的机器操作，再把观察结果写回状态，让模型继续决策；当任务跨越时间或需要委派时，同一套机制如何扩展。

## A1–A8：全轨道共用的导航坐标

下列 ID 是后续章节共用的稳定坐标；[00](00-one-agent-turn.md) 拥有权威完整流程图。

| ID | 稳定节点 | 它回答的问题 |
| --- | --- | --- |
| A1 | User Task | 用户意图和约束怎样进入 turn？ |
| A2 | Model View Assembly | runtime 怎样组装本次模型真正可见的世界？ |
| A3 | Model Request and Stream | 请求怎样发出，模型输出怎样流回？ |
| A4 | Runtime Decision | runtime 怎样区分文本完成与工具意图？ |
| A5 | Tool Intent | 模型提出的结构化机器操作是什么？ |
| A6 | Controlled Machine Effect | 意图怎样经过控制后产生真实效果？ |
| A7 | Tool Observation and State Update | 结果怎样关联原意图并写回状态？ |
| A8 | Continue, Stop, Recover, or Delegate | 系统怎样继续、结束、恢复或委派？ |

## 三种阅读模式

### 总览路径

本页 README → [00：一次完整的 Agent Turn](00-one-agent-turn.md) → 各部分 README（建立后）→ 99 Interview Playbook（建立后）。适合先获得全局认知，再决定往哪里放大。

### 完整学习路径

从本页开始，按编号读取每一个文件：00 → 第一至第四部分的 README 与细节文章 → 99 Interview Playbook。编号就是因果顺序，不先跳到源码变体。

### 面试复习路径

[00：一次完整的 Agent Turn](00-one-agent-turn.md) → 各章末尾的面试回答（建立后）→ 99 Interview Playbook（建立后）；回答卡住时，再回到相应 A1–A8 节点。

## 四部分学习路线图

以下是后续建设路线，目前只是文字路标，不是链接：

1. `01-model-turn/`：模型如何获得世界并持续决策，放大 A2–A4。
2. `02-controlled-effects/`：工具意图如何变成受控机器效果，放大 A5–A7。
3. `03-session-continuity/`：任务如何跨中断、压缩和恢复继续，放大 A7–A8 的时间维度。
4. `04-subagent-delegation/`：父循环如何通过显式边界委派给子循环，放大 A8 的委派扩展。

四部分完成后，`99-interview-playbook.md` 才把机制压缩成 30 秒结论、白板流程和深入追问入口。

## 源码快照与证据标签

- 本轨道的源码快照固定为 `712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf`；版本变化不能悄悄改写既有结论。
- 每条 `Source-confirmed` 证据统一写成 `snapshot commit + repository-relative path + symbol`；三项必须出现在同一证据记录中，行号只能辅助定位，不能替代 symbol 或机制解释。
- 当结论性质可能混淆时，使用三类标签：`Source-confirmed` 表示快照直接支持，`Architectural interpretation` 表示由多处行为归纳，`General principle` 表示不依赖 Claude Code 实现的通用约束。

## 如何使用代码摘录与图

先陈述机制、不变量和状态边界，再给最小代码摘录。摘录只证明当前结论，并附 `snapshot commit + repository-relative path + symbol`；它不展开无关分支，也不把文章重新变成源码地图。

核心图优先使用可编辑的 Mermaid、Markdown 表格和文本图。图后必须有文字解释，且术语要与 A1–A8 一致。光栅图片不承担核心机制说明；它最多保存外部界面或历史现场。

## 历史归档

[历史归档索引](_archive/README.md) 保存旧版 source-tracing 笔记，供追溯证据和设计演变。它不是当前学习路径；遇到与本轨道冲突的组织方式，以当前 README 和 00 的稳定模型为准。
