# Agent 边界与执行循环

## 这篇解决什么问题

很多人把“模型能输出 tool call”直接叫 Agent。这样会混淆两件事：Function Calling 是输出形态，Agent 是控制循环。一个系统可以有 Function Calling 但没有 Agent，也可以用固定 workflow 调工具但没有让模型决定下一步。

这一篇解决的问题是：什么时候普通 LLM 调用、结构化输出、Function Calling 或 workflow 已经够用，什么时候才需要 Agent loop。

## 学前检查

读这篇前，建议先理解：

- Function Calling 只是结构化调用意图：[Function Calling 的输出形态](../03-generation-control/03-function-calling-output-shape.md)
- AI 系统设计要先定义任务和边界：[AI 系统设计方法论](../08-system-design-project-narrative/01-ai-system-design-method.md)

如果还不熟，可以先记住一句话：Agent 不是一个工具名，而是一种“观察结果后继续决策”的执行架构。

## 概念为什么出现

单次 LLM 调用适合回答、改写、分类和生成草稿。问题变成多步执行时，系统会遇到新需求：

```text
需要查状态: 当前信息不在模型上下文里
需要行动: 系统要调用 API、创建记录或发起审批
需要观察: 上一步工具结果决定下一步做什么
需要恢复: 工具失败、权限不足或信息缺失时不能直接编造
```

Agent 出现，是为了把这些多步任务组织成一个受控循环，而不是让模型一次性猜完整流程。

## 最小心智模型

最小 Agent loop 是：

```text
goal -> state -> decide next action -> tool call -> observation -> update state -> stop or continue
```

各步职责：

- goal：用户要完成什么任务。
- state：目前已知信息、约束、工具结果和待办步骤。
- decide next action：模型或策略决定下一步是回答、追问、调用工具还是停止。
- tool call：模型输出结构化调用形态。
- observation：应用层真实执行工具后得到结果。
- update state：把观察结果写回状态。
- stop or continue：达到目标、失败终止或进入下一轮。

边界要清楚：Function Calling 只负责生成 call shape；应用层负责执行工具、处理错误、记录状态和控制循环。

## 最小例子

用户问：

```text
我订单 A123 的退款现在到哪一步了？
```

如果只是 Function Calling，模型可以输出：

```json
{"name": "get_refund_status", "arguments": {"order_id": "A123"}}
```

但 Agent loop 会多一层控制：

```text
目标: 回答退款进度
状态: order_id=A123，尚未查询
下一步: 调用 get_refund_status(A123)
观察: 状态为 pending_bank，预计 2 个工作日到账
更新状态: 已查到退款状态
停止: 给用户解释当前进度和下一步等待时间
```

如果工具返回“订单号不存在”，循环不能编造退款状态，而应该更新状态为查询失败，追问用户是否提供正确订单号。

## 原理层

几种相近概念的边界如下：

| 形态 | 解决什么 | 是否 Agent |
|------|----------|------------|
| One-shot LLM call | 一次输入到一次文本输出 | 否 |
| 结构化输出 | 输出稳定 JSON、分类或字段 | 否 |
| Function Calling | 输出工具名和参数 | 否 |
| Workflow orchestration | 应用按固定流程调用模型和工具 | 不一定 |
| Agent loop | 根据状态和观察结果动态决定下一步 | 是 |

workflow 和 Agent 的区别不在于有没有工具，而在于下一步由谁决定。固定退款流程“先查订单，再查退款，再生成回复”是 workflow；如果系统根据观察结果决定追问、补查、创建工单或停止，才接近 Agent。

Agent 也不是 RAG。RAG 解决外部知识证据接入；Agent 可以把检索当工具使用，但它额外关心多步行动、状态更新和失败恢复。

## 和应用/面试的连接

应用里，不要为了“显得智能”默认上 Agent。能用一次结构化输出解决的分类任务，不需要循环；能用固定 workflow 稳定完成的审批流，也不一定需要 Agent。Agent 适合目标明确但路径会随观察结果变化的任务，例如退款追踪、运维排查、数据分析助手和多系统客服协作。

面试里，可以这样回答：Function Calling 是模型输出工具调用意图；Agent 是应用层围绕这个意图建立的状态机和循环。设计 Agent 时要说明状态、工具权限、停止条件、失败恢复和日志，而不只是说“让模型调用工具”。

下一篇会展开工具执行、权限和恢复：[工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| 有 Function Calling 就是 Agent | Function Calling 只是输出协议 |
| Agent 会自动执行工具 | 应用层执行工具并控制权限 |
| workflow 一定比 Agent 低级 | 固定流程更可控，适合路径稳定的业务 |
| Agent 越自主越好 | 生产系统需要边界、停止条件和审计 |
| RAG Agent 是一个固定架构 | RAG 可以作为 Agent 的一个工具，不是 Agent 本身 |

## 自测

1. Agent 和 Function Calling 的边界是什么？
2. Agent 和 workflow 的区别是什么？
3. 为什么 Agent 需要状态？
4. 什么场景不该用 Agent？

## 回到主线

到这里，你已经知道 Agent 的问题边界：它用于需要观察、状态更新、动态决策和恢复的多步任务。下一步要看：工具本身如何设计权限、校验和失败恢复，才能让循环可控。

下一篇：[工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)
