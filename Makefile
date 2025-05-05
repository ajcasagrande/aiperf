
.PHONY: ruff ruff-fix format check-format install-dev setup-venv isntall-uv

VENV ?= .venv

ruff:
	ruff check .

ruff-fix:
	ruff check . --fix

format:
	ruff format .

check-format:
	ruff format . --check-only

isntall-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

setup-venv: isntall-uv
	uv venv $(VENV)
	$(MAKE) install-dev

install-dev:
	. $(VENV)/bin/activate && uv pip install -e .
