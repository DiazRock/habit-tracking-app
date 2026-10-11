# =============================================================
#  Habit Tracking App — Makefile
#  Python 3.11 project
#
#  Usage:  make help
# =============================================================

# ---------- Config ----------
PYTHON_VERSION   := 3.11
VENV             := .venv
PYTHON           := $(VENV)/bin/python
PIP              := $(VENV)/bin/pip
PYTEST           := $(VENV)/bin/pytest
UVICORN          := $(VENV)/bin/uvicorn
TYPER            := $(VENV)/bin/habit
HABIT_DB         ?= habits.db
API_HOST         ?= 127.0.0.1
API_PORT         ?= 8000
SRC              := habit_tracker
TESTS            := tests

# ---------- Colors ----------
GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
RESET  := \033[0m

# ---------- Default ----------
.DEFAULT_GOAL := help

# ---------- Help ----------
.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "$(BLUE)Habit Tracking App — available targets$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================
#  SETUP
# =============================================================

.PHONY: setup
setup: check-python create-venv install-deps install-dev env-file ## Full first-time setup (venv + deps + .env)
	@echo "$(GREEN)✔ Setup complete. Activate with: source $(VENV)/bin/activate$(RESET)"

.PHONY: check-python
check-python: ## Verify python3.11 is available on PATH
	@command -v python$(PYTHON_VERSION) >/dev/null 2>&1 || { \
		echo "$(YELLOW)python$(PYTHON_VERSION) not found on PATH.$(RESET)"; \
		echo "Install it, or set PYTHON_VERSION in the Makefile."; \
		exit 1; \
	}
	@echo "$(GREEN)✔ python$(PYTHON_VERSION) found$(RESET)"

.PHONY: create-venv
create-venv: ## Create the Python 3.11 virtual environment
	@if [ -d "$(VENV)" ]; then \
		echo "$(YELLOW)venv already exists at $(VENV), skipping.$(RESET)"; \
	else \
		echo "$(BLUE)Creating venv with python$(PYTHON_VERSION)...$(RESET)"; \
		python$(PYTHON_VERSION) -m venv $(VENV); \
	fi

.PHONY: install-deps
install-deps: ## Install runtime dependencies
	@echo "$(BLUE)Upgrading pip...$(RESET)"
	@$(PIP) install --upgrade pip wheel setuptools
	@echo "$(BLUE)Installing runtime dependencies...$(RESET)"
	@$(PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: ## Install dev/test dependencies
	@echo "$(BLUE)Installing dev dependencies...$(RESET)"
	@$(PIP) install -r requirements-dev.txt
	@echo "$(BLUE)Installing package in editable mode...$(RESET)"
	@$(PIP) install -e .

.PHONY: env-file
env-file: ## Create .env from .env.example if missing
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✔ Created .env from .env.example$(RESET)"; \
	else \
		echo "$(YELLOW).env already exists, skipping.$(RESET)"; \
	fi

# =============================================================
#  BUILD
# =============================================================

.PHONY: build
build: ## Build the package (wheel + sdist)
	@$(PYTHON) -m build

.PHONY: build-clean
build-clean: ## Remove build artifacts
	@rm -rf dist/ build/ *.egg-info

# =============================================================
#  RUN
# =============================================================

.PHONY: run
run: ## Run the CLI (interactive). Override: make run ARGS="list"
	@$(TYPER) $(ARGS)

.PHONY: run-api
run-api: ## Run the FastAPI server with uvicorn (reload)
	@HABIT_DB=$(HABIT_DB) $(UVICORN) $(SRC).api.main:app \
		--host $(API_HOST) --port $(API_PORT) --reload

.PHONY: run-api-prod
run-api-prod: ## Run the FastAPI server without reload
	@HABIT_DB=$(HABIT_DB) $(UVICORN) $(SRC).api.main:app \
		--host $(API_HOST) --port $(API_PORT)

.PHONY: shell
shell: ## Open an interactive Python shell with the package importable
	@$(PYTHON) -c "import IPython; IPython.start_ipython(argv=[])" 2>/dev/null \
		|| $(PYTHON)

.PHONY: load-fixtures
load-fixtures: ## Load the 5 predefined habits + 4-week fixture into $(HABIT_DB)
	@$(TYPER) --db $(HABIT_DB) load-fixtures

# =============================================================
#  TEST
# =============================================================

.PHONY: test
test: ## Run unit + integration tests (default: all)
	@$(PYTEST) $(TESTS) -v

.PHONY: test-unit
test-unit: ## Run only unit tests (tests/unit)
	@$(PYTEST) $(TESTS)/unit -v -m unit

.PHONY: test-integration
test-integration: ## Run only integration tests (tests/integration)
	@$(PYTEST) $(TESTS)/integration -v -m integration

.PHONY: test-cov
test-cov: ## Run all tests with coverage report (terminal + html)
	@$(PYTEST) $(TESTS) -v \
		--cov=$(SRC) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=85

.PHONY: test-watch
test-watch: ## Re-run tests on file change (requires pytest-watch)
	@$(VENV)/bin/ptw -- $(TESTS) -v

.PHONY: test-fast
test-fast: ## Run tests, stop at first failure, no coverage
	@$(PYTEST) $(TESTS) -x -q

# =============================================================
#  QUALITY
# =============================================================

.PHONY: lint
lint: ## Run ruff + black --check + mypy
	@echo "$(BLUE)ruff...$(RESET)"
	@$(VENV)/bin/ruff check $(SRC) $(TESTS)
	@echo "$(BLUE)black --check...$(RESET)"
	@$(VENV)/bin/black --check $(SRC) $(TESTS)
	@echo "$(BLUE)mypy...$(RESET)"
	@$(VENV)/bin/mypy $(SRC)

.PHONY: format
format: ## Auto-format with black + ruff --fix
	@$(VENV)/bin/black $(SRC) $(TESTS)
	@$(VENV)/bin/ruff check --fix $(SRC) $(TESTS)

.PHONY: typecheck
typecheck: ## Run mypy only
	@$(VENV)/bin/mypy $(SRC)

# =============================================================
#  CLEAN
# =============================================================

.PHONY: clean
clean: ## Remove caches, build artifacts, coverage reports
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache"  -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache"  -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ .coverage coverage.xml dist/ build/ *.egg-info
	@echo "$(GREEN)✔ Cleaned$(RESET)"

.PHONY: clean-venv
clean-venv: ## Remove the virtual environment
	@rm -rf $(VENV)
	@echo "$(GREEN)✔ Removed $(VENV)$(RESET)"

.PHONY: clean-db
clean-db: ## Remove local SQLite database
	@rm -f $(HABIT_DB)
	@echo "$(GREEN)✔ Removed $(HABIT_DB)$(RESET)"

.PHONY: reset
reset: clean clean-venv clean-db ## Full reset: caches, venv, local DB
	@echo "$(GREEN)✔ Full reset done. Run 'make setup' to start fresh.$(RESET)"

# =============================================================
#  CI SHORTCUT
# =============================================================

.PHONY: ci
ci: lint test-cov ## What CI runs