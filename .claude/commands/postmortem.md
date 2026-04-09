Generate a postmortem document from an incident description.

## Instructions

1. Ask the user (if not already specified):
   - **Incident title**: brief description of what happened
   - **Severity**: SEV1 (critical) / SEV2 (major) / SEV3 (minor) / SEV4 (low)
   - **Duration**: when did it start and end?
   - **Impact**: what was affected? (users, services, revenue)

2. Generate the postmortem using this blameless template:

```markdown
# Postmortem: {Incident Title}

**Date:** {YYYY-MM-DD}
**Severity:** {SEV1/SEV2/SEV3/SEV4}
**Duration:** {start time} — {end time} ({total duration})
**Authors:** {names}
**Status:** Draft | In Review | Final

## Executive Summary

{2-3 sentence summary: what happened, what was the impact, and is it fully resolved?}

## Impact

| Metric | Value |
|--------|-------|
| Users affected | {number or percentage} |
| Duration of impact | {duration} |
| Revenue impact | {estimated $} |
| SLA impact | {e.g., dropped below 99.9%} |
| Support tickets | {count} |

## Timeline (all times in UTC)

| Time | Event |
|------|-------|
| {HH:MM} | {First signal: alert fired / user report / monitoring} |
| {HH:MM} | {Detection: who noticed and how} |
| {HH:MM} | {Escalation: who was paged} |
| {HH:MM} | {Investigation: what was checked first} |
| {HH:MM} | {Mitigation: what stopped the bleeding} |
| {HH:MM} | {Resolution: root cause fixed} |
| {HH:MM} | {All-clear: confirmed recovery} |

## Root Cause

{Detailed technical explanation of what went wrong and why. Be specific — name the exact component, config, or code path.}

## Detection

- **How was it detected?** {alert / user report / manual check}
- **Time to detect (TTD):** {duration from start to detection}
- **Could we have detected it sooner?** {yes/no and how}

## Mitigation & Resolution

### Immediate mitigation
{What was done to stop the impact? (rollback, feature flag, scaling, etc.)}

### Root cause fix
{What was done to permanently fix the underlying issue?}

## Contributing Factors

{What conditions allowed this to happen? Think systemic, not individual.}

- {factor 1: e.g., missing integration test for this code path}
- {factor 2: e.g., no alerting on this specific error class}
- {factor 3: e.g., deploy happened outside normal hours without extra review}

## Lessons Learned

### What went well
- {thing that worked: e.g., alerting fired within 2 minutes}
- {thing that worked: e.g., runbook was accurate and up-to-date}

### What went poorly
- {thing that failed: e.g., took 30 min to identify the failing service}
- {thing that failed: e.g., no rollback automation}

### Where we got lucky
- {thing that could have been worse: e.g., happened during low-traffic hours}

## Action Items

| Priority | Action | Owner | Due Date | Ticket |
|----------|--------|-------|----------|--------|
| P0 | {critical fix} | {name} | {date} | {link} |
| P1 | {important improvement} | {name} | {date} | {link} |
| P2 | {nice-to-have improvement} | {name} | {date} | {link} |

## Appendix

### Related Links
- {monitoring dashboard}
- {relevant PR or commit}
- {Slack thread}
- {alert configuration}

### Raw Data
{Any relevant logs, graphs, or metrics snapshots}
```

3. Pre-fill the timeline by:
   - Checking git log for recent deploys around the incident time
   - Looking for relevant error patterns in the codebase
   - Suggesting contributing factors based on code review

4. Save the file to `docs/postmortems/{YYYY-MM-DD}-{kebab-case-title}.md` (create directory if needed).

## Output
- The generated postmortem document
- Sections that need human input highlighted
- Reminder to schedule a blameless postmortem review meeting
