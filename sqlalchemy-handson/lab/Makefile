.PHONY: sync unit integration lint typecheck verify db-up db-down

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

verify: lint typecheck unit integration

db-up:
	docker compose up -d --wait

db-down:
	docker compose down -v
