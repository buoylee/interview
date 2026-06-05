.PHONY: install up down db-init ingest test

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
