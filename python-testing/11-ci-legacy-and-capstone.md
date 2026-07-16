# 11. CI、遗留系统与 capstone：用证据安全修复退款幂等性

## 1. 核心问题：CI 不是更大的 `pytest`

资深工程师面对遗留系统时，难点通常不是「怎样写 assertion」，而是同时回答四个问题：

1. 哪些现有行为是必须保留的外部契约，哪些只是碰巧如此的实现细节？
2. 怎样先稳定复现缺陷，再改变事务、外部调用和状态机，而不制造更危险的重复副作用？
3. 哪一层测试可以证明哪一种风险，哪些结论必须由真数据库或完整进程边界提供？
4. 怎样让本机证据在 CI 可重复，并让失败能被快速归类，而不是重新猜测？

本章以一个真实形态的退款缺陷收束整条 track。下面是已经删除的旧实现之概念伪代码（pseudocode，不是当前 runnable lab 源码）；它直接把调用方每次重试提供的 request ID 发送给支付商：

```python
await gateway.refund(
    payment_reference=order.payment_reference,
    total=order.total,
    idempotency_key=request_id,
)
```

同一业务退款若以两个 request ID 重试，支付商看到的是两次不同操作。修复必须同时满足：

- 调用方仍可传 `Idempotency-Key`，HTTP 仍返回 `202` 和原响应结构；
- 支付商收到稳定的业务幂等键 `refund:{order_id}`；
- 未知外部结果不能被误报为成功，也不能退回 `PAID` 后换键重试；
- `REFUND_IN_PROGRESS` 与 provider reference 必须跨进程、跨 UoW 持久化；
- 并发完成只能有一个乐观锁写入成功；
- CI 的 fast、integration、E2E 层都能重放相应证据。

## 2. 直觉模型：先冻结边界，再移动内部

遗留改造可以看成三个同心环：

```text
外环：public contract
  HTTP status、response schema、required header

中环：application protocol
  状态转移、事务边界、provider idempotency key、错误语义

内环：implementation
  类名、函数拆分、repository mapping、legacy module
```

安全顺序是由外向内建立证据，再由内向外完成替换：

1. characterization test 记录当前外部行为；
2. regression test 取消预期失败，得到可重复 RED；
3. domain/component tests 定义新的应用协议；
4. integration tests 验证数据库事实；
5. E2E 证明所有边界组合后仍保留外部契约；
6. 最后删除 legacy seam，而不是永久保留双实现。

characterization test 回答「系统现在对调用方承诺了什么」。approval/golden test 则回答「一份大输出是否仍与被批准的快照一致」。前者适合小而稳定的协议事实；后者适合人工审阅价值高、结构庞大的输出。把普通 JSON API 全量快照化，会让无关字段顺序和格式变化放大审阅噪声。本 lab 因此直接断言；以下片段逐字摘自 [`lab/tests/component/test_refund_characterization.py`](lab/tests/component/test_refund_characterization.py)：

```python
assert response.status_code == 202
assert response.json() == {
    "order_id": str(PAID_ORDER_ID),
    "status": "accepted",
}
```

## 3. 机制深入：一次退款为什么需要两个本地事务

### 3.1 不要持有数据库事务等待网络

`RefundOrder.execute` 使用两个本地事务：

```text
Tx 1                      no DB transaction              Tx 2
PAID                      provider.refund                load current row
 -> REFUND_IN_PROGRESS    stable key                     -> REFUNDED
commit                    refund:{order_id}              save + commit
```

若把 provider HTTP 调用放在数据库事务内部，网络延迟会延长锁持有时间；超时、连接池耗尽和数据库阻塞会互相放大。更关键的是，数据库 rollback 无法撤销外部支付商已经执行的退款。把它写成一个看似原子的 transaction，只是隐藏了不可原子的事实。

第一个 commit 是一条 durable intent：系统已经开始退款。第二个 commit 记录已确认的 provider 结果。中间崩溃时，数据库保留 `REFUND_IN_PROGRESS`，reconciler 或重试可继续使用同一幂等键查询/重放。

### 3.2 未知结果不是失败结果

支付商明确拒绝和网络超时是两种不同事实：

