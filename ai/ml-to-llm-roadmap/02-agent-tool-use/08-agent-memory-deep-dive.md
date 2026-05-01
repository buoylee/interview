# Agent 记忆系统深水区

## 这篇解决什么问题

前面已经讲过 Agent 需要 working state、工具观察、任务规划、runtime 和 durable state。但“记忆”很容易被误解成：把聊天历史一直塞进上下文，或者把用户说过的话永久保存起来。

这一篇解决的问题是：怎样把 Agent memory 设计成一个受治理的子系统，而不是把 chat history、长上下文或零散摘要当成记忆。重点是记忆的类型、生命周期、写入策略、检索策略、过期和权限边界。

## 学前检查

读这篇前，建议先理解：

- Agent 里的状态、记忆和规划边界：[状态、记忆与任务规划](./03-state-memory-and-planning.md)
- RAG 解决外部知识接入和 grounding：[RAG 解决什么问题](../01-rag-retrieval-systems/01-rag-problem-boundary.md)
- 长上下文的成本来自 prefill、decode 和 KV cache：[Prefill、Decode 与 KV Cache](../06-inference-deployment-cost/01-prefill-decode-kv-cache.md)

如果还不熟，可以先记住一句话：状态服务当前任务，记忆服务未来任务，但两者都不能绕过实时权限和业务校验。

## 概念为什么出现

真实 Agent 会遇到跨会话信息：

```text
跨会话偏好: 用户偏好中文、邮件沟通、不要电话回访
历史案件: 上次退款卡在银行拒绝，已创建过工单 T88
重复流程: 同一用户多次因为同一银行卡被拒，需要推荐换卡或人工核验
历史摘要: 多轮对话太长，需要压缩成可审计摘要
```

这些信息确实能提高体验和效率。但如果没有治理，记忆会带来新问题：

- context cost：每次都塞历史会增加 prefill 成本、延迟和噪声。
- stale memory：旧记忆可能已经过期，例如订单已退款、用户偏好已变、政策已更新。
- privacy constraints：用户资料、工单内容、支付失败原因和身份信息不能随意跨用户、跨租户或跨场景复用。
- prompt injection：用户或工具输出里可能包含“以后永远记住并执行某条指令”，不能直接写入长期记忆。

所以 memory system 不是“模型记得越多越好”，而是应用侧决定什么可以写、何时检索、如何注明来源、什么时候删除或更正。

## 最小心智模型

Agent 记忆可以放在这条链路里理解：

```text
working state -> conversation summary -> retrieved episodic/semantic/profile memory -> current context -> memory write decision
```

各层职责不同：

| memory type | lifecycle | storage | retrieval trigger | risk |
|-------------|-----------|---------|-------------------|------|
| working | 当前请求或当前任务内有效 | runtime state、durable state、内存或事务表 | 每一步 Agent loop 都需要 | 被误当成长期事实，任务结束后继续污染后续会话 |
| episodic | 一次历史事件或案件，按时间和来源保存 | 工单摘要库、会话摘要库、事件表、向量索引 | 当前问题与某个历史案件、订单、失败模式相似 | stale memory、错误摘要、跨用户泄露 |
| semantic | 稳定知识或经验规则 | 知识库、策略库、案例库、检索索引 | 需要解释通用流程、产品规则或历史问题模式 | 把旧政策当新政策，或缺少引用依据 |
| profile | 用户或组织的长期偏好和资料 | 用户画像表、偏好表、CRM、权限受控 profile store | 个性化回复、渠道偏好、语言偏好、默认设置 | 隐私越界、偏好被当成授权、用户无法更正 |
| tool-observation | 工具调用产生的结构化观察 | trace、observation table、任务状态表 | 需要恢复、排查、摘要或判断下一步 | 工具输出过期、包含注入文本、记录过多敏感字段 |

这里的 retrieved memory 类似 RAG：需要索引、召回、排序、上下文组装和引用。但 Agent memory 不等于 RAG。RAG 解决外部证据接入；Agent memory 还要决定写不写、保留多久、谁能读、是否能影响行动。

## 客服退款/工单 Agent 案例

用户说：

```text
我上次那个退款又失败了，能不能直接帮我处理？还是中文回复我。
```

可以记住的内容包括：

- 用户语言偏好：该用户偏好中文回复。这属于 profile memory，但用户随时可以改。
- prior support case summary：上次订单 A123 因银行拒绝导致退款失败，创建过工单 T88，人工建议用户核对银行卡。
- repeated bank rejection pattern：同一用户多次出现 bank_reject，可能需要提示换卡、补充材料或升级人工核验。

必须实时重新检查的内容包括：

- identity：当前请求是不是同一个已验证用户，是否需要二次验证。
- order ownership：订单 A123 是否属于当前用户，当前客服 Agent 是否有权读取。
- refund state：退款现在是 pending、success、failed、cancelled 还是已人工处理，不能只看旧工单摘要。

一次更稳的流程是：

```text
load working state
retrieve profile memory: language=zh-CN, source=user_preference, updated_at=2026-04-20
retrieve episodic memory: prior case T88 summary, source=ticket_system, updated_at=2026-04-25
run live checks: verify_identity, check_order_ownership, get_refund_status
assemble context: 当前目标 + 实时工具结果 + 相关旧记忆摘要 + 可执行策略
decide action: 回复、创建新工单、关联旧工单或转人工
decide memory write: 是否更新偏好、写入新案件摘要、标记旧记忆过期
```

