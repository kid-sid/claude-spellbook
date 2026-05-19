---
name: github-issues
description: Use when creating, triaging, or filing GitHub issues — writing bug reports, feature requests, or task tickets; classifying severity; using the gh CLI; or handling edge cases like regressions, flaky failures, security vulnerabilities, or cross-repo dependencies.
---

# GitHub Issues

Write issues that are acted on — not ignored, misrouted, or reopened for missing info.

## When to Activate

- Filing a bug report, feature request, or engineering task on GitHub
- Triaging an issue and assigning severity or priority
- Using the `gh` CLI to create or manage issues programmatically
- Handling special cases: regressions, flaky tests, security holes, data-loss bugs
- Writing acceptance criteria or reproduction steps
- Linking issues across repositories or to pull requests

## Issue Types & When to Use Each

| Type | Label | Use When | Must Include |
|---|---|---|---|
| Bug | `bug` | Observed behavior differs from documented or expected | Repro steps, expected vs actual, environment |
| Regression | `bug`, `regression` | Previously working behavior broke in a specific version | Commit/PR that introduced it, last-good version |
| Feature | `enhancement` | New capability that doesn't exist yet | Problem statement, proposed solution, AC |
| Task / Chore | `chore` | Non-feature engineering work (refactor, migration, upgrade) | Why now, success criteria, estimated scope |
| Performance | `performance` | Measurable slowdown or resource regression | Benchmark before/after, profiling output |
| Security | (private) | Vulnerability, auth bypass, data exposure | **Do NOT file publicly — use private advisory** |
| Documentation | `documentation` | Missing, wrong, or outdated docs | Affected page/file, what's wrong, correct behavior |
| Flaky Test | `flaky`, `ci` | Test fails intermittently with no code change | Failure frequency, CI run links, log excerpts |

## Severity × Priority Matrix

Severity = impact if it occurs. Priority = urgency to fix.

| | High Priority | Low Priority |
|---|---|---|
| **High Severity** | P0: fix immediately, page oncall | P1: fix this sprint |
| **Low Severity** | P2: schedule soon, workaround exists | P3: backlog, good first issue |

**P0 triggers:** data loss, auth bypass, production down, PII exposure, charge errors.  
**P1 triggers:** feature broken for >1% of users, no workaround, SLA at risk.

Add severity to issue title: `[P0]`, `[P1]`, etc. for anything P1 and above.

## gh CLI Reference

```bash
# Create issue (interactive)
gh issue create

# Create issue with all fields
gh issue create \
  --title "feat: add rate limiting to /api/v1/export" \
  --body-file issue-body.md \
  --label "enhancement,api" \
  --assignee "@me" \
  --milestone "v2.1"

# Create from heredoc (no temp file needed)
gh issue create --title "fix: null pointer in PaymentService.charge" --body "$(cat <<'EOF'
## Description
...
EOF
)"

# List, filter, search
gh issue list --label "bug" --state open --assignee "@me"
gh issue list --search "is:open label:regression sort:created-desc"

# View and edit
gh issue view 42
gh issue edit 42 --add-label "priority:high" --remove-label "needs-triage"

# Close with comment
gh issue close 42 --comment "Fixed in #87. Verified in staging."

# Reopen
gh issue reopen 42 --comment "Regression in v2.3 — reopening."

# Pin critical issues
gh issue pin 42

# Create in another repo
gh issue create --repo org/other-repo --title "..." --body "..."

# Bulk label
gh issue list --label "needs-triage" --json number --jq '.[].number' | \
  xargs -I{} gh issue edit {} --add-label "bug" --remove-label "needs-triage"
```

## Bug Report Template

```markdown
## Description
One sentence: what breaks, under what conditions.

## Steps to Reproduce
1. Go to `/settings/billing`
2. Click "Update card"
3. Enter card number `4000 0000 0000 0002` (decline test card)
4. Submit the form

## Expected Behavior
Error toast: "Card declined. Please try a different card."

## Actual Behavior
Spinner runs indefinitely. Network tab shows `POST /api/v1/charges` hanging.
Console: `Uncaught TypeError: Cannot read property 'status' of undefined`

## Environment
- OS: macOS 15.2
- Browser: Chrome 132 / Node 22.3
- App version / commit: v2.4.1 / `a3f9b12`
- Relevant config: `STRIPE_ENV=test`

## Logs / Screenshots
<details>
<summary>Stack trace</summary>

```
TypeError: Cannot read property 'status' of undefined
  at handleChargeError (payments.ts:214)
  ...
```
</details>

## Workaround
None found. All card submissions are broken in test mode.

## Acceptance Criteria
- [ ] Declined card returns 402 with user-facing error message
- [ ] Spinner stops on error
- [ ] No console errors thrown
```

