---
name: development-workflow
description: Git branching strategies (GitHub Flow, Git Flow, trunk-based), conventional commits spec, PR workflow and description templates, code review practices (giving and receiving feedback), and release tagging with semantic versioning.
---

# Development Workflow

A complete reference for Git branching, commit conventions, pull request workflow, code review practices, and release management — covering everything from first branch to published release.

## When to Activate

- Starting work on a new feature, bug fix, or chore
- Writing a commit message
- Opening or reviewing a pull request
- Deciding on a branching strategy for a new project or team
- Creating a release or version tag
- Setting up commit message linting or changelog generation

## Branching Strategies

### Comparison Table

| Strategy | Branches Used | Release Cadence | Team Size Fit | Pros | Cons |
|---|---|---|---|---|---|
| **GitHub Flow** | `main` + feature branches | Continuous (deploy on merge) | Small–medium | Simple, fast feedback, CD-friendly | No built-in release staging |
| **Git Flow** | `main`, `develop`, `feature/*`, `release/*`, `hotfix/*` | Scheduled / versioned | Medium–large | Clear release lifecycle, hotfix path | Complex, slow merging, overhead |
| **Trunk-Based Development** | `main` (+ very short-lived branches) | Continuous | Any (with CI maturity) | Maximum integration speed, minimal merge conflicts | Requires feature flags, strong CI discipline |

### GitHub Flow

Developers branch from `main`, open a pull request, and merge back to `main` on approval. Merging to `main` triggers deployment. Suitable when every merged commit should ship.

```bash
git checkout -b feat/PROJ-42-add-oauth main
# ... commit work ...
git push -u origin feat/PROJ-42-add-oauth
# Open PR → review → merge → auto-deploy
```

### Git Flow

Use when releases are batched on a schedule (e.g., sprint releases, versioned libraries).

```bash
# New feature
git checkout -b feature/PROJ-99-dark-mode develop

# Prepare a release
git checkout -b release/1.4.0 develop
# bump version, final fixes, then merge to main AND develop
git checkout main && git merge release/1.4.0
git tag -a v1.4.0 -m "Release v1.4.0"

# Emergency hotfix
git checkout -b hotfix/fix-login-crash main
# fix, then merge to main AND develop
```

### Trunk-Based Development

All engineers commit to `main` (or merge very short-lived branches within a day or two). Unfinished work is hidden behind feature flags.

```bash
# Short-lived branch — merged same day or next
git checkout -b fix/null-check-cart
git commit -m "fix(cart): guard against null item list"
git push && gh pr create --fill
```

### Decision Guide

- **Deploy on every merge (CD pipeline)** → GitHub Flow or Trunk-Based Development
- **Scheduled release trains / versioned artifacts** → Git Flow
- **Maximum integration speed, mature CI, feature-flag infrastructure** → Trunk-Based Development

## Branch Naming

Pattern: `<type>/<ticket>-<short-description>`

| Type | Example |
|---|---|
| `feat` | `feat/PROJ-123-user-auth` |
| `fix` | `fix/login-null-pointer` |
| `chore` | `chore/update-deps` |
| `docs` | `docs/api-readme` |
| `refactor` | `refactor/PROJ-200-extract-service` |

Rules:
- Lowercase letters and hyphens only — no underscores or slashes in the description segment
- Include a ticket reference where one exists
- Keep total length under 50 characters
- No personal identifiers (no `johns-branch`)

## Conventional Commits

### Commit Type Reference

| Type | Meaning | Changelog / Version Effect |
|---|---|---|
| `feat` | New feature | Minor version bump |
| `fix` | Bug fix | Patch version bump |
| `docs` | Documentation only | No bump |
| `style` | Formatting, whitespace — no logic change | No bump |
| `refactor` | Code restructure, no feature or fix | No bump |
| `perf` | Performance improvement | Patch version bump |
| `test` | Tests only | No bump |
| `chore` | Build scripts, tooling, dependencies | No bump |
| `ci` | CI/CD configuration changes | No bump |
| `build` | Build system or external dependency changes | No bump |
| `revert` | Reverts a prior commit | Depends on reverted commit |

### Breaking Changes

Add `!` after the type to signal a breaking change, or add a `BREAKING CHANGE:` footer in the commit body.

```bash
feat!: remove legacy v1 authentication endpoint

BREAKING CHANGE: The /api/v1/auth endpoint has been removed.
Clients must migrate to /api/v2/auth before upgrading.
```

### Scope

Optional. Place in parentheses between type and colon.

```
feat(auth): add refresh token rotation
fix(cart): prevent duplicate item insertion
chore(deps): upgrade eslint to v9
```

### BAD / GOOD Example

```bash
# BAD — vague, no type, no scope, doesn't explain impact
git commit -m "fix stuff"

# GOOD — type, scope, imperative mood, explains what changed
git commit -m "fix(auth): resolve null pointer when session token is missing"
```

## Pull Request Workflow

### PR Description Template

```markdown
## What
[one paragraph: what changed — be specific about files, components, or APIs affected]

## Why
[one paragraph: why this change is needed; link to ticket or issue]

## How
[optional: explain non-obvious implementation decisions or trade-offs]

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Tested manually: [describe steps and environment]

## Screenshots / Demo
[if UI change — include before/after screenshots or a short screen recording]
```

### Draft PRs

