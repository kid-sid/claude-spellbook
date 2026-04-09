# Tools

Reusable tool configurations for code formatting, linting, and quality checks.
These configs power the Claude Code hooks in `.claude/settings.local.json`.

## Structure

```
tools/
├── node/
│   ├── package.json            # prettier, eslint, markdownlint-cli2
│   ├── .prettierrc             # Prettier config
│   ├── .markdownlint.json      # Markdownlint rules
│   └── eslint.config.js        # ESLint for JS/TS
├── typescript/
│   ├── package.json            # typescript, tsx, prettier, eslint
│   ├── tsconfig.json           # strict TypeScript config
│   ├── .prettierrc             # Prettier config
│   └── eslint.config.js        # ESLint with type-checked rules
├── svelte/
│   ├── package.json            # SvelteKit, vite, svelte-check, prettier-plugin-svelte
│   ├── svelte.config.js        # SvelteKit adapter + alias config
│   ├── vite.config.ts          # Vite config with test setup
│   ├── tsconfig.json           # TypeScript config for Svelte
│   ├── .prettierrc             # Prettier with svelte plugin
│   └── eslint.config.js        # ESLint for .ts + .svelte files
├── python/
│   ├── requirements-dev.txt    # black, ruff
│   └── pyproject.toml          # black + ruff config
├── go/
│   └── .golangci.yml           # golangci-lint config
├── rust/
│   ├── rustfmt.toml            # rustfmt formatting config
│   ├── clippy.toml             # clippy lint thresholds
│   └── rust-toolchain.toml     # pins stable + rustfmt + clippy + rust-analyzer
├── install.sh                  # copies configs into any project
└── README.md                   # this file
```

## Installing into a Project

```bash
# From inside the claude-spellbook directory:

bash tools/install.sh node           --target /path/to/project
bash tools/install.sh typescript     --target /path/to/project
bash tools/install.sh svelte         --target /path/to/project
bash tools/install.sh python         --target /path/to/project
bash tools/install.sh go             --target /path/to/project
bash tools/install.sh rust           --target /path/to/project
bash tools/install.sh all            --target /path/to/project

# Install into current directory (omit --target)
bash tools/install.sh python
```

Or from the spellbook root using `make`:

```bash
make setup TARGET=/path/to/project LANG=typescript
make setup TARGET=/path/to/project LANG=svelte
make setup TARGET=/path/to/project LANG=rust
```

## After Installing

### Node
```bash
npm install
```

### TypeScript
```bash
npm install
# Run type check
npx tsc --noEmit
```

### Svelte
```bash
npm install
npx svelte-kit sync   # generates .svelte-kit/tsconfig.json (needed by tsconfig.json)
npm run dev
```

### Python
```bash
pip install -r requirements-dev.txt
```

### Go
```bash
# gofmt ships with Go — no install needed
# golangci-lint:
brew install golangci-lint           # macOS
# or: curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh
```

### Rust
```bash
rustup component add rustfmt clippy rust-analyzer
# Verify:
cargo fmt --check
cargo clippy -- -D warnings
```

## Tool Reference

| Tool | Language | What it does | Hook |
|------|----------|-------------|------|
| `prettier` | TS/JS/Svelte/MD | Auto-formats code | `afterWrite` |
| `eslint` | TS/JS | Lints and fixes | `afterEdit` |
| `eslint-plugin-svelte` | Svelte | Lints `.svelte` files | `afterEdit` |
| `markdownlint-cli2` | Markdown | Lints markdown | `afterEdit` |
| `svelte-check` | Svelte | Type checks `.svelte` | manual / CI |
| `black` | Python | Auto-formats code | `afterWrite` |
| `ruff` | Python | Lints and fixes | `afterEdit` |
| `gofmt` | Go | Auto-formats code | `afterWrite` |
| `golangci-lint` | Go | Lints code | `afterEdit` |
| `rustfmt` | Rust | Auto-formats code | `afterWrite` |
| `clippy` | Rust | Lints code | `afterEdit` |
| `rust-analyzer` | Rust | IDE + type checks | IDE / LSP |

## Hook Commands (copy into `.claude/settings.local.json`)

```json
"afterWrite": [
  { "matcher": "src/**/*.ts",     "command": "prettier --write {file}" },
  { "matcher": "src/**/*.svelte", "command": "prettier --write {file}" },
  { "matcher": "src/**/*.py",     "command": "black {file}" },
  { "matcher": "src/**/*.go",     "command": "gofmt -w {file}" },
  { "matcher": "src/**/*.rs",     "command": "rustfmt {file}" }
],
"afterEdit": [
  { "matcher": "src/**/*.ts",     "command": "eslint --fix {file}" },
  { "matcher": "src/**/*.svelte", "command": "eslint --fix {file}" },
  { "matcher": "src/**/*.py",     "command": "ruff check --fix {file}" },
  { "matcher": "src/**/*.go",     "command": "golangci-lint run {file}" },
  { "matcher": "src/**/*.rs",     "command": "cargo clippy --fix --allow-dirty 2>/dev/null || true" }
]
```
