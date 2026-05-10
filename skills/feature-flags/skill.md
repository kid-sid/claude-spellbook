---
name: feature-flags
description: Use when adding feature flag support to a service, designing a percentage-based rollout, setting up A/B experiments or multivariate tests, choosing between LaunchDarkly, Unleash, and OpenFeature, writing tests for flag-gated code, or managing flag lifecycle and cleanup.
---

# Feature Flags & A/B Testing

Tactical patterns for flag evaluation, progressive rollouts, controlled experiments, and flag lifecycle — the code-level companion to infrastructure-level canary deployments.

## When to Activate

- Adding feature flag support to a new or existing service
- Designing a percentage-based or ring-based rollout
- Setting up A/B experiments or multivariate tests
- Choosing between LaunchDarkly, Unleash, and OpenFeature
- Implementing sticky bucketing or mutual exclusion across experiments
- Writing unit or integration tests for flag-gated code paths
- Auditing, cleaning up, or governing stale flags

## Flag Types & Evaluation Context

Four flag types cover all use cases:

| Type | SDK method | Use for |
|---|---|---|
| `boolean` | `getBooleanValue` | On/off gates, kill switches |
| `string` | `getStringValue` | Variant selection (A/B/C), layout names |
| `number` | `getNumberValue` | Numeric config: timeout, batch size, rate limit |
| `object` | `getObjectValue` | Complex config blob, multi-key experiment payload |

### Evaluation Context

The context is the set of attributes the flag platform uses to apply targeting rules. Always include a stable user identifier.

```typescript
// TypeScript — OpenFeature
import { OpenFeature, type EvaluationContext } from "@openfeature/server-sdk";

const ctx: EvaluationContext = {
  targetingKey: user.id,        // required: stable, not session-scoped
  email: user.email,
  orgId: user.orgId,
  plan: user.plan,              // "free" | "pro" | "enterprise"
  country: request.geo.country,
  appVersion: "2.4.1",
  betaTester: user.betaTester,  // custom boolean attribute
};

const client = OpenFeature.getClient("payments");
const enabled  = await client.getBooleanValue("new-checkout", false, ctx);
const variant  = await client.getStringValue("checkout-layout", "control", ctx);
const timeout  = await client.getNumberValue("api-timeout-ms", 5000, ctx);
const config   = await client.getObjectValue("rate-limit-config", { rpm: 100 }, ctx);
```

```python
# Python — Unleash
context = {
    "userId": str(user.id),
    "properties": {
        "orgId":   str(user.org_id),
        "plan":    user.plan,
        "country": request.geo.country,
    },
}

enabled = client.is_enabled("new-checkout", context, fallback_function=lambda: False)
variant = client.get_variant("checkout-layout", context)
# variant = {"name": "control" | "v2-grid", "payload": {"type": "string", "value": "..."}}
```

```go
// Go — LaunchDarkly
ctx := ldcontext.NewBuilder(user.ID).
    Kind("user").
    SetString("email", user.Email).
    SetString("orgId", user.OrgID).
    SetString("plan", user.Plan).
    Build()

enabled, _ := ldClient.BoolVariation("new-checkout", ctx, false)
variant, _  := ldClient.StringVariation("checkout-layout", ctx, "control")
timeout, _  := ldClient.IntVariation("api-timeout-ms", ctx, 5000)
```

## SDK Setup Patterns

### LaunchDarkly

```python
# Python
import ldclient
from ldclient.config import Config
from datetime import timedelta

ldclient.set_config(Config(
    sdk_key="sdk-your-key",
    stream=True,                             # streaming pushes changes; polling pulls on interval
    poll_interval=30,                        # seconds, only used when stream=False
    initial_reconnect_delay=timedelta(seconds=1),
))
ld = ldclient.get()

if not ld.is_initialized():
    logger.warning("LaunchDarkly SDK not initialized — flag calls will return defaults")
```

```go
// Go
import (
    ld     "github.com/launchdarkly/go-sdk/ldclient"
    ldconf "github.com/launchdarkly/go-sdk/ldconfig"
)

config := ldconf.Config{
    Events: ldconf.EventsConfig{Capacity: 10_000},
}
ldClient, err := ld.MakeCustomClient("sdk-your-key", config, 5*time.Second)
if err != nil {
    log.Warnf("LaunchDarkly init failed: %v — using fallback defaults", err)
}
defer ldClient.Close()
```

### Unleash

