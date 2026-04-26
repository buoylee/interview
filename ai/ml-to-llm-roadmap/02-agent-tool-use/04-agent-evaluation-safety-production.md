# Agent 评估、安全与生产排查

## 这篇解决什么问题

普通生成任务可以先看最终答案是否正确。Agent 不够，因为最终答案可能看起来合理，但中间调用了错误工具、越权访问数据、重复执行写操作，或在失败后编造结果。Agent 评估必须看完整轨迹。

这一篇解决的问题是：Agent 上线前和上线后应该评估什么、限制什么、记录什么，以及常见生产故障如何定位。

## 学前检查

读这篇前，建议先理解：

- 生产排查需要日志和回归集：[生产排查、监控与回归定位](../07-evaluation-safety-production/03-production-debugging-monitoring.md)
- 平台层要管理成本和路由：[LLM 平台、路由与成本治理](../08-system-design-project-narrative/02-llm-platform-routing-cost.md)
- Guardrails 不是只过滤脏话：[幻觉、安全与 Guardrails](../07-evaluation-safety-production/02-hallucination-safety-guardrails.md)

如果还不熟，可以先记住一句话：Agent 的质量等于结果质量、轨迹质量和权限安全共同成立。

## 概念为什么出现

Agent 的失败不一定体现在最终文本里：

```text
工具选错: 应查退款状态却查了订单物流
循环失控: 一直重试同一个失败工具
观察过期: 使用旧库存或旧审批状态继续决策
状态漂移: 忘记用户预算、权限或已完成步骤
安全绕过: 工具输出诱导模型忽略系统策略
```

所以评估和监控要覆盖每一步，而不是只问用户“回答满意吗”。

## 最小心智模型

Agent-specific eval 可以按这些维度看：

| 维度 | 关注点 |
|------|--------|
| task success | 用户目标是否完成 |
| trajectory quality | 步骤是否必要、顺序是否合理 |
| tool call validity | 工具名、参数和依赖是否正确 |
| tool success rate | 工具是否成功执行，失败是否分类 |
| permission safety | 是否越权读取或执行 |
| cost/latency | token、工具耗时、重试次数和 p95 |
| loop termination | 是否能正确停止，是否过早停止 |
| human escalation correctness | 该转人工时是否转，能自动处理时是否误转 |

安全控制则放在循环外层：

```text
tool allowlist -> permission boundary -> policy checks -> loop limits -> audit logs -> sandbox dangerous actions
```

## 最小例子

一次退款追踪 trace：

```text
goal: 回答订单 A123 退款失败原因，并给出下一步
step 1 tool call: get_refund_status(order_id=A123)
observation: status=failed, reason=bank_reject
step 2 tool call: create_refund_ticket(order_id=A123, reason=bank_reject)
failure: ticket service timeout
fallback/escalation: 记录失败原因，转人工队列，返回人工处理时效
final answer: 退款被银行拒绝，已转人工复核，预计 1 个工作日内更新
```

评估不能只看最终回答，还要检查：A123 是否属于当前用户，第二步是否允许自动创建工单，超时后是否没有重复创建，转人工日志是否包含失败原因。

## 原理层

常见生产故障：

| 故障 | 表现 | 排查字段 |
|------|------|----------|
| infinite loop | 重复同一工具或同一追问 | loop_count、last_action、stop_reason |
| tool hallucination | 调用不存在工具或不存在参数 | tool_name、schema_version、validation_error |
| stale observation | 使用旧结果继续决策 | observation_timestamp、data_version |
| unsafe action | 越权写入或高风险操作 | user_permission、policy_check_result |
| hidden state drift | 状态与对话或工具结果不一致 | state_diff、trajectory |
| prompt injection through tool output | 工具文本诱导模型改规则 | tool_output_source、sanitization_result |

loop limit 防止无限循环和成本失控，例如最多 6 步、最多 2 次同类重试、总耗时不超过 30 秒。但它也可能让复杂任务过早停止，所以要配合 stop_reason 和 fallback：达到限制时说明当前进度、缺口和人工升级方式。

生产日志至少应记录：request_id、user_id 或匿名主体、goal、state snapshot、model/prompt/schema 版本、tool calls、tool arguments、observations 摘要、validation errors、policy results、retry count、latency、token cost、stop_reason、final answer 和 human escalation 标记。

## 和应用/面试的连接

应用里，Agent 上线前要准备离线轨迹集：正常完成、缺信息、工具失败、权限失败、危险动作、prompt injection 和需要人工的样本。上线后要监控工具失败率、循环步数、人工升级率、成本和用户反馈，并把高风险失败回灌到回归集。

面试里，可以强调：Agent eval 不是只看最终自然语言答案，而是看“是否用正确方式完成任务”。如果一个客服 Agent 最终说“已处理”，但没有合法创建工单，或者重复创建了两个工单，任务就是失败。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| 最终答案对就代表 Agent 对 | 中间可能越权、重复执行或成本失控 |
| loop limit 只是省钱 | 它也防无限循环，但可能导致过早停止 |
| tool hallucination 只能靠 prompt 解决 | 还要注册工具白名单和 schema 校验 |
| 工具输出来自系统所以可信 | 工具可能返回用户文本、网页或第三方内容 |
| 生产日志只记最终回答 | Agent 排查必须记状态、工具、观察和停止原因 |

## 自测

1. Agent eval 为什么不能只看最终答案？
2. 怎么发现 tool hallucination？
3. Loop limit 防什么，可能带来什么副作用？
4. Agent 生产日志需要记录哪些字段？

## 回到主线

到这里，Agent 与工具调用模块形成闭环：先判断是否需要 Agent，再设计工具权限和失败恢复，然后管理状态、记忆和计划，最后用轨迹评估、安全控制和生产日志保证它能上线运行。

继续学习时，可以回到系统设计模块，把 Agent 当作多步行动组件放进完整 AI 产品架构中。
