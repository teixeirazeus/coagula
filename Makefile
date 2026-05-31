.PHONY: install dev test mypy lint clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	python -m pytest -v --tb=short --cov=src/coagula

test-all:
	python -m pytest -v --tb=short --cov=src/coagula --cov-report=term-missing

mypy:
	python -m mypy -p coagula --strict

lint: mypy

clean:
	rm -rf .venv/ build/ dist/ *.egg-info .pytest_cache .mypy_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean
	pip install build
	python -m build

.PHONY: ci
ci: dev test mypy
