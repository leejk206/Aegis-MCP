.PHONY: install test e2e lint typecheck clean langfuse langfuse-down

install:
	pip install -e ".[dev]"

test:
	pytest tests/unit

lint:
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

langfuse:
	docker compose up -d

langfuse-down:
	docker compose down
