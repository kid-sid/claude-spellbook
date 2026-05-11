Create one or more GitHub issues from a description. Accepts natural language — infers titles, labels, and bodies from context.

**Usage:** `/create-issue <description of what issues to file>`

Example: `/create-issue The login page crashes on Safari 17 and the password reset email has a broken link`

## Instructions

### 1. Parse the arguments

Read `$ARGUMENTS`. Identify how many distinct issues are described — look for "and", numbered lists, separate sentences describing separate problems. Each distinct problem becomes one issue.

For each issue, determine:
- **Title**: concise, imperative, ≤ 72 chars (`fix:`, `feat:`, `chore:` prefix optional)
- **Body**: reproduce steps or acceptance criteria
- **Labels**: pick from what exists in the repo (`gh label list`) — common ones: `bug`, `enhancement`, `documentation`, `question`, `good first issue`, `performance`, `security`
- **Assignee**: only if the user explicitly named someone

If arguments are empty or too vague to produce a useful title and body, ask one clarifying question before proceeding.

### 2. Check the repo

```bash
# Confirm gh is authenticated and repo is detected
gh auth status
gh repo view --json nameWithOwner -q .nameWithOwner

# List existing labels (pick from these, don't invent new ones)
gh label list
```

### 3. Create each issue

```bash
gh issue create \
  --title "<title>" \
  --body "<body>" \
  --label "<label1>,<label2>"
```

For the body, use this template:

```markdown
## Description
<what is broken or what is needed>

## Steps to reproduce / Acceptance criteria
<numbered steps for bugs; bullet list of done-criteria for features>

## Expected behaviour
<what should happen>

## Actual behaviour / Current state
<what happens now — omit for feature requests>

## Context
<browser, OS, version, env — omit if not relevant>
```

### 4. Report results

After all issues are created, print a summary table:

```
Created N issue(s):

| # | Title | Labels | URL |
|---|-------|--------|-----|
| 42 | fix: login crashes on Safari 17 | bug | https://github.com/... |
| 43 | fix: broken link in password reset email | bug | https://github.com/... |
```

Do not open a browser or push any code.
