# Claude Code Source Notes

这是一份面向面试复盘的 Claude Code 源码阅读指南。目标不是逐行解释代码，而是把 Claude Code 当作一个 coding agent runtime 来拆：它如何接收输入、组装 prompt/context、进入 query loop、消费 model stream、编排 tool_use、执行本地工具、回填 tool_result，并继续下一轮循环。

源码仓库固定参考：

```text
/Users/buoy/Development/gitrepo/Claude-Code-true
```

本文档仓库只写源码阅读笔记，不改动源码仓库。

## 阅读主线

新版笔记按 coding agent runtime pipeline 组织：

```text
input -> prompt/context -> query loop -> model stream -> tool_use -> tool execution -> tool_result -> next loop
```

这条线也是面试里最容易讲清楚 Claude Code 的方式：先讲闭环，再讲闭环里每个阶段的实现职责。核心章节会解释实现逻辑、状态流转和关键边界，不走逐行代码风格；需要定位源码时再配合 [13 - 源码地图](./13-source-code-map.md)。

旧版 subagent 相关笔记已经归档到 [_archive/](./_archive/)，保留作历史参考。新版章节会重新按 runtime pipeline 放置 subagent、fork、prompt cache 等内容。

## 最终导航

建议从 `00` 一直读到 `14`。前半部分建立主循环和工具执行模型，后半部分再看 session、interrupt、subagent、MCP/plugin 以及面试表达。旧版材料保留在 [_archive/](./_archive/)，需要追溯历史 subagent 笔记时再看。

- [00 - Coding Agent 总览](./00-coding-agent-big-picture.md)
- [01 - Runtime Entry](./01-runtime-entry.md)
- [02 - Query Loop](./02-query-loop.md)
- [03 - Prompt 与 Context 组装](./03-prompt-and-context-assembly.md)
- [04 - Model Streaming](./04-model-streaming.md)
- [05 - Tool System 与 Orchestration](./05-tool-system-and-orchestration.md)
- [06 - Permission 与 Sandbox](./06-permission-and-sandbox.md)
- [07 - Shell 与 File Editing](./07-shell-and-file-editing.md)
- [08 - Session History / Compaction / Resume](./08-session-history-compaction-resume.md)
- [09 - Interrupt / Abort / Continue](./09-interrupt-abort-continue.md)
- [10 - Subagent Runtime](./10-subagent-runtime.md)
- [11 - Fork Subagent 与 Prompt Cache](./11-fork-subagent-and-prompt-cache.md)
- [12 - MCP / Plugin / Bridge 附录](./12-mcp-plugin-bridge-appendix.md)
- [13 - 源码地图](./13-source-code-map.md)
- [14 - 面试 Playbook](./14-interview-playbook.md)
- [_archive/ - 历史笔记归档](./_archive/)

## 怎么使用这组笔记

- 面试前先读 `00`，形成一句话大图：Claude Code 是围绕 model、tools、state 运转的闭环 runtime。
- 需要讲执行链路时，按 `01` 到 `07` 串起来：入口、上下文、query、stream、tool、permission、shell/file effect。
- 需要讲长期会话能力时，看 `08` 到 `11`：transcript、compaction、resume、interrupt、subagent、fork。
- 需要找源码锚点时，打开 [13 - 源码地图](./13-source-code-map.md)，先定位文件，再回到对应章节理解实现逻辑。
- 需要准备面试表达时，用 [14 - 面试 Playbook](./14-interview-playbook.md) 把概念压缩成可讲的回答模板。
- 需要追溯旧版材料时，看 [_archive/](./_archive/)，但主阅读顺序以上面 `00` 到 `14` 为准。
