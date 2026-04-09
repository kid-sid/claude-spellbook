Scaffold a new service or project with production-ready boilerplate.

## Instructions

1. Ask the user (if not already specified):
   - **Language/framework**: TypeScript (Express/Fastify), Python (FastAPI/Django), Go (net/http/Chi), Rust (Axum/Actix), Svelte (SvelteKit)
   - **Service type**: API service, web app, CLI tool, library
   - **Name**: project/service name (kebab-case)

2. Generate the project structure based on the selected stack:

### For every project type:
- `README.md` — with prerequisites, quickstart (3 commands), config reference
- `CLAUDE.md` — project-specific context for Claude Code
- `.gitignore` — language-appropriate
- `Dockerfile` — multi-stage build (from containerization skill)
- `docker-compose.yml` — app + DB + Redis for local dev
- `.github/workflows/ci.yml` — lint, test, build, security scan (from ci-cd skill)
- `.claude/settings.local.json` — hooks for the chosen language
- `Makefile` — install, dev, test, build, lint targets

### For API services, additionally:
- Health check endpoint (`/health/live`, `/health/ready`)
- Structured logging setup (from observability skill)
- Prometheus metrics endpoint (`/metrics`)
- Error handling middleware
- Request ID / correlation ID middleware
- OpenAPI spec stub

### For web apps (Svelte), additionally:
- Layout with error boundary
- Auth guard pattern
- Environment variable handling

3. Copy relevant tool configs from the spellbook:
   - Run the equivalent of `tools/install.sh <language>`

4. Initialize git and create initial commit.

5. Print a summary of what was created and next steps.

## Output
A complete, runnable project skeleton. The user should be able to `cd` into it, run `make dev`, and have a working service.
