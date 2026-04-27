.PHONY: help clean lint test coverage docs build install dev
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  install    Install project (editable) with dev extras"
	@echo "  dev        Install pre-commit hooks"
	@echo "  lint       Run ruff check + format check"
	@echo "  test       Run unit tests"
	@echo "  coverage   Run tests with coverage report"
	@echo "  build      Build sdist + wheel into dist/"
	@echo "  docs       Build Sphinx HTML docs"
	@echo "  clean      Remove build / cache artifacts"

install:
	python -m pip install -e ".[dev]"

dev: install
	pre-commit install

lint:
	ruff check .
	ruff format --check .

test:
	pytest

coverage:
	pytest --cov=telegram_upload --cov-report=term-missing

build: clean
	python -m build
	ls -l dist

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html

clean:
	rm -rf build/ dist/ *.egg-info .eggs htmlcov/ .coverage .tox/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
