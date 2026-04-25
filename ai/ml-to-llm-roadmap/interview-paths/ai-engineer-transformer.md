# AI Engineer Transformer 面试阅读路径

> **定位**：这不是第一次学习材料。先读完 [Transformer 系统学习主线](../04-transformer-foundations/)，再用这条路径按面试优先级复习。

## 适合谁

- 做过 RAG / Agent / LLM 应用，但底层 Transformer 不够稳。
- 需要准备 AI Engineer / LLM Application Engineer 面试。
- 想把系统学习内容压缩成可回答、可追问、可连接项目的材料。

## 2 周冲刺路径

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [04-transformer-foundations/README.md](../04-transformer-foundations/) | 按顺序过一遍系统主线 |
| 2 | [09-kv-cache-context-cost.md](../04-transformer-foundations/09-kv-cache-context-cost.md) | 重点复习成本、延迟、长上下文 |
| 3 | [07-transformer-architecture-variants.md](../04-transformer-foundations/07-transformer-architecture-variants.md) | 准备 BERT/T5/GPT 对比 |
| 4 | [03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md) | 压缩成面试答案 |

## 系统学习路径

1. 从 [04-transformer-foundations/README.md](../04-transformer-foundations/) 开始顺序读 1 到 9。
2. 每次卡住先回 foundation，不直接背 review note。
3. 学完后再读 [03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md)。
4. 用下面的问题做口头复述。

## 高频问题

- 为什么 Attention 需要上下文读取？
- Self-Attention 里的 Q/K/V 分别是什么？
- Transformer Block 里 FFN、Residual、Norm 分别解决什么问题？
- 原始 Transformer 为什么有 Encoder 和 Decoder？
- BERT、T5、GPT 架构有什么区别？
- 为什么现代通用 LLM 多数是 Decoder-only？
- KV Cache 为什么能加速生成，但不能让长 prompt 免费？

## 项目连接

- RAG embedding / rerank：常见做法更接近 Encoder-only 的理解/匹配思路。
- RAG 长文档上下文：连接 prefill、context cost。
- Agent 工具调用：连接 Decoder-only 生成结构化 token。
- 流式输出：连接自回归 decode 和 KV Cache。

## 使用规则

如果这份路径里某个问题答不上来，不要先背答案，回到对应系统学习章节重读。
