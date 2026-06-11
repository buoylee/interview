# ml-to-llm-roadmap 实战补全:MVP 主轴 + 文档锚点回填(方案 A)

> 2026-06-11 · 在职 3-6 个月节奏 · 服务于 LLM 应用工程师面试

---

## 一、背景与问题

`ai/ml-to-llm-roadmap/` 的 04-07 模块已完成概念层学习,但内容偏「概念骨架」——07(评估安全生产)最明显:rubric、judge 校准、red teaming 都是一句话带过,没有真实 eval pipeline 的样子、没有数字锚点、没有工具实操。被面试追问「你们 eval 怎么做的、judge 一致率多少、幻觉率多少」时答不出亲手数字。

市场调研结论(2026,国内外面经 + JD):

- AI 岗位分三层:算法/模型研究、LLM Infra、**LLM 应用工程师**。本计划只对标第三层。
- 应用岗面试权重排序:**项目深挖(数字与细节)> Evals 工程 > Agent 工程细节 > 系统设计(带成本/延迟预算)> 模型基础八股 > 手撕(Python + 调 API 级)**。
- Evals 工程是 2026 权重最高、挂人最多的环节——恰是现有文档最虚的部分。
- 模型基础八股只要求讲清机制,现有 04-06 深度已够,不需要再加深。

## 二、目标定位

**面试达标线:LLM 应用工程师 + 微调实操一次。**

- 微调取「实操层」:用现成 Unsloth notebook(`ai/fine-tuning/`)在开源小模型上跑通一次 LoRA/QLoRA,自构数据,微调前后用 eval 对比。能回答「什么时候微调 vs RAG、数据怎么构造、效果怎么验证」。
- 可观测取「OTel-first」:核心资产是 OTel GenAI 语义约定 + 三边界打 span(LLM 调用/工具调用/检索),Langfuse 只是 OTLP 后端之一。
- Agent 取「裸循环 + 框架权衡」:能手写 agent loop,能讲清「框架解决的是 checkpoint/HITL/并发,简单场景裸写、复杂状态机才上框架」。

### 非目标(明确不做)

- 算法层:全参微调、RLHF/DPO 实操、分布式训练、手推数学。
- 框架收集:Pydantic AI / OpenAI Agents SDK / Google ADK 保持阅读级(已有材料),不逐个动手。
- 把 07 等概念文档重写成教科书:文档只回填锚点,不扩成大部头。

## 三、总体方案

**实战主战场 = 把 MVP(`ai/langchain/mvp-agentic-rag/`)Plan 2-4 做完 + 三个独立小实验;roadmap 文档只回填薄锚点层。**

每小时投入产出双份价值:既是面试项目叙事素材(亲手数字),又让概念文档落地。否决的替代方案:

- ~~B handson 实验室模式~~(每模块独立实验):玩具实验面试叙事不硬,与 MVP 重复建设,总耗时大。仅保留 MVP 覆盖不到的两个实验(微调、本地部署)。
- ~~C 纯文档工程深化~~:数字是抄的不是跑的,evals 被深挖时依然虚。其工程细节(工具对比、排查 walkthrough)并入回填动作。

## 四、关键决策

### 决策 1:Plan 3 可观测改 OTel-first

MVP Plan 3 的可观测实现从「Langfuse callback 接线」升级为:

- instrument 遵循 **OTel GenAI 语义约定**(`gen_ai.*` span/attribute),手动打 span 或用 OpenInference/OpenLLMetry;
- Langfuse(自托管)作为 OTLP 后端之一,保留设计中已有的 `OBS_BACKEND` 切换;
- 验收新增:同一份 trace 数据切换后端(如 Phoenix)零代码改动,或至少在文档中说明切换路径。

面试话术(同时是真实实现):「我在三个边界打 trace,遵循 OTel GenAI 语义约定,后端走 OTLP 出口,Langfuse/Phoenix/Datadog 可互换。」

### 决策 2:新增「裸循环 agent 对照实验」

- 位置:`ai/agent-loop-lab/`,一个周末量级。
- 内容:裸 OpenAI 兼容 SDK 手写 agent loop(工具 schema → tool call → 执行 → append → 循环),接 1-2 个工具(其中一个走 MCP),**OTel 手动打 span**,Langfuse 看 trace。
- 复刻 MVP 的一个薄切片(简化版 supervisor 路由),产出「同一功能:裸写 vs LangGraph」对比笔记——这是面试架构权衡素材。
- 时机:月 1-2,与 Plan 2(LangGraph agent 图)同期或紧后,对照效果最好。

### 决策 3:微调实操

