# Variables
VENV = virtual_env
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
MAIN = main.py
MAP = maps/easy/03_basic_capacity.txt

.PHONY: install run debug clean lint lint-strict

install:
	@echo "Creating virtual environment and installing dependencies..."
	python3 -m venv $(VENV)
	$(PIP) install pygame
	@echo "Dependencies successfully installed inside $(VENV)."

run:
	@echo "Running the simulation..."
	$(PYTHON) $(MAIN) $(MAP)

debug:
	@echo "Starting debugger..."
	$(PYTHON) -m pdb $(MAIN) $(MAP)

clean:
	@echo "Cleaning temporary files and caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf $(VENV)
	@echo "Clean complete."
lint:
	@echo "Running standard linting..."
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	@echo "Running strict linting..."
	flake8 .
	mypy . --strict