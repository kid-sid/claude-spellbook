.PHONY: install install-node install-python check format lint help

## Install all tool configs into this directory (for spellbook dev)
install: install-node install-python
	@echo "✓ All tools installed"

## Install Node tools
install-node:
	@command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found — https://nodejs.org"; exit 1; }
	cp tools/node/package.json .
	cp tools/node/.prettierrc .
	cp tools/node/.markdownlint.json .
	cp tools/node/eslint.config.js .
	npm install
	@echo "✓ Node tools ready"

## Install Python tools
install-python:
	@command -v pip >/dev/null 2>&1 || { echo "ERROR: pip not found — https://python.org"; exit 1; }
	cp tools/python/requirements-dev.txt .
	cp tools/python/pyproject.toml .
	pip install -r requirements-dev.txt
	@echo "✓ Python tools ready"

## Install tools into a specific project (usage: make setup TARGET=/path/to/project LANG=all)
setup:
	@[ -n "$(TARGET)" ] || { echo "Usage: make setup TARGET=/path/to/project LANG=[node|python|go|all]"; exit 1; }
	bash tools/install.sh $(or $(LANG),all) --target $(TARGET)

## Check which tools are available
check:
	@echo "Checking installed tools..."
	@command -v prettier          >/dev/null 2>&1 && echo "  ✓ prettier"          || echo "  ✗ prettier          (run: make install-node)"
	@command -v eslint            >/dev/null 2>&1 && echo "  ✓ eslint"            || echo "  ✗ eslint            (run: make install-node)"
	@npx markdownlint-cli2 --version >/dev/null 2>&1 && echo "  ✓ markdownlint-cli2" || echo "  ✗ markdownlint-cli2 (run: make install-node)"
	@command -v black             >/dev/null 2>&1 && echo "  ✓ black"             || echo "  ✗ black             (run: make install-python)"
	@command -v ruff              >/dev/null 2>&1 && echo "  ✓ ruff"              || echo "  ✗ ruff              (run: make install-python)"
	@command -v gofmt             >/dev/null 2>&1 && echo "  ✓ gofmt"             || echo "  ✗ gofmt             (install Go: https://go.dev)"
	@command -v golangci-lint     >/dev/null 2>&1 && echo "  ✓ golangci-lint"     || echo "  ✗ golangci-lint     (brew install golangci-lint)"

## Format all markdown files in skills/
format:
	npx prettier --write "skills/**/*.md" "*.md" --ignore-path .gitignore

## Lint all markdown files in skills/
lint:
	npx markdownlint-cli2 "skills/**/*.md" "*.md" "#node_modules"

## Show this help
help:
	@grep -E '^##' Makefile | sed 's/## /  /'
