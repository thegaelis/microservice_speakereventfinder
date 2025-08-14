# Simple Event Speaker Finder Microservice
# Makefile for essential development tasks

# Variables
PYTHON = python3
PIP = pip3
VENV = venv
VENV_ACTIVATE = $(VENV)/bin/activate
APP_MODULE = app.py
PORT = 8345
HOST = 0.0.0.0

# Default target
.PHONY: help
help: ## Show available commands
	@echo "Simple Event Speaker Finder Microservice"
	@echo "========================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Setup
.PHONY: setup
setup: ## Setup project (venv + install deps)
	@echo "🚀 Setting up project..."
	$(PYTHON) -m venv $(VENV)
	. $(VENV_ACTIVATE) && $(PIP) install --upgrade pip
	. $(VENV_ACTIVATE) && $(PIP) install -r requirements.txt
	@echo "✅ Setup complete!"

# Run
.PHONY: run
run: ## Start the server
	@echo "🌟 Starting server on http://$(HOST):$(PORT)"
	. $(VENV_ACTIVATE) && $(PYTHON) $(APP_MODULE)

.PHONY: dev
dev: stop run ## Restart server

.PHONY: stop
stop: ## Stop the server
	@pkill -f "python.*$(APP_MODULE)" || echo "No server running"
	@sleep 1

# Clean
.PHONY: clean
clean: ## Clean cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

.PHONY: reset
reset: ## Reset everything (clean + reinstall)
	rm -rf $(VENV)
	$(MAKE) setup
