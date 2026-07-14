.PHONY: install test lint typecheck format clean build check-all

install:
	pip install -e ".[dev,all]"

test:
	pytest --cov=incident_commander --cov-report=term-missing

lint:
	ruff check src/ tests/

typecheck:
	mypy --strict src/

format:
	ruff format src/ tests/

clean:
	rm -rf dist/ build/ *.egg-info/
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	rm -rf htmlcov/ .coverage

build:
	python -m build

check-all: lint typecheck test
	@echo "All checks passed ✓"