- 位置:`ai/fine-tuning/`(已有 Unsloth Qwen3-14B notebook + 讲解)。
- 步骤:先原样跑通 → 换成自构数据(默认:MVP 知识库问答风格对齐,可直接复用 MVP 的 golden set 与 judge 做前后对比;若该方向数据难构造,备选托福陪练语料)→ 微调前后用 MVP 的 eval 流程对比,产出前后对比报告。
- 算力:Colab 免费 GPU 或租卡,QLoRA 即可,不需要 A100。

### 决策 4:文档回填规则

每完成一块实战,在对应概念文档**追加一节「实战锚点」**(不改动原有正文结构):

- 必含:亲手跑出的真实数字(幻觉率、judge 与人类一致率、p95 延迟、token 成本等)、指向实战产物的链接(eval 报告、trace 截图、代码)。
- 07 模块额外补:ragas / promptfoo / LangSmith / Langfuse 工具对比一节;2 个从症状到根因的排查 walkthrough(素材取自跑 MVP 过程中的真实问题)。
- 05 模块回填微调:数据构造经验、前后 eval 对比、「什么时候微调 vs RAG」决策树。
- 06 模块回填部署(若做月 5):vLLM 部署参数、量化前后吞吐/显存/质量对比表。

## 五、月度排期(在职节奏,3-6 个月)

| 月 | 主线 | 产出物 | 回填 |
|----|------|--------|------|
| 1-2 | MVP Plan 2(agent 图)+ Plan 3(API + OTel 可观测);裸循环实验 | 可跑的 supervisor/CRAG 图;Langfuse 完整 trace 树;`ai/agent-loop-lab/` + 对比笔记 | 02-agent-tool-use 锚点(裸 loop vs 框架);07/03 监控篇锚点(OTel 三边界) |
| 3 | MVP Plan 4(eval) | `eval/reports/` 真实报告;golden set 扩充;judge 校准记录(与人工抽检一致率);CI 质量门 | **07 全模块锚点 + 工具对比 + 2 个排查 walkthrough**(本计划核心交付) |
| 4 | 微调实操 | 微调前后 eval 对比报告;数据构造笔记 | 05 模块锚点 + 微调决策树 |
| 5(可选) | vLLM 本地部署 + 量化对比 | 部署笔记 + 量化对比表(`ai/local-llm-deploy/`) | 06 模块锚点 |
| 6 | 叙事串联 | 更新 PROJECT-NARRATIVE / interview-qa;走完 08 模块 + interview-paths;简历项目栏更新(填上真实数字) | 09 review-notes 复盘 |

排期原则:每月主线只有一个;月 5 可裁剪;若中途启动面试,跳到月 6 的叙事串联,已完成部分即为素材。

## 六、验收标准(面试达标检验)

完成后应能不查资料回答,且每条都有亲手产物支撑:

1. 「你们的 eval 怎么做的?」→ golden set 规模、维度拆分、judge prompt 长什么样、跑一轮多少钱多久。
2. 「LLM-as-Judge 怎么校准?」→ 与人工抽检的一致率数字、发现过什么 judge 偏差、怎么修的。
3. 「线上质量突然变差怎么排查?」→ 用自己的 trace 树讲一条真实排查路径(症状 → span → 根因)。
4. 「不用 LangChain 怎么写 agent?」→ 手写 loop 的真实经历 + 「框架解决什么」权衡。
5. 「可观测怎么做的?」→ OTel GenAI 约定 + 三边界 span + 后端可换,自托管 Langfuse 演示。
6. 「微调过吗?」→ 一次完整经历:动机、数据构造、QLoRA 配置、前后 eval 对比数字、什么时候不该微调。
7. 「设计一个企业知识库问答系统」→ 用 08 框架 + MVP 真实参数(成本/延迟/容量)作答。

## 七、风险与取舍

- **在职时间波动**:排期按月不按周;每月主线唯一,落后则顺延而非并行追赶。
- **eval 数字不好看**(如幻觉率高):不好看的数字 + 改进动作 = 更好的面试故事,如实记录,不美化。
- **API key / 算力成本**:eval 与微调均需 key/GPU;月 3 前预估单轮 eval 成本并写入报告;微调用免费 Colab 起步。
- **LangGraph 风评风险**:已对冲——裸循环实验 + OTel-first 让叙事不绑定框架;LangGraph 在 2026 年仍是有状态生产 agent 的主流选择之一。

## 八、与既有计划的关系

- MVP Plan 2-4 的实现计划已存在(`docs/superpowers/plans/2026-06-05-agentic-rag-mvp-plan-{2,3,4}-*.md`),本 spec 不重做,仅对 Plan 3 施加决策 1 的修正(写 plan 阶段更新该文件或以增补说明执行)。
- 需要新写 plan 的部分:裸循环实验(决策 2)、微调实操(决策 3)、文档回填(决策 4,可并入各月主线 plan 的收尾步骤)、月 5 部署实验(可选,届时再计划)。
