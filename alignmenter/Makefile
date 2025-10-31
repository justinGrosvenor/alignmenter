.PHONY: venv install demo test lint

VENV?=.venv
PYTHON?=python3

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/bin/pip install -e .[dev]

demo:
	$(VENV)/bin/alignmenter demo

 test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check alignmenter
