# 顺序依赖复现

该目录刻意共享模块级 `seen`，因此不属于默认 `testpaths = ["tests"]`。

声明顺序：

```bash
uv run pytest scenarios/order-dependency/test_seed.py scenarios/order-dependency/test_expect_seed.py -q
# 2 passed
```

反转顺序：

```bash
uv run pytest scenarios/order-dependency/test_expect_seed.py scenarios/order-dependency/test_seed.py -q
# FAILED ... assert [] == ['seed']; 1 failed, 1 passed
```

它不是让团队保留顺序依赖，而是提供确定性故障标本。生产套件应让每个测试拥有自己的 factory、fixture 与状态。
