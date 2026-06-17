# 第0章：LangChain 与 LangGraph — 生态全景与关系（先读这章）

> 学这套东西,90% 的初学者卡在同一个地方:**LangChain 和 LangGraph 到底什么关系?是两个竞品吗?谁取代谁?为什么要装一堆包?为什么教程半年就过时?** 这章先把这张地图铺平,后面每一章你才知道自己站在哪。深水区(为什么有人不爱用 LangChain、跟 provider Agents SDK 怎么选)放在 [`07-agents.md §9`],这里只打地基。

---

## 一、一句话定调:它俩不是竞品,是「同一家公司的分层」

```
❌ 错误心智:LangChain ── 对打 ── LangGraph(选一个)
✅ 正确心智:LangChain   是「楼上」
            LangGraph   是「楼下的承重结构」
            一栋楼,同一家(LangChain Inc.)盖的,分工不同
```

- **LangChain** = 偏**高层**的应用框架(给你 models / prompts / retrievers / 现成 agent 入口)。
- **LangGraph** = 偏**底层**的编排引擎(状态图、循环、分支、持久化、人工介入)。
- **关系**:LangChain 现在的 agent **底层就是用 LangGraph 实现的**;LangGraph 也能**完全脱离 LangChain 单独用**。

> **Java 桥**:像 **Spring Boot(全家桶,开箱即用)vs 一个 workflow/状态机引擎(你自己编排流程)**。不是二选一 —— 你常常 Spring 那层调业务、底下用引擎跑长流程。

---

## 二、生态全景:5 个包,各管一段

`pip install langchain` 之所以让人懵,是因为 LangChain 早就**拆成了一组包**,各司其职:

| 包 | 它是什么 | 你什么时候碰它 |
|---|---|---|
| **`langchain-core`** | **地基**:`Runnable` / LCEL(`\|` 管道)/ `Message` 类型 / 各种基础接口。依赖极少,所有其他包都依赖它 | 几乎一直在用(隐式) |
| **`langchain`** | **高层**:`create_agent`、retrieval 辅助、(历史上的)chains。v1 后变薄,老 chains 多已弃用 | 想要高层快捷入口时 |
| **`langchain-openai` / `-anthropic` / …** | **官方集成(partner 包)**:把某家模型接进统一接口。从 community 拆出来,质量/版本更稳 | 连具体某家模型 |
| **`langchain-community`** | **社区集成**:几百个 vectorstore / loader / tool / 第三方接入 | 连向量库、文档加载器、杂项工具 |
| **`langgraph`** | **编排引擎**:`StateGraph`、节点/边、循环、`checkpointer` 持久化、`interrupt` 人工介入、`prebuilt`(含已弃用的 `create_react_agent`) | 构建有循环/状态/HITL 的 agent |
| **`langsmith`** | **可观测(旁路)**:trace / eval / 调试平台(SaaS + SDK),跟前面是正交的 | 想看「到底发了什么、哪步慢」 |

**关系栈图(从你的应用往下看)**:

```
┌──────────────────────────────────────────────────────┐
│  你的应用                                               │
├──────────────────────────────────────────────────────┤
│  langgraph       编排层:状态图 / 循环 / 持久化 / HITL    │ ← agent 的"骨架"
│  langchain       高层:create_agent、retrieval(变薄了)  │
│  langchain-core  地基:Runnable / LCEL / Message        │ ← 谁都依赖它
├──────────────────────────────────────────────────────┤
│  langchain-openai / -anthropic / -community            │ ← 集成:连模型/向量库/工具
├──────────────────────────────────────────────────────┤
│  langsmith       观测:trace / eval(旁路,不在主链上)    │
└──────────────────────────────────────────────────────┘
              ↓ 真正发 HTTP 请求的
        OpenAI SDK / Anthropic SDK / …
```

> 记住最底下那行:**不管套了几层,真正把字节发给模型的,还是各家 provider 的 SDK。** LangChain/LangGraph 是它上面的「编排 + 集成」层。

---

## 三、最大的坑:「LCEL vs LangGraph」≠「LangChain vs LangGraph」

这两个对比天天被混为一谈,其实是**两个不同维度**的问题:

| | 在比什么 | 两边是 |
|---|---|---|
| **LangChain vs LangGraph** | 两个**包 / 两层** | 高层框架  vs  编排引擎 |
| **LCEL vs LangGraph** | 两种**编程模型(怎么连流程)** | 线性管道 `A\|B\|C`  vs  状态图(节点+边+**环**) |

关键点:**LCEL 属于 `langchain-core`,LangGraph 是另一个包**。所以:

- 「LangChain vs LangGraph」回答的是「**整个高层框架** 和 **编排层** 的分工」。
- 「LCEL vs LangGraph」回答的是「我这段流程,用**直线管道**写,还是用**有环的图**写」。

```
LCEL(线性):    Prompt ─→ LLM ─→ Parser            一条道走到黑
LangGraph(图): LLM ⇄ Tools,带条件分支、能回头     循环 / 分支 / 有状态
```

**一句话**:流程是直的 → LCEL;要循环/分支/状态/人工介入 → LangGraph。(细表见 [`05-lcel-deep-dive.md §10`] 和 [`09-langgraph-core.md §1`]。)

---

## 四、为什么有这么多包、为什么教程半年就烂:演化史

不懂这段,你会被满网过时教程和 deprecation 警告搞疯。一条线讲完:

