# 何时 property／stateful testing 能发现样例遗漏的缺陷？

## 30 秒回答

当风险存在于大输入域、表示变换或操作序列时，生成测试比继续手列样例更有价值。property test 定义 strategy、SUT 与 invariant；stateful test 再用独立 reference model 逐步比较状态。Hypothesis 的核心收益不是随机数量，而是探索未预见组合并 shrink 成最小、可重播的反例。

## 机制

strategy 应直接生成合法域，避免大量 filter/assume。property 可以来自不变量、round-trip、metamorphic relation 或 reference model。state machine 用 precondition 限制合法动作，也必须主动生成非法动作，否则 guard 被放宽的缺陷不会被调用。每条 rule 后比较最小模型状态与生产对象；模型若复制 production 条件，就会产生同源 oracle 错误。

## lab 生产案例

[`test_order_properties.py`](../lab/tests/property/test_order_properties.py) 组合两位 Decimal 与 currency strategy，验证值保持和大小写规范化；[`test_order_state_machine.py`](../lab/tests/property/test_order_state_machine.py) 生成开始支付、批准、拒绝、重放和非法转换序列，并逐步比较 status、reference、version。曾放宽 PAID 后失败 guard 时，Hypothesis shrink 成四步可解释序列。

## 取舍／反例

具名样例仍保存业务语言和已知事故；property 不应取代它们。若 oracle 比 production 更复杂、外部系统昂贵且无法重置、流程只有一条固定路径，stateful testing 可能增加噪声。固定 seed 与 example database 是诊断辅助，不是永久证据；修复后应保留 general property，并在高价值事故上增加具名 regression。

## 追问

- 为什么 CI 的 derandomize 模式与 example database 不能同时启用？
- shrinking 对测试可重入性和外部状态提出什么要求？
- 怎样判断一个 mutation 应补 property、state machine 还是具名样例？
- 如何控制 rules × objects × steps 造成的 state explosion？

## 证据链接

- 章节：[property 核心问题](../09-property-and-stateful-testing.md#核心问题)、[shrinking 与 profile](../09-property-and-stateful-testing.md#机制深入)、[reference model 取舍](../09-property-and-stateful-testing.md#设计取舍)
- Production：[`order.py`](../lab/src/order_service/domain/order.py)
- Tests：[`test_order_properties.py`](../lab/tests/property/test_order_properties.py)、[`test_order_state_machine.py`](../lab/tests/property/test_order_state_machine.py)、[`test_hypothesis_profiles.py`](../lab/tests/property/test_hypothesis_profiles.py)

[返回速答索引](README.md)
