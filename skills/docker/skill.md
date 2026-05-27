---
name: docker
description: Use when writing or optimizing a Dockerfile or docker-compose.yml for local dev, debugging containers that behave differently from local, or reducing image size for Python and Node.js apps. Not for Kubernetes resources or Helm — use containerization.
---

# Docker Patterns

Production-ready Docker patterns for Python and Node.js services.

## When to Activate

- Writing or optimizing a Dockerfile (multi-stage, layer caching)
- Configuring Docker Compose services, networking, or volumes
- Adding health checks or startup dependencies
- Passing secrets and environment variables safely
- Debugging a container that won't start or behaves differently in Docker vs local
- Reducing image size

---

## Dockerfile — Python (FastAPI / uv)

```dockerfile
# syntax=docker/dockerfile:1

# --- Build stage ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install uv --no-cache-dir

# Copy dependency files first — cached unless they change
COPY pyproject.toml uv.lock ./

# Install deps into a prefix (not system), no dev deps
RUN uv sync --frozen --no-dev --prefix /install

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code last (changes most often)
COPY src/ ./src/

# Non-root user — security best practice
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Dockerfile — Node.js (Next.js)

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production

# Only copy what's needed to run
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

Enable standalone output in `next.config.js`:
```js
output: "standalone"
```

---

## .dockerignore

```
# Always include these
.git
.gitignore
**/.env
**/.env.*
**/node_modules
**/__pycache__
**/*.pyc
**/*.pyo
.venv
dist
build
.next
coverage
*.log
.DS_Store
```

---

## Layer Caching Rules

**Order files from least-changed to most-changed:**

```dockerfile
# ✅ GOOD — deps cached unless pyproject.toml changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY src/ ./src/           # code changes don't bust dep layer

# ❌ BAD — any code change busts the dep install layer
COPY . .
RUN uv sync --frozen
```

**Cache mounts (BuildKit) — don't write pip/uv cache to image:**
```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
```

---

## Docker Compose

```yaml
# docker-compose.yml
services:
  api:
    build:
      context: .
      target: runtime          # use a specific stage
    ports:
      - "5003:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://user:pass@db:5432/app
      REDIS_URL: redis://redis:6379
    depends_on:
      db:
        condition: service_healthy   # wait for health check, not just start
      redis:
        condition: service_started
    restart: unless-stopped
    networks:
      - backend

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: app
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d app"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s
    networks:
      - backend

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes   # persist to disk
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - backend

volumes:
  pg_data:
  redis_data:

networks:
  backend:
    driver: bridge
```

---

## Health Checks

```yaml
# Standard health check pattern
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s       # how often to check
  timeout: 10s        # max time per check
  retries: 3          # failures before unhealthy
  start_period: 30s   # grace period before first check counts
```

FastAPI health endpoint:
```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Environment Variables and Secrets

```yaml
services:
  api:
    # Option 1: inline (dev only — visible in docker inspect)
    environment:
      SECRET_KEY: dev-secret

    # Option 2: reference host env var (no value = pass-through)
    environment:
      SECRET_KEY: ${SECRET_KEY}

    # Option 3: .env file (dev only — don't commit secrets)
    env_file:
      - .env

    # Option 4: Docker secrets (production / Swarm)
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

Access secret in container at `/run/secrets/db_password`.

---

## Networking

```yaml
networks:
  frontend:   # API + nginx
  backend:    # API + DB + Redis (not exposed to frontend network)

services:
  nginx:
    networks: [frontend]
  api:
    networks: [frontend, backend]   # bridge between networks
  db:
    networks: [backend]             # only reachable from backend
```

**Service DNS:** containers on the same network reach each other by service name.
```
# From api container, reach db:
postgresql://db:5432/mydb       # "db" resolves to the db container IP
redis://redis:6379
```

---

## Common Commands

```bash
# Build
docker build -t myapp .
docker build --target builder -t myapp:builder .   # build specific stage
docker build --no-cache -t myapp .                  # force rebuild

# Compose
docker compose up -d                   # start in background
docker compose up --build              # rebuild before starting
docker compose down -v                 # stop + remove volumes
docker compose logs -f api             # follow logs for one service
docker compose exec api bash           # shell into running container
docker compose ps                      # status of all services

# Inspect
docker inspect <container>             # full config, env vars, mounts
docker stats                           # live resource usage
docker system df                       # disk usage by layer/image/volume

# Cleanup
docker system prune -f                 # remove stopped containers + dangling images
docker volume prune -f                 # remove unused volumes
docker image prune -a -f               # remove all unused images
```

---

## Debugging

```bash
# Container exits immediately — run it interactively
docker run -it --entrypoint bash myapp

# Check environment inside container
docker exec <container> env

# Copy files out of container
docker cp <container>:/app/logs ./local-logs

# Run with host network (skip Docker networking)
docker run --network host myapp

# Override CMD for one-off
docker compose run --rm api python manage.py migrate
```

---

## Image Size Reduction

| Technique | Savings |
|---|---|
| Use slim/alpine base (`python:3.12-slim`) | 60–80% vs full image |
| Multi-stage build — don't ship build tools | varies |
| `--no-install-recommends` on apt-get | 20–40% |
| Remove apt cache: `rm -rf /var/lib/apt/lists/*` | small |
| `--no-cache-dir` on pip | small |
| `.dockerignore` to skip test/docs | small |

```dockerfile
# Minimal apt install pattern
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*
```

---

## Red Flags

- **`COPY . .` before installing dependencies** — copying all source code first busts the dependency layer on every code change; always `COPY pyproject.toml uv.lock ./` → install → `COPY src/ ./` so deps are cached unless manifests change
- **Running the container as root** — the default user is root inside a container; a process escape gives the attacker full host access; always add `RUN adduser --disabled-password appuser && USER appuser` in the runtime stage
- **No health check on services others `depends_on`** — `depends_on` without `condition: service_healthy` starts the dependent service immediately, before the dependency is actually ready; always define a `healthcheck` and use `service_healthy`
- **Secrets in `environment:` as plaintext** — environment variables are visible in `docker inspect`, CI logs, and image layers if baked in; use Docker secrets, a secrets manager, or pass via host env refs (`SECRET_KEY: ${SECRET_KEY}`)
- **No `.dockerignore`** — without it, `COPY . .` sends the entire repo (`.git`, `node_modules`, `__pycache__`, `.env`) into the build context, bloating image size and potentially leaking secrets
- **Single-stage build shipping build tools to production** — compilers, dev headers, and test dependencies included in the runtime image increase attack surface and image size; use multi-stage builds so the runtime stage starts fresh from a slim base
- **Anonymous volumes for data that must persist** — `volumes: ["/var/lib/postgresql/data"]` (without a named volume) is recreated on `docker compose down`; use named volumes (`pg_data:/var/lib/postgresql/data`) to persist data across restarts

## Checklist

- [ ] Multi-stage build used — builder installs, runtime only has what's needed
- [ ] `.dockerignore` excludes `.git`, `node_modules`, `.env`, `__pycache__`
- [ ] Dependencies copied before source code (layer cache)
- [ ] Non-root user for runtime stage
- [ ] Health check defined for services that others `depends_on`
- [ ] `depends_on` uses `condition: service_healthy` not just `service_started`
- [ ] Secrets not hardcoded in Dockerfile or committed `.env`
- [ ] Volumes named (not anonymous) for data you want to persist