## Feature Request Template

```markdown
## Problem
Describe the pain point without prescribing the solution.
"As a team admin, I cannot revoke individual API keys without deleting the entire
integration — so a single compromised key forces us to rotate all integrations."

## Proposed Solution
What you want to happen.
"Add per-key revocation on the API Keys settings page. Revoked keys return 401
immediately; no grace period."

## Alternatives Considered
- Short-lived keys (doesn't solve the emergency revoke case)
- IP allowlisting (different problem)

## Acceptance Criteria
- [ ] Admin can revoke any key independently
- [ ] Revoked key returns 401 within 60 seconds
- [ ] Audit log entry created on revocation
- [ ] Key owner notified by email

## Additional Context
Affects all teams using our Zapier integration (~400 accounts per support data).
```

## Regression Bug: Extra Requirements

A regression needs more than a standard bug report:

````markdown
## Regression Details
- **Last good version:** v2.3.0
- **First bad version:** v2.3.1
- **Introducing commit:** `git bisect` result → `c8d1e4f`
  ([commit link](https://github.com/org/repo/commit/c8d1e4f))
- **Introducing PR:** #312 — "Refactor payment middleware"

## Bisect Log
```
git bisect start
git bisect bad HEAD
git bisect good v2.3.0
# ... binary search ...
c8d1e4f is the first bad commit
```
````

Always run `git bisect` before filing a regression — "it worked before" without a
commit is not actionable.

## Flaky Test: Extra Requirements

````markdown
## Failure Rate
~30% of runs over the last 7 days (tracked manually / via CI dashboard).

## CI Run Examples
- Failed: https://github.com/org/repo/actions/runs/12345678
- Failed: https://github.com/org/repo/actions/runs/12345900
- Passed: https://github.com/org/repo/actions/runs/12345800

## Failure Pattern
Fails consistently on: parallel runs, slow CI runners, after `db:reset`.
Never fails locally. Timing-dependent (test passes with `sleep 100ms` injected).

## Log Excerpt (failure)
```
FAIL src/payments/__tests__/charge.test.ts
  ● PaymentService › charge › handles decline
    Expected: "declined"
    Received: undefined
    at Object.<anonymous> (charge.test.ts:42)
```

## Suspected Cause
Async setup in `beforeEach` not awaited before first assertion.
````

## Security Vulnerabilities: Do NOT File Publicly

```
# WRONG — never do this
gh issue create --title "SQL injection in /api/v1/search"

# CORRECT — use GitHub's private security advisory
gh api repos/org/repo/security-advisories \
  --method POST \
  --field summary="SQL injection in search endpoint" \
  --field description="..." \
  --field severity="high"

# Or via UI: repo → Security tab → Advisories → New advisory
```

Security issues must stay private until a patch is released and deployed.
Coordinated disclosure: notify maintainer → agree on fix timeline → publish advisory.

## Performance Issues: Extra Requirements

```markdown
## Benchmark: Before (v2.3.0)
```
GET /api/v1/reports/monthly  p50=120ms  p95=340ms  p99=890ms
(k6: 50 VUs, 5 min, 1000 req/min)
```

## Benchmark: After (v2.4.0)
```
GET /api/v1/reports/monthly  p50=1200ms  p95=4100ms  p99=timeout
```

## Profiling Output
Attached: `profile-v2.4.0.png`
Hotspot: `ReportAggregator.groupBy()` — 83% of CPU time.
Introduced by #318 (full-table scan, missing index on `reports.created_at`).

## Acceptance Criteria
- [ ] p95 ≤ 400ms under same load profile
- [ ] No full-table scans (verified via EXPLAIN ANALYZE)
```

## Linking Issues and PRs

```markdown
# In an issue body — creates a tracked reference
Depends on #42
Blocks #55
Related to #67
Part of #80 (epic)

# In a PR body — auto-closes the issue when PR merges to default branch
Fixes #42
Closes #42
Resolves #42

# Cross-repo
Fixes org/other-repo#42

# In commit message (also closes on merge)
git commit -m "fix: handle declined cards in test mode

Closes #42"
```

Use `Fixes` only in the PR/commit that resolves the issue — not in the issue itself.

## Duplicate Detection Before Filing

```bash
# Search before creating
gh issue list --search "payment decline spinner" --state all
gh issue list --search "card test mode broken" --state all

# Check closed issues too (may have a workaround)
gh issue list --search "charge 402" --state closed
```

If a duplicate exists:
- If open: add a comment with your reproduction details, don't file a new issue
- If closed and regressed: reopen with a comment linking the regression context

## Labels Reference

| Label | Meaning |
|---|---|
| `bug` | Confirmed behavior defect |
| `regression` | Was working, now broken |
| `enhancement` | New capability |
| `chore` | Maintenance, no user-visible change |
| `documentation` | Docs only |
| `performance` | Measurable slowdown |
| `flaky` | Intermittent test failure |
| `security` | Vulnerability (use sparingly on public repos) |
| `good first issue` | Isolated, well-scoped, beginner-friendly |
| `needs-triage` | Filed but not yet classified |
| `needs-repro` | Cannot reproduce without more info |
| `wontfix` | Intentional behavior or out of scope |
| `blocked` | Waiting on another issue or external dependency |
| `breaking-change` | Fix or feature changes existing behavior |

## Edge Cases

### Issue Spans Multiple Repositories
Create a **tracking issue** in the primary repo:
```markdown
## Scope
- [ ] org/frontend#— (UI changes)
- [ ] org/backend#— (API changes)
- [ ] org/infra#— (database migration)

This issue tracks overall completion. Sub-issues are self-contained.
```
File sub-issues in each repo, link back to the tracker.

### Breaking Change
A fix that itself breaks existing behavior needs two issues:
1. The bug issue (what's broken now)
2. A separate `breaking-change` issue documenting the behavior change, migration path, and which major version it ships in

### Issue Has Insufficient Information
Add `needs-repro` label and comment:
```
Thanks for the report. To investigate, we need:
- Exact app version (run `app --version`)
- Browser console output when the error occurs
- Whether this reproduces in an incognito window

Will keep open for 14 days awaiting info.
```

### Data-Loss Bug
Always P0. Beyond the standard bug template:
- Quantify scope: how many records, which users, time window
- Identify if the data is recoverable (backups, event log, audit trail)
- Document any immediate mitigation applied

### Issue is Actually a Support Request
Close with:
```
This looks like a configuration question rather than a bug.
Please open a support ticket at support.example.com or ask in #help on Discord.
Closing to keep the issue tracker focused on confirmed defects.
```

### Cross-Platform Bug (Only Fails on Windows/Linux)
```markdown
## Platform
- Fails on: Windows 11 (PowerShell 5.1, path separator `\`)
- Passes on: macOS 15, Ubuntu 22.04

## Root Cause Hypothesis
Path concatenation uses hardcoded `/` — breaks on Windows.
Candidate line: `config.ts:88`
```

## Red Flags

- **Title is a symptom, not a location** — "App crashes" tells nothing; "NullPointerException in PaymentService.charge when card is declined" is actionable
- **No reproduction steps** — "It doesn't work" forces the maintainer to reverse-engineer the bug; every bug needs numbered repro steps
- **Filing a security vuln as a public issue** — exposure before a patch is deployed can cause immediate harm; always use private advisories
- **Regression without a bisect** — "it worked last month" is impossible to act on; run `git bisect` and identify the introducing commit before filing
- **Flaky test filed as a bug** — flaky tests need failure rate and CI run links, not just a one-time failure screenshot
- **Feature request with no problem statement** — "add dark mode" without explaining who needs it and why will be deprioritized or misbuilt
- **Performance issue with no benchmark** — "it's slow" requires before/after numbers and a profiling output; without data it can't be triaged
- **Duplicate filed without searching first** — adds noise, splits discussion, wastes maintainer time; always search `--state all` before filing
- **Acceptance criteria missing checkboxes** — prose acceptance criteria can't be tracked; always use `- [ ]` items so progress is visible

## Checklist

- [ ] Searched existing issues (`--state all`) before filing to detect duplicates
- [ ] Title is specific: what breaks, where, under what condition (not "it doesn't work")
- [ ] Issue type identified and correct label applied
- [ ] Severity classified (P0–P3); title prefixed for P0/P1
- [ ] Bug: numbered reproduction steps that a stranger can follow
- [ ] Bug: expected vs actual behavior stated explicitly
- [ ] Bug: environment captured (OS, version, browser, config)
- [ ] Regression: introducing commit identified via `git bisect`
- [ ] Flaky test: failure rate and CI run links included
- [ ] Performance: benchmark numbers before/after attached
- [ ] Security: filed as private advisory, NOT a public issue
- [ ] Feature: problem statement written before solution
- [ ] Acceptance criteria written as `- [ ]` checkboxes
- [ ] Related issues and PRs linked (`Blocks`, `Depends on`, `Related to`)
- [ ] Correct milestone set if fix is version-targeted
- [ ] Assignee set if ownership is known at filing time

> See also: `development-workflow` (branch naming, commit conventions, PR process)
> See also: `ci-cd` (flaky test triage in GitHub Actions, workflow run links)