| 观察 | 可以确认 | 不可以确认 | 本地状态 |
|---|---|---|---|
| provider 明确拒绝 | 未执行退款 | — | 由业务策略决定是否回退 |
| timeout / disconnect | 不知道是否执行 | 不能宣称失败，也不能宣称成功 | 保持 `REFUND_IN_PROGRESS` |
| approved + reference | 已确认退款 | — | 写入 `REFUNDED` 与 reference |

`PaymentUncertain` 必须原样传播。错误处理若把状态恢复为 `PAID`，下一次重试可能被当成新退款；错误处理若直接写 `REFUNDED`，则制造 false success。唯一安全的自动重试条件是：仍使用 `refund:{order_id}`。

### 3.3 两种幂等性不能混为一谈

- caller request key：保护一次 HTTP command 的重试语义，也是既有 API 的兼容字段；
- provider operation key：标识同一笔业务退款，必须由稳定业务身份派生。

把 caller key 透传到 provider，相当于把内部副作用身份交给外部调用方控制。本 lab 保留 header 验证，却不使用它构造 provider key。以下调用逐字摘自 [`lab/src/order_service/application/refund_order.py`](lab/src/order_service/application/refund_order.py)：

```python
result = await self._gateway.refund(
    payment_reference=payment_reference,
    total=order.total,
    idempotency_key=f"refund:{order.id}",
)
```

稳定 key 不等于本地并发控制。两个进程可能同时读取 `REFUND_IN_PROGRESS` 并调用支付商；provider 以相同 key 去重，而本地 `version` 乐观锁确保只有一个 completion save 成功。另一个写入得到 `ConcurrentOrderUpdate`，不能吞掉后伪装成功。

### 3.4 optimistic save 的事实边界

repository 的 version predicate 可用以下 SQL 等价伪代码表示（pseudocode；生产实现见 [`lab/src/order_service/adapters/sqlalchemy.py`](lab/src/order_service/adapters/sqlalchemy.py)）：

```sql
UPDATE orders
SET status = ..., refund_reference = ..., version = :new_version
WHERE id = :id AND version = :new_version - 1
```

`rowcount == 1` 才表示调用方的版本仍有效。unit test 可以验证 domain version 递增，component test 可以注入 conflict，但只有真 Postgres integration test 能证明 SQL predicate、rowcount 和 transaction rollback 组合正确。

## 4. 设计取舍：用证据矩阵限制 change amplification

change amplification 是一次业务变更迫使多少无关模块、fixture、snapshot 和 pipeline 同步修改。它既是架构耦合指标，也是测试套件维护成本指标。

| 风险 | 最小可信测试层 | 为什么不再更低一层 |
|---|---|---|
| 非法退款状态、空白 reference、replay version | unit | 纯状态机，不需要 I/O |
| 两事务编排、unknown outcome、稳定 provider key | component | 需要 UoW 与 gateway seam，但不需要 Docker |
| migration、nullable column、fresh UoW reload | integration | 依赖真实 DDL、type reflection、commit visibility |
| stale concurrent save | integration | 依赖数据库 `UPDATE ... WHERE version` 的 rowcount |
| caller header 兼容、HTTP 202、支付与退款串联 | E2E | 风险来自多个真实 adapter 的组合 |

不要用 E2E 重复所有非法状态分支，也不要用 mock 声称 migration 正确。每个事实只放在能推翻它的最低成本边界；高层测试只覆盖关键组合和 public contract。

本次 seam discovery 的顺序是：

1. characterization test 暴露 route 对 `LegacyRefund` 的依赖；
2. `UnitOfWorkFactory` 允许在 component 层观察两次 commit；
3. `PaymentGateway` 允许注入确定成功或 `PaymentUncertain`；
4. SQLAlchemy repository 是 domain 与 schema 的唯一 mapping seam；
5. FastAPI dependency override 允许保留 route 并替换 use case；
6. fake provider 记录 wire-level refund key，提供 E2E 可观察性。

如果一次 use-case 替换要求所有测试 patch module global、启动真网络并共享数据库，问题不是「mock 技巧不足」，而是生产代码缺少明确 ownership seam。

## 5. 贯穿 lab：从 XFAIL 到完整证据链

### 5.1 先得到真实 RED

修复前的旧测试曾明确标记已知缺陷；以下是历史伪代码（pseudocode，不属于当前默认 collection）：

