PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: setup check test-unit test-all

setup:
	$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

check:
	$(VENV_PYTHON) -m ruff format --check .
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m mypy src tests scripts
	$(VENV_PYTHON) scripts/check_repo_contract.py

test-unit:
	$(VENV_PYTHON) -m pytest tests/unit -q

test-all:
	$(VENV_PYTHON) -m pytest -q

