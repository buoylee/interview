# 10 测试套件可靠性与规模

## 核心问题

大型套件的目标不是“偶尔全绿”，而是每次失败都可信、可复现、可归属。flaky 的来源至少分六类：产品竞态、测试竞态、环境漂移、clock/random 不受控、外部依赖，以及资源耗尽。自动 rerun 会把这些风险改写成概率，不能成为修复。

## 直觉模型

把测试看成并发执行的租户：每个租户必须拥有自己的可变对象、临时路径、端口与 UUID；共享能力只能是只读资源或显式隔离的 factory。速度预算也按反馈环分层：fast 层守本地秒级反馈，integration/E2E 单独报告，不用一个全局平均值掩盖长尾。

## 机制深入

pytest-xdist 的 worker 是独立进程；session fixture 是“每个 worker 一份”，不是整个运行一份。异步任务并发发生在一个 worker 的 event loop 内，与多 worker 并行是两层不同调度。固定端口、共享文件名和进程级 singleton 都会在 `-n 2` 下暴露所有权错误。

coverage 记录代码是否执行；branch coverage 进一步暴露未走过的分支，但都不证明断言正确。mutation testing 改写已执行逻辑，只有 oracle 能杀死行为不同的 mutant。mutation score 受等价 mutant、工具能力与选择范围影响，不能游戏化为单一 KPI。

本 lab 使用 mutmut 3.6。它会跳过带 `@dataclass` 的整个类，因此金额与新订单验证被提取为私有纯验证函数：这同时把规则从数据容器中分离成可独立推理的 seam，领域 API 不变，mutation 仍限定在 `order_service.domain.order`。

## 设计取舍

测试选择应从风险与变更面出发：PR 先跑 fast，数据库和 E2E 由显式 marker 选择。warning 默认应被看见，项目代码的 `RuntimeWarning` 升格为 error；不能 blanket suppression。慢测试先用 `--durations` 找证据，再决定拆层、减少 setup 或优化实现。

quarantine 只是一份有期限的风险登记：必须记录 owner、故障链接、隔离理由、expiry 与退出条件；到期仍未修复就使构建失败。禁止无 owner 的永久 skip、非严格 xfail、自动 retry 和任意 sleep。

## 贯穿 lab

顺序标本在 `lab/scenarios/order-dependency/`：声明顺序 `2 passed`，反序稳定得到 `assert [] == ['seed']`。mutation 标本在 `lab/scenarios/mutation/`：弱测试即使让 `fee.py` 达到 100% line coverage，也无法发现乘法变加法；精确金额 oracle 会失败。

fast suite 使用：

```bash
uv run pytest tests/unit tests/component tests/contract tests/property -n 2 -q --durations=10
```

本次结果为 `129 passed in 1.28s`；最慢节点是验证 function-scoped factory 的隔离测试。branch report 为 82%，未覆盖的 SQLAlchemy adapter 是明确需要 Docker 的 integration 风险，另有 HTTP 错误分支与少量 worker/process-payment 分支需要按业务风险补证据，而不是为了百分比伪造测试。

正式 mutation 共 26 个：21 killed、5 survived。逐一 `mutmut show` 后，五个 survivor 只在完整异常消息两端加入 `XX`；异常类型、触发条件与测试所依赖的语义片段都不变。完整文案不是本领域 API contract，因此它们被记录为 message-only、non-actionable survivors，而不是增加脆弱的全文比对来追求 100%。时间规则另有真实 survivor 风险：仅检查 `tzinfo is not None` 会接受 `utcoffset() is None`；针对该语义先得到 `DID NOT RAISE`，再改为检查 `created_at.utcoffset()`。

## 故障工单

症状：单独运行通过，反序失败。证据：`test_expect_seed` 在 `test_seed` 前运行时看到空 list。假设：模块全局状态跨测试泄漏。定位：同一 Python 进程复用已 import 的 `state` 模块。修复：真实套件不共享可变领域实例，fixture 返回无状态 factory/function，每次调用创建新对象；端口用系统分配，路径用 worker 私有临时目录，UUID 由测试拥有。

失败 artifact 至少保留 nodeid、seed、worker、环境版本、耗时、完整 traceback 与相关日志。套件观测应持续跟踪 p50/p95、最慢节点、flaky 率、quarantine 年龄、warning 与失败分类，而不只展示测试总数。

## Java/Go 对照

JUnit 5 parallel execution 与 Gradle fork 同样会放大 static state；Spring context cache 也不等于测试数据隔离。Go 的 `t.Parallel()` 要求 subtest 不捕获共享循环变量，`-race` 能找数据竞态但不能替代业务 oracle。三者共同原则都是先修资源 ownership，不是关闭并行。

## 验收与面试卡

- 如何处理 flaky？先分类并最小化复现，修 ownership/时钟/依赖；不以 rerun 掩盖。
- coverage 100% 为什么仍不够？它证明执行，不证明结果被断言；mutation 标本的弱测试就是反例。
- xdist 为何暴露 fixture 问题？worker 是独立进程，session fixture 每 worker 实例化，共享外部名字仍会冲突。
- survivor 怎么处理？逐一查看 diff；非等价 survivor 先用 mutation 证明新测试 RED，再恢复实现 GREEN；等价项附理由，不改生产语义骗分。
- quarantine 最低字段？owner、issue、原因、expiry、退出条件和失败 artifact。
