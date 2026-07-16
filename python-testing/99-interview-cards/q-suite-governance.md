# 如何治理一个 30 分钟且 flaky 的测试套件，而不隐藏失败？

## 30 秒回答

先把“30 分钟”和“flaky”拆开：按 nodeid、seed、worker、阶段、依赖与资源证据分类失败；按 fast、integration、E2E、property、quality 反馈环统计 p50/p95 和长尾。修复共享状态、时钟、端口、任务与外部依赖的 ownership，再安全启用 xdist。禁止把 rerun、永久 skip 或宽泛 warning suppression 当作绿色；quarantine 必须有 owner、期限和退出条件。

## 机制

xdist worker 是进程，每个 worker 各有 session fixtures；共享外部 namespace 仍必须隔离。coverage 找执行盲区，branch coverage 找分支盲区，mutation 检验 oracle，但三个指标都不等于业务风险覆盖。CI 用 frozen lockfile 和 Nox 固定 Python 3.11–3.14 fast matrix，Docker tiers 显式选择，失败 artifact 保存 JUnit、coverage、log、Hypothesis blob 和容器证据。

## lab 生产案例

[`pyproject.toml`](../lab/pyproject.toml) 开启 strict config/markers、strict xfail、strict asyncio、默认排除 Docker 与定向 warning policy；[`noxfile.py`](../lab/noxfile.py) 定义四版本 fast 和独立 integration/E2E/coverage/mutation sessions。order-dependency scenario 稳定复现顺序污染，mutation scenario 证明 100% line coverage 仍可能没有金额 oracle；capstone 从 characterization 逐层推进退款修复。

## 取舍／反例

盲目 `-n auto` 会把固定端口、共享文件或数据库命名冲突放大；先做 ownership audit。给所有 flaky 自动 rerun 会降低失败率报表，却不降低产品风险。追求 100% coverage/mutation score 会诱导无意义测试；survivor 应逐项判断是否有业务语义。慢的 Postgres/E2E 不应塞进默认本地反馈，但也不能因慢而永久跳过。

## 追问

- 怎样建立 flaky budget，且不鼓励团队用 rerun 洗绿？
- 哪些测试适合 PR blocking，哪些适合排程或发布门禁？
- quarantine 到期仍未修复，构建应发生什么？
- suite 总时长下降但 p95 变差时，你如何解释？

## 证据链接

- 章节：[flaky 分类](../10-suite-reliability-and-scale.md#核心问题)、[xdist 与 mutation](../10-suite-reliability-and-scale.md#机制深入)、[CI 契约](../11-ci-legacy-and-capstone.md#7-ci-契约hermeticcache-与-artifact)
- Config：[`pyproject.toml`](../lab/pyproject.toml)、[`noxfile.py`](../lab/noxfile.py)、[`lab README`](../lab/README.md)
- Evidence：[order dependency scenario](../lab/scenarios/order-dependency/README.md)、[mutation scenario](../lab/scenarios/mutation/README.md)、[`test_refund_characterization.py`](../lab/tests/component/test_refund_characterization.py)

[返回速答索引](README.md)
