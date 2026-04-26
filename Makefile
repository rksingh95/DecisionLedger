# ══════════════════════════════════════════════════════════════════════════════
#  DecisionLedger SDK — Developer Makefile
#  Run `make help` to see all available commands.
# ══════════════════════════════════════════════════════════════════════════════

# ── Configuration ─────────────────────────────────────────────────────────────
# Auto-detect venv: use .venv if it exists, otherwise fall back to system python
# This makes `make lint` / `make test` work in CI (no .venv) and locally (with .venv).
PYTHON       := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP          := $(if $(wildcard .venv/bin/pip),.venv/bin/pip,pip)
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
        lint format typecheck check pre-commit \
        test test-unit test-integration test-cov test-watch \
        server server-prod \
        migrate migrate-down migrate-create migrate-history \
        docker-up docker-down docker-clean docker-logs docker-logs-api \
        docker-status docker-migrate docker-rebuild docker-shell docker-psql \
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

install-dev: ## Install SDK + dev + server deps, set up pre-commit hooks (creates .venv)
	@if [ ! -d .venv ]; then python3.13 -m venv .venv; echo "Created .venv with Python 3.13"; fi
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev,server]"
	$(PYTHON) -m pre_commit install --install-hooks
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example — update values as needed"; fi
	@echo ""
	@echo "$(GREEN)✓ Ready!$(RESET)"
	@echo "  Pre-commit hooks : installed (runs on every git commit)"
	@echo "  Activate venv    : source .venv/bin/activate"
	@echo "  Start server     : make server"
	@echo "  Run tests        : make test"

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
	$(PYTHON) -m ruff check .

format: ## Auto-format code with ruff (modifies files)
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check . --fix

typecheck: ## Run mypy strict type-checker on the SDK
	$(PYTHON) -m mypy dai/

check: lint typecheck ## Run lint + typecheck together (full CI quality gate)
	@echo ""
	@echo "$(GREEN)✓ All checks passed$(RESET)"

pre-commit: ## Run all pre-commit hooks against all files (useful before a PR)
	$(PYTHON) -m pre_commit run --all-files

# ─────────────────────────────────────────────────────────────────────────────
#  TESTING
# ─────────────────────────────────────────────────────────────────────────────

test: ## Run all tests with coverage report (>90% required on SDK)
	$(PYTHON) -m pytest tests/unit/ --cov=dai --cov-report=term-missing --cov-fail-under=90

test-unit: ## Run unit tests only (fast, no DB required)
	$(PYTHON) -m pytest tests/unit/ -v

test-integration: ## Run integration tests (requires a running server / DB)
	$(PYTHON) -m pytest tests/integration/ -v

test-cov: ## Generate HTML coverage report (opens at htmlcov/index.html)
	$(PYTHON) -m pytest tests/ --cov=dai --cov=dai_server --cov=cli \
	          --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(GREEN)Coverage report:$(RESET) htmlcov/index.html"

test-watch: ## Re-run unit tests automatically on file changes (requires pytest-watch)
	$(PYTHON) -m pytest_watch tests/unit/ -- -v

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

docker-up: ## Build images + start full stack (Postgres → migrate → API) — one command
	@echo "$(BOLD)$(CYAN)Building images…$(RESET)"
	$(DOCKER_COMPOSE) build
	@echo "$(BOLD)$(CYAN)Starting stack…$(RESET)"
	$(DOCKER_COMPOSE) up -d --wait
	@echo ""
	@echo "$(GREEN)✓ Stack is up and healthy$(RESET)"
	@echo "  API     → http://localhost:$(PORT)"
	@echo "  Health  → http://localhost:$(PORT)/health"
	@echo "  Docs    → http://localhost:$(PORT)/docs"
	@echo "  Postgres → localhost:5432  (user: dai / db: dai)"
	@echo ""
	@echo "  Logs : make docker-logs"
	@echo "  Stop : make docker-down"

docker-down: ## Stop and remove all containers (keeps Postgres volume)
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Stack stopped$(RESET)"

docker-clean: ## Stop containers AND remove all volumes (wipes the database)
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✓ Stack stopped and volumes removed$(RESET)"

docker-logs: ## Tail logs from all services (Ctrl+C to stop)
	$(DOCKER_COMPOSE) logs -f

docker-logs-api: ## Tail API server logs only
	$(DOCKER_COMPOSE) logs -f api

docker-status: ## Show current status of all containers
	$(DOCKER_COMPOSE) ps

docker-migrate: ## Run Alembic migrations inside the Docker network
	$(DOCKER_COMPOSE) run --rm migrate

docker-rebuild: ## Force-rebuild images from scratch and restart the stack
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d --wait
	@echo "$(GREEN)✓ Stack rebuilt and restarted$(RESET)"

docker-shell: ## Open a shell inside the running API container
	$(DOCKER_COMPOSE) exec api /bin/bash

docker-psql: ## Connect to Postgres inside the Docker network
	$(DOCKER_COMPOSE) exec postgres psql -U dai -d dai

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