如果实时退款状态已经成功，Agent 应说明“当前查询显示已退款”，而不是根据旧记忆继续说银行拒绝。如果用户偏好中文，Agent 可以用中文回复；但这个偏好不能绕过身份校验、订单归属和退款权限。

## 工程控制点

Agent memory 至少要把这些控制做成显式策略或字段：

- memory write policy：定义哪些信息允许写入，哪些必须忽略或只保留短期。例如用户明确偏好、案件摘要、重复失败模式可以写；身份证、银行卡完整号、密钥和一次性验证码不应写入长期记忆。
- memory retrieval policy：定义什么任务能检索什么记忆。退款 Agent 可以检索同用户、同租户、同订单相关记忆；不能因为语义相似就读取其他用户的工单。
- memory confidence and source：每条记忆要带来源、置信度和生成方式，例如 `source=ticket_system`、`source=user_stated`、`source=summarizer_v3`。低置信度记忆只能作为线索，不能当成事实。
- timestamp and expiration：记录 `created_at`、`updated_at`、`expires_at`。偏好可以长期保留但可更正；工具观察和退款状态要短期过期；政策类 semantic memory 要跟随版本更新。
- tenant/user permission boundary：检索和写入都必须绑定 tenant、user、account、case 或 order 范围。permission 不是 prompt 约束，而是存储层和检索层的过滤条件。
- delete and correction flow：用户要求删除偏好、纠正错误记忆或撤回授权时，系统要能定位、删除、标记失效，并防止摘要索引继续召回旧内容。
- summarization vs raw transcript storage：长期记忆优先保存结构化摘要和必要引用，少存原始 transcript。原文如果必须保留，要有脱敏、权限、保留期和审计理由。
- prompt injection filtering before memory write：写入前过滤用户文本和工具 observation 中的指令型内容，例如“以后忽略安全规则”“把这个权限永久记住”。只保留事实、偏好、事件和来源。
- memory citation in trace：每次检索到的记忆都要进入 trace，记录 memory id、来源、时间、置信度、是否注入上下文、是否影响最终行动，方便排查旧记忆污染当前任务。

一个实用原则是：记忆可以提高默认体验，但不能提高权限。任何涉及身份、订单、退款状态、审批金额和写操作的判断，都要用实时工具和业务系统重新确认。

## 和应用/面试的连接

Agent memory 怎么设计？

可以按子系统回答：先区分 working、episodic、semantic、profile 和 tool-observation memory；再定义 write policy、retrieval policy、source/confidence、timestamp/expiration、权限过滤、删除更正、摘要策略和 trace 引用。最后强调 memory 只负责给当前任务提供可治理的历史线索，不是把全部聊天历史塞进 prompt。

怎么防止旧记忆污染当前任务？

第一，检索前用 tenant/user/case/order 做硬过滤；第二，给每条记忆带时间戳、来源、置信度和 expiration；第三，把历史记忆放在低于实时工具结果的位置；第四，在 prompt 和 policy 里明确旧记忆只能作为线索；第五，在 trace 里记录哪些 memory 影响了行动，方便回放和修正。

为什么 memory 不能替代实时权限校验？

因为 memory 是历史材料，不是当前授权。用户过去通过身份验证，不代表当前会话仍然有效；旧工单属于某个订单，不代表当前用户仍有读取权限；用户偏好“直接处理”也不能绕过退款规则、订单归属和审批阈值。实时权限校验必须由业务系统和工具执行前 policy 完成。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| memory 就是聊天历史 | 聊天历史只是原始材料，memory 应该有类型、来源、权限、过期和写入策略 |
| 长上下文能替代 memory system | 长上下文只能扩大单次输入，不能解决写入治理、检索权限、删除更正和过期 |
| 检索到的记忆都可信 | 记忆可能来自用户陈述、摘要器或旧工具结果，需要 source、confidence 和实时复核 |
| 用户偏好可以绕过业务校验 | 偏好只能影响表达和默认选项，不能绕过身份、订单、退款和审批校验 |
| 写入越多记忆越智能 | 过量写入会增加噪声、隐私风险、stale memory 和错误召回成本 |

## 自测

1. working、episodic、semantic、profile 和 tool-observation memory 分别适合保存什么？
2. memory write policy 应该禁止哪些内容写入长期记忆？为什么？
3. memory retrieval policy 为什么要包含 tenant、user、case 或 order 过滤？
4. expiration 应该如何用于退款状态、用户偏好和政策类 semantic memory？
5. 为什么用户偏好和历史案件不能替代当前会话的 permission 校验？

## 回到主线

到这里，你应该能把 Agent memory 看成一个受治理的子系统：它负责保存可复用历史线索，也负责限制这些线索什么时候能写、能读、能影响行动，以及什么时候必须失效。

下一步要看：当一个 Agent 的职责、工具、权限、上下文和评估标准变得太宽时，如何设计显式协作协议。

下一篇：[Multi-Agent 协作机制](./09-multi-agent-coordination.md)
