"""共享测试基建。

两件事:
1. 有 `.env` 就加载(方便把 OPENAI_API_KEY 放进去跑 live 测试)。
2. 无 OPENAI_API_KEY 时,自动 skip 所有 `@pytest.mark.live` 测试 —— 保证默认
   `pytest` 在任何机器上都全绿(离线、确定性的可信基线)。
"""

import os

import pytest

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:  # dotenv 是可选的,缺了也不影响离线测试
    pass


def pytest_collection_modifyitems(items):
    if os.getenv("OPENAI_API_KEY"):
        return  # 有 key,放行 live 测试
    skip_live = pytest.mark.skip(reason="未设置 OPENAI_API_KEY,跳过真实 OpenAI 调用")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
