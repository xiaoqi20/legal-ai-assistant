.PHONY: install dev worker migrate check
install:
	uv sync --frozen
dev:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
worker:
	uv run python -m app.worker
migrate:
	uv run alembic upgrade head
check:
	uv run ruff check .
	uv run python -m compileall -q app migrations scripts
	uv run pytest -q
