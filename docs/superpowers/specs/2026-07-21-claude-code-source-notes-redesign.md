# Claude Code 源码笔记渐进式重构设计

## 1. 背景

当前 ai/claude-code-source/ 已经覆盖 Claude Code 的 runtime、context、query loop、tool、permission、sandbox、session、subagent 等主题，但阅读体验仍然接近源码追踪报告：

- 源码文件、函数和行号成为主叙事，机制本身退居其次。
- 每篇文章套用相似模板，却没有形成一条能够持续推进的认知主线。
- 正常路径、变体、失败分支和产品入口过早混在一起。
- 同一个概念在多篇文章重复解释，容易产生口径漂移。
- 读者可以找到源码，却难以先建立稳定的整体模型，再自然深入细节。

本次重构不是继续补充更多源码位置，而是重新设计整套笔记的认知顺序和证据层级。

源码参考仓库：

~~~text
/Users/buoy/Development/gitrepo/Claude-Code-true
~~~

本设计使用的源码快照：

~~~text
branch: note
commit: 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf
~~~

## 2. 核心目标

整套笔记必须同时满足三个目标。

### 2.1 先建立整体认知

读者在进入源码和局部实现前，应先获得一张后续不会被推翻的完整运行图，并理解：

- 一次 agent turn 如何从用户意图走到模型请求。
- 模型如何产生文本或 tool use。
- runtime 如何把 tool use 转换为受控机器效果。
- tool result 如何回到模型并推动下一轮。
- 会话如何跨时间保存、压缩、中断和恢复。
- subagent 如何作为嵌套的 agent loop 接入主流程。

整体认知不只有控制流程，还必须包含核心对象、状态归属、模块边界和不变量。

### 2.2 讲清所有相关且必要的实现细节

对于保留的主题，凡是会影响以下任一事项的内容，都必须解释清楚：

- 输入与输出
- 状态变化
- 执行顺序
- 并发关系
- 权限或安全结果
- 失败、中断与恢复行为
- 与上下游模块的契约
- 非显然的设计取舍

与机制语义无关的 UI、日志、遥测、纯转发、普通 wrapper、兼容性胶水和不改变行为的 feature flag 不进入主叙事。

### 2.3 保持流畅的线性阅读

读者不应依靠频繁跳转才能理解正文。所有概念按照因果关系和依赖顺序出现：

- 先完整流程，后局部细节。
- 先标准路径，后变体和异常。
- 先机制解释，后源码证据。
- 先定义概念，后使用概念。
- 每章结尾自然产生下一章要回答的问题。

## 3. 非目标

本次重构不追求：

- 从零实现一个完整 coding agent。
- 覆盖 Claude Code 的全部产品功能。
- 逐行解释源码或复刻完整调用图。
- 深入 React、Ink、普通 CLI 参数解析和 UI 渲染。
- 深入 plugin marketplace、desktop bridge 或 remote bridge。
- 罗列全部 feature gate、遥测、日志和历史兼容分支。
- 让每篇文章具有相同篇幅或机械套用完全一致的标题模板。
- 使用不可编辑的图片承担核心机制说明。

Runtime 入口只保留“不同入口如何规范化为统一 agent turn”的必要边界，不再作为独立主主题。

MCP 只作为外部工具适配器放入 Tool System。Plugin 与 Bridge 移出主阅读路径。

## 4. 统一主线

整套笔记只使用一条主线：

> 一次 agent turn，如何把用户意图转换成安全的机器操作，再把观察结果写回状态，让模型继续决策；当任务跨越时间或需要委派时，同一套机制如何扩展。

主线的稳定骨架是：

~~~text
用户提出任务
  ↓
构造模型可见上下文
  ↓
Query Loop 驱动模型并消费 stream
  ↓
模型产生文本或 tool use
  ↓
runtime 解析工具请求并通过受控执行管线产生机器效果
  ↓
生成 tool result
  ↓
更新 messages 与 transcript
  ↓
继续下一轮或结束
  ↓
必要时跨时间恢复或委派给 child agent loop
~~~

后续主题不是彼此独立的功能清单，而是对这条主线不同位置的放大。

## 5. 双重递进架构

### 5.1 整套笔记的递进

主阅读顺序如下。

#### 00：一次完整的 Agent Turn

先走完一个完整任务，不深挖源码。建立：

- 全局流程
- 核心参与者
- 核心对象
- 状态归属
- 模块交接点
- 全书不变量

