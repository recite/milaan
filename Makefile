.PHONY: help install check fmt lint types test run report clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync the Python environment
	uv sync --all-extras

fmt:  ## Format
	uv run ruff format src tests
	uv run ruff check --fix src tests cases backends lib

lint:  ## Lint
	uv run ruff format --check src tests
	uv run ruff check src tests cases backends lib

types:  ## Type-check
	uv run pyright

test:  ## Unit tests (no subprocesses, no network)
	uv run pytest

check: lint types test  ## Everything CI would run

run:  ## Run the full cross-implementation suite
	uv run milaan run --all

report:  ## Regenerate reports/latest.md
	uv run milaan report

clean:
	rm -rf .pytest_cache .ruff_cache dist build
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
