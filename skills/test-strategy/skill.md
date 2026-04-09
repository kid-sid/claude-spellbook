---
name: test-strategy
description: "Test strategy design: testing model selection (Pyramid vs Trophy vs Honeycomb), coverage target setting by codebase type, shift-left testing techniques (linting/types/contracts as tests), non-functional test types (load/stress/soak/a11y/security), and test plan templates."
---

# Test Strategy

Design a complete testing strategy for any project: choose the right model, set meaningful coverage targets, shift quality left, and plan non-functional testing.

## When to Activate

- Starting a new project and deciding on a testing approach
- Auditing an existing test suite that is slow or provides low confidence
- Writing a QA plan or test plan document
- Deciding how to balance unit vs integration vs E2E tests for a feature
- Setting coverage targets for a team or project
- Planning non-functional testing (load, security, accessibility)

## Testing Models

Choosing the right testing model is the first decision. Each reflects a different philosophy about where confidence comes from.

### The Pyramid (Classic)

```
        /\
       /E2E\        few (slow, fragile)
      /------\
     /  Integ  \    some
    /------------\
   /    Unit      \  many (fast, reliable)
  /-----------------\
```

- Best for: well-defined layers, strong service boundaries, experienced team
- Risk: integration tests are often underdone; false confidence from high unit coverage

### The Trophy (Kent C. Dodds)

```
        /\
       /E2E\        few
      /------\
     /        \
    / Integra-  \   most  ← emphasis here
   /   tion      \
  /---------\
 /  Unit     \       some
/  (static)   \  type checking, linting
```

- Best for: React/frontend apps, services where user behavior drives quality
- The "integration" layer tests realistic slices (full request/response, not mocked)

### The Honeycomb (Spotify / Microservices)

- Emphasized: service integration tests (call your API, hit a real DB)
- De-emphasized: pure unit tests (too many mocks = low confidence)
- Best for: microservices, event-driven systems

### Decision Table

| Context | Recommended Model | Reason |
|---------|-------------------|--------|
| Monolith, complex business logic | Pyramid | Units test business rules cheaply |
| Frontend-heavy application | Trophy | Integration tests reflect user behavior |
| Microservices (many small services) | Honeycomb | Service integration > unit isolation |
| Data pipeline | Custom (mostly integration) | Units are trivial; real data matters |

## Coverage Target Setting

### What Coverage Measures

| Metric | What It Measures | How to Get It |
|--------|-----------------|---------------|
| Line coverage | Were these lines executed? | `--cov`, `--coverage`, `go test -cover` |
| Branch coverage | Were all if/else paths taken? | `--branch` flag |
| Mutation coverage | Do tests catch logic mutations? | `mutmut` (Python), `stryker` (TS), `go-mutesting` |

### Realistic Targets

| Codebase Type | Line Coverage Target | Notes |
|---------------|---------------------|-------|
| New greenfield project | 80%+ | Enforce from day 1 |
| Adding tests to legacy | Raise by 5% per sprint | Ratchet: never let it drop |
| Critical path (payments, auth) | 95%+ | Include branch coverage |
| Generated code, migrations, config loaders | Exclude from measurement | Noisy, not meaningful |

**Rule:** coverage is a floor, not a goal. 60% with excellent integration tests > 100% with trivial mocks.

### Enforcing Coverage in CI

```yaml
# pytest example (pyproject.toml)
[tool.pytest.ini_options]
addopts = "--cov=src --cov-fail-under=80 --cov-branch"

[tool.coverage.report]
omit = ["src/migrations/*", "src/generated/*", "**/config_loader.py"]
```

```json
// Jest example (package.json)
{
  "jest": {
    "coverageThreshold": {
      "global": {
        "lines": 80,
        "branches": 70
      }
    },
    "coveragePathIgnorePatterns": ["/generated/", "/migrations/"]
  }
}
```

```go
// Go example (Makefile)
// go test ./... -coverprofile=coverage.out && go tool cover -func=coverage.out | grep total
```

## Shift-Left Testing

Shift-left = catch defects earlier in the development cycle (before code review, before CI).