```python
@pytest.mark.xfail(strict=True, reason="CAPSTONE-REFUND-IDEMPOTENCY")
@pytest.mark.asyncio
async def test_retry_with_new_request_id_does_not_refund_twice() -> None:
    ...
```

修复开始时只删除 XFAIL，不改测试体：

```bash
uv run pytest \
  tests/component/test_refund_idempotency.py::test_retry_with_new_request_id_does_not_refund_twice \
  -q
```

关键失败证据是：

```text
E       AssertionError: assert 2 == 1
```

这一步区分了「任务单说有 bug」和「当前 checkout、当前 dependency、当前执行路径确实能复现」。如果测试 XPASS，应先调查环境或代码漂移，不能直接开始修复。

### 5.2 按风险逐层推进

domain RED/GREEN 覆盖：

- 只有 `PAID` 可进入 `REFUND_IN_PROGRESS`；
- `start_refund` replay 不重复增加 version；
- 完成退款要求非空 provider reference；
- 相同 reference 的 `mark_refunded` replay 保持 version；
- 不同状态不能伪造完成。

component RED/GREEN 覆盖：

- missing order 不调用 provider；
- invalid/already-refunded/PAID/in-progress 各走不同分支；
- 首次成功有两个 commit，in-progress retry 只有 completion commit；
- timeout 后保持 in-progress，连续 retry 的 key 完全相同；
- provider 成功后本地 row 消失会抛 `OrderNotFound`；
- completion 的 concurrent conflict 会传播，不产生 false success。

integration RED/GREEN 覆盖：

- migration `0002` upgrade 增加 nullable `TEXT refund_reference`；
- downgrade 回 `0001` 时原 orders/outbox exact schema 不漂移；
- migration test 无论 assertion 是否失败都在 `finally` 恢复 head；
- timeout 后从新 UoW 可读到 `REFUND_IN_PROGRESS`；
- `REFUNDED` 与 reference 从新 UoW 可读；
- 两份 stale aggregate 只有第一份 save 成功。

E2E 最后创建订单、经 outbox worker 支付，再以两个 caller key 调用 refund route。两个响应都保持原 `202` shape，fresh UoW 只看到一笔已完成退款，fake provider 只记录：

```text
Idempotency-Key: refund:{order_id}
```

### 5.3 安全删除顺序

legacy refactor 不是先删旧代码再修测试。安全顺序是：

1. characterization tests 锁定 HTTP contract；
2. regression test 得到 `2 == 1`；
3. 新 `RefundOrder` 在 component 层完成行为；
4. dependency override 切到新 use case；
5. characterization 与 E2E 保持 green；
6. 全仓搜索确认没有 import 后，删除 `legacy_refund.py`。

这样删除是最后一个机械步骤，而不是一次跨越多个未知边界的豪赌。

## 6. 故障工单：先分类，再修复

CI 失败先分为三类：

| 类别 | 典型证据 | 下一步 |
|---|---|---|
| product bug | 同一输入稳定违反领域/API 契约 | 保留 RED，最小修复并加 regression |
| test bug | assertion 验证错误层、fixture 泄漏、错误 mock target | 修正测试模型，证明新测试能杀死对应 mutation |
| environment failure | Docker daemon、DNS、port、interpreter 缺失 | 修 CI image/runner，不修改产品语义让它「通过」 |

flaky 诊断不要从「加 retry」开始。保留 seed、Python 版本、worker ID、test nodeid、容器日志与失败 artifact，然后依次检查：

1. 单测能否在同一 seed 重放；
2. 单独运行与整套运行是否不同，判断顺序依赖；
3. `-n 0` 与 xdist 是否不同，判断共享资源竞态；
4. 固定 clock/ID 后是否消失，判断隐式非确定性；
5. 真 Postgres session/transaction 是否跨 test 泄漏；
6. 失败是否来自 runner，而非 assertion 所描述的业务事实。

quarantine 只能附 owner、issue 和到期时间；它是隔离污染的临时机制，不是成功率工具。未知失败被盲目 rerun 后变绿，会丢失最有价值的第一次失败证据。

## 7. CI 契约：hermetic、cache 与 artifact

`noxfile.py` 是本 lab 的可执行矩阵，而 CI YAML 只是 runner adapter：

```text
fast-3.11  fast-3.12  fast-3.13  fast-3.14
integration-3.14
e2e-3.14
```

