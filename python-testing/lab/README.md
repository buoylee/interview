# Order service testing lab

这是 [Python 测试工程 track](../README.md) 的累积式订单／支付 lab。项目采用 src layout，包名为 `order-service-testing-lab`，支持 CPython 3.11+；默认快速测试不需要 Docker。

## 初始化

在本目录执行：

```bash
uv lock
uv sync --extra dev
```

`uv.lock` 是依赖版本的可执行基线，开发和 CI 都应从它同步环境。

## 验证 bootstrap

```bash
uv run pytest -q
```

当前预期输出为 `6 passed`。该命令验证可编辑安装、版本契约与 bridge 基础示例，不会连接数据库、网络服务或 Docker。

## 分层测试命令

```bash
# fast：unit + component + contract + 轻量 property；不需要 Docker
uv run pytest -m "not integration and not e2e and not docker" -q

# integration：真 Postgres；需要可用的 Docker daemon
uv run pytest -m "integration and docker" -q

# E2E：完整应用边界；需要可用的 Docker daemon
uv run pytest -m "e2e and docker" -q
```

`integration`、`contract`、`e2e`、`property` 和 `docker` 都是严格注册的 marker。容器测试必须显式带 `docker`，避免快速层意外接触基础设施。

## Nox：本地与 CI 的共同契约

CI 编排器只负责提供运行环境，实际测试入口统一由 Nox 定义：PR 对 CPython 3.11–3.14 执行 `fast` 矩阵，并在 3.14 执行 `coverage`；具备 Docker 的 job 在 3.14 执行 `integration` 与 `e2e`；`mutation` 属于定时或手动 quality job。可用 `uv run nox --list` 检查完整 session 清单。

| Nox session | 等价的本地直接命令 |
|---|---|
| `fast-3.11` … `fast-3.14` | `uv run pytest tests/unit tests/component tests/contract tests/property -q` |
| `integration` | `uv run pytest tests/integration -m "integration and docker" -q` |
| `e2e` | `uv run pytest tests/e2e -m "e2e and docker" -q` |
| `coverage` | `uv run pytest tests/unit tests/component tests/contract tests/property --cov=order_service --cov-branch --cov-report=term-missing` |
| `mutation` | `uv run mutmut run "order_service.domain.order*"` |

CI cache key 必须至少包含操作系统、Python minor version 与 `uv.lock` hash，避免跨 ABI 或依赖基线复用环境。失败时保存 JUnit XML、coverage report、pytest log、Hypothesis reproduction blob；Docker job 还保存容器日志。JUnit 与文件型 coverage 可由 CI 在调用同一测试入口时附加 pytest 的 `--junitxml`、`--cov-report=xml`，不会改变测试选择契约。

## 排障

- Docker 不可用：先确认 `docker info` 成功以及当前用户可访问 daemon；fast/coverage 不应依赖 Docker，不能通过删除 marker 来绕过基础设施错误。
- Python interpreter 不可用：执行 `uv python install 3.11 3.12 3.13 3.14`，再重跑对应 Nox session；不得缩减矩阵。
- lockfile 过期：若 `uv sync --frozen --extra dev` 报错，先确认 `pyproject.toml` 是预期变更，再显式运行 `uv lock` 并审查 `uv.lock` diff；CI 不应现场解析出一套新依赖。