```typescript
// TypeScript
import { initialize } from "unleash-client";

const unleash = initialize({
  url: "https://unleash.example.com/api/",
  appName: "frontend-app",
  customHeaders: { Authorization: "Bearer <token>" },
  refreshInterval: 15,     // seconds between polls
  metricsInterval: 60,
});

// Block until first sync so requests don't see stale state
await new Promise<void>((resolve) => unleash.on("synchronized", resolve));
```

```python
# Python
from UnleashClient import UnleashClient

client = UnleashClient(
    url="https://unleash.example.com/api",
    app_name="backend-service",
    custom_headers={"Authorization": "Bearer <token>"},
    refresh_interval=15,
    metrics_interval=60,
)
client.initialize_client()
```

### OpenFeature — Provider Abstraction

OpenFeature decouples evaluation code from the vendor SDK. Swap providers without touching call sites.

```typescript
import { OpenFeature } from "@openfeature/server-sdk";
import { LaunchDarklyProvider } from "@openfeature/launchdarkly-provider";
// import { UnleashProvider } from "@openfeature/unleash-provider";

// Change this one line to migrate vendor:
await OpenFeature.setProviderAndWait(new LaunchDarklyProvider("sdk-key"));

const client = OpenFeature.getClient("payments");
// All getBooleanValue / getStringValue calls remain identical after the swap
```

### Caching & Offline Fallbacks

```python
# GOOD: evaluate once per request, pass result down
async def handle_checkout(request):
    ctx = build_context(request.user)
    use_v2 = client.is_enabled("new-checkout", ctx)   # one call
    return render_checkout(request, v2=use_v2)

# BAD: evaluate inside a loop — one SDK call per item
async def handle_cart(request):
    for item in request.cart.items:
        if client.is_enabled("new-pricing", ctx):      # N calls
            item.price = calculate_new_price(item)
```

Always define safe defaults — the value returned when the SDK cannot reach the flag service:

```typescript
// Default must be the safe/conservative behavior
const enabled = await client.getBooleanValue("new-checkout", false, ctx);
//                                                              ^^^^^ off by default
const rateLimit = await client.getNumberValue("rpm-limit", 100, ctx);
//                                                          ^^^ conservative default
```

## Targeting & Rollout Patterns

| Pattern | Use Case | Bucketing | Remove after |
|---|---|---|---|
| Dark launch | Code ships, invisible to users | — | Feature is stable |
| Percentage rollout | Gradual ramp 1→5→25→100% | Sticky by user ID | 100% + 2-week soak |
| Ring deployment | Internal → beta → enterprise → all | Group (org, plan) | All rings enabled |
| Kill switch | Emergency disable without deploy | — | Keep indefinitely |
| Permission flag | Role/plan-gated capability | Attribute exact match | Pricing restructure |
| A/B experiment | Controlled hypothesis test | Sticky by user ID | Experiment concluded |

### Sticky Bucketing

Sticky bucketing ensures a user always gets the same variant — across sessions, devices, and services.

```
# GOOD: stable user ID as bucketing key
bucket = murmurhash(flag_key + user.id) % 100
# user 'alice' → always bucket 37 → always "treatment"

# BAD: session ID as bucketing key
bucket = murmurhash(flag_key + session_id) % 100
# 'alice' gets control on mobile, treatment on desktop, control after re-login
```

### Multivariate Flags

```python
variant = client.get_variant("checkout-layout", context)

match variant["name"]:
    case "v2-grid":
        return render_grid_layout()
    case "v2-list":
        return render_list_layout()
    case _:
        return render_control()   # always handle the default / unknown case
```

### Mutual Exclusion

Two experiments on the same surface contaminate each other's results. Use traffic partitioning:

```
Total traffic: 100%
├── Experiment A pool: 50% of users  (checkout button color)
└── Experiment B pool: 50% of users  (checkout button size)

No user is in both pools — interaction effects are eliminated.
```

Most flag platforms expose this as "experiment groups" or "mutex layers." For manual control, add an upstream assignment flag that routes users into pools before the experiment flags fire.

## A/B Testing & Experimentation

### Hypothesis Framing

```
Template: "If we [change], then [metric] will [direction] by [magnitude]
          for [audience] because [reason]."

Good: "If we show inline address validation, then checkout completion
       will increase by 8% for mobile users because form errors are caught earlier."

Bad:  "The new checkout will be better."       (no metric, no magnitude)
Bad:  "Conversion will improve."               (no baseline, no MDE)
```

### Sample Size Calculation

