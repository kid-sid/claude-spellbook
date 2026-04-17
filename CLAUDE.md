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
This repo includes an MCP server at `mcp/server.py` that provides persistent memory and conversation history.

**Tools available:**
- `load_memory` / `save_memory` / `delete_memory` — per-project key-value context store
- `load_history` / `save_history` — rolling conversation history (20 chunks)
- `set_compression` — set output compression level (0=raw, 1=compact, 2=dense)
- `get_local_structure` — local directory tree (gitignore-aware)
- `get_github_structure` — GitHub repo file tree
- `get_git_history` — recent commits

**One-time setup (already done):** `claude mcp add file-structure C:/Users/Sidhartha/claude-spellbook/mcp/venv/Scripts/python.exe C:/Users/Sidhartha/claude-spellbook/mcp/server.py`

**Manual history save:** use `/mem_save` at any time to checkpoint the current conversation.

---

# Claude Spellbook

This is a curated library of Claude Code skills, agents, and slash commands covering the full software engineering lifecycle.

## Repository Layout

```
skills/<skill-name>/skill.md     — skill reference files (install to ~/.claude/skills/)
.claude/agents/<name>.md         — autonomous subagents (install to ~/.claude/agents/)
.claude/commands/<name>.md       — slash commands (install to ~/.claude/commands/)
```

## Skill Inventory

### Requirements & Design
- `requirements-planning` — user stories, PRDs, acceptance criteria, story pointing
- `system-design` — HLD/LLD, capacity estimation, ADRs, scalability/reliability patterns
- `api-design` — REST API conventions, pagination, error responses, versioning
- `database-design` — schema design, indexing, migrations, query optimization
- `microservices` — service decomposition, sync/async communication, circuit breaker, saga, CQRS, API gateway

### Development
- `coding-standards` — naming conventions, SOLID, design patterns, code smells
- `development-workflow` — branching, conventional commits, PR workflow, code review

### Testing
- `unit-testing` — AAA pattern, mocking, parameterized tests, TDD, coverage
- `integration-testing` — Testcontainers, HTTP API tests, contract testing, test data
- `solution-testing` — Playwright E2E, BDD/Gherkin, smoke tests, flakiness prevention
- `test-strategy` — Pyramid/Trophy/Honeycomb models, coverage targets, test plans
- `performance-testing` — k6, Locust, Go benchmarks, SLO-based pass/fail

### Security & Quality
- `security` — OWASP Top 10, JWT/OAuth2, secrets management, STRIDE, dependency scanning
- `accessibility` — WCAG 2.1/2.2 conformance, ARIA, keyboard navigation, focus management, contrast, screen readers
- `claude-api` — Anthropic SDK patterns, tool use, streaming, agent SDK
- `azure` — DefaultAzureCredential, Blob Storage, AI Search (vector/hybrid), Document Intelligence, Key Vault, retry patterns

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

## Agent Inventory

| Agent | Purpose |
|---|---|
| `security-auditor` | Full codebase OWASP Top 10 audit — secrets, injection, auth, crypto, misconfiguration, dependencies |
| `code-reviewer` | Deep PR review across logic, quality, security, test coverage, and performance for large diffs |
| `dependency-auditor` | Audit all manifests for vulnerable, outdated, unpinned, and abandoned packages across every ecosystem |
| `test-coverage-agent` | Map untested code paths across a module and write the missing tests |
| `onboarding-agent` | Generate a new-joiner guide covering architecture, setup, key files, env vars, and gotchas |

## Conventions for This Repo

### Skill File Format
Every skill file follows this exact structure:
```markdown
---
name: <kebab-case matching folder name>
description: <one dense keyword-rich sentence>
---

# Title

One-sentence intro.

## When to Activate
- 6-8 verb-leading trigger conditions

## Content Sections (## and ###)

## Checklist
- [ ] 8-15 items, "before you ship" perspective
```

### Code Examples
- Language-agnostic topics: show Python, TypeScript, and Go as siblings
- Tool-specific content (GitHub Actions, Terraform, Dockerfile): use native syntax only
- Anti-patterns: show as `# BAD` / `# GOOD` pairs in the same code block
- Every skill has at least one decision/comparison table

### Quality Standards
- No meta-commentary ("This skill covers...")
- No filler prose — terse, code-forward writing
- Tables for decision matrices and comparisons
- Checklists close every skill
- Cross-references via `> See also: \`skill-name\`` where meaningful

## When Editing Skills
- Read the existing `api-design` and `claude-api` skills first — they set the canonical format
- Match the density and style of existing skills exactly
- Test activation by describing a relevant task in a new Claude Code session
- Keep skills focused: one domain per skill, no overlap with adjacent skills

## When Adding New Skills
1. Create `skills/<name>/skill.md`
2. Follow the frontmatter + content format above exactly
3. Add the skill to the inventory list in this file
4. Update `README.md` if the structure section is outdated

### Agent File Format

Every agent file lives at `.claude/agents/<name>.md` and follows this structure:

```markdown
---
name: kebab-case-name
description: <one sentence — when to delegate to this agent vs. using a slash command>
tools: Read, Grep, Glob, Bash   # comma-separated; omit to inherit all
model: sonnet                   # sonnet | opus | haiku | inherit
color: red                      # optional: red | blue | green | yellow | purple | orange
---

System prompt content. This is what the agent receives instead of the parent session's context.

Describe the agent's methodology, output format, and any rules it must follow.
```

**Key differences from slash commands:**
- Agents run in an isolated context window — they do not see the parent session history
- The `description` field controls when Claude auto-delegates; write it as "Use this agent when…"
- Restrict `tools` to the minimum needed — a read-only audit agent should not have `Write` or `Edit`
- The body is a system prompt, not a task prompt — write it in second person ("You are a…")

## When Adding New Agents
1. Create `.claude/agents/<name>.md`
2. Set `tools` to the minimum required (principle of least privilege)
3. Include a clear output format in the system prompt so results are consistent
4. Add the agent to the Agent Inventory table in this file
5. Update the Agents section in `README.md`
