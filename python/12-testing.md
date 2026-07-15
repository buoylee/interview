# 12 · 测试

> 本章用十分钟建立框架选型和 pytest 基础。测试策略、可测架构、真实数据库、契约、并发、property/stateful、flaky 治理与 CI 的系统训练，进入 [Python 测试工程 track](../python-testing/README.md)。

## 为什么 pytest 是默认选择

新建 Python 项目通常优先选择 pytest：测试可以写成普通函数并使用原生 `assert`，fixture 负责可组合的 setup/teardown，parametrize 把一组输入变成独立用例；它也能收集现有 `unittest.TestCase`，便于渐进迁移。

pytest 的优势不是语法更短，而是失败信息、依赖组织和插件生态形成了统一 runner。框架只能提供工具；测试边界仍应由业务风险、反馈速度、维护成本和环境失真决定。

## pytest 十分钟上手

下面的完整文件同时演示原生 `assert`、yielding fixture 和 parametrize。可执行源文件是 [`python-testing/lab/tests/unit/test_pytest_basics.py`](../python-testing/lab/tests/unit/test_pytest_basics.py)，本代码块与文件逐字一致：

```python
from collections.abc import Iterator

import pytest


def add(left: int, right: int) -> int:
    return left + right


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


@pytest.fixture
def sample_order() -> Iterator[dict[str, object]]:
    order = {"id": "order-1", "paid": False}
    yield order
    order.clear()


def test_fixture_supplies_isolated_order(sample_order: dict[str, object]) -> None:
    assert sample_order["paid"] is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" paid ", "paid"), ("PENDING", "pending"), ("", "")],
)
def test_normalize_status(raw: str, expected: str) -> None:
    assert raw.strip().lower() == expected
```

`test_add_returns_sum` 是一个原生断言用例；fixture 通过参数名注入依赖，`yield` 前后分别是 setup 与 teardown；parametrize 则让三组数据拥有独立 node ID 和失败结果。它们合计生成五个测试用例。

从仓库根目录执行精确的聚焦命令：

```bash
cd python-testing/lab && uv run pytest tests/unit/test_pytest_basics.py -q
```

这三种写法足以开始小型测试；fixture scope、collection/import mode、mock seam、async loop ownership 等高级机制留给 [Python 测试工程 track](../python-testing/README.md) 结合可执行 lab 展开。

## unittest 与 doctest 什么时候仍然合理

`unittest` 仍适合以下情形：标准库零额外依赖是硬约束；项目已有大量 `TestCase`、`setUp` 和自定义 runner；或团队明确依赖 xUnit 生命周期。pytest 可以直接运行多数 unittest 测试，因此不必为换 runner 一次性重写全部代码。

`doctest` 适合验证短小、稳定、确定的文档示例，例如纯函数的 REPL 片段。它不适合作为服务测试主框架：空白与字符串表示会造成脆弱失败，fixture、复杂失败路径和资源清理也不够清晰。

选型原则很简单：新项目默认 pytest；保留有价值的 unittest 资产并渐进互操作；只把 doctest 用在“文档示例本身就是契约”的窄边界。

## 下一步：Python 测试工程 track

[Python 测试工程 track](../python-testing/README.md) 面向有后端经验的读者，以订单／支付服务为贯穿 lab，覆盖从 unit、component 到真 Postgres、HTTP contract、async/background、property/stateful、E2E 与 suite governance 的完整证据链。

入口页提供 00–11 章节地图、fast/integration/E2E 命令层级、每章固定模板和进度表。先从测试策略与风险模型开始，不把覆盖率或固定“测试金字塔”比例当作目标。

## Java/Go 对照框

| 维度 | JUnit / Java | Go | pytest |
|---|---|---|---|
| 基本形态 | 类 + `@Test` | `func TestXxx(t *testing.T)` | 普通 `test_*` 函数 + 原生 `assert` |
| 生命周期 | `@BeforeEach` / `@AfterEach` | helper + `t.Cleanup` | fixture + `yield` teardown |
| 参数化 | `@ParameterizedTest` | table-driven test | `@pytest.mark.parametrize` |
| 依赖组织 | 手动或框架注入 | 显式传参／接口 | fixture 按参数名组成依赖图 |
| 迁移提醒 | 不必把每个 fixture 变成类 | 不必把每个 case 手写循环 | 优先描述行为，不绑定实现结构 |

## 章末面试卡

**Q：为什么新 Python 项目通常默认 pytest？**

普通函数、原生断言、可组合 fixture、参数化和插件生态降低样板并提高失败可诊断性；但测试层级仍由风险和证据强度决定。

**Q：fixture 相比 setUp/tearDown 的关键差异是什么？**

fixture 是按依赖名组合、可设 scope 的资源图；`yield` 同时表达提供值与可靠清理，不受单一测试类生命周期限制。

**Q：什么时候不该迁移 unittest 或使用 doctest？**

已有稳定 unittest 资产时让 pytest 直接收集并渐进迁移；doctest 只保留给短小稳定的文档契约，不承担复杂服务测试。

**Q：掌握 fixture 和 parametrize 是否等于会做测试工程？**

不等于。资深测试工程还要能选择边界、设计 seam、控制真实基础设施、保留失败证据，并治理 flaky、并发与 CI；这些进入 [独立 track](../python-testing/README.md)。
