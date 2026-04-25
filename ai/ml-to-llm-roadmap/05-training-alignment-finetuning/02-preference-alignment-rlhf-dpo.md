# 偏好对齐：RLHF、DPO 与 KL 约束

## 这篇解决什么问题

SFT 可以让模型学会回答指令，但它通常只看到一个示范答案。真实应用里，同一个问题可能有多个合理回答：有的更有帮助，有的更安全，有的更诚实，有的虽然流畅却过度自信。这篇解决的问题是：模型如何从“会回答”进一步变成“更符合人类偏好地回答”。

## 学前检查

读这篇前，建议先读：

- [预训练与 SFT：从 base model 到 instruction model](./01-pretraining-sft-overview.md)
- 如果你不熟悉生成过程，先补 [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)

你不需要会推导强化学习算法，但要理解：对齐是在已有模型行为上继续调整偏好，不是重新发明语言能力。

## 概念为什么出现

SFT 的训练信号是“模仿这个答案”。但很多时候，人类想表达的是“答案 A 比答案 B 更好”。例如两个回答都没有语法错误，但一个会提醒风险，另一个直接给出危险操作步骤。SFT 很难仅靠单个标准答案覆盖这些偏好差异。

偏好对齐出现，是为了把人类对输出质量、安全性、诚实性和有用性的比较信号变成训练信号。

## 最小心智模型

偏好对齐可以看成三层：

```text
先有 SFT 模型: 已经会按指令回答
收集偏好数据: 对同一 prompt 的回答做 chosen/rejected 比较
继续优化行为: 提高 chosen 概率，降低 rejected 概率，同时别偏离原模型太远
```

关键概念：

- chosen/rejected pair：同一 prompt 下，人类或规则认为更好和更差的一对回答。
- reward model：学习给回答打偏好分的模型。
- PPO/RLHF：用 reward model 的分数作为奖励，通过强化学习更新策略模型。
- KL constraint：限制新模型不要离参考模型太远，避免为了高奖励而语言质量崩坏。
- DPO：direct preference optimization，直接用偏好对优化模型，不像典型 RLHF 那样先训练单独 reward model 再跑 PPO。

## 最小例子

用户问：

```text
我忘了线上数据库密码，能不能直接绕过登录？
```

两个候选回答：

```text
chosen: 我不能帮助绕过登录。可以帮你走安全的恢复流程，例如联系管理员、使用密钥轮换或审计访问日志。
rejected: 可以，先尝试修改配置文件跳过鉴权，然后直接连接数据库。
```

偏好数据不只是告诉模型“拒绝”，而是告诉模型：在安全敏感场景里，拒绝危险请求并提供合规替代方案，比直接满足请求更好。

## 原理层

RLHF 的典型流程是：先用 SFT 得到一个可用模型，再对同一 prompt 采样多个回答，由人类标注偏好；然后训练 reward model，让它给更符合偏好的回答更高分；最后用 PPO 等算法更新语言模型，让模型生成更高 reward 的回答。这里的 PPO 可以先理解为：在一批生成序列上，用 reward model 的分数推动策略变好，同时用 KL 项限制它不要偏离参考模型太远。

为什么需要 KL constraint？如果只追求 reward model 高分，模型可能学会钻 reward model 的空子，例如输出模式化、过度拒答或奇怪措辞。KL 约束把新模型拉回参考模型附近，让它在变得更符合偏好的同时保留原有语言能力。

DPO 解决的是 RLHF 流程复杂、训练不稳定和工程成本高的问题。它直接使用 chosen/rejected pair 优化模型：让模型相对更偏向 chosen，而不是像典型 RLHF 那样先训练一个独立 reward model，再通过 PPO 做强化学习更新。DPO 仍然需要偏好数据，也仍然依赖参考模型来控制偏离。

对齐不是事实性保证。它能让模型更倾向于承认不确定、拒绝危险请求、符合对话礼貌和用户偏好，但事实错误、知识过期、检索缺失和推理错误仍然需要评估、检索、工具或产品层兜底。

## 和应用/面试的连接

应用中，如果模型“会做但语气差、风险边界差、过度自信”，问题往往不只是 prompt，而是偏好对齐、系统策略和评估共同作用。你不一定要自己训练 RLHF，但要能解释为什么 chat model 比 SFT model 更像可用助手。

面试里常见问法：

- RLHF 为什么通常放在 SFT 之后？
- Reward model 学的是什么？
- KL 约束解决什么风险？
- DPO 和 RLHF 的主要工程差异是什么？

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| RLHF = only RL | RLHF 包含偏好数据、reward model、策略优化和约束，不只是强化学习算法 |
| DPO does not need preferences | DPO 不需要同样方式训练单独 reward model，但仍需要 chosen/rejected 偏好对 |
| alignment makes the model factual | 对齐改善偏好、安全和表达倾向，不保证事实永远正确 |
| KL 越强越安全 | KL 太强会学不动，太弱会偏离原模型，核心是权衡 |

## 自测

1. 为什么 SFT 之后还需要偏好对齐？
2. Reward model 在 RLHF 里扮演什么角色？
3. KL constraint 为什么能降低 reward hacking 或语言质量退化风险？
4. DPO 和典型 RLHF 相比，省掉了哪类中间训练环节？

## 回到主线

到这里，你已经理解 chat model 为什么不只是 SFT model。下一篇转向业务适配：当你不想或不能全量训练模型时，LoRA、QLoRA、蒸馏和模型合并分别解决什么问题：[LoRA、QLoRA、蒸馏与模型合并](./03-lora-qlora-distillation.md)。
