.PHONY: install test lint format typecheck migrate migrate-down server

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=dai --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy dai/

server:
	uvicorn dai_server.main:app --reload --host 0.0.0.0 --port 8080

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-create:
	alembic revision --autogenerate -m "$(name)"

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-migrate:
	docker compose -f docker/docker-compose.yml run --rm migrate
