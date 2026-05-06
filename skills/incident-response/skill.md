---
name: incident-response
description: Use when triaging a production alert, writing a postmortem, creating or updating a runbook, classifying incident severity, or setting up on-call escalation paths.
---

# Incident Response

Incident response is the structured process of detecting, mitigating, communicating, and learning from production failures to minimise user impact and prevent recurrence.

## When to Activate

- Triaging a production alert or on-call page
- Writing a postmortem after an incident
- Creating or updating a runbook for a service
- Defining severity levels and escalation paths for a team
- Setting up an on-call rotation
- Running an incident response drill or game day

## Severity Classification

| Severity | Definition | Response SLA | Comms cadence | Example |
|----------|-----------|-------------|---------------|---------|
| P0 | Total outage or data loss — all users affected | Page immediately, < 5 min | Every 15 min | Payment service down, DB unreachable |
| P1 | Major feature broken — most users affected | < 15 min acknowledgement | Every 30 min | Login failing for 50%+ of users |
| P2 | Significant degradation — subset of users affected | < 1 hour | Every 2 hours | Search slow for US region |
| P3 | Minor issue — small impact, workaround available | Next business day | Once resolved | Non-critical dashboard shows stale data |
| P4 | Cosmetic / no user impact | Sprint backlog | N/A | Log noise, minor UI misalignment |

Escalation path:
- P0/P1: page on-call engineer → page on-call lead if not ack'd in 5 min → escalate to eng manager
- P2: page on-call engineer
- P3/P4: create ticket, no page

## Incident Lifecycle

```
Detection → Triage → Mitigate → Communicate → Resolve → Review (Postmortem)
```

### First 5 Minutes — Triage Checklist

- [ ] Acknowledge the alert and claim the incident in your incident tool (PagerDuty / Opsgenie)
- [ ] Identify: what is broken, who is affected, since when?
- [ ] Check the deployment timeline: was anything deployed in the last 2 hours?
- [ ] Check the dashboards: error rate, latency, saturation — which service is the origin?
- [ ] Open an incident channel: `#inc-YYYY-MM-DD-short-description`
- [ ] Post initial acknowledgement message (see template below)
- [ ] Assign roles: Incident Commander (IC), Communicator, Subject Matter Expert (SME)

## Communication Templates

### Initial Acknowledgement

```
🔴 [P0/P1 INCIDENT] Payment service degradation

Status: Investigating
Impact: ~30% of payment requests failing with 500 errors since 14:23 UTC
Affected: All users attempting checkout

IC: @alice
SME: @bob
Next update: 14:45 UTC

Tracking: https://incident.example.com/inc-2024-0042
```

### Status Update (every 15–30 min for P0/P1)

```
🟡 [P1 UPDATE] Payment service — 14:45 UTC

Status: Mitigating
Root cause identified: Connection pool exhaustion after deploy at 14:15
Action taken: Rolled back to v2.3.1, monitoring error rate
Current error rate: 2% (down from 30%)

Next update: 15:00 UTC
```

### Resolution

```
✅ [P1 RESOLVED] Payment service — 15:02 UTC

Status: Resolved
Duration: 39 minutes (14:23 – 15:02 UTC)
Root cause: Deploy v2.4.0 introduced a connection leak; pool exhausted under load
Resolution: Rolled back to v2.3.1; error rate returned to baseline at 15:00

Users impacted: ~15,000 failed checkout attempts
Follow-up: Postmortem scheduled for 2024-01-16 15:00 UTC
Incident report: https://incident.example.com/inc-2024-0042
```

## Mitigation Decision Tree

```
Error rate > SLO threshold?
├── Yes
│   ├── Was something deployed in the last 2 hours?
│   │   ├── Yes → ROLLBACK first, investigate after
│   │   └── No  → Check: DB, cache, upstream dependency, config change
│   ├── Can we isolate the impact with a feature flag kill?
│   │   └── Yes → Kill the flag immediately
│   └── Is this a traffic spike?
│       └── Yes → Scale up horizontally, enable circuit breaker
└── No — latency degraded only?
    ├── Check DB: slow queries, lock contention, pool saturation
    ├── Check cache hit rate: has cache been evicted?
    └── Check upstream service latency
```

**When NOT to roll back immediately:**
- The new version fixes a critical security issue (rolling back re-introduces the vulnerability)
- Rollback would itself cause data migration issues
- The issue is cosmetic (P3/P4) and the fix is already in progress

## Runbook Structure

Runbooks must be written for the 3am engineer who has never seen this service.

```markdown
# Runbook: [Service Name] — [Alert Name]

## Service Overview
[2–3 sentences: what does this service do, what does it depend on?]

## Alert: [Alert Name]
**Trigger condition:** [e.g., error rate > 1% for 5 minutes]
**Severity:** P1
**Dashboard:** [link]
**Logs:** [link to log query]

## Diagnostic Steps
1. Check the error rate panel on the [service dashboard](link)
   - Expected: < 0.1%
   - If > 1%: proceed to step 2
2. Check recent deployments:
   ```bash
   kubectl rollout history deployment/payment-service -n production
   ```
3. Check DB connection pool:
   ```bash
   kubectl exec -it $(kubectl get pod -l app=payment-service -o name | head -1) \
     -- curl -s localhost:8080/metrics | grep db_pool
   ```
   - If `db_pool_wait_duration_seconds` > 1s: pool is exhausted, proceed to step 4
4. Check for slow queries:
   ```sql
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```

## Mitigation Steps
- **If recent deployment:** `kubectl rollout undo deployment/payment-service -n production`
- **If DB pool exhausted:** Scale up replicas: `kubectl scale deployment/payment-service --replicas=6`
- **If upstream dependency:** Enable circuit breaker feature flag: `[link to flag]`

## Escalation
- If not resolved in 30 minutes: page @payment-team-lead
- DB issues: page @dba-on-call
- Infrastructure: page @infra-on-call

## Related Runbooks
- [Database connection issues](link)
- [High memory usage](link)
```