#### 第一部分：模型如何获得世界并持续决策

放大以下链路：

~~~text
Context Assembly
  → Model Request
  → Model Streaming
  → Query Loop
  → text 或 tool use
~~~

覆盖：

- system prompt、messages、tools、attachments、memory
- model-visible context 与 runtime-only state
- Query Loop 的继续与停止
- stream 如何形成 assistant message
- tool use 与 tool result 的协议闭环

#### 第二部分：模型意图如何变成受控机器效果

放大以下链路：

~~~text
tool use
  → Tool Contract
  → Resolution / Input Preparation
  → Execution Ordering
  → Per-call Validation / Permission
  → Sandbox / Process / File Effect
  → tool result
~~~

覆盖：

- Tool contract 与 schema
- 工具查找、校验和结果映射
- 串行、并行和流式工具执行
- allow、ask、deny
- Bash command analysis
- sandbox
- Read、Edit、Write 的一致性与安全约束
- MCP 作为外部 Tool adapter

#### 第三部分：任务如何跨时间继续

放大以下链路：

~~~text
messages
  → Transcript
  → Context Pressure
  → Compaction
  → Interrupt / Queue
  → Continue / Resume
  → Reconstructed Next Turn
~~~

覆盖：

- 模型上下文与完整 transcript 的区别
- compaction 的输入、输出和信息损失
- interrupt 与 abort 的作用范围
- queued command 何时注入
- continue 与 resume 如何重建状态
- 为什么恢复不是恢复原调用栈

#### 第四部分：任务如何委派给另一个 Agent Loop

放大以下链路：

~~~text
Parent Query Loop
  → Agent Tool
  → Child Context
  → Child Query Loop
  → Foreground / Background Lifecycle
  → Result / Notification
  → Parent Tool Result
~~~

覆盖：

- child context 的继承与隔离
- foreground 与 background 生命周期
- parent 与 child 的通信
- task result 如何返回
- abort 如何传播
- fork 如何重用父上下文
- prompt cache 为什么要求稳定前缀

#### 最后：回到全景形成面试表达

完整面试回答放在理解机制之后：

- 30 秒结论
- 3 分钟白板流程
- 深入追问入口
- 常见错误心智模型

### 5.2 每个主题内部的递进

每篇主文章遵循相同的阅读节奏，但不强迫使用完全相同的标题：

~~~text
在全局图中定位
  → 局部完整流程
  → 贯穿案例
  → 关键状态
  → 沿流程逐步拆解
  → 把异常和变体挂回对应节点
  → 关键伪代码
  → 真实源码证据
  → 设计取舍
  → 回到全局图
  → 面试表达
  → 引出下一章
~~~

读者可以用三遍阅读：

1. 第一遍看懂整体流程。
2. 第二遍讲清状态、顺序、不变量和异常。
3. 第三遍用关键源码验证结论。

## 6. 目标目录结构

目标结构采用“总览主章 + 按因果顺序排列的细节文章”：

~~~text
ai/claude-code-source/
  README.md
  00-one-agent-turn.md

  01-model-turn/
    README.md
    01-context-assembly.md
    02-query-loop-and-streaming.md

  02-controlled-effects/
    README.md
    01-tool-contract-and-orchestration.md
    02-permission-decision.md
    03-bash-security-analysis.md
    04-sandbox-runtime.md
    05-file-editing-safety.md

  03-session-continuity/
    README.md
    01-transcript-and-model-context.md
    02-compaction.md
    03-interrupt-queue-continue-resume.md

  04-subagent-delegation/
    README.md
    01-child-loop-and-context-isolation.md
    02-foreground-background-lifecycle.md
    03-communication-and-result-return.md
    04-fork-and-prompt-cache.md

  appendices/
    runtime-entry-adapters.md
    source-evidence-index.md

  99-interview-playbook.md
  _archive/
~~~

每个部分的 README 是局部总览，必须能够独立解释该部分的完整机制。细节文章按照 README 中的流程节点顺序展开。

主阅读路径必须是线性的。README 和每篇文章都明确标注“上一篇”和“下一篇”，读者不需要自行选择跳转顺序。

source-evidence-index.md 只索引“结论 → path + symbol → 适用边界”，不能重新扩张成按文件和行号组织的源码地图。每篇正文中的证据说明仍是理解该结论的权威位置。

现有主笔记在重写时先整体移入带日期的 archive 子目录，作为证据和历史材料保留，不直接删除。