fast session 不应需要 Docker、外网或开发者机器上的全局包。`uv sync --frozen --active --extra dev` 让 lockfile 决定 dependency graph；src layout 与新 virtualenv 避免从 checkout 偶然 import 未安装代码。

cache 是性能优化，不是 correctness 输入。cache key 至少包含 OS、Python minor、lockfile hash 与工具版本；cache miss 必须仍能成功。不要缓存运行中的数据库 data directory，也不要让一个 branch 的 mutable venv 覆盖另一个 branch。

artifact 是诊断契约。失败时建议保留：

- JUnit XML：nodeid、duration、failure message；
- coverage XML/HTML：仅作为风险信号，不作为测试质量替代；
- Hypothesis replay seed/example database；
- container/service logs 与 migration revision；
- flaky 重放所需的 xdist worker、随机顺序和 interpreter；
- E2E provider request ledger，但必须脱敏 token、卡号和个人数据。

hermetic 不等于完全没有外部进程；它表示依赖由测试声明和拥有。integration session 可以拥有一个 Postgres 16 container，但不能悄悄连接开发者本机数据库。fixture 必须负责启动、migration、清理与释放；test 只消费明确能力。

本章验证命令：

```bash
# 默认反馈，不启动 Docker
uv run pytest -q

# capstone component
uv run pytest \
  tests/component/test_refund_idempotency.py \
  tests/component/test_refund_order.py \
  tests/component/test_refund_characterization.py -q

# 真数据库
uv run pytest \
  tests/integration/test_refund_persistence.py \
  tests/integration/test_migrations.py \
  -m "integration and docker" -q

# 完整退款路径
uv run pytest tests/e2e/test_refund_flow.py -m "e2e and docker" -q

# CI matrix
uv run nox -s fast-3.11 fast-3.12 fast-3.13 fast-3.14
uv run nox -s integration-3.14
uv run nox -s e2e-3.14
```

完成标准不是「本机某次绿」，而是：没有 XFAIL/XPASS；默认 suite 无 Docker；各层命令独立可重放；migration 失败后恢复 head；worktree 无未追踪执行产物；失败输出足以定位责任层。

## 8. Java/Go 对照与面试卡

### Java / Go 对照

- Java 常用 Testcontainers、JUnit tags 与 Gradle/Maven task 表达相同矩阵；关键仍是让 transaction ownership 明确，不能用 `@Transactional` 测试自动 rollback 冒充跨 transaction 可见性。
- Go 常用 table-driven tests、interface fake 和 `go test -race`；race detector 能发现内存数据竞态，却不能证明 provider 幂等键或数据库 optimistic predicate 正确。
- Python 的 pytest fixture/plugin 很灵活，也更容易产生隐式依赖。资深实践不是堆 fixture，而是让资源 ownership、scope 与 marker 成为可审计契约。

### 一句话版本

> 我先用 characterization test 冻结 HTTP 契约并取消 XFAIL 得到 `2 == 1`，再用稳定业务 key、两阶段本地事务和持久化 in-progress 状态修复退款；component 证明编排，真 Postgres 证明 migration 与乐观锁，E2E 证明两个 caller retry 只有一个有效 provider refund，最后由 Nox 重放整个 CI 矩阵。

### 深答追问

**为什么 timeout 后不回退到 `PAID`？**

因为 timeout 只表示没有收到结果，支付商可能已经退款。回退会允许另一业务身份再次执行；保持 in-progress 并以同一 key reconcile 才不制造重复副作用。

**既然 provider key 幂等，为什么还要 version？**

provider key 管外部副作用，本地 version 管 aggregate completion 的并发写入。两者保护不同一致性边界，不能互相替代。

**为什么不只写 E2E？**

E2E 能证明关键组合，却无法低成本穷举状态机分支，也很难精确定位是 domain、orchestration、DDL 还是 wire contract 失败。分层矩阵同时降低反馈时间和归因成本。

**怎样向架构评审证明这是安全重构？**

展示一条时间有序的 evidence ledger：原 XFAIL、可重复 RED、每个风险边界的 focused GREEN、exact migration up/down、unknown-outcome regression、E2E backward compatibility、全矩阵命令与最终 clean diff。重点不是测试数量，而是每项高风险声明都有能推翻它的独立证据。