```python
import math

def min_sample_size(p_baseline: float, mde_absolute: float, alpha=0.05, power=0.80) -> int:
    """
    Returns minimum users per variant.
    p_baseline: current conversion rate (e.g. 0.12 for 12%)
    mde_absolute: smallest effect worth detecting (e.g. 0.02 for +2pp)
    """
    z_alpha = 1.96   # two-tailed, α=0.05
    z_power = 0.84   # power=0.80
    sigma = math.sqrt(p_baseline * (1 - p_baseline))
    n = ((z_alpha + z_power) * sigma / mde_absolute) ** 2
    return math.ceil(n)

# Baseline: 12% conversion. Want to detect +2pp lift.
n = min_sample_size(0.12, 0.02)   # → ~4,100 per variant → ~8,200 total
```

**Rule of thumb by effect size (binary metric, 80% power, α=0.05):**

| Relative MDE | Approx. n per variant |
|---|---|
| 10% | 1,500 |
| 5% | 5,500 |
| 2% | 34,000 |
| 1% | 130,000 |

### Statistical Significance & the Peeking Problem

```
Target: p < 0.05 (two-tailed), power ≥ 0.80

Peeking problem: checking significance daily and stopping at first p < 0.05
inflates false positive rate from 5% to ~40% over 20 checks.

Fix options:
1. Pre-register sample size → evaluate ONCE at that threshold (no peeking)
2. Sequential testing (SPRT) — designed for continuous monitoring
3. Bayesian testing — computes probability of being best, handles early stopping
```

### Holdout Groups

```python
HOLDOUT_PCT = 5  # 5% of users never see any experiment

def in_holdout(user_id: str) -> bool:
    bucket = mmh3.hash(f"global-holdout:{user_id}", signed=False) % 100
    return bucket < HOLDOUT_PCT

# Check before any experiment assignment
if in_holdout(user.id):
    serve_all_controls(user)
else:
    assign_experiments(user)
```

Holdout groups measure the cumulative long-term effect of all experiments combined. Without one, you can't distinguish "we shipped 10 wins" from "we got lucky with 3 wins and 7 neutral experiments."

### Metrics Hierarchy

```
Primary:    the one metric the experiment is designed to move
            → checkout_completion_rate

Guardrail:  metrics that must NOT degrade, regardless of primary movement
            → api_p95_latency ≤ 400ms, error_rate ≤ 0.5%, revenue_per_user

Secondary:  directional signals, inform future work, never the decision basis
            → add_to_cart_rate, session_duration
```

An experiment is a **win** only if: primary improved AND all guardrails held.  
A guardrail violation kills the experiment — even with a strong primary improvement.

### Metric Event Emission

```typescript
// Emit metric events alongside flag evaluation
const { value: inExperiment } = await client.getBooleanDetails(
  "checkout-v2-exp", false, ctx
);

trackEvent("experiment.assigned", {
  experiment: "checkout-v2-exp",
  variant: inExperiment ? "treatment" : "control",
  userId: ctx.targetingKey,
});

// On conversion — linked by userId to calculate per-variant rate
trackEvent("checkout.completed", { userId: ctx.targetingKey, revenue: order.total });
```

## Observability for Flags

### Structured Logging

```python
# Python — log every flag evaluation
import structlog, time
log = structlog.get_logger()

def evaluate_flag(key: str, ctx: dict, default: bool) -> bool:
    t0 = time.monotonic()
    result = client.is_enabled(key, ctx, fallback_function=lambda: default)
    log.info(
        "flag.evaluated",
        flag_key=key,
        variant=str(result),
        user_id=ctx.get("userId"),
        org_id=ctx.get("properties", {}).get("orgId"),
        duration_ms=round((time.monotonic() - t0) * 1000, 2),
    )
    return result
```

```typescript
// TypeScript — include evaluation reason from OpenFeature
const details = await client.getBooleanDetails("new-checkout", false, ctx);
logger.info("flag.evaluated", {
  flag_key:    "new-checkout",
  variant:     String(details.value),
  reason:      details.reason,      // TARGETING_MATCH | DEFAULT | STATIC | ERROR
  user_id:     ctx.targetingKey,
  duration_ms: performance.now() - start,
});
```

### Metrics

```
# Prometheus counters / histograms
flag_evaluations_total{flag, variant, reason}
flag_evaluation_duration_seconds{flag, quantile}
flag_sdk_errors_total{flag, error_type}
stale_flags_count{flag, days_since_last_change}    # from audit log
```

