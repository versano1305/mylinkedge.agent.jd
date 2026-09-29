.PHONY: install dev test sqs-worker

install:
	uv pip install -e ".[dev]"

dev:
	langgraph dev

test:
	pytest

sqs-worker:
	python -m jd_agent.container.cli --container sqs
