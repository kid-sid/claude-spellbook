---
name: smoke-testing
description: Use when verifying a fresh deployment, gating a CI pipeline before full test runs, checking that core user flows are reachable after a release, or building a minimal health-check suite for a new service.
---

# Smoke Testing

A minimal test pass that confirms the critical paths of an application work before investing in deeper testing.

## When to Activate

- Verifying a fresh deployment to staging or production
- Gating a CI pipeline before the full test suite runs
- Checking core user flows after a release or hotfix
- Building an initial test suite for a new service
- Deciding which tests to run on every commit vs. nightly
- Validating a rollback brought the system back to a working state
- Confirming third-party integrations are reachable after infrastructure changes

---

## What to Test

Smoke tests cover the **happy path only** — the shortest route through each critical feature.

| Layer | What to check |
|---|---|
| API / Backend | Health endpoint returns `200`, auth flow succeeds, main CRUD endpoints respond |
| Frontend | App loads without JS errors, login page renders, primary navigation works |
| Database | Connection succeeds, a simple read query returns data |
| External services | Auth provider, payment gateway, email service are reachable |
| Workers / queues | Worker process starts, picks up a test job, completes without error |

---

## Scope: Smoke vs. Other Test Types

| Test type | Breadth | Depth | Speed | When to run |
|---|---|---|---|---|
| Smoke | Wide | Shallow | Seconds–1 min | Every deploy |
| Sanity | Narrow | Medium | Minutes | After targeted fixes |
| Integration | Medium | Deep | Minutes | Every commit / PR |
| Regression | Full | Deep | Minutes–hours | Nightly / pre-release |

---

## Implementation Examples

### Python (pytest + httpx)

```python
import httpx
import pytest

BASE_URL = "https://staging.example.com"

@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10)

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200

def test_login(client):
    r = client.post("/auth/login", json={"email": "smoke@test.com", "password": "test"})
    assert r.status_code == 200
    assert "token" in r.json()

def test_list_users(client):
    token = client.post("/auth/login", json={"email": "smoke@test.com", "password": "test"}).json()["token"]
    r = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
```

### TypeScript (jest + fetch / supertest)

```typescript
const BASE = process.env.SMOKE_BASE_URL ?? "http://localhost:3000";

let token: string;

beforeAll(async () => {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "smoke@test.com", password: "test" }),
  });
  token = (await res.json()).token;
});

test("health check", async () => {
  const res = await fetch(`${BASE}/health`);
  expect(res.status).toBe(200);
});

test("list users returns 200", async () => {
  const res = await fetch(`${BASE}/api/v1/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(res.status).toBe(200);
});
```

### Go (net/http + testing)

```go
package smoke_test

import (
    "net/http"
    "testing"
)

var base = "https://staging.example.com"

func get(t *testing.T, path string) *http.Response {
    t.Helper()
    resp, err := http.Get(base + path)
    if err != nil {
        t.Fatalf("request failed: %v", err)
    }
    return resp
}

func TestHealth(t *testing.T) {
    resp := get(t, "/health")
    if resp.StatusCode != http.StatusOK {
        t.Errorf("want 200, got %d", resp.StatusCode)
    }
}

func TestHomePage(t *testing.T) {
    resp := get(t, "/")
    if resp.StatusCode != http.StatusOK {
        t.Errorf("want 200, got %d", resp.StatusCode)
    }
}
```

---

## CI Integration

Run smoke tests as a dedicated job that gates the full test suite:

```yaml
# .github/workflows/ci.yml
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run smoke tests
        run: pytest tests/smoke/ -m smoke --timeout=60
        env:
          SMOKE_BASE_URL: ${{ vars.STAGING_URL }}

  full-tests:
    needs: smoke          # only runs if smoke passes
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/ --ignore=tests/smoke/
```

Tag smoke tests explicitly so they can run in isolation:

```python
# Python — use pytest marks
@pytest.mark.smoke
def test_health(): ...

# run only smoke
# pytest -m smoke
```

```typescript
// TypeScript — use jest testPathPattern or describe label
describe("[smoke]", () => {
  test("health", ...);
});
// jest --testNamePattern="\[smoke\]"
```

---

## Red Flags

- **Testing too much** — smoke tests that take >5 minutes become a bottleneck and get skipped; keep them under 2 minutes.
- **Shared mutable state** — smoke tests hitting real data that other tests modify causes false failures; use a dedicated smoke test account.
- **No environment isolation** — running smoke tests against production instead of staging risks data corruption and real side effects.
- **Skipping auth** — testing unauthenticated endpoints only misses the most common deployment break (misconfigured secrets/env vars).
- **Asserting too loosely** — checking only that the response is not `500` hides broken payloads; assert on response shape too.
- **No timeout** — smoke tests that hang block the entire pipeline; always set a request and suite-level timeout.
- **Duplicating integration tests** — smoke tests should not re-assert business logic; if a test checks calculation results it belongs in integration or unit tests.
- **Missing notifications** — a smoke failure in production that no one sees for hours defeats the purpose; wire failures to alerting (PagerDuty, Slack).

---

## Checklist

- [ ] Smoke suite runs end-to-end in under 2 minutes
- [ ] Covers health/readiness endpoint, auth flow, and at least one primary resource endpoint
- [ ] Tests are tagged (`@pytest.mark.smoke`, `[smoke]`, `//go:build smoke`) so they can run in isolation
- [ ] Runs automatically on every deploy to staging and production
- [ ] Blocks the full test suite in CI via `needs:` or equivalent gate
- [ ] Uses a dedicated test account/fixture data — never touches user production data
- [ ] Sets explicit timeouts on requests and the overall suite
- [ ] Asserts on HTTP status code AND basic response shape (not just "not 500")
- [ ] Failure triggers an immediate alert (Slack, PagerDuty, email)
- [ ] Covers at least one critical external dependency (database ping, third-party API reachability)
- [ ] Does not duplicate business-logic assertions already covered by integration tests
- [ ] `SMOKE_BASE_URL` (or equivalent) is configurable via environment variable — no hardcoded URLs