Open as a draft (`gh pr create --draft`) when the branch is in progress and early feedback is wanted. Convert to ready-for-review once CI is green and the description is complete.

```bash
gh pr create --draft --title "feat(auth): add OAuth2 PKCE flow" --body "$(cat pr-body.md)"
gh pr ready <PR-number>   # convert to ready
```

### Linking Issues

```
Closes #123      # closes the issue on merge
Fixes #456       # alias for Closes
Relates to #789  # reference without auto-closing
```

### PR Size

Target under 400 LOC of production code per PR. Large changes should be split into stacked PRs where each PR builds on the previous and can be reviewed independently.

### Merge Strategies

| Strategy | History Shape | When to Use |
|---|---|---|
| **Squash merge** | One commit per feature branch | Clean main history; preferred for most feature branches |
| **Merge commit** | Full branch history preserved | When branch history is meaningful (e.g., a spike or investigation) |
| **Rebase merge** | Linear, no merge commits | When team values perfectly linear history and all commits are high quality |

Pick one strategy per repository and enforce it consistently. GitHub allows disabling unwanted strategies under repository settings.

## Code Review Practice

### Reviewer Responsibilities

Reviewers check for: correctness, test coverage, security implications, performance concerns, naming clarity, and API design consistency. Checking formatting is the job of the linter, not the reviewer.

### Feedback Labels

Prefix review comments to signal urgency and type:

| Prefix | Meaning | Blocking? |
|---|---|---|
| `nit:` | Style or preference, minor polish | No |
| `suggestion:` | A better approach exists; author's call | No |
| `question:` | Seeking clarification or understanding | No |
| `request:` | Must be addressed before approval | Yes |

### Giving Feedback

- Be specific: reference the exact line or pattern, not a general feeling.
- Explain why: link to a doc, standard, or reason — not just "change this."
- Suggest an alternative: show what you'd prefer, don't just flag the problem.
- Don't be personal: comment on the code, not the author.

```markdown
# BAD
This is wrong.

# GOOD
request: `userId` can be null here if the session has expired.
Suggest adding a null guard before the lookup:
`if (!userId) return res.status(401).json({ error: 'Unauthorized' });`
```

### Receiving Feedback

- Separate ego from code — the review is about quality, not judgment.
- Ask for clarification before defending: "Can you say more about why X is preferred here?"
- Address every comment, even if just to acknowledge it: "Acknowledged — leaving as-is because [reason]."
- Avoid drive-by rewrites; if a comment sparks a bigger refactor, open a follow-up ticket.

### Author Checklist Before Requesting Review

- Self-review the diff in GitHub/GitLab before submitting — read your own code as if you were the reviewer.
- PR description is complete: What, Why, How, Testing.
- CI is green.
- No debug code, `console.log`, or commented-out blocks remain.
- No unresolved merge conflicts.

## Release Tagging and Semantic Versioning

### SemVer Rules

Format: `MAJOR.MINOR.PATCH`

| Segment | Increment When |
|---|---|
| `MAJOR` | Breaking change — existing callers must update |
| `MINOR` | New backward-compatible feature added |
| `PATCH` | Backward-compatible bug fix |

Pre-release labels: `1.0.0-alpha.1`, `2.3.0-rc.2`
Build metadata (ignored in precedence): `1.0.0+20240102`

### Creating Annotated Tags

```bash
# Annotated tag — preferred for releases (stores tagger, date, message)
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3

# List tags
git tag -l "v*"

# Delete a mistaken tag (locally and remotely)
git tag -d v1.2.3
git push origin --delete v1.2.3
```

### CHANGELOG

Maintain a `CHANGELOG.md` in [Keep a Changelog](https://keepachangelog.com) format with sections `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

```markdown
## [1.2.3] - 2026-04-02
### Fixed
- Resolve null pointer in session validation (#456)

## [1.2.0] - 2026-03-15
### Added
- OAuth2 PKCE authentication flow (#399)
```

### Automation Tools

| Tool | Approach | Notes |
|---|---|---|
| `semantic-release` | Fully automated — reads commits, bumps version, publishes, creates GitHub release | Zero-touch; requires strict Conventional Commits discipline |
| `release-please` (Google) | Creates a "Release PR" with changelog and version bump; engineer merges to ship | Semi-automated; good for teams that want a human gate before release |
| `standard-version` (deprecated) | Local CLI, generates changelog and tag | Superseded by `release-please` / `semantic-release` |

## Checklist

- [ ] Branch name follows `<type>/<ticket>-<description>` convention
- [ ] All commits follow Conventional Commits spec (type, optional scope, imperative subject)
- [ ] Breaking changes marked with `!` or `BREAKING CHANGE:` footer
- [ ] PR description filled out (What / Why / How / Testing sections complete)
- [ ] PR is under 400 LOC of production code, or split into stacked PRs
- [ ] CI is green before requesting review
- [ ] No debug code, `console.log`, or commented-out blocks left in
- [ ] Issues linked with `Closes #` or `Fixes #` where applicable
- [ ] Reviewer feedback addressed or explicitly acknowledged before merge
- [ ] Merge strategy matches team convention (squash / merge commit / rebase)
- [ ] Release tagged with annotated tag following SemVer (`git tag -a vX.Y.Z`)
- [ ] CHANGELOG updated or auto-generated via `semantic-release` / `release-please`
