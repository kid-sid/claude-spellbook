Run a pre-deployment verification checklist before releasing to production.

## Instructions

1. Determine the deployment context:
   - What environment? (staging / production)
   - What type of change? (feature / bugfix / hotfix / infrastructure)
   - What services are affected?

2. Run through the pre-deployment checklist:

### Code Readiness
- [ ] All CI checks passing on the branch/tag being deployed
- [ ] Code has been reviewed and approved (check PR status with `gh pr view`)
- [ ] No TODO/FIXME/HACK comments in changed files related to this deploy
- [ ] No debug code left in (console.log, print statements, debugger)
- [ ] Feature flags in place for risky changes

### Testing
- [ ] Unit tests passing (`make test` or equivalent)
- [ ] Integration tests passing
- [ ] Manual QA completed for user-facing changes
- [ ] Load/performance test results reviewed (for high-traffic changes)
- [ ] Rollback tested or rollback plan documented

### Database
- [ ] Migrations are backward-compatible (can old code run with new schema?)
- [ ] Migration has been tested against a production-size dataset
- [ ] No destructive migrations (DROP TABLE, DROP COLUMN) without data backup
- [ ] Indexes added for new queries on large tables
- [ ] Seed data / backfill scripts ready if needed

### Configuration & Secrets
- [ ] Environment variables set in target environment
- [ ] Secrets rotated if compromised or newly required
- [ ] Feature flags configured for target environment
- [ ] No hardcoded environment-specific values in code

### Infrastructure
- [ ] Sufficient capacity (CPU, memory, disk) for the deployment
- [ ] Health check endpoints working (`/health/live`, `/health/ready`)
- [ ] Monitoring and alerting configured for new endpoints/services
- [ ] Log aggregation capturing new log events

### Communication
- [ ] Team notified of deployment window
- [ ] Stakeholders informed of new features / changes
- [ ] Runbook updated if operational procedures changed
- [ ] On-call aware of the deployment

### Rollback Plan
- [ ] Rollback procedure documented
- [ ] Previous version tagged and available
- [ ] Database rollback migration exists (if applicable)
- [ ] Feature flags can disable new functionality without redeploy
- [ ] Estimated rollback time: {X minutes}

3. Auto-check what can be verified programmatically:
   - Run `gh pr checks` for CI status
   - Run `git log --oneline main..HEAD` to list commits being deployed
   - Check for debug statements with grep
   - Check for TODO/FIXME in changed files
   - Verify Dockerfile builds successfully
   - Verify health check endpoint exists in code

4. Output the checklist:

```
## Pre-Deployment Checklist
**Branch/Tag:** {branch}
**Target:** {environment}
**Commits:** {count} commits since last deploy
**Change type:** {feature/bugfix/hotfix}

### ✅ Auto-Verified
- {items that were programmatically checked and passed}

### ⚠️ Auto-Verified with Warnings
- {items that need attention}

### 📋 Manual Verification Required
- [ ] {items that need human confirmation}

### 🚀 Deploy Command
{the command or steps to execute the deployment}

### 🔙 Rollback Command
{the command to roll back if something goes wrong}
```

## Output
- Completed checklist with auto-verified items checked off
- Clear list of items needing manual verification
- Deploy and rollback commands ready to execute
