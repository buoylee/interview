.PHONY: install up down db-init ingest test serve eval langfuse-up langfuse-down

install:
	uv sync --extra dev

up:
	docker compose up -d postgres

down:
	docker compose down

db-init:
	uv run python -m mvp_agentic_rag.core.db

ingest:
	uv run python -m mvp_agentic_rag.ingest.cli sample_docs

test:
	uv run pytest -v

serve:
	uv run uvicorn mvp_agentic_rag.main:build_app --factory --reload --port 8000

eval:
	uv run python -m mvp_agentic_rag.eval.cli

# ---- 可选:自托管 Langfuse(v3,独立 compose,与主栈隔离)----
langfuse-up:
	docker compose -f docker-compose.langfuse.yml up -d

langfuse-down:   # 加 ARGS=-v 连数据一起删:make langfuse-down ARGS=-v
	docker compose -f docker-compose.langfuse.yml down $(ARGS)
