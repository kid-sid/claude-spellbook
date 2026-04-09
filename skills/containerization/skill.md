---
name: containerization
description: "Docker and Kubernetes patterns: multi-stage Dockerfiles for Python/Node/Go, image optimization, docker-compose for local dev, Kubernetes core resources (Deployment, Service, Ingress, ConfigMap, Secret, HPA), Helm basics, security context, and resource requests/limits."
---

# Containerization

Package and orchestrate services with Docker and Kubernetes using production-ready patterns for image builds, local development, cluster deployments, and autoscaling.

## When to Activate

- Writing or reviewing a Dockerfile for a service
- Setting up docker-compose for local development
- Writing Kubernetes manifests for a new service
- Deploying to a Kubernetes cluster
- Sizing CPU/memory requests and limits for a pod
- Setting up a Helm chart
- Optimizing Docker image build time or image size

## Dockerfile Best Practices

### Multi-Stage Builds

Multi-stage builds keep build-time tools out of the final image, reducing attack surface and image size.

**Python**

```dockerfile
# Stage 1: build dependencies
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Stage 2: runtime image
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
ENV PATH="/app/.venv/bin:$PATH"
USER 1000:1000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1
ENTRYPOINT ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Node.js / TypeScript**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/dist ./dist
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost:3000/health || exit 1
CMD ["node", "dist/index.js"]
```

**Go (smallest possible image)**

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/server ./cmd/server

FROM gcr.io/distroless/static-debian12 AS runtime
COPY --from=builder /app/server /server
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/server"]
```

### Layer Caching Order

Docker caches each layer. If a layer's input changes, all subsequent layers are invalidated. Copy dependency manifests before source code so that the expensive dependency-install step is only re-run when dependencies actually change, not on every source edit.

```dockerfile
# BAD — source copy before dependency install; every code change busts the npm ci cache
COPY . .
RUN npm ci

# GOOD — copy only the manifest first; npm ci cache survives source-only changes
COPY package*.json ./
RUN npm ci
COPY . .
```

The same principle applies to all runtimes:

| Runtime | Copy first | Then install |
|---------|-----------|--------------|
| Python (uv) | `pyproject.toml uv.lock` | `uv sync --frozen` |
| Node | `package*.json` | `npm ci` |
| Go | `go.mod go.sum` | `go mod download` |

### .dockerignore

Always create a `.dockerignore` at the repo root. Files excluded here are never sent to the Docker build context, speeding up builds and preventing accidental secret leaks.

```dockerignore
.git
.gitignore
.env
*.env
__pycache__
*.pyc
node_modules
dist
build
.pytest_cache
.coverage
*.log
README.md
```

### Base Image Selection

| Image | Size | Vulnerability surface | Best for |
|-------|------|----------------------|----------|
| `ubuntu:22.04` | ~80 MB | High | Dev/debug only |
| `debian:bookworm-slim` | ~75 MB | Medium | General purpose |
| `python:3.12-slim` | ~150 MB | Medium | Python apps |
| `node:20-alpine` | ~170 MB | Low | Node apps |
| `alpine:3.19` | ~7 MB | Very low | Custom builds |
| `gcr.io/distroless/static-debian12` | ~2 MB | Minimal | Go static binaries |
| `gcr.io/distroless/python3-debian12` | ~80 MB | Minimal | Python (no shell!) |

Pin to digest for reproducibility in production:

```dockerfile
FROM python:3.12-slim@sha256:abc123...
```

## docker-compose for Local Development

Use docker-compose for wiring together the application and its backing services locally. Keep secrets in `.env` (gitignored) and load them via `env_file`.

```yaml
version: '3.9'
services:
  app:
    build:
      context: .
      target: runtime  # use multi-stage target
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/appdb
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./src:/app/src  # hot-reload in dev
    profiles:
      - dev

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: appdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d appdb"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

**Profiles.** Use `profiles` to mark optional services. Start only what you need:

```bash
docker compose --profile dev up
```

**Override file.** Create `docker-compose.override.yml` for local-only tweaks (e.g., mounting a local SDK, exposing extra ports). Add it to `.gitignore` so it never ships.

```yaml
# docker-compose.override.yml (gitignored)
services:
  app:
    environment:
      DEBUG: "true"
    volumes:
      - ../my-local-sdk:/app/vendor/sdk
```

## Kubernetes Core Resources

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # zero-downtime: always have full capacity during rollout
  template:
    metadata:
      labels:
        app: payment-service
    spec:
      containers:
        - name: payment-service
          image: ghcr.io/org/payment-service:abc123
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          envFrom:
            - configMapRef:
                name: payment-service-config
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: payment-service-secrets
                  key: database-url
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
            failureThreshold: 3
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: production
spec:
  selector:
    app: payment-service
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP  # internal only; use LoadBalancer for external
```

**Service type reference:**

| Type | Accessibility | Use case |
|------|--------------|----------|
| `ClusterIP` | Cluster-internal only | Internal services |
| `NodePort` | External via node IP:port | Dev/testing |
| `LoadBalancer` | External via cloud LB | Prod external services |
| `ExternalName` | DNS alias | Off-cluster services |

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: payment-service
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - api.example.com
      secretName: api-tls-cert
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /payments
            pathType: Prefix
            backend:
              service:
                name: payment-service
                port:
                  number: 80
```

### ConfigMap and Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: payment-service-config
data:
  LOG_LEVEL: "INFO"
  APP_ENV: "production"
---
apiVersion: v1
kind: Secret
metadata:
  name: payment-service-secrets
type: Opaque
data:
  database-url: <base64-encoded-value>  # echo -n "postgresql://..." | base64
