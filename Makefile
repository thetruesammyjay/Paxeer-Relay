.DEFAULT_GOAL := help

.PHONY: help install dev lint format typecheck test test-unit test-integration test-e2e \
        migrate seed generate build clean docker-up docker-down

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all JS and Python dependencies
	pnpm install
	uv sync --all-packages

dev: ## Start all applications in development mode
	pnpm dev

lint: ## Run all linters
	pnpm lint
	uv run ruff check .

format: ## Format all code
	pnpm format
	uv run ruff format .

typecheck: ## Run all type checkers
	pnpm typecheck
	uv run mypy .

test: ## Run all tests
	pnpm test
	uv run pytest

test-unit: ## Run unit tests only
	uv run pytest -m unit

test-integration: ## Run integration tests only
	uv run pytest -m integration

test-e2e: ## Run end-to-end tests
	pnpm test:e2e

migrate: ## Run database migrations
	uv run --package paxrelay-db alembic upgrade head

seed: ## Seed development data
	uv run python scripts/seed.py

generate: ## Generate API clients and type stubs
	pnpm generate

build: ## Build all packages and applications
	pnpm build

clean: ## Remove build artifacts and caches
	pnpm clean
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

docker-up: ## Start local Docker services (Postgres + Redis)
	docker compose up -d postgres redis

docker-down: ## Stop local Docker services
	docker compose down