## 7. 总览模型必须包含什么

00 章和每个部分 README 不能只有一张流程图，还必须包含：

### 7.1 控制流

- 当前动作由谁驱动
- 下一步由什么条件决定
- 什么时候继续、停止、等待或恢复

### 7.2 数据流

- messages、tool use、tool result、attachments 如何移动和转换
- 哪些数据进入模型，哪些只在 runtime 内部流动

### 7.3 状态归属

至少区分：

- 模型协议状态
- runtime 控制状态
- 机器效果与安全状态
- 持久化会话状态
- child agent / task 状态

### 7.4 不变量

全书至少维持以下不变量：

- 模型只能提出机器操作意图，不能绕过 runtime 直接制造副作用。
- 每个已进入协议历史的 tool use 都必须得到可关联的 tool result。
- Permission 决定是否授权，Sandbox 限制授权后的执行环境，两者不可混为一谈。
- 模型上下文是当前可见视图，transcript 是持久化历史，两者不可混为一谈。
- Compaction 改变模型视图，不等于删除完整 transcript。
- Interrupt 必须保持后续消息协议合法。
- Continue 和 Resume 重建下一轮状态，不恢复旧调用栈。
- Subagent 是具有明确上下文与结果边界的 child loop，不默认等于独立进程。

## 8. 相关细节的纳入规则

### 8.1 因果相关性测试

一个细节只有在解释以下任一元素时，才进入正文：

- 全局或局部图中的节点
- 节点之间的箭头
- 关键状态
- 关键不变量
- 主流程上的异常分支
- 模块之间的输入输出契约

如果删除一段内容后，读者仍然可以正确画出流程、解释状态变化、说明异常行为并回答设计原因，该内容应降到证据索引或直接删除。

### 8.2 标准路径优先

每个主题先声明标准路径假设，再解释完整正常流程。变体只能在读者理解标准路径后出现。

变体包括：

- interactive 与 headless
- REPL 与 SDK
- streaming 与 non-streaming
- foreground 与 background
- normal 与 fork
- feature-gated behavior
- fallback、abort 与 recovery

每个变体必须挂在标准路径实际发生分叉的节点上。

### 8.3 一个概念只有一个所有者

概念所有权：

| 概念 | 所有者 |
|---|---|
| model-visible context | Model Turn |
| Query Loop 的继续与停止 | Model Turn |
| tool use / tool result 协议配对 | Model Turn |
| Tool contract、validation、orchestration | Controlled Effects |
| allow / ask / deny | Controlled Effects / Permission |
| Bash 分析与 sandbox | Controlled Effects / Safety |
| transcript 与 model context | Session Continuity |
| compaction | Session Continuity |
| interrupt、queue、continue、resume | Session Continuity |
| child context 与 task lifecycle | Subagent Delegation |
| fork 与 prompt cache | Subagent Delegation |

其他文章只能解释自己如何使用该契约，不重复拥有完整定义。

## 9. 保持流畅阅读的写作规则

### 9.1 使用贯穿案例

主案例采用“定位并修复一个失败测试”：

- 读取项目信息
- 搜索与读取文件
- 模型提出修改
- runtime 执行 Edit 或 Write
- 运行测试
- 接收工具结果
- 继续或结束

长会话、中断和 subagent 章节在同一任务背景上扩展，不另起完全无关的故事。

### 9.2 展示状态前后变化

关键步骤使用简化状态快照，而不是只描述调用关系：

~~~text
执行前

messages:
  user
  assistant(tool use: t1)

runtime:
  t1 = pending

执行后

messages:
  user
  assistant(tool use: t1)
  user(tool result: t1)

runtime:
  t1 = completed
~~~

### 9.3 异常挂回主流程

失败不能成为章末的孤立清单。必须标明：

- 从主流程哪一步分叉
- 修改了什么状态
- 是否产生 tool result 或 transcript event
- 是否回到 Query Loop
- 后续模型能看到什么

### 9.4 明确章节交接

每章结尾必须说明：

- 刚完成了全局图中的哪个节点
- 当前系统状态是什么
- 下一章为什么自然出现

完整的“面试式回答”放在章末。章首只保留核心问题和一句话结论。

## 10. 代码与证据规范

### 10.1 解释顺序

代码不能承担第一次解释机制的任务：

~~~text
流程与状态
  → 简化伪代码
  → 真实源码片段
  → 片段证明的结论
~~~

### 10.2 代码片段纳入条件

