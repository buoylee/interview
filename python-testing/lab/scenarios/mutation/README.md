# 100% coverage 仍缺少 oracle

弱测试只调用 `fee`。从本目录运行：

```bash
uv run pytest test_fee.py --cov=fee --cov-report=term-missing -q
# fee.py  3 statements  0 missing  100%; 1 passed
```

把乘法临时改为加法后，弱测试仍然是 `1 passed`。恢复实现并把测试强化为精确断言后，再应用同一 mutation：

```text
E AssertionError: assert Decimal('100.02') == Decimal('2.0000')
1 failed
```

仓库只保留正确乘法与强 oracle；该 scenario 不进入默认套件。
