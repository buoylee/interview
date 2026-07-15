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