```
2022 末  LangChain 发布,单体大包(monolith)
   │      靠它补模型的洞:output parser、ReAct 文本解析、prompt 拼装
   ▼
2023     爆火 → 单体包又重又乱、集成几百个挤一起
   │      引入 LCEL(`|` 管道 / Runnable),统一"可组合"范式
   ▼
2024 初  拆包:langchain-core / langchain / langchain-community / partner 包
   │      (这就是你现在看到一堆包的由来)
   ▼
2024     发布 LangGraph:专治 LCEL 表达不了的「循环/状态/HITL」
   │      老 AgentExecutor 那套逐步被劝退,agent 改用 LangGraph 建
   ▼
2025     langchain v1:create_agent(底层=LangGraph),老 chains 退场
```

这条线一次性解释了三件事:
1. **为什么包这么多** —— 单体拆出来的。
2. **为什么教程容易过时** —— 三年里范式换了好几轮(monolith → LCEL → LangGraph → v1)。
3. **为什么 `create_react_agent` 在 `langgraph.prebuilt` 里、却又被 `langchain.agents.create_agent` 取代** —— 它正处在「LangGraph 实现」到「v1 高层入口」的交接点上(这正是 [`07-agents.md §2.1`] 那条弃用警告的根因)。

---

## 五、那我到底该装哪个、用哪个?

**地基版决策**(选型深水区 → [`07-agents.md §9`]):

| 你要做的 | 装 / 用 |
|---|---|
| 调一次模型 / 线性流程(如 RAG 检索→生成) | `langchain-core` + LCEL,或干脆直接 provider SDK |
| 连某家模型 | `langchain-openai` / `langchain-anthropic` |
| 连向量库 / 文档加载器 / 杂项工具 | `langchain-community` |
| 有**循环/分支/状态/人工介入**的 agent | `langgraph` |
| 想要现成的高层 agent 入口 | `langchain` 的 `create_agent`(底层还是 langgraph) |
| 看 trace / 做 eval | `langsmith`(或开源的 Langfuse,见 [`11-production.md`]) |

**一个现代最小 agent,常常只要两个包**:

```bash
pip install langgraph langchain-anthropic   # 编排 + 一家模型,够跑一个 agent
# 注意:你甚至可以不装顶层的 `langchain`
```

---

## 六、这套笔记的地图:每章落在全景的哪一层

| 章 | 主题 | 落在全景的 |
|---|---|---|
| `02`–`04` chat models / prompts / parsers | 统一调用、prompt、结构化输出 | **`langchain-core` 地基** |
| `05` LCEL | `\|` 管道编程模型 | `langchain-core` 的编程范式 |
| `06` tool calling | 让 LLM 调工具 | core + 模型原生能力 |
| `07` agents | ReAct / 架构家族 / **选型(§9)** | `langgraph.prebuilt` |
| `08` RAG | 检索增强 | `langchain` + `community` 集成 |
| `09`–`10` LangGraph 核心 / 进阶 | 状态图、持久化、HITL、子图 | **`langgraph` 编排层** |
| `11` 生产化 | trace / eval / 部署 | `langsmith` / Langfuse |
| `12` 多 Agent | supervisor / swarm | `langgraph` |

> 读法建议:**先读本章建立全景 → `02`–`06` 打 core 地基 → `07` agents → `09`–`10` 进 LangGraph → `11`–`12` 生产与多 agent。** 顺序也是 [`01-langchain-learning-path.md`] 的路线。

---

## 七、面试高频问答

> **Q: LangChain 和 LangGraph 是什么关系?是不是 LangGraph 取代了 LangChain?**
>
> A: 不是取代,是**分层**。同一家公司:`langchain-core` 是地基(Runnable/LCEL/Message),`langchain` 是高层框架(变薄,老 chains 已弃用),**`langgraph` 是底层编排引擎**(循环/状态/持久化/HITL)。现在 LangChain 的 agent 底层就用 LangGraph 实现;LangGraph 也能脱离 LangChain 单独用。

> **Q:「LCEL vs LangGraph」和「LangChain vs LangGraph」是一回事吗?**
>
> A: 不是。「LangChain vs LangGraph」比的是**两层/两个包**(高层框架 vs 编排引擎);「LCEL vs LangGraph」比的是**两种编程模型**(线性管道 vs 有环状态图),而 LCEL 本身属于 `langchain-core`。流程是直的用 LCEL,有循环/分支/状态用 LangGraph。

> **Q: 一个新项目你会装哪些包?为什么这么多包?**
>
> A: 现代最小 agent 常常只要 `langgraph` + 一个模型 partner 包(如 `langchain-anthropic`),顶层 `langchain` 都未必需要。包多是因为它从 2022 的单体大包**拆**出来了:core(地基)/ langchain(高层)/ community + partner(集成)/ langgraph(编排)/ langsmith(观测),各自独立版本,避免一个巨包牵一发动全身。

---

## 八、一句话记忆

- **不是竞品,是分层**:`core`(地基)→ `langchain`(高层,薄了)→ `langgraph`(编排骨架);`partner/community`(集成)、`langsmith`(观测)在旁边。
- **两个对比别混**:`LangChain vs LangGraph` = 框架 vs 编排层;`LCEL vs LangGraph` = 直线管道 vs 有环图。
- **最底下永远是 provider SDK 在发请求**;LangChain/LangGraph 是它之上的编排+集成层。
- **选型深水区**(为什么有人不爱用 LangChain、vs provider Agents SDK 怎么选)→ [`07-agents.md §9`]。

---

> **本章掌握后,你应该能**:一句话说清 LangChain 与 LangGraph 的分层关系、辨明「LCEL vs LangGraph」和「LangChain vs LangGraph」两个不同问题、知道一个新项目该装哪几个包,并能在脑子里把后面每一章定位到这张全景图上。
