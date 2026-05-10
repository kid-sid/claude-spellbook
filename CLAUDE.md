# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with `C:\Users\Sidhartha\claude-spellbook`
2. Call `load_history` with `C:\Users\Sidhartha\claude-spellbook`
3. Read both outputs — they contain saved context and conversation history
4. Do not explore files or ask clarifying questions that memory already answers

Save or update memory entries whenever you learn something worth keeping across sessions.
If something loaded from memory is no longer accurate, update it with `save_memory` using the same key.
Use short, lowercase keys: `stack`, `current_work`, `gotchas`, `key_files`, etc. Keep values concise — one or two sentences max.

---

## MCP Server (memory_map)
Persistent memory and conversation history is provided by the standalone [memory_map](https://github.com/kid-sid/memory_map) repo — not bundled in this repo.

**Tools available:**
- `load_memory` / `save_memory` / `delete_memory` — per-project key-value context store
- `load_history` / `save_history` — rolling conversation history (20 chunks)
- `set_compression` — set output compression level (0=raw, 1=compact, 2=dense)
- `get_local_structure` — local directory tree (gitignore-aware)
- `get_github_structure` — GitHub repo file tree
- `get_git_history` — recent commits

**Manual history save:** use `/mem_save` at any time to checkpoint the current conversation.

---

## Repository Layout

```
skills/<skill-name>/skill.md     — skill reference files (install to ~/.claude/skills/)
.claude/agents/<name>.md         — autonomous subagents (install to ~/.claude/agents/)
.claude/commands/<name>.md       — slash commands (install to ~/.claude/commands/)
tools/<lang>/                    — drop-in linter/formatter configs for 6 languages
templates/                       — scaffold starters
```

---

## Development Commands

```bash
make install      # Install Node + Python linting tools locally (copies from tools/ into root)
make check        # Check which linting tools are available on your PATH
make format       # Run prettier over all skill markdown files
make lint         # Run markdownlint over all skill markdown files
make help         # List all make targets

# Install tool configs into another project
make setup TARGET=/path/to/project LANG=typescript
bash tools/install.sh python --target /path/to/project
```

There are no automated tests — validation is done by the CI workflows in `.github/workflows/ci.yml`. CI checks run on every push and PR to `main`.

---

## CI Validation Rules

Every `skills/*/skill.md` must pass these checks or CI fails:

- First line is `---` (frontmatter open)
- Has `name:` field in frontmatter
- Has `description:` field in frontmatter
- Has a `## When to Activate` section
- Has a `## Checklist` section with at least one `- [ ]` item

`.claude/commands/*.md` files must be non-empty.

---

## Skill File Format

Every skill follows this exact structure — enforced by CI:

```markdown
---
name: <kebab-case matching folder name>
description: Use when <triggering conditions — NOT a summary of topics>
---

# Title

One-sentence intro.

## When to Activate
- Verb-leading trigger condition (6–8 items)

## Content Sections (## and ###)

## Red Flags
- **Anti-pattern name** — why it's wrong and what to do instead (6–10 items)

## Checklist
- [ ] 8–15 items, "before you ship" perspective
```

**Description discipline:** The `description` field must start with `Use when` and list triggering conditions only. Topic summaries cause auto-activation to fail.

**Code examples:**
- Language-agnostic topics: show Python, TypeScript, and Go as siblings
- Tool-specific content (GitHub Actions, Terraform, Dockerfile): native syntax only
- Anti-patterns: `# BAD` / `# GOOD` pairs in the same code block
- Every skill must have at least one decision/comparison table

**Style:** No meta-commentary. No filler prose. Tables for decision matrices. Checklists close every skill.

---

## Agent File Format

```markdown
---
name: kebab-case-name
description: <one sentence — when to delegate to this agent vs. using a slash command>
tools: Read, Grep, Glob, Bash   # minimum required; omit to inherit all
model: sonnet                   # sonnet | opus | haiku | inherit
color: red                      # optional: red | blue | green | yellow | purple | orange
---

System prompt in second person ("You are a…").
```

Agents run in an isolated context window — they do not see the parent session history. Restrict `tools` to the minimum needed (a read-only audit agent must not have `Write` or `Edit`).

---

## When Editing Skills
- Read `skills/api-design/skill.md` and `skills/claude-api/skill.md` first — they are the canonical format reference
- Match their density and style exactly
- Keep skills focused: one domain per file, no overlap with adjacent skills

## When Adding New Skills
1. Create `skills/<name>/skill.md` following the format above
2. Add the skill to the inventory list in both `CLAUDE.md` and `README.md`
3. Open a PR — CI validates format automatically

## When Adding New Agents
1. Create `.claude/agents/<name>.md`
2. Set `tools` to the minimum required
3. Include a clear output format in the system prompt
4. Add the agent to the Agent Inventory table in both `CLAUDE.md` and `README.md`

---

## Skill Inventory

### Requirements & Design
- `requirements-planning` — user stories, PRDs, acceptance criteria, story pointing
- `system-design` — HLD/LLD, capacity estimation, ADRs, scalability/reliability patterns
- `api-design` — REST API conventions, pagination, error responses, versioning
- `database-design` — schema design, indexing, migrations, query optimization
- `microservices` — service decomposition, sync/async communication, circuit breaker, saga, CQRS, API gateway
- `writing-plans` — zero-placeholder implementation plans: absolute paths, full code blocks, verify commands, rollback steps
- `promptbase` — write and review Claude Code skills for PromptBase sale: scope rules, rejection reasons, listing copy, examples, pre-submission checklist

### Development
- `coding-standards` — naming conventions, SOLID, design patterns, code smells
- `development-workflow` — branching, conventional commits, PR workflow, code review
- `frontend` — React component design, state management (Zustand/Redux Toolkit), TanStack Query, React Hook Form, routing, performance, testing
- `react` — advanced hooks, Next.js App Router, compound components, error boundaries, TypeScript + React patterns
- `angular` — signals, standalone components, inject(), NgRx, RxJS patterns, Angular 17+ control flow
- `tailwind` — composing utilities, responsive design, dark mode, cva variants, custom theme config
- `event-driven` — Kafka producer/consumer, topic partitioning, outbox pattern, dead-letter queues, idempotency, event sourcing
- `caching` — Redis patterns, cache-aside/write-through/write-behind, TTL design, stampede prevention, HTTP Cache-Control, invalidation
- `claude-code` — skills/commands/agents setup, hooks, settings.json permissions, MCP servers, CLAUDE.md
- `spellbook-setup` — install claude-spellbook globally or per-project: skills, agents, commands, memory_map MCP server, lifecycle hooks, tool configs, CLAUDE.md
- `memory-map` — install and configure memory_map MCP server: per-project/global memory, rolling history, hooks, CLAUDE.md session setup, cross-project recall, compression, privacy
- `general-temporal` — durable Python workflows with Temporal: workflow/activity split, determinism rules, retries, signals, state management, versioning, testing
- `temporal` — Temporal workflows, activities, signals, determinism, failure handling (Agentex/ADK-flavored)
- `go` — error handling patterns, goroutines/channels, context propagation, interface composition, generics, functional options, HTTP, table-driven tests

### Languages & Frameworks
- `python` — advanced type hints, async pitfalls, decorators, generators, pattern matching
- `typescript` — utility types, conditional/mapped types, discriminated unions, branded types, `satisfies`
- `fastapi` — FastAPI app structure, Depends injection, Pydantic v2 schemas, error handling, testing routes
- `pydantic` — `field_validator`/`model_validator`, `Annotated` constraints, serialization, generic models, `pydantic-settings`
- `sqlalchemy` — async SQLAlchemy 2.0 `Mapped` models, session management, joins, relationships, Alembic migrations
- `mongodb` — Motor async CRUD, aggregation pipelines, index design, transactions
- `postgresql` — window functions, CTEs, JSONB queries, index design, `EXPLAIN ANALYZE`, schema migrations
- `redis` — data structure selection, caching strategies, pub/sub, Redis Streams, distributed locks
- `websockets-sse` — real-time server push, LLM token streaming, WebSocket connection management, Redis broadcast
- `docker` — Dockerfiles, multi-stage builds, Compose networking, health checks, debugging containers

### AI & Agents
- `agentex` — ACP agent types (sync/async/Temporal), manifests, ADK modules, local dev on Windows
- `openai-agents` — agent definitions, `@function_tool`, handoffs, streaming, guardrails, Agentex ADK integration
- `langgraph` — StateGraph pipelines, conditional routing, tool calling, checkpointers, interrupts
- `ai-engineer` — RAG pipelines, vector search, agent orchestration, prompt engineering, multimodal AI, cost optimization, AI safety
- `complex-doc-rag` — RAG for PDFs (scanned, native, multi-column, tables, images), Excel (merged cells, charts, hidden sheets), CSV (dialect, encoding, wide tables), and standalone images
- `claude-api` — Anthropic SDK patterns, tool use, streaming, agent SDK

### Testing
- `unit-testing` — AAA pattern, mocking, parameterized tests, TDD, coverage
- `integration-testing` — Testcontainers, HTTP API tests, contract testing, test data
- `solution-testing` — Playwright E2E, BDD/Gherkin, smoke tests, flakiness prevention
- `test-strategy` — Pyramid/Trophy/Honeycomb models, coverage targets, test plans
- `performance-testing` — k6, Locust, Go benchmarks, SLO-based pass/fail

### Security & Quality
- `security` — OWASP Top 10, JWT/OAuth2, secrets management, STRIDE, dependency scanning
- `accessibility` — WCAG 2.1/2.2 conformance, ARIA, keyboard navigation, focus management, contrast, screen readers
- `azure` — DefaultAzureCredential, Blob Storage, AI Search (vector/hybrid), Document Intelligence, Key Vault, retry patterns
- `azure-service-bus` — queues vs topics/subscriptions, peek-lock settlement, DLQ, sessions, subscription filters, scheduled messages
- `aws` — IAM credential chain, S3, DynamoDB single-table design, Lambda, SQS batch, Secrets Manager, botocore retry

### CI/CD & Infrastructure
- `ci-cd` — GitHub Actions workflows, quality gates, OIDC auth, artifact publishing
- `containerization` — Dockerfiles, docker-compose, Kubernetes, Helm, security context
- `infrastructure-as-code` — Terraform state, modules, environments, plan/apply workflow

### Deployment & Operations
- `deployment-strategies` — rolling, blue/green, canary, feature flags, rollback
- `observability` — structured logging, Prometheus metrics, OpenTelemetry tracing, SLOs
- `performance` — profiling, caching, N+1 fixes, async patterns, performance budgets
- `incident-response` — severity classification, runbooks, postmortems, MTTD/MTTR
- `technical-documentation` — README templates, OpenAPI, ADRs, tech specs, docs-as-code

---

## Agent Inventory

| Agent | Purpose |
|---|---|
| `security-auditor` | Full codebase OWASP Top 10 audit — secrets, injection, auth, crypto, misconfiguration, dependencies |
| `code-reviewer` | Two-stage PR review: spec compliance then code quality, security, test coverage, and performance |
| `code-reviewer-spec` | Stage 1 only — verify a change fully implements its stated requirements |
| `code-reviewer-quality` | Stage 2 only — code quality, security, performance, and test coverage after spec is confirmed |
| `dependency-auditor` | Audit all manifests for vulnerable, outdated, unpinned, and abandoned packages across every ecosystem |
| `test-coverage-agent` | Map untested code paths across a module and write the missing tests |
| `onboarding-agent` | Generate a new-joiner guide covering architecture, setup, key files, env vars, and gotchas |