| Technique | When It Runs | What It Catches |
|-----------|-------------|-----------------|
| Type checking (mypy, tsc, go vet) | IDE + pre-commit | Type errors, wrong function signatures |
| Linting (ruff, eslint, staticcheck) | IDE + pre-commit | Style, common bugs, dead code |
| Pre-commit hooks | On `git commit` | Both above, secret scanning |
| Contract tests | CI on PR | API contract violations between services |
| Property-based tests | CI | Edge cases the developer didn't think of |

### Pre-Commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
```

### Contract Testing (Pact)

Contract tests verify that two services agree on the shape of requests and responses without needing both services running simultaneously.

```typescript
// Consumer side (TypeScript/Pact)
const interaction = {
  state: "user 123 exists",
  uponReceiving: "a request for user 123",
  withRequest: { method: "GET", path: "/users/123" },
  willRespondWith: {
    status: 200,
    body: { id: 123, name: like("Alice") },
  },
};
```

### Property-Based Testing

```python
# Python / Hypothesis
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(lst):
    assert sorted(sorted(lst)) == sorted(lst)
```

## Non-Functional Test Types

| Type | What It Tests | Tools | When to Run |
|------|--------------|-------|-------------|
| Load testing | Behavior under expected traffic | k6, Locust, JMeter | Pre-launch, nightly |
| Stress testing | Behavior beyond capacity | k6, Gatling | Before scaling decisions |
| Soak testing | Behavior over extended time (memory leaks) | k6, Locust | Weekly |
| Spike testing | Sudden traffic burst handling | k6 | Before big events |
| Security testing | Vulnerability scanning | OWASP ZAP, Snyk, pip-audit | Every CI run (SAST), nightly (DAST) |
| Accessibility (a11y) | WCAG compliance | axe-core, Playwright + axe | Every PR for UI changes |
| Visual regression | Unintended UI changes | Playwright screenshots, Percy | Every PR for UI changes |

### k6 Load Test Example

```javascript
// k6 load test
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "1m", target: 50 },   // ramp up
    { duration: "3m", target: 50 },   // hold
    { duration: "1m", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95th percentile under 500ms
    http_req_failed: ["rate<0.01"],   // error rate under 1%
  },
};

export default function () {
  const res = http.get("https://api.example.com/health");
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(1);
}
```

### Accessibility Testing with Playwright

```typescript
// Playwright + axe-core
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("homepage has no WCAG violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});
```

## Test Plan Template

```markdown
# Test Plan: [Feature / Release Name]

## Scope
What is being tested:
- [Feature 1]
- [Feature 2]

## Out of Scope
- [Explicitly excluded items]

## Test Environments
| Environment | URL | Data State |
|-------------|-----|-----------|
| Staging | ... | Anonymized copy of prod |

## Test Types and Owners
| Type | Owner | Tools | When |
|------|-------|-------|------|
| Unit | Dev | pytest/Jest/Go test | Every PR |
| Integration | Dev | Testcontainers | Every PR |
| E2E smoke | QA | Playwright | Post-deploy |
| Load | SRE | k6 | Pre-launch |

## Entry Criteria
- [ ] Feature code merged to main
- [ ] CI green

## Exit Criteria
- [ ] All P0/P1 test cases pass
- [ ] No open CRITICAL/HIGH bugs
- [ ] Coverage >= 80%
- [ ] Smoke tests pass on staging

## Risk Areas
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ...  | ...       | ...    | ...       |
```

> See also: `unit-testing`, `integration-testing`, `solution-testing`, `performance-testing`

## Checklist

- [ ] Testing model chosen (Pyramid/Trophy/Honeycomb) and matches team context
- [ ] Coverage targets defined per layer and enforced in CI
- [ ] Branch coverage measured for critical business logic
- [ ] Pre-commit hooks configured for linting, type-checking, secret scanning
- [ ] Non-functional test types identified (at least: load testing and security scanning)
- [ ] Test plan written for major releases
- [ ] Generated code and config loaders excluded from coverage measurement
- [ ] Test suite runs in under 10 minutes in CI (unit + integration; E2E separate)
- [ ] Contract tests in place for any service-to-service API dependencies
- [ ] Accessibility tests run on every PR touching UI components
