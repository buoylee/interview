# 阅读失败报告

失败报告的目标不是只告诉你“失败了”，而是把违反的不变量、相关证据和裁剪后的历史放在一起，方便定位真实系统里需要对账或修复的位置。

下面以 `payment-timeout-late-success` 为例。这个实验描述的是：本地把支付标记为失败后，外部渠道又返回了成功。

## 字段说明

- `Experiment`：实验 id，例如 `payment-timeout-late-success`。运行单个用例时用它传给 `--case`。
- `Scenario`：业务场景说明，帮助你先用业务语言理解异常。
- `Seed`：历史生成种子。当前固定用例使用类似 `fixed:payment-timeout-late-success` 的值，方便复现同一段历史。
- `Result`：一致性判定结果。`FAILED` 表示 verifier 找到了不变量违反。
- `Violated invariant`：被违反的不变量名称，例如 `EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE`。
- `Relevant facts`：与违反直接相关的事实或证据。当前报告输出可能使用 `Related items:`，含义相同。
- `Reduced history`：为了说明问题而保留的最小历史片段，通常只包含相关事实、事件或命令的 id。
- `Verifier`：发现问题的判定器，例如 `ExternalFactVerifier`。
- `Interpretation`：对报告的人工解读。代码输出里可能拆成 `Reason`、`Boundary`、`Related items` 和 `Reduced history` 等字段；阅读时要把它们合起来理解。

## 示例解读

`payment-timeout-late-success` 的关键输出包括：

```text
Experiment: payment-timeout-late-success
Result: FAILED
Violated invariant: EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE
Reason: businessKey=P1 has external success and local FAILED state
Verifier: ExternalFactVerifier
Related items: payment-late-external-success, payment-late-local-failed
Reduced history:
- payment-late-local-failed
- payment-late-external-success
```

解读顺序：

1. `Experiment` 和 `Scenario` 确认这是“支付超时后本地失败，但渠道晚成功”的场景。
2. `Violated invariant` 说明违反的是外部成功与本地失败之间没有被解释或修复的边界。
3. `Verifier` 表明问题由外部事实判定器发现，而不是流水平衡或消息传播判定器发现。
4. `Related items:` 中的 id 指回 `Reduced history` 里的事实、事件或命令。先用这些 id 找证据，再判断真实系统中对应的是数据库行、渠道流水、消息投递记录还是审计事件。
5. `Reduced history` 只保留了 `payment-late-local-failed` 和 `payment-late-external-success`，说明最小矛盾就是“本地失败”和“外部成功”同时存在，且没有后续修复证据。

在真实系统里，这类报告通常意味着需要对账任务、人工修复任务或状态机补偿逻辑介入，不能仅靠重试本地接口解决。
