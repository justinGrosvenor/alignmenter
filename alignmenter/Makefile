.PHONY: venv install quickstart demo test lint report-last

VENV?=.venv
PYTHON?=python3
REPORTS_DIR?=reports

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/bin/pip install -e .[dev]

quickstart: venv install demo
	@echo "✓ Quickstart complete. View report:"
	@$(MAKE) report-last

demo:
	$(VENV)/bin/alignmenter demo

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check alignmenter

report-last:
	@LATEST=$$(ls -t $(REPORTS_DIR) | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "No reports found in $(REPORTS_DIR)/"; \
		exit 1; \
	fi; \
	REPORT_PATH="$(REPORTS_DIR)/$$LATEST/index.html"; \
	if [ ! -f "$$REPORT_PATH" ]; then \
		echo "No HTML report found at $$REPORT_PATH"; \
		exit 1; \
	fi; \
	echo "Opening $$REPORT_PATH"; \
	if command -v open >/dev/null 2>&1; then \
		open "$$REPORT_PATH"; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open "$$REPORT_PATH"; \
	else \
		echo "Report location: $$REPORT_PATH"; \
		echo "Please open this file in your browser."; \
	fi
