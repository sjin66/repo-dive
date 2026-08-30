VENV ?= .venv
ifeq ($(OS),Windows_NT)
PYTHON ?= python
VENV_PYTHON := $(VENV)/Scripts/python.exe
else
PYTHON ?= python3
VENV_PYTHON := $(VENV)/bin/python
endif
DIST_DIR ?= dist

.PHONY: setup check test-unit test-all package package-smoke bundle bundle-smoke release-check

setup:
	$(PYTHON) -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ is required'"
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev]"

check:
	$(VENV_PYTHON) -m ruff format --check .
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m mypy src tests scripts
	$(VENV_PYTHON) scripts/check_repo_contract.py
	$(VENV_PYTHON) scripts/check_release_contract.py

test-unit:
	$(VENV_PYTHON) -m pytest tests/unit -q

test-all:
	$(VENV_PYTHON) -m pytest -q

package:
	$(VENV_PYTHON) -m build --wheel --sdist --outdir "$(DIST_DIR)"

package-smoke: package
	$(VENV_PYTHON) scripts/package_smoke.py --dist-dir "$(DIST_DIR)"

BUNDLE_TARGET ?= darwin-arm64
BUNDLE_ARCHIVE ?= $(DIST_DIR)/repo-dive-v$$( $(VENV_PYTHON) -c "import repo_dive; print(repo_dive.__version__)" )-$(BUNDLE_TARGET).tar.gz

bundle:
	$(VENV_PYTHON) -m PyInstaller --noconfirm --clean repo-dive.spec
	$(VENV_PYTHON) scripts/archive_bundle.py --bundle dist/repo-dive --target "$(BUNDLE_TARGET)" --output "$(BUNDLE_ARCHIVE)"

bundle-smoke:
	$(VENV_PYTHON) scripts/bundle_smoke.py --archive "$(BUNDLE_ARCHIVE)" --target "$(BUNDLE_TARGET)"

release-check:
	$(VENV_PYTHON) scripts/check_release_contract.py
