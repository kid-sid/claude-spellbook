---
name: deployment-strategies
description: "Deployment strategies: rolling updates, blue/green deployments, canary releases with automated analysis (Argo Rollouts/Flagger), feature flags (LaunchDarkly/Unleash/OpenFeature), expand-contract database migration pattern for zero-downtime deployments, and rollback procedures."
---

# Deployment Strategies

A reference for selecting and implementing deployment strategies that minimize risk, enable zero-downtime releases, and provide fast rollback paths.

## When to Activate

- Planning a deployment strategy for a new service or major release
- Implementing feature flags in an application
- Coordinating a database migration with a zero-downtime deployment
- Setting up canary releases or progressive delivery
- Defining rollback procedures for a service
- Reducing deployment risk for a high-traffic service

## Strategy Comparison

| Strategy | Traffic routing | Rollback speed | Risk | Infrastructure cost | Best for |
|---|---|---|---|---|---|
| Recreate | Stop all, start new | Fast (redeploy) | High (downtime) | Low | Dev/non-prod |
| Rolling update | Replace pods gradually | Medium (rollback flag) | Medium | Low | Most services |
| Blue/Green | Flip all traffic at once | Instant (flip back) | Low | 2x | High-stakes releases |
| Canary | Shift % traffic gradually | Instant (shift back) | Very low | Slightly > 1x | High-traffic, data-sensitive |
| A/B Testing | Route by user segment | Instant | Low | ~1x | Feature experiments |
| Shadow | Mirror traffic, no user impact | N/A | None | ~2x | Testing new version with real traffic |

## Rolling Updates (Kubernetes)

Default Kubernetes behavior when you run `kubectl apply`. Pods are replaced incrementally — no full restart required.

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # max pods above desired count during rollout
    maxUnavailable: 0  # never go below desired count (zero-downtime)
```

- Set `maxUnavailable: 0` to guarantee zero downtime — new pods must pass readiness probes before old pods are terminated.
- Rollback: `kubectl rollout undo deployment/my-service`
- Target a specific revision: `kubectl rollout undo deployment/my-service --to-revision=3`
- Monitor progress: `kubectl rollout status deployment/my-service`
- Issue: slow rollback if many replicas; new version runs alongside old — both app versions must be compatible with current DB schema.

## Blue/Green Deployments

Two identical environments run in parallel: **Blue** (live) and **Green** (new version). Traffic flips atomically from one to the other.

### Process

1. Deploy new version to Green environment
2. Run smoke tests against Green (no user traffic yet)
3. Flip traffic: update load balancer rule or Kubernetes Service selector
4. Monitor error rate and latency for 15–30 minutes
5. Decommission Blue (or keep as instant rollback for 24 hours)

### Kubernetes Implementation

Flip the Service selector to switch which deployment receives traffic.

```yaml
# Blue deployment (live)
spec:
  selector:
    app: payment-service
    version: blue   # Service points here

# Green deployment (new)
spec:
  selector:
    app: payment-service
    version: green  # Update Service to point here after smoke tests
```

Flip command:

```bash
kubectl patch service payment-service -p '{"spec":{"selector":{"version":"green"}}}'
```

### Considerations

- **Cost:** 2x infrastructure during transition window.
- **Warm-up:** Green must receive warming traffic (health checks, cache pre-warming) before the flip to avoid cold-start latency spikes.
- **Database:** Both Blue and Green versions must be compatible with the same DB schema during the transition window. Use the expand-contract pattern for migrations.

## Canary Releases

Gradually shift traffic from the stable version to the new version. Automated analysis gates promotion based on SLO metrics.

- Typical progression: 5% → 25% → 50% → 100%
- Automated promotion: if error rate < 1% and p99 latency < 500 ms, advance
- Manual gate: require human approval before advancing beyond 25%
- Automated abort: if metrics breach thresholds, roll back instantly

### Argo Rollouts

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-service
spec:
  strategy:
    canary:
      steps:
        - setWeight: 5
        - pause: { duration: 10m }
        - setWeight: 25
        - pause: {}  # manual gate — requires human approval
        - setWeight: 50
        - pause: { duration: 10m }
        - setWeight: 100
      analysis:
        templates:
          - templateName: error-rate-check
        startingStep: 1
        args:
          - name: service-name
            value: payment-service
```

Promote or abort the rollout:

```bash
kubectl argo rollouts promote payment-service  # advance to next step
kubectl argo rollouts abort payment-service    # rollback to stable
```

### Flagger (Linkerd / Istio)

Flagger integrates with service meshes for automatic traffic splitting and metric-based promotion. Define a `Canary` CR with `analysis.metrics` referencing Prometheus queries. Flagger handles weight increments and rollback automatically — no manual step definitions required.

## Feature Flags

### Why Feature Flags

- **Decouple deployment from release:** deploy code, enable for users later
- **Progressive rollout:** enable for 1% → 10% → 100% of users without redeploying
- **Kill switch:** disable instantly without a deployment or rollback
- **A/B testing:** different experiences for user segments based on targeting rules

### Flag Lifecycle

1. Add flag (disabled by default)
2. Deploy code wrapped behind flag
3. Enable for internal users → beta users → percentage rollout → 100%
4. Remove flag and dead code (flags are technical debt — clean up within a sprint of full rollout)

