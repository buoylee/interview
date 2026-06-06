# 01 - Subagent 后台执行与通信机制

> 这篇原本是 subagent 的总览长文。内容已经按主题拆分，旧文件保留为迁移索引，避免旧链接失效。

建议按下面顺序阅读：

| 新章节 | 说明 |
|--------|------|
| [01 - Subagent 心智模型](./01-subagent-mental-model.md) | 建立大图：subagent 不是新 runtime，而是另一个 `query()` loop |
| [02 - Subagent 后台生命周期](./02-subagent-background-lifecycle.md) | 从 `AgentTool.call()` 到后台 `runAgent()` 的完整启动链路 |
| [03 - Agent 间通信协议](./03-agent-communication-protocol.md) | 深入解释 `tool_result`、`task-notification`、`commandQueue`、`pendingMessages`、sidechain transcript |
| [04 - 取消、继续与恢复](./04-cancel-resume-and-abort.md) | ESC、kill agents、用户说“继续”、resume 的真实代码路径 |
| [05 - Fork Subagent 与 Prompt Cache](./05-fork-subagent-prompt-cache.md) | fork subagent 如何最大化 prompt cache 命中 |

一句话总结：

```text
Claude Code 的 local subagent 不是独立 agent server，而是同一 Node 进程里的后台 query() 协程。
它和主 agent 的通信不是 RPC，而是由 runtime 通过 tool_result、task-notification、pendingMessages、sidechain transcript 这些通道中介完成。
```
