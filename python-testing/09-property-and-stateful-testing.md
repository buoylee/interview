# Property 与 stateful testing：从样例到状态空间

## 核心问题

命名样例擅长证明已知业务故事，却很难枚举金额、币种大小写和状态转移序列。Property test 的目标不是生成很多随机单测，而是声明对一类输入都成立的不变量；stateful test 再把输入空间提升为操作序列空间。本章用 Hypothesis 检查 `Money` 规范化，并用独立 reference model 检查 `Order` 的状态、支付引用和版本。

生成测试不会替代 `test_paid_order_cannot_fail_payment` 这类具名业务样例。具名测试保存需求语言并快速定位；property/state machine 寻找作者没有预先想到的输入和顺序。二者承担不同 oracle。

## 直觉模型

一个 property test 是 `strategy → SUT → invariant`。Strategy 定义合法数据域，SUT 执行业务逻辑，invariant 判定关系而非某个固定答案。State machine 则是 `当前模型状态 → 可用规则 → SUT 与模型同步演进 → 每步比较`。

好的 property 常来自：

- 不变量：金额始终为正、币种始终为三位大写字母；
- 往返关系：encode 后 decode 得到等价值；
- metamorphic relation：改变输入表示但不改变语义，例如 `usd`、`Usd` 与 `USD` 规范化后相同；
- reference model：简单、独立且明显正确的模型与生产实现逐步一致。

## 机制深入

Hypothesis 先生成数据，发现失败后 shrink 到仍失败的更小样例。本 lab 的 `tests/property/conftest.py` 注册两个 profile：本地 `dev` 跑 25 examples，并把样例保存在 `.hypothesis/examples`；存在 `CI` 环境变量时加载 `ci`，跑 100 examples、关闭 deadline、启用 `print_blob`，并用 `derandomize=True` 得到稳定生成顺序。Hypothesis 不允许 deterministic mode 同时启用 example database，因此 CI 明确使用 `database=None`。本地数据库路径相对 `python-testing/lab/`，不应提交；它是加速再发现的缓存，不是唯一 regression test。

失败输出若包含 blob，会给出一个 `@reproduce_failure(...)` decorator。把它暂时贴到失败 property 的 `@given` 上方即可精确重播；确认问题后删除 decorator，让测试继续探索完整输入域。当前安装版本不提供 `--hypothesis-replay` CLI，不能把 blob 当命令行参数。

```bash
uv run pytest tests/property/test_order_properties.py -q
```

固定 seed 可用于临时诊断，但不能把 seed 当长期正确性保证；环境、Hypothesis 版本或 strategy 改动都会改变生成轨迹。长期证据应是保留 property、最小具名 regression test，必要时才保存 `@example`。

Strategy 应通过组合直接构造合法域。本章金额用有界、两位小数 `Decimal`，币种用有限枚举；支付引用使用排除控制符、分隔符的字符域，不用大量 `.filter()`。过滤和 `assume()` 会丢弃已生成数据，拒绝率高时触发 health check，也浪费探索预算。不要全局 suppress health checks；先重写 strategy，只有能够解释的局部算法限制才局部处理。

Deadline 检测异常慢的单例，适合本地提醒；共享 CI 容易受调度噪声影响，因此 CI profile 明确 `deadline=None`，但仍用套件时长预算治理性能。Shrinking 会重复执行测试，所以测试必须可重入、隔离外部状态，不依赖随机数或当前时间。

## 设计取舍

Reference model 必须比 SUT 简单且独立；复制 production 条件只会制造同源错误。本章模型只保存 `status/reference/version`，production 则保留完整 `Order`。每条 rule 用 precondition 表示模型允许的合法动作；另设非法动作 rule，要求 production 抛出 `InvalidOrderTransition`。若只生成合法动作，「PAID 后错误允许 decline」不会被调用，也就无法发现 guard 被放宽。

Bundles 适合让后续规则复用前面创建的动态对象，例如多订单、多支付引用；本例只有一个 aggregate，加入 bundle 只会扩大无意义状态。规则数、对象数和步数相乘会造成 state explosion，应先选高风险操作、缩小数据域、拆分独立状态机，再提高 examples/step count。

不适合 stateful testing 的情况包括：流程只有一条固定路径、oracle 本身比 production 更复杂、每步依赖昂贵或不可重置的外部系统，以及失败无法稳定重播。此时优先具名 component/integration test，或先抽出纯状态核心。

## 贯穿 lab

可执行文件是：

- `tests/property/test_order_properties.py`：组合 `Decimal` 与 currency strategies，验证值保持及大写规范化；
- `tests/property/test_order_state_machine.py`：`RuleBasedStateMachine` 建立、支付开始、批准、拒绝及非法操作，并在每步比较 reference model；
- `tests/property/conftest.py`：集中配置 dev/CI profile，不改变全局 health-check policy。

生成的 unittest `TestCase` 类本身附加 `property` marker，因此下列 marker 选择会同时收集普通 property 与状态机：

```bash
uv run pytest -m property -q --hypothesis-show-statistics
```

## 故障工单

症状一：把 `Money.__post_init__` 的 `.upper()` 临时改为 `.lower()`。Property 立即失败，并给出最小反例 `amount=Decimal('0.01'), currency='usd'`。恢复 `.upper()` 后 property 通过；这证明测试观察的是规范化行为，而非只执行代码。

症状二：临时放宽 `mark_payment_failed`，允许从 `PAID` 转入失败。过去的具名样例覆盖成功和失败路径，却没有组合「成功后又收到失败事件」。State machine shrink 为四步失败工单：

1. 建立 `PENDING_PAYMENT` 订单；
2. `start_payment()`；
3. `approve(reference='0')`；
4. `reject_decline_outside_payment()` 预期异常，但 production 未抛出。

这条短序列既说明缺陷，也说明为何 reference model 必须生成非法动作。恢复严格 guard 后，状态、reference 与 version 三项逐步一致。Property 输出中的最小样例是诊断证据；修复后的状态机和具名业务测试才是永久 regression evidence。

## Java/Go 对照

Java 的 jqwik/QuickTheories 与 Hypothesis 都把 generator、property、shrinking 分离；JUnit parameterized test 更接近有限样例表，不自动探索和 shrink。模型测试可用 jqwik stateful API 或显式 command model，但仍要避免复制 production 状态机。

Go 的 `testing/quick` 与原生 fuzzing 能探索输入并持久化 corpus，但复杂业务对象通常需要自定义 generator；状态序列往往用 command slice 加 reference model 手写。无论语言，关键不是随机框架，而是可解释的数据域、独立 oracle、可重播失败与层级边界。

## 验收与面试卡

验收命令：

```bash
uv run pytest tests/property -q --hypothesis-show-statistics
CI=1 uv run pytest tests/property -q --hypothesis-show-statistics
uv run pytest tests/unit tests/component tests/contract tests/property -q
```

面试速答：

- **Property test 与参数化测试差异？** 参数化列出作者已知的有限案例；property 声明输入域与不变量，由引擎探索并 shrink 未预见案例。
- **Shrinking 为什么重要？** 它把复杂随机失败变成短、可解释、可转成 regression ticket 的反例；前提是测试确定、隔离且 oracle 稳定。
- **如何设计 stateful model？** 只保存判定业务不变量所需的最小状态，用 precondition/rule 描述动作，用 invariant 每步比较，并显式生成非法动作。
- **何时不该用？** 当状态空间风险低、reference model 不独立、外部状态难重置或具名例子已提供更快更清楚的证据时。
