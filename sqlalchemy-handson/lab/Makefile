.PHONY: sync unit integration lint typecheck evidence verify db-up db-down

sync:
	uv sync

unit:
	uv run pytest tests/unit -q

integration:
	uv run pytest -m integration -q

lint:
	uv run ruff check src tests scenarios

typecheck:
	uv run mypy src tests scenarios

evidence:
	uv run python -m scenarios.environment
	uv run python -m scenarios.ch01_engine_execution
	uv run python -m scenarios.ch02_schema_types
	uv run python -m scenarios.ch03_expression_compiler
	uv run python -m scenarios.ch04_core_dml_results
	uv run python -m scenarios.ch05_connection_transactions
	uv run python -m scenarios.ch06_pooling_capacity

verify: lint typecheck unit integration

db-up:
	docker compose up -d --wait

db-down:
	docker compose down -v
