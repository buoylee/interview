# Collection 与 assert rewriting 场景

这个目录是一个最小、可运行且**故意失败**的 pytest 机制场景。它位于
`scenarios/`，而项目的 `testpaths = ["tests"]`，所以从 `lab/` 执行默认
`uv run pytest -q` 时不会收集这里的测试。

所有命令都从 `python-testing/lab/` 执行。先只做 collection，不执行测试：

```bash
uv run pytest --collect-only scenarios/collection -q
```

预期退出码为 `0`，并且只出现一个 node ID：
`scenarios/collection/test_assertion_report.py::test_assert_rewrite_shows_both_operands`。

再显式运行这个场景：

```bash
uv run pytest scenarios/collection/test_assertion_report.py -q
```

预期退出码为 `1`，失败发生在 test call 阶段。`helpers.py` 中的断言会同时报告
`Decimal('9.99')` 和 `Decimal('10.00')`，证明 `conftest.py` 在 helper 导入前调用的
`pytest.register_assert_rewrite("helpers")` 已使 import hook 重写该支持模块。

这个红灯不是产品缺陷，也不要用 `xfail`、skip 或修改期望值把它洗绿。恢复常规开发反馈时，
回到默认测试范围：

```bash
uv run pytest -q
```

预期退出码为 `0`；`testpaths` 会继续把本目录排除在默认 collection 之外。
