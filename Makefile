#!/usr/bin/make -f
# Makefile for local development tasks (start OpenSearch, manage deps)

.PHONY: local local-down deps uv-sync uv-test worker beat help

# Detect docker compose command at make-parse time (prefer `docker compose`)
DOCKER_COMPOSE_CMD_DETECTED := $(if $(shell docker compose version >/dev/null 2>&1 && echo ok),docker compose,$(if $(shell command -v docker-compose >/dev/null 2>&1 && echo ok),docker-compose,))

# Start the local OpenSearch stack (uses elastic-start-local/docker-compose.yml)
local:
	@echo "Starting local OpenSearch stack..."
	@$(MAKE) ensure-docker
	@cd elastic-start-local && . ../.make_docker_env && eval "$$DOCKER_COMPOSE_CMD up -d --remove-orphans"
	@echo "OpenSearch stack started."

local-down:
	@echo "Stopping local OpenSearch stack..."
	@cd elastic-start-local && . ../.make_docker_env && eval "$$DOCKER_COMPOSE_CMD down --volumes --remove-orphans"
	@echo "OpenSearch stack stopped."


.PHONY: ensure-docker
ensure-docker:
	# detect compose command at parse time and write to .make_docker_env
	@if [ -z "$(DOCKER_COMPOSE_CMD_DETECTED)" ]; then \
		echo "No docker compose command detected; please install Docker or docker-compose."; rm -f .make_docker_env; exit 1; \
	fi; \
	# Quick check if Docker daemon is responsive; try to start Docker on macOS
	@if ! docker info >/dev/null 2>&1; then \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "Docker daemon not running. Attempting to start Docker Desktop..."; \
			open -a Docker || true; \
			SECS=0; until docker info >/dev/null 2>&1 || [ $$SECS -ge 120 ]; do sleep 2; SECS=$$((SECS+2)); echo "waiting for docker... ($$SECS)s"; done; \
			if ! docker info >/dev/null 2>&1; then \
				echo "Timed out waiting for Docker daemon; please start Docker Desktop manually."; exit 1; \
			fi; \
		else \
			echo "Docker daemon not running; please start Docker."; exit 1; \
		fi; \
	fi; \
	echo "Using compose command: $(DOCKER_COMPOSE_CMD_DETECTED)"
	echo "DOCKER_COMPOSE_CMD='$(DOCKER_COMPOSE_CMD_DETECTED)'" > .make_docker_env


# Install dependencies via pip as a fallback
deps:
	@echo "Installing Python deps from requirements.txt (pip)..."
	@python -m pip install -r requirements.txt

# Install dependencies using uv (reads pyproject.toml, creates .venv + uv.lock)
uv-sync:
	@command -v uv >/dev/null 2>&1 || (echo "uv not found; install with: brew install uv"; exit 1)
	@echo "Running uv sync..."
	uv sync --all-extras
	@echo "Done. Activate with: source .venv/bin/activate"

# Run tests via uv (no need to activate .venv manually)
uv-test:
	uv run pytest -q

worker:
	uv run celery -A cdm.workers.celery_app:celery_app worker --pool=solo --loglevel=INFO

beat:
	uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO

help:
	@printf "Available targets:\n"
	@printf "  local       - Start local OpenSearch stack via docker-compose\n"
	@printf "  local-down  - Stop local OpenSearch stack and remove volumes\n"
	@printf "  deps        - Install dependencies via pip (legacy)\n"
	@printf "  uv-sync     - Install deps via uv into .venv (reads pyproject.toml)\n"
	@printf "  uv-test     - Run pytest via uv run\n"
	@printf "  worker      - Start the RabbitMQ Celery worker\n"
	@printf "  beat        - Start the daily Celery scheduler\n"
