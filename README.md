<div align="center">

# claude-spellbook

**A curated library of skills, slash commands, and tool configs that turn Claude Code into a precision engineering assistant.**

[![CI](https://github.com/sidharthamohanty/claude-spellbook/actions/workflows/ci.yml/badge.svg)](https://github.com/sidharthamohanty/claude-spellbook/actions/workflows/ci.yml)
![Skills](https://img.shields.io/badge/skills-21-blueviolet)
![Commands](https://img.shields.io/badge/slash%20commands-10-blue)
![License](https://img.shields.io/badge/license-MIT-green)

*Each skill is a spell. Cast wisely.*

</div>

---

## What's in the box

| Layer | What | Count |
|---|---|---|
| **Skills** | Structured instruction sets loaded contextually by Claude | 21 |
| **Slash Commands** | One-shot `/commands` for common engineering tasks | 10 |
| **Agents** | Autonomous subprocesses for multi-file, long-running tasks | 1 |
| **Tool Configs** | Drop-in linter/formatter configs for 6 languages | 6 |
| **Templates** | Scaffold starters for Node, TypeScript, Python, Svelte | 4 |

---

## Quick Start

### 1. Install skills into Claude Code

Copy the skills you want into your Claude skills directory:

```bash
# Install a single skill
cp -r skills/security ~/.claude/skills/

# Install everything
cp -r skills/* ~/.claude/skills/
```

Claude Code picks them up automatically on the next session — no restart needed.

### 2. Install agents

Copy the `.claude/agents/` folder into any project:

```bash
cp -r .claude/agents /path/to/your-project/.claude/agents
```

Or install globally so they're available in every project:

```bash
cp -r .claude/agents/* ~/.claude/agents/
```

### 3. Install slash commands

Copy the `.claude/commands/` folder into any project you work on:

```bash
cp -r .claude/commands /path/to/your-project/.claude/commands
```

Or install globally into your home Claude directory:

```bash
cp -r .claude/commands ~/.claude/commands
```

### 4. Install tool configs into a project

Use the installer script to drop configs into any project:

```bash
# Single language
bash tools/install.sh node --target /path/to/your-project
bash tools/install.sh python --target /path/to/your-project

# All languages at once
bash tools/install.sh all --target /path/to/your-project
```

Or use the Makefile shorthand:

```bash
make setup TARGET=/path/to/your-project LANG=typescript
```

---

## Skills

Skills are markdown files that Claude loads when a relevant task is triggered. They encode judgment, checklists, and domain knowledge — turning Claude from a general assistant into a specialist for a specific phase of your workflow.

### How skills activate

When you describe a task, Claude matches it against the **"When to Activate"** section in each skill. You don't invoke them manually — they're loaded automatically based on context.

> Example: start a conversation about "designing a REST API for user authentication" and the `api-design` skill loads. Ask Claude to "write a Dockerfile for this service" and `containerization` loads.

### Skill inventory

#### Requirements & Design
| Skill | Activates when… |
|---|---|
| `requirements-planning` | Writing user stories, PRDs, or acceptance criteria |
| `system-design` | Designing systems, estimating capacity, drawing architecture |
| `api-design` | Designing or reviewing REST endpoints |
| `database-design` | Designing schemas, indexes, or migrations |

#### Development
| Skill | Activates when… |
|---|---|
| `coding-standards` | Writing or reviewing code for quality/style |
| `development-workflow` | Branching, PRs, commits, or code review |

#### Testing
| Skill | Activates when… |
|---|---|
| `unit-testing` | Writing or fixing unit tests |
| `integration-testing` | Testing APIs, databases, or service boundaries |
| `solution-testing` | Writing E2E or BDD tests with Playwright/Gherkin |
| `test-strategy` | Planning test coverage or choosing a testing model |
| `performance-testing` | Load testing with k6 or Locust |

#### Security & Quality
| Skill | Activates when… |
|---|---|
| `security` | Security reviews, threat modeling, auth/secrets |
| `claude-api` | Building with the Anthropic SDK or Agent SDK |

#### CI/CD & Infrastructure
| Skill | Activates when… |
|---|---|
| `ci-cd` | Writing GitHub Actions workflows or quality gates |
| `containerization` | Writing Dockerfiles, Compose, or Kubernetes configs |
| `infrastructure-as-code` | Working with Terraform modules or environments |

#### Deployment & Operations
| Skill | Activates when… |
|---|---|
| `deployment-strategies` | Planning rollouts, canary deploys, or rollbacks |
| `observability` | Adding logging, metrics, or distributed tracing |
| `performance` | Profiling, caching, or fixing N+1 queries |
| `incident-response` | Responding to, documenting, or learning from incidents |
| `technical-documentation` | Writing READMEs, OpenAPI specs, or tech specs |

---

## Agents

Agents are autonomous subprocesses that run in their own context window with their own tool permissions. Unlike slash commands (which run inline and can pollute the main conversation), agents are isolated — ideal for tasks that span many files, run in parallel, or need a fresh context.

Agents live in `.claude/agents/` and are invoked automatically when Claude decides to delegate based on the agent's `description`.

### When agents beat slash commands

| Use case | Use `/command` | Use agent |
|---|---|---|
| Review current git diff | `/review` | — |
| Audit an entire service (40+ files) | — | `security-auditor` |
| Generate tests for one function | `/test-gen` | — |
| Generate tests for a whole module | — | *(coming soon)* |
| Explain a single file | `/explain` | — |

### Available agents

#### `security-auditor`

Scans a full codebase for OWASP Top 10 vulnerabilities: hardcoded secrets, injection flaws, broken auth, weak crypto, security misconfiguration, vulnerable dependencies, and data exposure.

**Tools:** `Read`, `Grep`, `Glob`, `Bash` · **Model:** Sonnet · **Color:** Red

**Invoke by describing the task:**

```
Audit the src/ directory for security vulnerabilities
Do a full security review of this codebase
Security scan everything under services/payments
```

**Output:** Structured report with severity levels (Critical / High / Medium), file + line citations, evidence snippets, and specific fixes.

> The agent reads context around every pattern match before reporting — false positives from grep are discarded silently.

---

## Slash Commands

Slash commands are one-shot prompts you run with `/command-name` in Claude Code. They're stored in `.claude/commands/` and show up in the `/` menu automatically once installed.

| Command | What it does |
|---|---|
| `/review` | Reviews staged/unstaged changes or a PR for quality and security issues |
| `/security-scan` | Audits code against OWASP Top 10 and the security skill checklist |
| `/test-gen` | Generates unit and integration tests for a file or function |
| `/explain` | Explains a file, function, or architectural pattern in depth |
| `/refactor` | Analyzes code smells and suggests or applies refactoring |
| `/scaffold` | Scaffolds a new service with production-ready boilerplate |
| `/deploy-check` | Runs a pre-deployment verification checklist |
| `/adr` | Generates an Architecture Decision Record from a discussion |
| `/postmortem` | Generates a postmortem document from an incident description |
| `/prd` | Generates a Product Requirements Document pre-filled from context |

### Usage examples

```
# Review your current git diff
/review

# Review a specific pull request
/review 42

# Generate tests for a specific file
/test-gen src/auth/middleware.ts

# Scaffold a new Python API service
/scaffold python-api payments-service

# Create an ADR for a recent decision
/adr We chose Postgres over MongoDB because our data is highly relational
```

---

## Tool Configs

Drop-in configuration files for linters and formatters. Consistent settings across all your projects, managed from one place.

| Language | Tools included |
|---|---|
| `node` | prettier, eslint, markdownlint |
| `typescript` | tsc (strict), prettier, eslint |
| `svelte` | SvelteKit, vite, prettier-plugin-svelte, eslint-plugin-svelte |
| `python` | black, ruff |
| `go` | golangci-lint (gofmt ships with Go) |
| `rust` | rustfmt, clippy, rust-toolchain |

### Installing into a project

```bash
# Node project
bash tools/install.sh node --target ~/projects/my-app

# TypeScript project
bash tools/install.sh typescript --target ~/projects/my-api

# Python project
bash tools/install.sh python --target ~/projects/my-service

# Rust project
bash tools/install.sh rust --target ~/projects/my-crate

# Everything
bash tools/install.sh all --target ~/projects/monorepo
```

> Files that already exist (e.g. `pyproject.toml`) are skipped with a warning pointing to the source — so you can manually merge without losing your customizations.

### Development commands (for working on the spellbook itself)

```bash
make install      # Install Node + Python tools locally
make check        # Check which tools are available on your PATH
make format       # Run prettier over all skill markdown files
make lint         # Run markdownlint over all skill markdown files
make help         # List all available make targets
```

---

## CI / Workflows

Two GitHub Actions workflows keep the spellbook healthy:

### `ci.yml` — runs on every push and PR to `main`

| Job | What it checks |
|---|---|
| **Validate Skill Format** | Every `skills/*/skill.md` has frontmatter (`name`, `description`), a `## When to Activate` section, a `## Checklist` section, and at least one `- [ ]` item |
| **Lint Markdown** | All `.md` files pass markdownlint |
| **Validate Tool Configs** | `tools/install.sh` parses cleanly; all 6 language tool directories and key config files are present |
| **Validate Slash Commands** | Every `.claude/commands/*.md` is non-empty |
| **Check Cross-References** | Logs how many other skills reference each skill (informational) |

### `release.yml` — runs on version tags (`v*`)

Creates a GitHub Release with an auto-generated changelog and a summary of how many skills, commands, and tool configs are in the release.

```bash
# Create a release
git tag v1.2.0
git push origin v1.2.0
```

---

## Repository Structure

```
claude-spellbook/
├── skills/
│   └── <skill-name>/
│       └── skill.md          # Frontmatter + sections + checklist
│
├── .claude/
│   ├── agents/
│   │   └── <agent>.md        # Agent definitions (system prompt + frontmatter)
│   └── commands/
│       └── <command>.md      # Slash command definitions
│
├── tools/
│   ├── install.sh            # Installer script
│   ├── node/                 # prettier, eslint, markdownlint
│   ├── typescript/           # tsconfig, strict eslint
│   ├── svelte/               # SvelteKit, vite, prettier-plugin-svelte
│   ├── python/               # black, ruff (pyproject.toml)
│   ├── go/                   # golangci-lint
│   └── rust/                 # rustfmt, clippy, rust-toolchain
│
├── templates/
│   ├── python-api/           # FastAPI scaffold starter
│   ├── typescript-api/       # Express/Fastify scaffold starter
│   └── svelte-app/           # SvelteKit scaffold starter
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml            # Format + skill validation on push/PR
│   │   └── release.yml       # GitHub Release on version tags
│   ├── ISSUE_TEMPLATE/
│   │   ├── new-skill.md      # Issue template for proposing skills
│   │   └── bug_report.md     # Issue template for bugs
│   └── PULL_REQUEST_TEMPLATE.md
│
├── CLAUDE.md                 # Skill format spec and repo conventions
└── Makefile                  # install / check / format / lint / setup
```

---

## Writing a New Skill

Every skill follows a strict format enforced by CI. Read `CLAUDE.md` for the full spec, or use `api-design` and `claude-api` as canonical examples.

The required structure:

```markdown
---
name: kebab-case-name
description: One dense keyword-rich sentence.
---

# Title

One-sentence intro.

## When to Activate
- Verb-leading trigger condition
- ...

## Content sections...

## Checklist
- [ ] At least 8 items
```

To add a new skill:

1. Create `skills/<name>/skill.md` following the format above
2. Add an entry to the skill inventory table in `CLAUDE.md`
3. Open a PR — CI will validate the format automatically

To propose a skill without writing it, open an issue using the **New Skill Request** template.

---

## Contributing

1. Fork the repo and create a branch: `feat/skill-<name>` or `fix/<issue>`
2. Follow the skill format — CI will catch format errors
3. Fill in the PR template (type of change, checklist, test notes)
4. Conventional commit messages: `feat:`, `fix:`, `docs:`, `chore:`

---

## License

MIT
