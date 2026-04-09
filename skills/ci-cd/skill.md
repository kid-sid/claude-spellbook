---
name: ci-cd
description: "CI/CD pipelines with GitHub Actions: workflow triggers, job dependencies, dependency caching, matrix builds, quality gates (lint/test/security/coverage), OIDC-based cloud auth, environment promotion (staging to prod), artifact publishing to GHCR/PyPI/npm, and complete workflow examples for Python, TypeScript, and Go."
---

# CI/CD with GitHub Actions

A complete reference for building robust, secure, and efficient CI/CD pipelines using GitHub Actions, covering everything from workflow anatomy to multi-environment deployment promotion.

## When to Activate

- Creating or modifying a GitHub Actions workflow
- Adding a quality gate (coverage, lint, security scan) to a pipeline
- Setting up CD with environment promotion from staging to production
- Optimizing a slow CI pipeline with caching or parallelism
- Publishing a Docker image, Python package, or npm package from CI
- Configuring secrets and OIDC-based cloud authentication

---

## Workflow Anatomy

Every GitHub Actions workflow is defined in `.github/workflows/*.yml`. Understanding the core building blocks is essential before composing pipelines.

### Triggers

| Trigger               | Use Case                                              |
|-----------------------|-------------------------------------------------------|
| `push`                | Run on commits to specified branches or tags          |
| `pull_request`        | Run on PR open, sync, or reopen                       |
| `workflow_dispatch`   | Manual trigger with optional input parameters         |
| `schedule`            | Cron-based triggers (e.g., nightly security scans)    |
| `workflow_call`       | Reusable workflow called by another workflow           |

### Jobs

- Jobs run **in parallel by default** unless `needs:` is specified.
- Use `needs: [job-a, job-b]` to declare dependencies; a job waits for all listed jobs to succeed.
- Each job runs in a fresh virtual machine (or container).

### Steps

- `uses:` — invokes a reusable action from the marketplace or a local path.
- `run:` — executes a shell command directly on the runner.
- Steps within a job share the same filesystem and runner environment.

### Key Contexts

| Context     | What It Provides                                         |
|-------------|----------------------------------------------------------|
| `github`    | Repo name, SHA, ref, event name, actor, run ID           |
| `secrets`   | Encrypted secret values; never printed in logs           |
| `env`       | Environment variables set at workflow, job, or step level|
| `matrix`    | Current values from the strategy matrix                  |
| `job`       | Current job status, container info                       |

### Expression Syntax

All dynamic values use `${{ expression }}` syntax:

```yaml
if: github.ref == 'refs/heads/main'
run: echo "SHA is ${{ github.sha }}"
env:
  BRANCH: ${{ github.ref_name }}
```

### Minimal Workflow Skeleton

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: make test
```

---

## Standard Pipeline Structure

The canonical stage sequence moves from fast feedback (lint) to slower gates (security), then publishing.

```
lint → test → build → security-scan → publish
```

### Job Dependency Graph

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: make lint

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test
        run: make test

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: make build

  security-scan:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security scan
        run: make scan

  publish:
    needs: [build, security-scan]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Publish
        run: make publish
```

### fail-fast Behavior

| Setting               | When to Use                                                  |
|-----------------------|--------------------------------------------------------------|
| `fail-fast: true` (default) | Sequential stage pipelines — stop early on first failure |
| `fail-fast: false`    | Matrix builds — collect all results before deciding          |

Use `fail-fast: false` in matrix strategies so you see failures across all OS/version combinations rather than stopping at the first one.

---

## Dependency Caching

Caching package manager dependencies is the single highest-impact optimization for CI speed. The key strategy: hash the lockfile so the cache automatically invalidates when dependencies change.

### Cache Key Strategy

```
cache-key = runner-os + lockfile-hash
restore-key = runner-os (fallback to most recent cache)
```

### Python

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: 'pip'  # built-in caching, hashes requirements*.txt
```

For more control with `pyproject.toml`:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml', '**/requirements*.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Node.js

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'  # hashes package-lock.json automatically
```

For pnpm or yarn, set `cache: 'pnpm'` or `cache: 'yarn'` respectively.

### Go

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.22'
    cache: true  # caches $GOPATH/pkg/mod and build cache
```

### Cache Hit Rate Tips

- Always commit lockfiles (`package-lock.json`, `poetry.lock`, `go.sum`) to the repository.
- Use `hashFiles('**/package-lock.json')` to scope cache keys to the exact dependency set.
- Restore keys act as fallbacks: a partial hit is better than no cache.

---

## Matrix Builds

Matrix builds let a single job definition run across multiple configurations (language versions, operating systems) in parallel.

### Matrix Strategy

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        python-version: ['3.11', '3.12', '3.13']
        os: [ubuntu-latest, windows-latest]
        include:
          - python-version: '3.12'
            os: ubuntu-latest
            publish: true      # custom flag for conditional steps
        exclude:
          - python-version: '3.11'
            os: windows-latest  # skip known unsupported combo
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pytest
      - name: Publish (only from designated matrix entry)
        if: matrix.publish == true
        run: make publish
```

