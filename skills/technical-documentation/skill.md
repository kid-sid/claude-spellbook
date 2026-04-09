---
name: technical-documentation
description: Technical documentation: README structure and templates, OpenAPI/Swagger YAML (paths, schemas, $ref reuse, security schemes), runbook writing, Architecture Decision Records (ADRs), technical spec templates, and docs-as-code with MkDocs/Docusaurus/mdBook.
---

# Technical Documentation

Good technical documentation reduces onboarding time, prevents repeated questions, and makes systems maintainable by people who didn't build them.

## When to Activate

- Writing a README for a new project or service
- Documenting an API with OpenAPI/Swagger
- Writing a runbook for an on-call engineer
- Creating an onboarding guide for a team
- Documenting a significant technical decision (ADR)
- Setting up documentation-as-code with auto-deploy to GitHub Pages

## README Structure

A README is the front door to your project — it answers "what is this and how do I use it?" in under 5 minutes.

```markdown
# service-name

[![CI](https://github.com/org/repo/actions/workflows/ci.yml/badge.svg)](...)
[![Coverage](https://codecov.io/gh/org/repo/badge.svg)](...)

One-sentence description of what this service does.

## Prerequisites

- Python 3.12+ / Node.js 20+ / Go 1.22+
- Docker 24+
- PostgreSQL 16 (or `docker compose up db`)

## Quickstart

\```bash
git clone https://github.com/org/service-name
cd service-name
cp .env.example .env        # fill in required values
docker compose up -d db     # start dependencies
make install                # install dependencies
make dev                    # start dev server on :8000
\```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `JWT_SECRET` | Yes | — | 32-byte secret for JWT signing |
| `LOG_LEVEL` | No | `INFO` | Log verbosity (DEBUG/INFO/WARN/ERROR) |
| `PORT` | No | `8000` | HTTP server port |

## Development

\```bash
make test          # run unit + integration tests
make lint          # run linters
make typecheck     # run type checker
make build         # build production artifact
\```

See [docs/development.md](docs/development.md) for detailed setup, running locally, and debugging.

## Deployment

This service is deployed via GitHub Actions. See [docs/deployment.md](docs/deployment.md).

## Contributing

1. Fork the repo and create a branch: `feat/your-feature`
2. Make changes, write tests
3. Open a PR — the CI must be green before review

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## License

MIT — see [LICENSE](LICENSE)
```

### README Anti-Patterns
- Wall of text with no headings — add structure
- "Works on my machine" setup steps — use Docker or make targets
- Outdated screenshots — use text commands instead
- Missing prerequisites — list every external dependency
- No copy-paste quickstart — someone must be able to run it in 3 commands

## OpenAPI / Swagger

OpenAPI 3.x is the standard for documenting REST APIs. Write it by hand (spec-first) or generate from code annotations.

### Basic Structure

```yaml
openapi: 3.1.0
info:
  title: Payment Service API
  version: 1.0.0
  description: |
    Processes payments and manages payment methods.

    ## Authentication
    All endpoints require a Bearer token in the `Authorization` header.

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: https://staging-api.example.com/v1
    description: Staging

security:
  - BearerAuth: []

paths:
  /payments:
    post:
      operationId: createPayment
      summary: Create a payment
      tags: [Payments]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreatePaymentRequest'
            example:
              amount: 10000
              currency: USD
              source: tok_visa
      responses:
        '201':
          description: Payment created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Payment'
        '400':
          $ref: '#/components/responses/ValidationError'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /payments/{id}:
    get:
      operationId: getPayment
      summary: Get a payment by ID
      tags: [Payments]
      parameters:
        - $ref: '#/components/parameters/PaymentId'
      responses:
        '200':
          description: Payment found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Payment'
        '404':
          $ref: '#/components/responses/NotFound'

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  parameters:
    PaymentId:
      name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
      description: Payment identifier

  schemas:
    CreatePaymentRequest:
      type: object
      required: [amount, currency, source]
      properties:
        amount:
          type: integer
          description: Amount in smallest currency unit (cents for USD)
          example: 10000
          minimum: 1
        currency:
          type: string
          enum: [USD, EUR, GBP]
          example: USD
        source:
          type: string
          description: Stripe payment method token
          example: tok_visa

    Payment:
      type: object
      properties:
        id:
          type: string
          format: uuid
        amount:
          type: integer
        currency:
          type: string
        status:
          type: string
          enum: [pending, succeeded, failed]
        created_at:
          type: string
          format: date-time

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          example: VALIDATION_ERROR
        message:
          type: string
          example: amount must be greater than 0
        details:
          type: array
          items:
            type: object

  responses:
    ValidationError:
      description: Request validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    Unauthorized:
      description: Missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
```

### `$ref` Reuse Rules
- Define all reusable schemas in `components/schemas`
- Define reusable responses in `components/responses`
- Define reusable parameters in `components/parameters`
- Never duplicate a schema — use `$ref` everywhere it appears

