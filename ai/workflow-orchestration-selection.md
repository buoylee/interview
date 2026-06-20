# 工作流 / 任务编排选型:Celery · Airflow · Prefect · Dagster · Temporal

> **一句话**:这五个**不是同一个工作的五个选项**,它们分属三类问题。选型第一步永远是先认清「我是哪一类问题」,认错类比选错工具更致命。
>
> **谁该读**:后端工程师在做「要不要上一个编排/队列系统、上哪个」的决策时。配套深挖见文末交叉链接。

---

## 0. 最重要的一张表:先分三类

| 类别 | 解决的问题 | 触发方式 | 谁的地盘 | 工具 |
|---|---|---|---|---|
| **任务队列** Task Queue | 把一个函数从请求路径上挪走,后台异步跑 | 事件 | 应用开发者 | **Celery** |
| **数据 / 工作流编排** Orchestration | 排程化的数据管线,步骤间有 DAG 依赖 | **定时**为主 | 数据工程师 | **Airflow / Prefect / Dagster** |
| **持久化执行** Durable Execution | 长时间、有状态、跨服务、必须撑过崩溃的业务流程 | 事件 | 应用开发者 | **Temporal** |

> **Java/Go 桥**:
> - Celery ≈ RabbitMQ consumer / Spring `@Async` / Go 的 worker pool 吃 channel
> - Airflow/Prefect/Dagster ≈ 数据团队的 ETL 调度器,Java 圈没有完全对位的(硬要说像 Quartz + 一堆胶水)
> - Temporal ≈ Cadence(同源)/ Camunda / Netflix Conductor —— 工作流引擎,JVM 圈的老熟人

**所以选型不是「哪个工具好」,而是「我是哪一类问题」。** 把这一步做对,后面就只剩同类内部的取舍。

---

## 1. 决策树

```
你的本质需求是……

┌─ 「把这个函数从请求路径上挪走,后台跑」
│   (发邮件、缩图、转码、异步处理上传)
│   → 任务队列 → Celery(轻量也可 RQ / 云原生 SQS+worker)
│   可靠性模型 = 「任务失败就重试」,它不记得自己在多步流程的第几步
│
├─ 「排程化的数据管线」
│   (定时从多源拉数据 → 转换 → 写仓库,步骤有依赖)
│   → 编排三选一,差别在哲学:
│      • Airflow  = 时间驱动 DAG 调度器,业界标准,生态最大,但又重又难运维
│      • Prefect  = Pythonic 版 Airflow,运行期动态 DAG,本地开发体验好
│      • Dagster  = 资产导向(software-defined assets),血缘/数据质量优先
│
└─ 「长时间、有状态、必须撑过崩溃的业务流程」
    (订单履约、支付 saga、跨天 onboarding、微服务编排+补偿、等人工审批)
    → Temporal:代码写得像永不失败,引擎持久化每一步,崩溃后 replay 回到精确状态
```

---

## 2. 五个工具,各一段(选它当什么 / 别拿它当什么)

### Celery —— 任务队列
- **选它当**:Web 后端的异步任务池。发请求、丢队列、worker 消费、失败重试。
- **别拿它当**:多步业务流程的**编排者**。你可以用 chain/chord 串 5 步,但分支、部分失败恢复、幂等、可观测性全得自己手刻,等于重造 Temporal/Prefect 给你的东西。
- **底层**:你要自己准备 broker(Redis/RabbitMQ)和 result backend。任务是「一个带重试的函数」,**没有跨步骤的流程记忆**——这是它和 Temporal 的根本分界。

### Airflow —— 数据编排的老牌标准
- **选它当**:企业既有环境、整合需求多、要写进简历的「安全答案」。Operator/Connector 生态最庞大。
- **别拿它当**:事件驱动的应用业务流。它是**时间驱动**(`schedule_interval`),受众是数据工程师。「用户上传即处理」这种事件流上 Airflow 是削足适履。
- **底层**:有中心 scheduler + metadata DB + executor,调度有秒级延迟,DAG 是静态定义(动态 task mapping 较新且受限)。重,运维成本高。

