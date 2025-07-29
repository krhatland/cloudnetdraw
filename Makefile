# CloudNet Draw - Simple Test Makefile

.DEFAULT_GOAL := help

<<<<<<< Updated upstream
.PHONY: help setup test unit integration performance security coverage clean clean-all examples
=======
.PHONY: help setup test unit integration performance security coverage clean clean-all clean-build build test-publish publish prepare-release examples example-hld example-mld stress

# Set SEED variable to enable deterministic topology generation
# Usage: make examples SEED=12345 (reproducible)
#        make examples          (random, default)
SEED ?=
SEED_FLAG = $(if $(SEED),--seed $(SEED),)

# Set ENSURE_ALL_EDGE_TYPES variable to enable EdgeType guarantee system
# Usage: make examples ENSURE_ALL_EDGE_TYPES=1 (enable EdgeType guarantee)
#        make examples                          (default, no guarantee)
ENSURE_ALL_EDGE_TYPES ?=
ENSURE_FLAG = $(if $(ENSURE_ALL_EDGE_TYPES),--ensure-all-edge-types,)
>>>>>>> Stashed changes


# Setup environment and install dependencies
setup:
	@echo "Setting up test environment..."
	@uv venv --clear && uv pip install -e ".[dev]"
	@echo "Test environment ready"

# Show help
help:
	@echo "Available CloudNet Make Targets:"
	@grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | grep -v '^help:' | awk -F: '{print "  " $$1}' | sort

# Run all tests  
test: setup random integration coverage
	@echo "All tests completed - unit tests with coverage and integration tests"

# Run unit tests only
unit: setup
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v

# Run integration tests only
integration: setup
	@echo "Running integration tests..."
	uv run pytest tests/integration/ -v

# Run performance tests
performance: setup
	@echo "Running performance tests..."
	uv run pytest tests/performance/ -v

# Run security tests
security: setup
	@echo "Running security tests..."
	uv run pytest tests/security/ -v

# Run tests with coverage
coverage: setup
	@echo "Running tests with coverage..."
	uv run pytest tests/unit/ --cov=cloudnetdraw --cov-report=term --cov-fail-under=80

# Clean up
clean:
	@rm -rf .pytest_cache/ .coverage htmlcov/ __pycache__/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Clean everything including .venv
clean-all: clean
	@rm -rf .venv
	@echo "All artifacts cleaned"

<<<<<<< Updated upstream
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
=======
# Generate all example diagrams
examples: setup
	@rm -f examples/*.json examples/*.drawio
#	@echo "Hub-rich networks (high centralization + high connectivity):"
	@cd utils && python3 topology-generator.py --vnets 50 --centralization 9 --connectivity 8 --isolation 1 --output ../examples/many_hubs_dense.json $(SEED_FLAG) $(ENSURE_FLAG)
	@cd utils && python3 topology-generator.py --vnets 100 --centralization 8 --connectivity 9 --isolation 2 --output ../examples/large_multi_hub.json $(SEED_FLAG) $(ENSURE_FLAG)
	@echo ""
#	@echo "Traditional hub-spoke (high centralization + low connectivity):"
	@cd utils && python3 topology-generator.py --vnets 30 --centralization 9 --connectivity 3 --isolation 1 --output ../examples/classic_hub_spoke.json $(SEED_FLAG) $(ENSURE_FLAG)
	@cd utils && python3 topology-generator.py --vnets 15 --centralization 8 --connectivity 2 --isolation 1 --output ../examples/small_hub_spoke.json $(SEED_FLAG) $(ENSURE_FLAG)
	@echo ""
#	@echo "Mesh-like networks (low centralization + high connectivity):"
	@cd utils && python3 topology-generator.py --vnets 40 --centralization 2 --connectivity 9 --isolation 1 --output ../examples/dense_mesh.json $(SEED_FLAG) $(ENSURE_FLAG)
	@cd utils && python3 topology-generator.py --vnets 25 --centralization 3 --connectivity 8 --isolation 1 --output ../examples/medium_mesh.json $(SEED_FLAG) $(ENSURE_FLAG)
	@echo ""
#	@echo "Sparse networks (low centralization + low connectivity):"
	@cd utils && python3 topology-generator.py --vnets 20 --centralization 3 --connectivity 3 --isolation 2 --output ../examples/sparse_network.json $(SEED_FLAG) $(ENSURE_FLAG)
	@cd utils && python3 topology-generator.py --vnets 60 --centralization 4 --connectivity 4 --isolation 3 --output ../examples/medium_sparse.json $(SEED_FLAG) $(ENSURE_FLAG)
	@echo ""
#	@echo "Fragmented networks (high isolation):"
	@cd utils && python3 topology-generator.py --vnets 30 --centralization 5 --connectivity 5 --isolation 8 --output ../examples/highly_fragmented.json $(SEED_FLAG) $(ENSURE_FLAG)
	@cd utils && python3 topology-generator.py --vnets 15 --centralization 2 --connectivity 2 --isolation 7 --output ../examples/mostly_isolated.json $(SEED_FLAG) $(ENSURE_FLAG)
	@echo ""
	@echo "Generating HLD diagrams..."
	@for json_file in examples/*.json; do \
		base_name=$$(basename "$$json_file" .json); \
		echo "  Creating $${base_name}_hld.drawio..."; \
		uv run cloudnetdraw hld -t "$$json_file" -o "examples/$${base_name}_hld.drawio"; \
	done
	@echo ""
	@echo "Generating MLD diagrams..."
	@for json_file in examples/*.json; do \
		base_name=$$(basename "$$json_file" .json); \
		echo "  Creating $${base_name}_mld.drawio..."; \
		uv run cloudnetdraw mld -t "$$json_file" -o "examples/$${base_name}_mld.drawio"; \
	done
	@echo ""
	@echo "Validating generated diagrams..."
	@cd examples && python3 ../utils/topology-validator.py

# Run comprehensive stress test
random: setup
	@echo "Generating and validating random topologies..."
	@cd utils && python3 topology-randomizer.py --iterations 25 --vnets 100 --max-centralization 10 --max-connectivity 10 --max-isolation 10 --parallel-jobs 5 $(ENSURE_FLAG)

# Build package for distribution
build: setup
	@echo "Building package..."
	@uv build
	@echo "Package built successfully"
>>>>>>> Stashed changes

# Publish to TestPyPI for testing
test-publish: build
	@echo "Publishing to TestPyPI..."
	@uv publish --publish-url https://test.pypi.org/legacy/
	@echo "Published to TestPyPI"

# Publish to production PyPI
publish: build
	@echo "Publishing to PyPI..."
	@uv publish --publish-url https://upload.pypi.org/legacy/
	@echo "Published to PyPI"

# Clean build artifacts
clean-build:
	@echo "Cleaning build artifacts..."
	@rm -rf dist/ build/ *.egg-info/
	@echo "Build artifacts cleaned"

# Prepare release - run tests, build, and validate
prepare-release: test build
	@echo "Preparing release..."
	@echo "All tests passed, package built successfully"
	@echo "Ready to publish to PyPI"
	@ls -la dist/
	@echo "Run 'make test-publish' to test on TestPyPI first, then 'make publish' for production"
