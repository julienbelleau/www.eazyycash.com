.PHONY: help install up down logs db-init db-shell migrate fmt lint typecheck test test-cov ci clean
.DEFAULT_GOAL := help

PYTHON ?= poetry run python

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## install python deps + pre-commit hooks
	poetry install --no-root
	poetry run pre-commit install

up:  ## start TimescaleDB + Redis (dev compose)
	docker compose up -d
	@echo "waiting for TimescaleDB to accept connections…"
	@until docker exec janus-timescaledb pg_isready -U $${POSTGRES_USER:-janus} >/dev/null 2>&1; do sleep 1; done
	@echo "ready."

down:  ## stop dev compose stack
	docker compose down

logs:  ## tail dev compose logs
	docker compose logs -f --tail=200

db-init:  ## create extension + run migrations
	$(PYTHON) scripts/init_db.py

db-shell:  ## psql shell into the dev DB
	docker exec -it janus-timescaledb psql -U $${POSTGRES_USER:-janus} -d $${POSTGRES_DB:-janus}

migrate:  ## generate a new migration (set MSG="…")
	poetry run alembic revision --autogenerate -m "$(MSG)"

fmt:  ## ruff format + ruff fix
	poetry run ruff format janus tests scripts
	poetry run ruff check --fix janus tests scripts

lint:  ## ruff check (no fixes)
	poetry run ruff check janus tests scripts

typecheck:  ## mypy strict on the package
	poetry run mypy janus

test:  ## pytest unit tests
	poetry run pytest tests/unit -q

test-cov:  ## pytest with coverage (must be >= 80%)
	poetry run pytest --cov-fail-under=80

ci: lint typecheck test  ## everything CI runs

api:  ## run the FastAPI dev server
	poetry run uvicorn janus.api.main:app --reload --host 0.0.0.0 --port 8000

docker-build:  ## build the production image locally
	docker build -t janus:dev .

docker-run-api:  ## run the API in the production image
	docker run --rm -it -p 8000:8000 --env-file .env janus:dev

bootstrap-tenant:  ## create a local tenant + admin key (requires DB up)
	poetry run python scripts/admin_keys.py create-tenant --name dev --plan free

clean:  ## drop caches, dist, eggs
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
