Fetch a GitHub issue, apply the fix, comment with what was done, and close the issue.

**Usage:** `/resolve-issue <#number> [optional guidance]`

Examples:
- `/resolve-issue #12` — read the issue and fix it as described
- `/resolve-issue #12 Only fix part 1 — adding the null check in auth.py` — fix with scoped guidance

## Instructions

### 1. Parse the arguments

From `$ARGUMENTS`:
- Extract the issue number — accept `#3`, `3`, or `GH-3` forms
- Everything after the number is **optional guidance** that narrows the scope or hints at the approach

### 2. Read the issue

```bash
gh issue view <number> --json number,title,body,labels,assignees,comments
```

Read the full issue body and all comments. Understand:
- What is broken / what is requested
- Any reproduction steps, error messages, or stack traces in the body
- Prior discussion in comments that narrows the fix

If the issue is already closed, tell the user and stop.

### 3. Locate the relevant code

Search the codebase for files, functions, or patterns mentioned in the issue. Use the optional guidance to narrow scope — if the user said "only fix part 1" or "just the auth.py null check", limit your changes accordingly.

Do not make changes outside the scope described by the issue + guidance.

### 4. Apply the fix

Make the minimal correct change. Follow the conventions already present in the file. Do not refactor surrounding code, add unrelated features, or touch files not relevant to the fix.

If the fix requires multiple steps (e.g., schema migration + code change), lay them out and apply in order.

### 5. Verify

If the repo has a test command discoverable from `Makefile`, `package.json`, or `pyproject.toml`, run the relevant tests for the changed files:

```bash
# Examples — use what fits the project
make test
npm test -- --testPathPattern=<changed file>
pytest <changed file> -x
go test ./...
```

If tests fail, fix them before proceeding.

### 6. Comment on the issue

```bash
gh issue comment <number> --body "$(cat <<'EOF'
## Fix applied

<one sentence describing what was changed and why it resolves the issue>

**Files changed:**
- `path/to/file.py` — <what changed>

**Approach:** <brief rationale — why this fix rather than alternatives>

**Testing:** <what was run to verify, or "no automated tests exist for this path">
EOF
)"
```

### 7. Close the issue

```bash
gh issue close <number> --comment "Resolved — see comment above."
```

### 8. Report to the user

Print a short summary:

```
✅ Issue #<number> — <title>

Fixed: <one-line summary>
Files: <list of changed files>
Closed: yes
```

If the issue cannot be fully resolved (e.g., requires information only the reporter has, or involves infrastructure changes outside the codebase), comment on the issue explaining what is needed and do NOT close it. Tell the user what's blocking.