### Matrix Reference

| Feature         | Syntax                                         | Purpose                                  |
|-----------------|------------------------------------------------|------------------------------------------|
| Access value    | `${{ matrix.python-version }}`                 | Use current dimension value in steps     |
| `include`       | Adds extra key-value pairs to specific entries | Inject flags or override runner for one combo |
| `exclude`       | Removes specific combinations                  | Skip known broken or unnecessary combos  |
| `fail-fast`     | `false` on matrix                              | See all failures, not just first         |

---

## Quality Gates

### Coverage Threshold

Fail the build if coverage drops below the required threshold.

```yaml
- name: Run tests with coverage
  run: pytest --cov=src --cov-report=xml --cov-fail-under=80

- name: Upload coverage report
  uses: codecov/codecov-action@v4
  with:
    file: ./coverage.xml
    fail_ci_if_error: true
```

For Node.js with Jest:

```yaml
- name: Run tests with coverage
  run: jest --coverage --coverageThreshold='{"global":{"lines":80}}'
```

### Inline Lint Annotations with reviewdog

reviewdog posts lint results as PR review comments, making issues visible without reading raw logs.

```yaml
- uses: reviewdog/action-flake8@v3
  with:
    reporter: github-pr-review
    level: warning
```

```yaml
- uses: reviewdog/action-eslint@v1
  with:
    reporter: github-pr-review
    eslint_flags: '--ext .js,.ts src/'
```

### Branch Protection Rules

Configure these in GitHub Settings → Branches, not in workflow YAML:

- **Required status checks**: list every CI job name that must pass before merge.
- **Required approvals**: minimum 1 reviewer for `main`.
- **Dismiss stale approvals**: re-approval required after new commits are pushed.
- **Require branches to be up to date**: prevents merging outdated branches.

### Security Scanning

```yaml
- name: Python dependency audit
  run: pip-audit

- name: Node audit
  run: npm audit --audit-level=high

- name: Go vulnerability check
  run: govulncheck ./...
```

For container scanning, integrate Trivy:

```yaml
- uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/${{ github.repository }}:${{ github.sha }}
    severity: 'CRITICAL,HIGH'
    exit-code: '1'
```

---

## Secrets and Environment Variables

### Contexts

```yaml
env:
  APP_ENV: production                    # plain env var (visible in logs)
  DB_HOST: ${{ vars.DB_HOST }}           # repository variable (not secret, visible)
  API_KEY: ${{ secrets.API_KEY }}        # encrypted secret (masked in logs)
```

### Variable Scoping

| Scope      | Set In                                    | Available To                  |
|------------|-------------------------------------------|-------------------------------|
| Workflow   | Top-level `env:` block                    | All jobs and steps            |
| Job        | `env:` under a specific job               | All steps in that job         |
| Step       | `env:` under a specific step              | That step only                |
| Repository | GitHub Settings → Secrets and Variables   | All workflows in the repo     |
| Environment| GitHub Settings → Environments            | Jobs using that environment   |

### `$GITHUB_TOKEN` Permissions

Declare only what the job requires (principle of least privilege):

```yaml
permissions:
  contents: read       # read repo files
  packages: write      # push to GHCR
  id-token: write      # request OIDC token for cloud auth
  pull-requests: write # post PR comments
  checks: write        # create check runs
```

Set `permissions: {}` at the workflow level, then grant specific permissions per job to minimize blast radius.

### OIDC for Cloud Auth (No Long-Lived Credentials)

OIDC eliminates the need to store cloud credentials as GitHub secrets. The cloud provider verifies the workflow's identity token and grants temporary credentials.

**AWS:**

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/github-actions
    aws-region: us-east-1
```

Requires an IAM role with a trust policy that allows `token.actions.githubusercontent.com` as an OIDC provider.

**Google Cloud:**

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/123/locations/global/workloadIdentityPools/my-pool/providers/github
    service_account: deployer@my-project.iam.gserviceaccount.com
```

Requires a Workload Identity Pool configured in GCP with a GitHub OIDC provider binding.

**Azure:**

```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

Uses federated credentials on the Azure App Registration — no client secret stored.

---

## CD and Environment Promotion

The standard promotion pattern: build once, deploy to staging automatically, then gate production behind a manual approval.

### Staging → Production Pipeline

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build artifact
        run: make build
      - uses: actions/upload-artifact@v4
        with:
          name: app-artifact
          path: dist/

  deploy-staging:
    environment: staging
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: app-artifact
          path: dist/
      - name: Deploy to staging
        run: ./scripts/deploy.sh staging

  smoke-test:
    runs-on: ubuntu-latest
    needs: deploy-staging
    steps:
      - name: Run smoke tests against staging
        run: ./scripts/smoke-test.sh https://staging.example.com

  deploy-production:
    environment: production   # required reviewers configured in GitHub Settings
    runs-on: ubuntu-latest
    needs: smoke-test
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: app-artifact
          path: dist/
      - name: Deploy to production
        run: ./scripts/deploy.sh production
      - name: Notify on failure
        if: failure()
        run: ./scripts/notify-failure.sh "${{ job.status }}"
```