### Tracing Integration

```python
# OpenTelemetry — attach flag decision to the active span
from opentelemetry import trace

span = trace.get_current_span()
span.set_attribute("feature_flag.key",      "new-checkout")
span.set_attribute("feature_flag.variant",  str(enabled))
span.set_attribute("feature_flag.provider", "unleash")
# Enables "show me all traces where new-checkout=true" in Jaeger/Tempo
```

### Alert Rule

```yaml
# Prometheus — fire if variant split drifts >20pp from expected 50/50
- alert: FlagVariantDistributionAnomaly
  expr: |
    abs(
      rate(flag_evaluations_total{variant="true"}[5m])
      / rate(flag_evaluations_total[5m])
      - 0.50
    ) > 0.20
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Flag {{ $labels.flag }} split drifted >20% from expected"
    description: "Check bucketing logic or targeting rule misconfiguration."
```

## Testing Flag-Gated Code

### Unit Tests — Mock the Client

```typescript
// TypeScript — Jest + OpenFeature InMemoryProvider
import { OpenFeature, InMemoryProvider } from "@openfeature/server-sdk";

async function setFlag(key: string, value: boolean) {
  await OpenFeature.setProviderAndWait(new InMemoryProvider({
    [key]: { defaultVariant: value ? "on" : "off", variants: { on: true, off: false } },
  }));
}

describe("CheckoutPage", () => {
  test("renders v2 when flag is on", async () => {
    await setFlag("new-checkout", true);
    render(<CheckoutPage />);
    expect(screen.getByTestId("checkout-v2")).toBeInTheDocument();
  });

  test("renders v1 when flag is off", async () => {
    await setFlag("new-checkout", false);
    render(<CheckoutPage />);
    expect(screen.getByTestId("checkout-v1")).toBeInTheDocument();
  });
});
```

```python
# Python — pytest with patch
from unittest.mock import patch
import pytest

@pytest.fixture
def flag_on():
    with patch("myapp.flags.client.is_enabled", return_value=True):
        yield

@pytest.fixture
def flag_off():
    with patch("myapp.flags.client.is_enabled", return_value=False):
        yield

def test_new_checkout_rendered(api_client, flag_on):
    r = api_client.get("/checkout")
    assert r.data["layout"] == "v2"

def test_old_checkout_rendered(api_client, flag_off):
    r = api_client.get("/checkout")
    assert r.data["layout"] == "v1"
```

```go
// Go — interface injection, table-driven
type FlagClient interface {
    BoolVariation(key string, ctx ldcontext.Context, def bool) (bool, error)
}

type stubClient struct{ val bool }

func (s *stubClient) BoolVariation(_ string, _ ldcontext.Context, _ bool) (bool, error) {
    return s.val, nil
}

func TestCheckoutHandler(t *testing.T) {
    for _, tc := range []struct {
        name, want string
        flag       bool
    }{
        {"flag on → v2", "v2", true},
        {"flag off → v1", "v1", false},
    } {
        t.Run(tc.name, func(t *testing.T) {
            h := NewCheckoutHandler(&stubClient{val: tc.flag})
            w := httptest.NewRecorder()
            h.ServeHTTP(w, httptest.NewRequest("GET", "/checkout", nil))
            assert.Contains(t, w.Body.String(), tc.want)
        })
    }
}
```

### E2E — Seed via API

```bash
# Seed flag state before test run (Unleash Admin API)
curl -sX POST https://unleash.example.com/api/admin/features \
  -H "Authorization: Bearer $UNLEASH_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"new-checkout","enabled":true,"strategies":[{"name":"default"}]}'

npx playwright test

# Tear down (or use a dedicated test environment that resets between runs)
curl -sX DELETE https://unleash.example.com/api/admin/features/new-checkout \
  -H "Authorization: Bearer $UNLEASH_ADMIN_TOKEN"
```

Never use the production flag service in tests — flag changes in tests would affect real users.

## Lifecycle & Governance

### Naming Convention

```
<team>_<feature>_<type>

type values:
  rollout   temporary gradual enable; remove after 100% soak
  kill      permanent emergency disable switch; keep indefinitely
  exp       A/B experiment; remove after conclusion
  gate      plan/role permission; long-lived, review quarterly

Examples:
  payments_checkout_v2_rollout
  infra_legacy_grpc_kill
  growth_homepage_hero_exp
  billing_pro_csv_export_gate
```

### Required Metadata

