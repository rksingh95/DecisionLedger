# ══════════════════════════════════════════════════════════════════════════════
#  DecisionLedger SDK — Developer Makefile
#  Run `make help` to see all available commands.
# ══════════════════════════════════════════════════════════════════════════════

# ── Configuration ─────────────────────────────────────────────────────────────
PYTHON       := .venv/bin/python
PIP          := .venv/bin/pip
PYTEST       := .venv/bin/pytest
RUFF         := .venv/bin/ruff
MYPY         := .venv/bin/mypy
DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml
PORT         ?= 8080

# Colour helpers (works on macOS & Linux)
BOLD  := \033[1m
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

# ── Phony targets ─────────────────────────────────────────────────────────────
.PHONY: help \
        install install-dev install-all \
        lint format typecheck check \
        test test-unit test-integration test-cov test-watch \
        server server-prod \
        migrate migrate-down migrate-create migrate-history \
        docker-up docker-down docker-logs docker-migrate docker-rebuild \
        build clean

# ── Default target ────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

# ─────────────────────────────────────────────────────────────────────────────
#  HELP
# ─────────────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)$(CYAN)DecisionLedger SDK$(RESET) — available commands"
	@echo ""
	@echo "$(BOLD)  SETUP$(RESET)"
	@grep -E '^install[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  CODE QUALITY$(RESET)"
	@grep -E '^(lint|format|typecheck|check)[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  TESTING$(RESET)"
	@grep -E '^test[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  SERVER$(RESET)"
	@grep -E '^server[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  DATABASE$(RESET)"
	@grep -E '^migrate[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  DOCKER$(RESET)"
	@grep -E '^docker[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)  BUILD$(RESET)"
	@grep -E '^(build|clean)[^:]*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)make %-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "  Variables: PORT=$(PORT)"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
#  SETUP
# ─────────────────────────────────────────────────────────────────────────────

install: ## Install the SDK in editable mode (basic deps only)
	$(PIP) install -e "."

install-dev: ## Install SDK + dev + server dependencies (creates .venv automatically)
	@if [ ! -d .venv ]; then python3.13 -m venv .venv; echo "Created .venv with Python 3.13"; fi
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,server]"
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example — update values as needed"; fi
	@echo ""
	@echo "$(GREEN)✓ Ready!$(RESET)"
	@echo "  Activate venv : source .venv/bin/activate"
	@echo "  Start server  : make server"
	@echo "  Run tests     : make test"

install-all: ## Install SDK + dev + all optional extras (langchain, opentelemetry, server)
	@if [ ! -d .venv ]; then python3.13 -m venv .venv; echo "Created .venv with Python 3.13"; fi
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,server,langchain,opentelemetry]"
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example — update values as needed"; fi
	@echo ""
	@echo "$(GREEN)✓ Ready. Activate with:$(RESET) source .venv/bin/activate"

# ─────────────────────────────────────────────────────────────────────────────
#  CODE QUALITY
# ─────────────────────────────────────────────────────────────────────────────

lint: ## Run ruff linter (check only, no changes)
	$(RUFF) check .

format: ## Auto-format code with ruff (modifies files)
	$(RUFF) format .
	$(RUFF) check . --fix

typecheck: ## Run mypy strict type-checker on the SDK
	$(MYPY) dai/

check: lint typecheck ## Run lint + typecheck together (full CI quality gate)
	@echo ""
	@echo "$(GREEN)✓ All checks passed$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
#  TESTING
# ─────────────────────────────────────────────────────────────────────────────

test: ## Run all tests with coverage report (>90% required on SDK)
	$(PYTEST) tests/unit/ --cov=dai --cov-report=term-missing --cov-fail-under=90

test-unit: ## Run unit tests only (fast, no DB required)
	$(PYTEST) tests/unit/ -v

test-integration: ## Run integration tests (requires a running server / DB)
	$(PYTEST) tests/integration/ -v

test-cov: ## Generate HTML coverage report (opens at htmlcov/index.html)
	$(PYTEST) tests/ --cov=dai --cov=dai_server --cov=cli \
	          --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(GREEN)Coverage report:$(RESET) htmlcov/index.html"

test-watch: ## Re-run unit tests automatically on file changes (requires pytest-watch)
	ptw tests/unit/ -- -v

# ─────────────────────────────────────────────────────────────────────────────
#  SERVER
# ─────────────────────────────────────────────────────────────────────────────

server: ## Start the API server in dev mode with auto-reload (port $(PORT))
	@if [ ! -f .env ]; then \
	  echo "$(BOLD)$(CYAN)Hint:$(RESET) No .env found — copying from .env.example (SQLite mode)"; \
	  cp .env.example .env; \
	fi
	$(PYTHON) -m uvicorn dai_server.main:app --reload --host 0.0.0.0 --port $(PORT)

server-prod: ## Start the API server in production mode via Gunicorn
	$(PYTHON) -m gunicorn dai_server.main:app \
	    -k uvicorn.workers.UvicornWorker \
	    --workers 4 \
	    --bind 0.0.0.0:$(PORT) \
	    --access-logfile - \
	    --error-logfile -

# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE MIGRATIONS (Alembic)
# ─────────────────────────────────────────────────────────────────────────────

migrate: ## Apply all pending Alembic migrations (upgrade to head)
	alembic upgrade head

migrate-down: ## Roll back the last Alembic migration
	alembic downgrade -1

migrate-create: ## Create a new migration (usage: make migrate-create name="add_my_table")
ifndef name
	$(error Usage: make migrate-create name="your migration description")
endif
	alembic revision --autogenerate -m "$(name)"

migrate-history: ## Show migration history
	alembic history --verbose

# ─────────────────────────────────────────────────────────────────────────────
#  DOCKER
# ─────────────────────────────────────────────────────────────────────────────

docker-up: ## Start Postgres + API server via Docker Compose
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)✓ Stack started$(RESET)  →  API on http://localhost:$(PORT)  |  Postgres on :5432"

docker-down: ## Stop and remove all Docker Compose containers
	$(DOCKER_COMPOSE) down

docker-logs: ## Tail logs from all Docker Compose services
	$(DOCKER_COMPOSE) logs -f

docker-migrate: ## Run Alembic migrations inside the Docker network
	$(DOCKER_COMPOSE) run --rm api alembic upgrade head

docker-rebuild: ## Rebuild Docker images and restart the stack
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

# ─────────────────────────────────────────────────────────────────────────────
#  BUILD & CLEAN
# ─────────────────────────────────────────────────────────────────────────────

build: ## Build sdist and wheel packages into dist/
	$(PYTHON) -m build
	@echo ""
	@echo "$(GREEN)✓ Packages built:$(RESET)"
	@ls -lh dist/

clean: ## Remove all build artefacts, caches, and coverage data
	rm -rf dist/ build/ *.egg-info .eggs/
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean$(RESET)"