### Prefect —— Pythonic 的现代编排
- **选它当**:从零起步、团队小、要好的开发体验;需要**运行期动态 DAG**(循环数、分支由数据决定)。
- **别拿它当**:需要「函数中断处精确续跑」的强持久化场景——它的恢复是 **task 级**粗粒度(整个 task 重来),不是 Temporal 的逐行 replay。
- **底层**:Flow 就是加 `@flow`/`@task` 装饰器的普通 Python 函数;result caching 可跳过已完成步骤;混合执行(控制面托管、计算在你机器上)。比 Airflow 轻得多。

### Dagster —— 资产 / 血缘优先
- **选它当**:在**建数据平台地基**,重视数据血缘、类型、测试、数据质量。
- **别拿它当**:应用业务工作流,或只想跑几个异步任务。它的心智模型是「我想要哪些数据资产存在」,不是「我要跑哪些 task」。
- **底层**:software-defined assets——你声明资产及其依赖,引擎反推该跑什么。内建 lineage、可观测性、分区(partition)与物化(materialization)概念。

### Temporal —— 持久化执行引擎
- **选它当**:长时间、有状态、跨服务、必须撑过崩溃、需要幂等与补偿(saga)、会等人工/等回调的业务流程。
- **别拿它当**:简单的「后台发个邮件」(杀鸡用牛刀),或纯数据 ETL 管线(那是 Airflow 系的活)。
- **底层**:**durable execution**。Workflow 代码写得像永不失败,引擎把每一步存进 workflow history;worker 崩溃后**重放历史**恢复到精确状态。Activity(真正有副作用的步骤,如调外部 API)各带重试策略 + 超时 + heartbeat。代价:要跑 Temporal 集群,或用 Temporal Cloud——运维不轻。

---

## 3. 关键对比(面试常问)

| 对比 | 区别一句话 |
|---|---|
| **Celery vs Temporal** | Celery 任务 = 一个带重试的函数,无流程记忆;Temporal = 整个多步流程都持久,崩溃后从下一行续跑,能做 saga、等人工、睡 30 天 |
| **Airflow vs Temporal** | Airflow = 数据工程师的**批次、定时**数据管线;Temporal = 应用开发者的**事件触发**业务流程。受众与触发模型都不同,别混 |
| **Airflow vs Prefect vs Dagster** | 同一个工作不同信仰:Airflow=task/排程老牌,Prefect=Pythonic 动态 flow,Dagster=asset/血缘优先 |
| **Prefect vs Temporal** | 都能跑多步带重试的流程;Prefect 恢复是 **task 级**(粗、易运维),Temporal 是**逐行 replay**(细、强一致、运维重) |

---

## 4. 实战范例:视觉 LLM 批改试卷流(4~5 步)

> 这是触发本文的真实场景。它最能体现「先分类再选型」,也暴露一个容易踩的坑:**别把两层混为一谈**。

### 4.1 先看清:这里其实有「两层」

如果你的 stack 是 LangChain/LangGraph,「4~5 步工作流」混了两件事:

1. **LLM 步骤编排层**——这 5 步的逻辑、步骤间的 state、分支。这是 **LangGraph** 的本职(它本就为「多步 LLM 流程 + checkpointing」而生,自带持久化 state)。
2. **生产可靠性层**——跨崩溃的重试、幂等、批次扇出、限流、上千份卷的可观测性。这才是 **Celery / Temporal / Prefect** 的战场。

> **一份卷、请求内跑完** → LangGraph 自己可能就够了。
> **要扛批量与崩溃恢复** → 才在底下加编排/持久化层。**批改逻辑的图 → LangGraph;撑生产规模 → 才需要这五个之一。**

### 4.2 把 5 步摊开,关键全在风险点

| 步骤 | 风险点 |
|---|---|
| 1. 收卷(上传扫描件) | **事件触发**(老师上传),不是排程 |
| 2. 前处理(切题、去斜、OCR 学号) | 一般 |
| 3. **视觉 LLM 批改** | 慢、会 timeout、有 rate limit、**会失败、要花钱** |
| 4. 汇总计分 / 标记边界分 | 可能要**人工复核**(human-in-the-loop) |
| 5. 写库 / 出报告 / 通知 | 一般 |

