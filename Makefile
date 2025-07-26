# CloudNet Draw - Simple Test Makefile

.DEFAULT_GOAL := help

.PHONY: help setup test unit integration performance security coverage clean clean-all examples example-hld example-mld


# Setup environment and install dependencies
setup:
	@echo "Setting up test environment..."
	@UV_VENV_CLEAR=1 uv venv .venv
	@uv pip install -r requirements-test.txt
	@if [ ! -f azure_query.py ]; then ln -sf azure-query.py azure_query.py; fi
	@echo "Test environment ready"

# Show help
help:
	@echo "Available CloudNet Make Targets:"
	@grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | grep -v '^help:' | awk -F: '{print "  " $$1}' | sort

# Run all tests
test: setup unit integration coverage
	@echo "Running all tests..."
	PYTHONPATH=. uv run pytest tests/ -v

# Run unit tests only
unit: setup
	@echo "Running unit tests..."
	PYTHONPATH=. uv run pytest tests/unit/ -v

# Run integration tests only
integration: setup
	@echo "Running integration tests..."
	PYTHONPATH=. uv run pytest tests/integration/ -v

# Run performance tests
performance: setup
	@echo "Running performance tests..."
	PYTHONPATH=. uv run pytest tests/performance/ -v

# Run security tests
security: setup
	@echo "Running security tests..."
	PYTHONPATH=. uv run pytest tests/security/ -v

# Run tests with coverage
coverage: setup
	@echo "Running tests with coverage..."
	PYTHONPATH=. uv run pytest tests/unit/ --cov=azure_query --cov-report=term --cov-fail-under=80

# Clean up
clean:
	@rm -rf .pytest_cache/ .coverage htmlcov/ __pycache__/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Clean everything including .venv
clean-all: clean
	@rm -rf .venv
	@echo "All artifacts cleaned"

# Generate all example diagrams
examples: setup example-hld example-mld
	@echo "All example diagrams generated"

# Generate HLD example diagrams
example-hld: setup
	@echo "Generating HLD example diagrams..."
	PYTHONPATH=. uv run python azure-query.py hld -t examples/single_zone.json -o examples/single_zone_hld.drawio
	PYTHONPATH=. uv run python azure-query.py hld -t examples/double_zone.json -o examples/double_zone_hld.drawio
	@echo "HLD example diagrams generated"

# Generate MLD example diagrams
example-mld: setup
	@echo "Generating MLD example diagrams..."
	PYTHONPATH=. uv run python azure-query.py mld -t examples/single_zone.json -o examples/single_zone_mld.drawio
	PYTHONPATH=. uv run python azure-query.py mld -t examples/double_zone.json -o examples/double_zone_mld.drawio
	@echo "MLD example diagrams generated"

