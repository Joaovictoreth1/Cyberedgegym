PYTHON ?= python3
VENV ?= .venv
BIN = $(abspath backend/$(VENV)/bin)
PORT ?= 5500

.PHONY: setup lock-python api web build lint typecheck test test-api test-web audit check

setup:
	cd backend && $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	npm ci
	npx playwright install chromium

lock-python:
	cd backend && CUSTOM_COMPILE_COMMAND='make lock-python' $(BIN)/pip-compile --upgrade --strip-extras requirements.in
	cd backend && CUSTOM_COMPILE_COMMAND='make lock-python' $(BIN)/pip-compile --upgrade --strip-extras requirements-dev.in

api:
	cd backend && $(BIN)/uvicorn main:app --reload --no-server-header

web: build
	$(PYTHON) -m http.server --bind 127.0.0.1 --directory dist $(PORT)

build:
	npm run build

lint:
	cd backend && $(BIN)/ruff check . && $(BIN)/ruff format --check .
	npm run lint

typecheck:
	cd backend && $(BIN)/mypy .

test-api:
	cd backend && $(BIN)/pytest --cov --cov-report=term-missing

test-web: build
	npm test

test: test-api test-web

audit:
	cd backend && $(BIN)/pip-audit -r requirements.txt -r requirements-dev.txt
	npm audit --audit-level=low

check: lint typecheck test audit
