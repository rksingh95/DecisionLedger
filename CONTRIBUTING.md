# Contributing to DAI SDK — Mandate

## Development setup

```bash
git clone https://github.com/Mandate/DecisionLedger
cd DecisionLedger
pip install -e ".[dev]"
```

## Running tests

```bash
# All tests with coverage
pytest tests/ -v --cov=dai

# Unit tests only
pytest tests/unit/ -v

# Integration tests only (uses SQLite, no server needed)
pytest tests/integration/ -v
```

## Running the server locally

```bash
cp .env.example .env
# Edit .env: set DAI_DATABASE_URL to a PostgreSQL instance
uvicorn dai_server.main:app --reload
```

## Code style

```bash
ruff format .      # Format
ruff check .       # Lint
mypy dai/          # Type check
```

## PR requirements

- All tests must pass (`pytest tests/ -v`)
- Type hints required on all public functions
- Docstrings required on all public classes and methods
- No free-text fields in the core schema (use enums or typed primitives)
- `ruff format` must produce no diff

## Core design principles (never violate)

1. **Append-only.** Records are never mutated after commit.
2. **Hash-chained.** Every record links cryptographically to the previous one.
3. **Typed.** No free-text fields in the core schema.
4. **Non-blocking.** SDK failure must never crash the agent.
5. **Framework-agnostic.** Works with any Python agent framework.
6. **Self-hostable.** Runs via `docker compose up`. No mandatory cloud.
7. **EU AI Act compliant.** Schema covers Article 19 fields explicitly.

## Database migrations

```bash
# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Create a new migration
alembic revision --autogenerate -m "add_new_field"
```
