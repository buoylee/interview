# 07 代码实验室路线图

## 目标

本章只定义后续可运行 Java 验证实验室的工程路线，不直接创建代码、不引入依赖、不绑定版本。它回答：如果下一阶段要把文档实验室落成代码，应该如何分层，以及每一层应该验证什么。

这个路线图仍然属于 `verification-lab` 文档阶段。当前阶段不创建工程、不查 API、不绑定 JUnit 5、jqwik、Testcontainers 或任何基础设施版本。

## 推荐未来 Java 结构

未来如果进入代码阶段，可以先从纯内存模型开始：

```text
verification-lab/
  model/
    Command
    Event
    Fact
    History
    State
    InvariantViolation
  oracle/
    StateMachineOracle
    LedgerOracle
    ExternalFactOracle
    PropagationOracle
    ManualRepairOracle
  generator/
    TransferHistoryGenerator
    PaymentHistoryGenerator
    OrderHistoryGenerator
    TravelHistoryGenerator
  runner/
    PropertyTestRunner
    FaultInjectionRunner
    HistoryReplayRunner
  scenarios/
    transfer/
    payment/
    order/
    travel/
```

这套结构的优先级是：先让 Command、Event、Fact、History 和 InvariantViolation 能表达一段异常历史，再让 oracle 独立判定不变量，最后才让 runner 组织生成、注入和回放。

## 模块职责

| 模块 | 职责 | 不负责 |
| --- | --- | --- |
| model | 表达 Command、Event、Fact、History、State 和 InvariantViolation | 不连接数据库，不调用生产服务 |
| oracle | 用独立规则检查不变量并输出 InvariantViolation | 不复用生产业务代码，不执行业务 Command |
| generator | 生成重复、乱序、超时、宕机、迟到回调和人工修复等异常 History | 不判断测试是否通过，不直接修改生产事实 |
| runner | 运行属性测试、故障注入和历史回放，并报告最小或 reduced failure History | 不保存生产 Fact，不替代对账或人工复核 |
| scenarios | 放置转账、支付、电商、旅行的领域样例和实验输入 | 不绑定真实 Kafka、Temporal、数据库或渠道 API |

Oracle 必须独立于生产代码。否则测试会重复生产逻辑里的同一个缺陷，只能证明两套代码犯了同样的错。StateMachineOracle、LedgerOracle 和 ExternalFactOracle 应该读取 History 里的 Fact，并给出被破坏的不变量、相关 Fact 和定位边界。

## 技术候选

| 技术 | 未来用途 | 当前阶段动作 |
| --- | --- | --- |
| JUnit 5 | 基础测试框架和报告入口 | 只记录候选，不引入 |
| jqwik | Java 属性测试，用于生成异常 History 和 shrinking | 只记录候选，不查 API，不绑定版本 |
| Testcontainers | 后续接入数据库、Kafka 或 Temporal test server | 只记录候选，不创建工程 |
| Spring Boot test slice | 未来验证服务边界或 adapter 层 | 只记录候选，不引入依赖 |
| JSON report + Markdown report | 输出 reduced failure History、InvariantViolation 和 oracle 结论 | 后续代码阶段再定义格式 |

技术顺序不能反过来。未来 infra 如 Kafka、Temporal、DB、Testcontainers 应该在纯模型、oracle、generator 和 runner 已经跑通后再接入。否则学习重点会从金融一致性验证变成环境搭建。

## 第一批可运行实验建议

未来进入代码阶段时，优先实现这些实验：

1. 内部转账幂等和 LedgerOracle 账本平衡。
2. 支付超时后迟到成功回调，由 StateMachineOracle 和 ExternalFactOracle 判断本地 Fact 是否可解释。
3. Outbox publisher 崩溃后恢复发布，检查传播 Fact 和消费者处理记录。
4. 消费者重复消息不重复业务效果，要求 runner 输出最小失败 History。
5. TCC Cancel 先于 Try，以及 Confirm/Cancel 并发，检查双终态是否产生 InvariantViolation。
6. Temporal Activity 外部成功但 completion 未记录后的重试幂等，只把 workflow history 当执行线索。
7. CDC offset 回退导致投影重复，检查读模型不能倒退或触发重复副作用。
8. 人工修复命令重复提交，检查审批、修复 Fact、账本调整和复核结果是否可解释。

第一批实验不需要真实 Kafka、Temporal、DB 或外部渠道。PropertyTestRunner 可以先调用纯内存 generator，FaultInjectionRunner 可以先在 History 中插入 Fault，HistoryReplayRunner 可以先重排已有 Command、Event 和 Fact。

## 设计约束

- 测试模型不能依赖真实生产数据库。
- Oracle 不能调用真实外部渠道，也不能复用生产服务代码。
- Generator 只生成异常 History，不直接修改事实。
- Runner 必须报告最小或 reduced failure History、随机种子或可重放参数、被破坏的不变量和 InvariantViolation。
- 所有未来代码都要能解释失败，而不是只输出 assertion failed。
- Future infra such as Kafka, Temporal, DB and Testcontainers must come after pure model/oracle verification works.
- 当前文档阶段不创建代码、不引入依赖、不查 API、不绑定版本。

## 危险误用

| 误用 | 后果 | 正确做法 |
| --- | --- | --- |
| 一开始接入真实 Kafka、Temporal 和数据库 | 学习者被基础设施复杂度淹没，忽略事实和不变量 | 先做纯模型、独立 oracle、异常 History 生成器和 runner |
| 复用生产服务代码做 oracle | 测试重复生产 bug，无法发现同源设计缺口 | oracle 用独立判定规则，只读取 History 和 Fact |
| 只写 JUnit 5 happy path | 只能证明正常流程能跑，无法发现异常 History 问题 | 先实现异常 History 生成器，再接入 JUnit 5 报告入口 |
| 让 generator 判断通过失败 | 生成和判定耦合，反例难以解释 | generator 只生成 History，oracle 输出 InvariantViolation |
| runner 只打印 assertion failed | 定位成本高，面试表达也空泛 | runner 输出 reduced failure History、violated invariants 和 oracle 结论 |
| 过早绑定 jqwik 或 Testcontainers API | 文档阶段变成框架教程，后续版本变化会污染路线图 | 只记录技术候选，代码阶段再查文档和选版本 |
| 把路线图当实现完成 | 没有可运行验证能力 | 后续单独开代码实现阶段，并按纯模型到 infra 的顺序推进 |

## 输出结论

代码实验室应从纯模型开始，先把 Command、Event、Fact、History、InvariantViolation 和 oracle 跑通，再逐步接入 PropertyTestRunner、FaultInjectionRunner 和 HistoryReplayRunner。runner 的核心产物不是绿色测试数量，而是最小或 reduced failure History、violated invariants、InvariantViolation 和具体 oracle 结论。

只有当纯模型、独立 oracle、异常 History generator 和 runner 都能解释失败后，才适合考虑 JUnit 5、jqwik、Testcontainers、Kafka、Temporal 或数据库。这样代码实验室才会服务于金融一致性验证，而不是被基础设施本身主导。
