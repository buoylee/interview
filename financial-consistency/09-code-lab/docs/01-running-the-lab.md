# 运行代码实验室

本实验室不依赖 Spring Boot、MySQL 或消息队列。脚本会编译 `src/main/java` 和 `src/test/java` 下的纯 Java 代码，并运行固定实验用例。

## 基本命令

从仓库根目录运行自检：

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

列出全部实验：

```bash
bash financial-consistency/09-code-lab/scripts/run-lab.sh list
```

运行一个指定失败用例：

```bash
bash financial-consistency/09-code-lab/scripts/run-lab.sh run --case payment-timeout-late-success
```

运行全部实验：

```bash
bash financial-consistency/09-code-lab/scripts/run-lab.sh run
```

## 输出预期

`test-lab.sh` 用于验证实验室自身行为，成功时会输出 `SELF_TEST_PASS`。

全量运行的汇总计数会随着实验数量变化而变化。当前版本预期显示：

```text
total=12
expectedPasses=3
expectedFailures=9
actualFailures=9
```

这里的 `expectedFailures` 不是脚本失败，而是实验故意构造的不一致历史；`actualFailures` 表示一致性判定器实际发现的不变量违反数量。

## 推荐运行顺序

1. 先运行 `test-lab.sh`，确认本地 Java 编译和自检都能通过。
2. 再运行 `list`，了解每个实验的 id、场景说明和期望结果。
3. 用 `--case` 聚焦一个失败报告，先练习读懂字段。
4. 最后运行全量实验，比较不同 verifier 发现的问题类型。
