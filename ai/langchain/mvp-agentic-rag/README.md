# 企业知识库 Agentic RAG 助手（MVP）

LangGraph 生产级 Agentic RAG 参考项目。详见
`../../../docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`。

## Plan 1 已实现：RAG 检索通路

```bash
make install          # uv 装依赖
make up               # 起 postgres(pgvector)
cp .env.example .env  # 填入你的 embedding 端点 + key
make db-init          # 建表
make ingest           # 把 sample_docs 入库
make test             # 跑测试(hermetic，不联网)
```