### Environment Protection Configuration

Set these in GitHub Settings → Environments, not in YAML:

| Setting                    | Recommended Value                              |
|----------------------------|------------------------------------------------|
| Required reviewers         | 1–2 senior engineers for `production`          |
| Wait timer                 | Optional: 5–10 min buffer before deployment    |
| Deployment branches        | Limit to `main` branch only                    |
| Environment secrets        | Prod credentials scoped here, not at repo level|

### Deployment Status

Use `job.status` in post-deploy notifications:

```yaml
- name: Notify Slack
  if: always()
  uses: slackapi/slack-github-action@v1
  with:
    payload: '{"text": "Deploy to production: ${{ job.status }}"}'
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Artifact and Package Publishing

### Docker Image to GHCR

```yaml
jobs:
  publish-image:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,prefix=,suffix=,format=short
            type=ref,event=branch
            type=semver,pattern={{version}}

      - uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Always tag images with the commit SHA. Never use `latest` as the only tag in production.

### PyPI with Trusted Publishing (No Token Needed)

Configure a Trusted Publisher in PyPI project settings pointing to this repository and workflow, then:

```yaml
jobs:
  publish-pypi:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # required for trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://upload.pypi.org/legacy/
          # For pre-release testing:
          # repository-url: https://test.pypi.org/legacy/
```

### npm Publish

```yaml
jobs:
  publish-npm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - run: npm ci
      - run: npm run build
      - run: npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

---

## Complete Workflow Examples

### Python Service

```yaml
name: Python CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy src/
      - run: pytest --cov=src --cov-report=xml --cov-fail-under=80
      - run: pip-audit
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

### TypeScript/Node Service

```yaml
name: Node CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test -- --coverage
      - run: npm audit --audit-level=high
```

### Go Service

```yaml
name: Go CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
          cache: true
      - run: go vet ./...
      - run: staticcheck ./...
      - run: go test -race -coverprofile=coverage.out ./...
      - run: go tool cover -func=coverage.out
      - run: govulncheck ./...
```

---

## Decision Tables

### Which Cache Approach to Use

| Language   | Recommended Approach                        | Lockfile to Hash                   |
|------------|---------------------------------------------|------------------------------------|
| Python     | `setup-python` built-in `cache: pip`        | `requirements*.txt`, `pyproject.toml` |
| Node.js    | `setup-node` built-in `cache: npm/pnpm`     | `package-lock.json`, `pnpm-lock.yaml` |
| Go         | `setup-go` built-in `cache: true`           | `go.sum`                           |
| Rust       | `actions/cache` on `~/.cargo`               | `Cargo.lock`                       |
| Java/Maven | `actions/cache` on `~/.m2`                  | `pom.xml`                          |

### When to Use OIDC vs Stored Secrets

| Credential Type         | Use OIDC | Use Stored Secret             |
|-------------------------|----------|-------------------------------|
| AWS IAM role            | Yes      | No — OIDC is the standard     |
| GCP service account     | Yes      | No — Workload Identity preferred |
| Azure managed identity  | Yes      | No — Federated credentials preferred |
| NPM publish token       | No       | Yes — npm does not support OIDC |
| PyPI publish token      | No (use Trusted Publishing) | Only if Trusted Publishing unavailable |
| Third-party API key     | No       | Yes                           |

### Trigger Selection Guide

| Scenario                            | Recommended Trigger                       |
|-------------------------------------|-------------------------------------------|
| Run CI on every PR                  | `pull_request` targeting `main`           |
| Deploy on merge to main             | `push` on `main` branch                   |
| Nightly dependency audit            | `schedule` with cron                      |
| Manual production deploy            | `workflow_dispatch` with input parameters |
| Shared CI logic across repos        | `workflow_call` (reusable workflow)        |
| Release on tag push                 | `push` with `tags: ['v*']`                |

---

## Checklist

- [ ] Workflow triggers cover both `push` to main and `pull_request`
- [ ] Jobs run in correct dependency order using `needs:`
- [ ] Package manager caching configured (pip/npm/go modules)
- [ ] Lint, type-check, test, and security scan are all separate steps
- [ ] Coverage threshold enforced (`--cov-fail-under` / `--coverage`)
- [ ] `$GITHUB_TOKEN` permissions scoped to least privilege
- [ ] Secrets accessed via `${{ secrets.X }}` — never hardcoded
- [ ] OIDC used for cloud credentials — no long-lived access keys stored as secrets
- [ ] CD deploys to staging first; production requires approval via environment protection
- [ ] Docker images tagged with commit SHA, not `latest`
- [ ] Failed jobs produce clear error output; no silent failures
- [ ] Pipeline completes in under 10 minutes on a typical PR
