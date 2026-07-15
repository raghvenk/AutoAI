.PHONY: install test lint check-ollama install-browsers run-mcp run-ui run-automation

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/ruff check .

check-ollama:
	curl --fail http://localhost:11434/api/tags

install-browsers:
	.venv/bin/playwright install chromium

run-mcp:
	.venv/bin/qa-agent-mcp

run-ui:
	.venv/bin/qa-agent-ui

run-automation:
	.venv/bin/qa-runner-agent --project-dir output/automation --url "$(TEST_URL)"
