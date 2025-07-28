# CloudNet Draw - Simple Test Makefile

.DEFAULT_GOAL := help

.PHONY: help setup test unit integration performance security coverage clean clean-all examples


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

# Generate example JSON files and both HLD/MLD diagrams
examples: setup
	@echo "Cleaning existing example files..."
	@rm -f examples/*.json examples/*.drawio
	@echo "Generating example JSON files..."
	@cd examples && uv run generate-sample-topology.py 1 15 20 single_zone.json
	@cd examples && uv run generate-sample-topology.py 2 40 25 double_zone.json
	@cd examples && uv run generate-sample-topology.py 1 8 0 hub_to_spoke_example.json
	@cd examples && uv run generate-sample-topology.py 0 6 3 spoke_to_spoke_example.json
	@cd examples && uv run generate-sample-topology.py 0 0 8 unpeered_only_example.json
	@cd examples && uv run generate-sample-topology.py 3 60 31 multi_hub_example.json
	@cd examples && uv run generate-sample-topology.py 2 8 5 test_topology.json
	@echo "Generating HLD diagrams..."
	@PYTHONPATH=. uv run azure-query.py hld -t examples/single_zone.json -o examples/single_zone_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/double_zone.json -o examples/double_zone_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/hub_to_spoke_example.json -o examples/hub_to_spoke_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/spoke_to_spoke_example.json -o examples/spoke_to_spoke_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/unpeered_only_example.json -o examples/unpeered_only_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/multi_hub_example.json -o examples/multi_hub_hld.drawio
	@PYTHONPATH=. uv run azure-query.py hld -t examples/test_topology.json -o examples/test_topology_hld.drawio
	@echo "Generating MLD diagrams..."
	@PYTHONPATH=. uv run azure-query.py mld -t examples/single_zone.json -o examples/single_zone_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/double_zone.json -o examples/double_zone_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/hub_to_spoke_example.json -o examples/hub_to_spoke_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/spoke_to_spoke_example.json -o examples/spoke_to_spoke_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/unpeered_only_example.json -o examples/unpeered_only_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/multi_hub_example.json -o examples/multi_hub_mld.drawio
	@PYTHONPATH=. uv run azure-query.py mld -t examples/test_topology.json -o examples/test_topology_mld.drawio
	@echo "Validating generated diagrams..."
	@cd examples && python3 validate-samples.py
	@echo "All example files and diagrams generated"