### Tools Comparison

| Tool | Hosting | SDK support | Best for |
|---|---|---|---|
| LaunchDarkly | Cloud (paid) | 20+ SDKs | Enterprise, A/B testing |
| Unleash | Self-hosted or cloud | 10+ SDKs | Open-source, full control |
| OpenFeature | Standard (vendor-agnostic SDK) | All vendors | Portability across providers |
| AWS AppConfig | Cloud | AWS SDK | AWS-native workloads |
| Environment variables | N/A | Simple | Simple boolean flags, no runtime toggle needed |

### Code Pattern (OpenFeature)

```typescript
import { OpenFeature } from '@openfeature/server-sdk';

const client = OpenFeature.getClient();

// Simple boolean flag
const isNewCheckoutEnabled = await client.getBooleanValue(
  'new-checkout-flow',
  false,  // default value — returned if flag is missing or evaluation fails
  { targetingKey: userId }
);

if (isNewCheckoutEnabled) {
  return newCheckoutHandler(req, res);
} else {
  return legacyCheckoutHandler(req, res);
}
```

OpenFeature's provider abstraction means swapping from LaunchDarkly to Unleash requires changing only the registered provider — application code stays the same.

## Database Migrations and Zero-Downtime Deployments

### The Problem

Direct `ALTER TABLE` can lock tables under load. Renaming columns breaks the old app version that runs alongside the new version during a rolling deploy. Any migration that removes or renames a column must be done in phases.

### Expand-Contract Pattern (Parallel Change)

Use for: adding NOT NULL columns, renaming columns or tables, changing data types.

**Phase 1 — Expand (additive only):**

- Add new column as NULLABLE
- Deploy application code that writes to **both** old and new columns
- No downtime — old app version still works with the old column

**Phase 2 — Migrate:**

- Backfill existing rows in batches to avoid table locks:
  ```sql
  UPDATE table SET new_col = old_col WHERE new_col IS NULL LIMIT 10000;
  ```
- Deploy application code that reads from the new column
- Add NOT NULL constraint once all rows are populated (now safe)

**Phase 3 — Contract (remove old):**

- Deploy application code that no longer references the old column
- Drop old column in a separate migration
- Can be done in a later sprint once confidence is high

### Example Timeline

Renaming `user.username` to `user.display_name`:

```
Sprint 1: Add display_name (nullable), write to both columns
Sprint 2: Backfill rows, read from display_name, add NOT NULL
Sprint 3: Remove username column
```

### Large Table Migrations

For tables with millions of rows, use `pt-online-schema-change` (Percona) or `gh-ost` (GitHub) to perform the migration on a shadow table and cut over with minimal locking.

## Rollback Procedures

### When to Roll Back

Roll back when:
- Error rate exceeds SLO threshold (e.g., > 1% errors) within 15 minutes of deploy
- p99 latency increases more than 2x baseline
- Critical functionality is broken (payments, login, data integrity)

Do **not** roll back immediately for:
- Cosmetic issues or minor UI regressions
- Minor performance variance within acceptable range
- Cases where rollback itself would cause different data loss (evaluate carefully)

### Rollback Decision Tree

```
Error rate > SLO?
├── Yes → Can we fix forward in < 15 minutes? → No  → ROLLBACK
│                                              → Yes → hotfix + monitor
└── No  → Monitor, do not rollback
```

### Rollback Commands

```bash
# Kubernetes rolling update — undo last rollout
kubectl rollout undo deployment/payment-service

# Kubernetes — target a specific revision
kubectl rollout undo deployment/payment-service --to-revision=3

# Argo Rollouts canary — abort and revert to stable
kubectl argo rollouts abort payment-service

# Helm — rollback to a previous release number
helm rollback payment-service 3
```

### Rollback Runbook Template

```markdown
## Rollback: [Service Name]

**Trigger criteria:** [e.g., error rate > 1% for 5 minutes]

**Steps:**
1. Notify on-call channel: "@oncall rolling back payment-service due to [reason]"
2. Run: `kubectl rollout undo deployment/payment-service -n production`
3. Verify: `kubectl rollout status deployment/payment-service`
4. Check metrics: confirm error rate returns to baseline
5. Create incident ticket with timeline and root cause

**Data rollback:** [specify if DB migration rollback is needed and how]
**Escalation:** [who to page if rollback fails]
```

> See also: `ci-cd`, `containerization`, `observability`, `incident-response`

## Checklist

- [ ] Deployment strategy chosen and documented (rolling / blue-green / canary)
- [ ] `maxUnavailable: 0` set for zero-downtime rolling updates
- [ ] Readiness probe passes before traffic is routed to new pods
- [ ] Smoke tests run automatically after each deployment
- [ ] Canary analysis configured with SLO-based pass/fail criteria
- [ ] Feature flags used for high-risk features — code deployed dark before enabling
- [ ] Dead feature flag code cleaned up within same sprint as full rollout
- [ ] Database migrations follow expand-contract pattern for zero-downtime
- [ ] Both app versions compatible with same DB schema during rolling deploy window
- [ ] Rollback procedure documented with specific commands and trigger criteria
