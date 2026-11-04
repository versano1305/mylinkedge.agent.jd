.PHONY: install codeartifact-login dev test sqs-worker http-server grpc-server

codeartifact-login: ## Print uv CodeArtifact exports (run: eval "$$(make codeartifact-login)")
	@./scripts/codeartifact-login.sh

install:
	uv sync --extra dev

dev:
	langgraph dev

test:
	pytest

sqs-worker:
	python -m jd_agent.container.cli --container sqs

http-server:
	python -m jd_agent.container.cli --container http

grpc-server:
	python -m jd_agent.container.cli --container grpc
