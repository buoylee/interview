# Order Contracts Lab

本 lab 是 `python-pydantic/` 教程的可执行事实来源，使用 CPython 3.11+、Pydantic v2、pydantic-settings v2 与 pytest。

```bash
uv sync
uv run pytest
```

它不连接数据库、消息 broker、支付平台或 LLM，也不需要 API key。`.env.example` 只有可公开的本地占位值；真实 `.env` 不得提交。