致命需求是这三个:
- **幂等**:第 4 步挂了,不能把第 3 步重跑一遍 → 重复调 LLM = 重复烧钱。
- **崩溃续跑**:worker 崩溃后从第 4 步继续,不是整份卷从头来。
- **批次扇出 + 限流**:一个班 40 份、一场考试上千份,要并发跑又得守住 LLM 的 rate limit。

「多步 + 有状态 + 外部调用很脆 + 必须撑过崩溃 + 幂等」—— 这就是 **Temporal 的教科书定义**。

### 4.3 选型结论

**首选 Temporal**,对应关系很干净:
- Workflow = 一份卷的 5 步流程
- 每步 = 一个 Activity,各自带重试策略 + timeout(LLM 那步给大 timeout + heartbeat)
- **Workflow ID = 卷的 ID → 自动去重/幂等**
- 第 4 步崩 → 从第 4 步续跑,1~3 不重跑 → **不会重复烧 LLM 的钱**
- 批次 = N 个 workflow(或 child workflow per paper),worker 并发数天然当限流阀
- 边界分人工复核 = 用 signal 注入

**务实轻量版 Prefect**:5 个 task 的 flow,每 task 各自重试 + result caching(跳过已完成步骤),API/webhook 触发。运维比 Temporal 轻很多。代价是「续跑」为 task 级粗粒度——只要每步尽量做成幂等,对批卷这种场景通常**刚刚好**。

**不选另外三个的理由**:
- **Airflow** ❌ 给数据工程师的排程化批次管线,触发模型(时间驱动)和受众都不对。除非公司已在跑 Airflow。
- **Dagster** ❌ 资产/血缘导向,为建数据平台而生,不是应用业务工作流。
- **只用 Celery** ⚠️ 你会重造编排层。Celery 更适合当**底层执行 worker**(那个真正去调 LLM 的池子),而不是 5 步流程的**编排者**。

### 4.4 一句话决策(可直接抄)

> **LangGraph 写批改逻辑的图,底下用 Temporal 撑生产可靠性**;不想扛 Temporal 运维就换 **Prefect**;规模还小、就十几人团队,先 **LangGraph + Celery worker** 起步,等「重复烧钱 / 批次恢复」开始痛了再上 Temporal。

**翻盘这个决定的唯一变量 = 规模 × 崩溃代价**:卷量上千、重跑一步就重烧一次 LLM 账单 → Temporal 的幂等与续跑值回票价;卷量几十、重跑无所谓 → 别过度工程,LangGraph + 一个 Celery 队列就够。

---

## 5. 速查:一句话收尾

> **Celery 跑「任务」,Airflow/Prefect/Dagster 跑「数据管线」,Temporal 跑「业务流程」。**
> 先问自己跑的是哪一种,选型就只剩同类内的取舍了。

| 你的处境 | 默认选 |
|---|---|
| 后端日常异步任务(发信、转码) | **Celery** |
| 公司要建数据管线、要简历安全答案 | **Airflow** |
| 从零起步、团队小、要好 DX | **Prefect**(数据平台思维则 Dagster) |
| 跨服务长流程、saga、工作流引擎 | **Temporal** |
| 多步 LLM 流程的**逻辑**本身 | **LangGraph**(底下再按上面选编排层) |

---

## 交叉链接

- [`ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md`](./ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md) —— Agent 为什么需要 durable execution、workflow/graph/持久化状态怎么组合
- [`langchain/09-langgraph-core.md`](./langchain/09-langgraph-core.md) —— LangGraph 状态图、循环、持久化(本文「LLM 步骤编排层」的实现)
- [`langchain/11-production.md`](./langchain/11-production.md) —— LangChain/LangGraph 生产化关注点
- [`../financial-consistency/05-patterns/05-temporal.md`](../financial-consistency/05-patterns/05-temporal.md) —— Temporal 在金融长流程/saga/对账里的深挖
