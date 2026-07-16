# Module-scoped 可变 fixture 泄漏场景

这是故意失败、必须显式选择的 pytest 场景。项目配置为 `testpaths = ["tests"]`，所以从 `python-testing/lab/` 执行默认 `uv run pytest -q` 不会收集本目录。

## 复现

所有命令从 `python-testing/lab/` 执行：

```bash
uv run python -m pytest scenarios/fixture-leak -q
```

预期退出码为 `1`，输出先显示 `.` 再显示 `F`：

- `test_a_mutates_shared_order` 通过，把共享订单推进到 `payment_in_progress`。
- `test_b_expected_fresh_order` 在 test call 阶段失败，实际值为 `payment_in_progress`，期望值为 `pending_payment`。

这不是 collection、fixture setup 或 teardown failure。第一项已经证明 module-scoped fixture 可用；第二项的 assertion diff 才证明状态从前一个 item 泄漏。

## 原因

`shared_order` 使用 module scope。pytest 为该测试模块只调用一次 fixture，并把同一个可变 `Order` 缓存在 scope 内。第一个测试调用真实的 `Order.start_payment()`，会原地修改 status 和 version；第二个测试收到相同实例。

`python -m pytest` 明确让当前 `lab/` 工作目录参与正常模块查找，所以场景可以导入 `tests.factories`；场景不修改 `sys.path`，也不复制 factory。该 runner contract 不改变泄漏机制，场景仍不进入默认 suite。

## 恢复与修复

恢复日常绿色反馈：

```bash
uv run pytest -q
```

真正修复同类生产测试有两个选择：

1. 返回 `make_order` factory，由每个测试调用并拥有新对象。
2. 让 object fixture 保持默认 function scope。

不要给 `Order` 增加测试专用 reset 方法，不要在 teardown 猜测反向状态转换，也不要用 `xfail` 或调换测试名字掩盖顺序依赖。回归政策由 `tests/unit/test_order_factory.py` 覆盖：两个调用身份不同，改变第一个不会改变第二个。