```

Never commit Secrets to git. Use one of:

- [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) — encrypts Secret with a cluster key; safe to commit
- [external-secrets-operator](https://external-secrets.io) — syncs from AWS Secrets Manager / GCP Secret Manager / Vault
- Vault agent injection — sidecar writes secrets to an in-memory volume

## Resource Management

### Requests vs Limits

| Field | Purpose | What happens when exceeded |
|-------|---------|---------------------------|
| `requests.cpu` | Guaranteed CPU; used for scheduling | N/A — node selection only |
| `limits.cpu` | Maximum CPU the container may use | Throttled (not killed) |
| `requests.memory` | Guaranteed memory; used for scheduling | N/A — node selection only |
| `limits.memory` | Maximum memory the container may use | OOMKilled (pod restarted) |

- **Requests** are what the scheduler uses to decide which node a pod lands on.
- **Limits** are enforced at runtime by the kernel cgroup.
- Setting `limits.memory` without headroom above `requests.memory` invites spurious OOMKills under GC pressure.

### QoS Classes

Kubernetes assigns a QoS class based on how requests and limits are configured. Higher QoS = last to be evicted under node memory pressure.

| Class | Condition | Eviction priority |
|-------|-----------|------------------|
| `Guaranteed` | `requests == limits` for every resource | Last to be evicted |
| `Burstable` | `requests < limits` for at least one resource | Middle |
| `BestEffort` | No requests or limits set at all | First to be evicted |

For critical services, set `requests == limits` to achieve `Guaranteed` QoS. For batch jobs or low-priority workers, `Burstable` is acceptable.

## Health Probes

| Probe | What it checks | Failure action |
|-------|---------------|----------------|
| `readinessProbe` | Is pod ready to receive traffic? | Remove from Service endpoints |
| `livenessProbe` | Is pod alive? | Restart pod |
| `startupProbe` | Has pod finished starting? (slow-starting apps) | Replaces liveness until started |

**Common mistake:** setting `livenessProbe.failureThreshold` too low (e.g., `2` with `periodSeconds: 10`) causes restart loops during slow GC pauses or transient DB query spikes. For most services, `failureThreshold: 3` with `periodSeconds: 30` is a safer baseline.

```yaml
# BAD — aggressive liveness; 20 seconds of GC pause triggers restart
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  periodSeconds: 10
  failureThreshold: 2

# GOOD — tolerates 90 seconds of unresponsiveness before restarting
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 30
  failureThreshold: 3
```

## HorizontalPodAutoscaler

HPA scales the replica count based on observed metrics. Requires the metrics-server addon (or custom metrics adapter for non-CPU metrics).

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

HPA only works correctly when `requests.cpu` is set — it calculates utilization as `actual / request`. Without a CPU request, HPA cannot compute a meaningful ratio and will not scale.

## Helm Basics

Helm packages Kubernetes manifests into versioned, parameterised charts.

**Chart structure:**

```
mychart/
├── Chart.yaml          # metadata (name, version, appVersion)
├── values.yaml         # default values
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── _helpers.tpl    # reusable template snippets
```

**Key commands:**

```bash
helm install my-release ./mychart --values prod-values.yaml
helm upgrade my-release ./mychart --values prod-values.yaml
helm rollback my-release 1
helm diff upgrade my-release ./mychart  # requires helm-diff plugin
```

**values.yaml pattern — expose only what varies per environment:**

```yaml
# values.yaml
image:
  repository: ghcr.io/org/payment-service
  tag: latest  # override per environment with --set image.tag=abc123

replicaCount: 3

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

Override at release time without editing the chart:

```bash
helm upgrade my-release ./mychart \
  --values prod-values.yaml \
  --set image.tag=abc123
```

## Security Context

Apply `securityContext` at both the pod level and the container level. The settings below satisfy most CIS Kubernetes Benchmark requirements.

```yaml
# pod-level: applies to all containers in the pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    seccompProfile:
      type: RuntimeDefault

  containers:
    - name: app
      # container-level: overrides/extends pod-level settings
      securityContext:
        readOnlyRootFilesystem: true
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
```

If `readOnlyRootFilesystem: true` causes write errors, mount an explicit `emptyDir` volume for the specific writable path rather than disabling the restriction:

```yaml
# BAD — disabling readOnly to allow one directory to be writable
securityContext:
  readOnlyRootFilesystem: false

# GOOD — keep readOnly, mount emptyDir for the specific path
securityContext:
  readOnlyRootFilesystem: true
volumeMounts:
  - name: tmp
    mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
```

> See also: `ci-cd`, `deployment-strategies`, `security`

## Checklist

- [ ] Multi-stage Dockerfile used — build tools not in final image
- [ ] Source files copied after dependency files (layer cache optimization)
- [ ] Non-root user set in Dockerfile (`USER 1000:1000` or `USER node`)
- [ ] `.dockerignore` excludes `.git`, `.env`, `node_modules`, `__pycache__`
- [ ] `HEALTHCHECK` instruction defined in Dockerfile
- [ ] All pods have `readinessProbe` and `livenessProbe` configured
- [ ] CPU and memory `requests` and `limits` set on every container
- [ ] Secrets stored in Kubernetes Secrets (or external secrets manager), not ConfigMaps
- [ ] `securityContext` sets `runAsNonRoot: true` and `allowPrivilegeEscalation: false`
- [ ] HPA configured for services with variable load
- [ ] `maxUnavailable: 0` in rolling update strategy for zero-downtime deployments
- [ ] Image tagged with commit SHA, not `latest`
