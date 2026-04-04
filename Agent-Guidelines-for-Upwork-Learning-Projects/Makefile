.PHONY: install lint fmt typecheck test all preflight clean

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip

install:
	uv venv .venv
	uv pip install -e ".[dev,security]" --python $(PYTHON)

lint:
	$(PYTHON) -m ruff check src/ tests/

fmt:
	$(PYTHON) -m ruff format src/ tests/

typecheck:
	$(PYTHON) -m mypy src/

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing

audit:
	uv pip install pip-audit --python $(PYTHON) && $(PYTHON) -m pip_audit

preflight:
	bash preflight.sh

all: lint typecheck test

clean:
	rm -rf .venv __pycache__ .mypy_cache .pytest_cache .coverage coverage.xml
