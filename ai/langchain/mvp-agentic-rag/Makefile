.PHONY: install up down db-init ingest test serve eval

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