只展示决定机制成立的代码，例如：

- Query Loop 的继续或停止判断
- tool use 到 tool result 的转换
- 工具并发与串行的调度条件
- Permission 的裁决顺序
- 中断后的消息补全
- Compaction 后的上下文重建
- parent 与 child context 的隔离
- fork 的 cache-compatible prefix

普通调用转发、UI 渲染、日志和大段完整函数不进入正文。

### 10.3 源码定位

源码证据使用：

~~~text
commit + repository-relative path + symbol
~~~

行号只作为辅助定位，不能作为叙事骨架。

### 10.4 事实层级

文章明确区分：

- 源码确认：源码能够直接证明
- 架构解释：从多个实现点总结出的机制含义
- 通用原则：可迁移到其他 coding agent 的设计知识

Feature-gated、平台相关或入口相关行为必须标明适用条件，不能泛化成唯一实现。

## 11. 图示规范

核心机制图必须可编辑、可 diff、可 review。

优先级：

1. Mermaid
2. Markdown 表格
3. 文本图
4. 不可编辑图片，仅限真实 UI 或运行证据

推荐映射：

| 内容 | 格式 |
|---|---|
| 全局 Agent Turn | Mermaid flowchart |
| Model、Runtime、Tool 交互 | Mermaid sequenceDiagram |
| Permission 管线 | Mermaid flowchart |
| Query、Task、Interrupt 生命周期 | Mermaid stateDiagram-v2 |
| Compaction 前后状态 | Mermaid + Markdown 表格 |
| Parent / Child 通信 | Mermaid sequenceDiagram |
| 状态归属与模式比较 | Markdown 表格 |

图示必须遵守：

- 全局图只使用稳定概念，不放源码函数和行号。
- 局部图标明自己放大了全局图中的哪个节点。
- 图中术语与正文完全一致。
- 正文可以引用图中稳定的步骤编号。
- 主图展示正常路径，复杂异常使用局部图。
- 图后必须有文字解释。
- 同一机制只维护一份权威图，其他地方引用或画明确标注的局部放大图。
- Mermaid 必须实际渲染验证。

## 12. 阅读模式

README 提供三条明确路径。

### 12.1 总览路径

适合第一次建立认知：

~~~text
README
  → 00
  → 各部分 README
  → 99 Interview Playbook
~~~

### 12.2 完整学习路径

按编号读取所有部分 README 和细节文章，不跳过必要机制。

### 12.3 面试复习路径

先读 00 的全局图，再读各章末尾的面试表达和 99 Interview Playbook，需要时回到对应机制。

## 13. 验收标准

### 13.1 整体认知

- 读完 00 后，读者能够不看源码画出完整 agent turn。
- 读者能够区分模型协议、runtime 控制、机器效果和持久化状态。
- 后续文章只细化 00 的模型，不推翻它。

### 13.2 相关细节

- 每段重要细节都能挂回一个流程节点、转换、状态、不变量或异常分支。
- 每个主题覆盖输入、输出、状态、顺序、失败、边界和取舍。
- 与机制无关的源码噪声不进入主叙事。

### 13.3 流畅阅读

- 主阅读路径线性且无未解释的前向依赖。
- 术语在首次使用时定义。
- 每章开头能在全局图中定位，结尾能回到全局图。
- 章节交接由上一个问题自然引出。
- 不要求读者跳转源码才能理解正文。

### 13.4 源码准确性

- 所有关键结论在固定源码快照中有证据。
- 源码位置使用 path + symbol，行号仅作辅助。
- canonical path、feature-gated path 和平台差异明确区分。
- 源码确认、架构解释和通用原则没有混写。

### 13.5 图示与文档质量

- Mermaid 块能够渲染。
- README、上一篇、下一篇和细节文章链接有效。
- 图示术语与正文一致。
- 没有 TBD、TODO、占位段落或未解决的设计歧义。

## 14. 重构边界

这次重构应优先完成认知结构，而不是一次性追求所有主题的最终篇幅：

1. 先建立目标目录、README、00 和统一术语。
2. 再按主线顺序重写 Model Turn。
3. 继续重写 Controlled Effects。
4. 再处理 Session Continuity。
5. 最后处理 Subagent Delegation 与 Interview Playbook。
6. 每个部分完成后进行源码准确性和阅读连贯性审查。

实现计划必须把每个部分作为独立可审查的交付单元，不允许把全部文章合成一次无结构的大改。