**Runbook quality checks:**
- Every step has an expected output — the engineer knows what "normal" looks like
- Commands are copy-paste ready (no placeholders that need substitution)
- Decision points have explicit branches ("if X, do Y; if Z, do W")
- Links to dashboards, log queries, and escalation contacts are current

## Blameless Postmortem

Write the postmortem within 48 hours while details are fresh. **Blameless = focus on systems and processes, not individuals.**

```markdown
# Postmortem: [Service] [Brief Description] — [Date]

## Summary
[2–3 sentences: what happened, impact, how it was resolved]

**Impact:** [number of users affected, % error rate, duration]
**Detection time:** [how long from start to detection]
**Resolution time:** [how long from detection to resolution]

## Timeline (UTC)
| Time  | Event |
|-------|-------|
| 14:15 | Deploy v2.4.0 rolled out to 100% |
| 14:23 | Alert fired: error rate > 1% |
| 14:28 | On-call acknowledged, started investigation |
| 14:38 | Root cause identified: connection pool exhausted |
| 14:45 | Rollback initiated |
| 15:00 | Error rate returned to baseline |
| 15:02 | Incident declared resolved |

## Root Cause Analysis (5 Whys)
1. **Why** did payment requests fail?
   → DB connection pool was exhausted
2. **Why** was the pool exhausted?
   → v2.4.0 introduced a connection leak in the retry handler
3. **Why** did the retry handler leak connections?
   → The `defer conn.Close()` was placed inside the retry loop, closing on each attempt but not releasing the acquired connection back to the pool
4. **Why** wasn't this caught in testing?
   → Integration tests used a single-connection test DB; pool exhaustion only manifests at scale
5. **Why** wasn't this caught by the integration test DB pool?
   → Test pool size was set to 100 (no practical limit); prod pool size is 20

## Contributing Factors
- No load test run before this deploy
- No DB pool exhaustion alert existed
- Code review missed the subtle connection lifecycle issue

## What Went Well
- Alert fired within 8 minutes of degradation starting
- On-call was paged and acknowledged quickly
- Rollback decision was made in < 10 minutes

## Action Items

| Action | Owner | Due | Category |
|--------|-------|-----|----------|
| Add DB pool wait time alert (threshold: > 1s for 5 min) | @alice | 2024-01-19 | Detection |
| Add integration test that simulates pool exhaustion under concurrent load | @bob | 2024-01-26 | Prevention |
| Add `db_pool_size` check to pre-deploy checklist | @alice | 2024-01-19 | Prevention |
| Run k6 load test before all deploys touching DB connection code | @bob | 2024-01-26 | Prevention |
```

### Action Item Categories
- **Prevention:** stops this class of failure from happening
- **Detection:** reduces time-to-detection (MTTD)
- **Response:** reduces time-to-resolution (MTTR)

## Metrics to Track

| Metric | Definition | Target |
|--------|-----------|--------|
| MTTD | Mean Time To Detect — start of incident to first alert firing | < 5 min |
| MTTA | Mean Time To Acknowledge — alert fires to on-call acks | < 5 min |
| MTTR | Mean Time To Resolve — detection to resolution | < 30 min for P0/P1 |
| Incident frequency | Number of P0/P1 incidents per month per service | Track trend; goal: decreasing |
| Repeat incidents | Incidents with the same root cause as a prior incident | Goal: 0 |

Review these monthly per service. Rising MTTR = runbooks need updating. Repeat incidents = action items not implemented.

> See also: `observability`, `deployment-strategies`

## Red Flags

- **Postmortem that names individuals as root cause** — "Alice deployed bad code" stops at the human rather than the system that allowed the bad code to reach production; blameless postmortems ask why the system made it possible
- **Action items with no owner or no due date** — "Improve monitoring" as an action item is never done; every item must have a named owner and a specific due date to be tracked and closed
- **Runbook that assumes the on-call engineer knows the service** — runbooks must include what "normal" looks like and copy-paste commands; a 3am engineer touching an unfamiliar service cannot safely improvise
- **Rolling back immediately without checking if the rollback itself causes data loss** — rolling back a deploy that ran a destructive migration may orphan or corrupt rows that were written against the new schema
- **Posting a P0 incident only in an engineering Slack channel** — stakeholders (product, support, leadership) need timely updates via their own channels; the Communicator role exists specifically to bridge this gap
- **Severity P0 declared for every outage regardless of blast radius** — "P0" becomes meaningless if used for single-user bugs; a calibrated P0 ensures the right resources are mobilized and avoids on-call fatigue
- **MTTD and MTTR tracked per-incident but never aggregated** — individual numbers without a monthly trend hide whether the team is improving; review rolling averages per service each month
- **Closing an incident before a postmortem is scheduled** — if the postmortem is not scheduled at resolution time it rarely happens; require a postmortem date as a condition of closing any P0 or P1

## Checklist

- [ ] Incident acknowledged within SLA (P0: 5 min, P1: 15 min)
- [ ] Incident channel opened and IC/SME roles assigned
- [ ] Initial acknowledgement posted to stakeholder channel
- [ ] Status updates sent on cadence (every 15 min for P0, 30 min for P1)
- [ ] Resolution announcement sent with impact summary
- [ ] Postmortem written within 48 hours of resolution
- [ ] 5 Whys root cause analysis complete (not just "human error")
- [ ] Action items are SMART: owner, due date, and category (prevention/detection/response)
- [ ] Runbook updated based on lessons learned
- [ ] MTTD, MTTA, MTTR recorded for this incident