Document in your flag platform or a `flags.yaml` alongside code:

```yaml
- key: payments_checkout_v2_rollout
  owner: payments-team
  ticket: ENG-1234
  created: 2026-03-01
  cleanup_by: 2026-06-01      # set at creation, not after the fact
  type: rollout
  description: Progressive rollout of checkout v2 to all users
```

### Cleanup Detection

A flag is stale when it has been at 0% or 100% for 90+ days with no targeting rule changes.

```bash
# Detect via Unleash metrics API
curl -s https://unleash.example.com/api/admin/metrics/feature-toggles \
  -H "Authorization: Bearer $TOKEN" | \
  jq '[.[] | select(.lastSeenAt < (now - 7776000 | todate))]'
  # 7776000 = 90 days in seconds
```

### Migration: Flag → Code (Three PRs)

```
PR 1: Ramp flag to 100% — observe for 2+ weeks
PR 2: Replace flag evaluation with hardcoded behavior
      client.getBooleanValue("payments_checkout_v2_rollout", false, ctx)
      → true (or remove the branch entirely)
      Keep flag registered in the platform — runtime still starts cleanly.
PR 3: Delete flag from platform, remove registration code
      Do NOT combine PR 2 and PR 3 — deleting the flag before removing
      the SDK call causes runtime errors if any service still evaluates it.
```

### When to Use a Flag vs. Not

| Situation | Use Flag? |
|---|---|
| New feature, gradual rollout needed | Yes — percentage rollout |
| Feature only for enterprise plan | Yes — permission gate |
| Bug fix | No — ship directly |
| Config value that differs per-env | No — env var or config service |
| Infrastructure change with instant rollback need | Maybe — kill switch only |
| A/B test with statistical hypothesis | Yes — experiment flag |
| Feature shipping to 100% in < 1 week | No — unnecessary complexity |

## Red Flags

- **No cleanup date set at creation** — flags accumulate silently; at 200 flags most engineers can't say what 80% do; set `cleanup_by` the day the flag is created
- **Session ID as bucketing key** — users see different variants on new tabs, after logout, and across devices; always bucket on stable user ID
- **Evaluating flags inside hot loops** — SDK calls hit an in-process cache but still allocate; evaluate once per request and pass the result down
- **Stopping experiment at first p < 0.05** — peeking without a pre-registered sample size inflates false positive rate from 5% to ~40%; pre-commit to a sample size and evaluate once
- **No guardrail metrics defined before launch** — a conversion lift that doubles p95 latency is not a win; define guardrails before the experiment starts, not after
- **Different bucketing logic per service** — user gets treatment in the frontend and control in the backend; always share evaluation context or use a single evaluation service
- **Using env vars as feature flags** — no targeting, no audit trail, requires a redeploy to change; not a flag system
- **A/B flag left running after conclusion** — the longer a concluded experiment flag lives, the higher the chance someone rolls it back by accident; remove within one sprint of the decision

## Checklist

- [ ] SDK initialized before first flag call; fallback defaults defined for SDK unavailability
- [ ] Evaluation context uses stable user ID, not session ID
- [ ] All four flag types evaluated — not everything needs a boolean
- [ ] Kill switch created alongside every rollout flag
- [ ] Sticky bucketing verified: same user gets same variant across services and sessions
- [ ] Sample size calculated and documented before any A/B experiment starts
- [ ] Experiment hypothesis written: change, metric, magnitude, audience, reason
- [ ] Guardrail metrics defined (latency, error rate) — experiment won't win if these degrade
- [ ] Mutual exclusion configured when multiple experiments touch the same UI surface
- [ ] Flag evaluation logged: `flag_key`, `variant`, `reason`, `user_id`, `duration_ms`
- [ ] Prometheus counter tracking variant distribution for every flag
- [ ] Alert configured: fire if variant split drifts >20% unexpectedly
- [ ] Unit tests cover both flag-on and flag-off paths with no real SDK calls
- [ ] E2E tests seed flags via admin API, not hardcoded to a single environment state
- [ ] Cleanup date (`cleanup_by`) set in flag platform at creation
- [ ] Flag naming follows `<team>_<feature>_<type>` convention
- [ ] Migration plan documented: ramp to 100% → hardcode → delete (three PRs)

> See also: `deployment-strategies` (canary infrastructure, Argo Rollouts, Flagger, rollback procedures)
> See also: `observability` (structured logging patterns, Prometheus metrics, OpenTelemetry tracing, SLO alerting)