### Tooling
| Tool | Purpose |
|------|---------|
| Swagger UI | Interactive API browser, served locally or hosted |
| Redoc | Clean read-only API docs, good for public docs |
| Stoplight Elements | Embeddable, modern OpenAPI renderer |
| `openapi-generator` | Generate client SDKs from spec |
| `prism` | Mock server from OpenAPI spec |

## Runbook Writing

See `incident-response` skill for the full runbook template. Key principles:

- **Write for the 3am engineer** — no tribal knowledge, no assumed context
- **Number every step** — so the engineer can say "I'm stuck on step 4"
- **Include expected output** — show what success looks like for each step
- **Copy-paste commands** — no `<REPLACE_ME>` placeholders in commands
- **Decision branches** — "if X, do Y; otherwise do Z"
- **Keep runbooks current** — update after every incident that required improvisation

## Architecture Decision Records (ADRs)

ADRs document *why* a significant decision was made — not just what was decided. Future engineers need context, not just conclusions.

See `system-design` skill for the full ADR template and lifecycle.

### When to Write an ADR
- Choosing a database or message queue technology
- Adopting a new framework or library with significant lock-in
- Changing authentication mechanism
- Moving from monolith to microservices (or vice versa)
- Adopting a new infrastructure pattern (Kubernetes, serverless)
- Any decision that would surprise a new team member

### Conventions
```
docs/
└── adr/
    ├── 0001-use-postgresql-for-primary-store.md
    ├── 0002-use-kafka-for-event-streaming.md
    └── 0003-adopt-opentelemetry-for-tracing.md
```
- Number sequentially, never renumber
- Superseded ADRs stay — add "Superseded by ADR-0012" to the status
- Store in-repo alongside code — ADRs are code

## Technical Spec Template

Write a spec when the feature is large enough to need design alignment before implementation (> 1 sprint, or involves multiple services).

```markdown
# Technical Spec: [Feature Name]

**Status:** Draft | In Review | Accepted | Implemented
**Author:** [name]
**Last updated:** YYYY-MM-DD
**Related:** [Jira/Linear ticket], [ADR-XXXX]

## Problem

[1–3 paragraphs: what problem are we solving? Why now? What happens if we don't?]

## Proposed Solution

[Describe the solution at a level where another engineer can implement it.
Include: API contracts, data model changes, component interactions, migration plan.]

### API Changes

[List new or modified endpoints with request/response shapes]

### Data Model

[Schema changes, new tables, index additions]

### Component Diagram

[ASCII or Mermaid diagram showing how components interact]

## Alternatives Considered

| Option | Pros | Cons | Reason not chosen |
|--------|------|------|------------------|
| ...    | ...  | ...  | ...              |

## Implementation Plan

1. [ ] Phase 1: ...
2. [ ] Phase 2: ...
3. [ ] Phase 3: ...

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ...  | ...       | ...    | ...       |

## Open Questions

| Question | Owner | Due |
|----------|-------|-----|
| ...      | ...   | ... |

## Stakeholder Sign-off

- [ ] Engineering lead: @name
- [ ] Product: @name
- [ ] Security (if auth/data): @name
```

## Documentation as Code

Keep docs alongside code in the same repository. Auto-deploy to GitHub Pages on merge.

### Tool Comparison

| Tool | Language | Best for | Config |
|------|----------|---------|--------|
| MkDocs + Material | Python | Technical docs, clean theme | `mkdocs.yml` |
| Docusaurus | Node/React | Developer portals, versioned docs | `docusaurus.config.js` |
| mdBook | Rust | Books, guides (no JS required) | `book.toml` |
| VitePress | Vue | Fast, modern Vue-based docs | `vitepress.config.ts` |

### MkDocs Example

```yaml
# mkdocs.yml
site_name: Payment Service Docs
theme:
  name: material
  features:
    - navigation.tabs
    - search.suggest

nav:
  - Home: index.md
  - API Reference: api.md
  - Runbooks:
    - Overview: runbooks/index.md
    - High Error Rate: runbooks/high-error-rate.md
  - ADRs: adr/index.md

plugins:
  - search
  - git-revision-date-localized
```

### GitHub Actions — Auto-deploy Docs

```yaml
name: Deploy Docs
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # for git-revision-date plugin
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install mkdocs-material mkdocs-git-revision-date-localized-plugin
      - run: mkdocs gh-deploy --force
```

> See also: `api-design`, `system-design`, `incident-response`

## Checklist

- [ ] README has prerequisites, copy-paste quickstart (≤ 3 commands), and config reference
- [ ] All environment variables documented with type, required flag, and description
- [ ] OpenAPI spec covers all public endpoints with request/response schemas
- [ ] All `$ref` components defined in `components/` — no duplicated schemas
- [ ] API error responses have consistent schema (`code` + `message` + optional `details`)
- [ ] Runbooks written for every production alert — no tribal-knowledge steps
- [ ] ADR written for every significant technology or architecture decision
- [ ] Tech spec written and signed off before implementing features > 1 sprint
- [ ] Docs live in-repo alongside code (not in a separate wiki that goes stale)
- [ ] Docs auto-deploy to GitHub Pages on merge to main
