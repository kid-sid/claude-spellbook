---
name: writing-plans
description: Use when creating an implementation plan for a non-trivial task — any change spanning multiple files, involving a database migration, requiring specific sequencing, or being handed off to a subagent for execution.
---

# Writing Plans

A plan is only useful if it's specific enough that a stranger could execute it without asking questions.

## When to Activate

- Creating a plan for a feature that touches more than 2 files
- Planning a refactor where the sequence of steps matters
- Designing a database migration or schema change
- Writing a plan to hand off to a subagent for implementation
- Any task where "implement X" is too vague to be actionable
- Planning work that requires specific test commands or rollback steps
- Onboarding a contributor to an ongoing task mid-stream

## The Zero-Placeholder Rule

Every element of a plan must be fully specified. If you write it, it must be complete — no fill-in-the-blank, no ellipsis, no "implement as needed."

| Element | BAD — placeholder | GOOD — complete |
|---|---|---|
| File path | `path/to/file.py` | `src/api/routes/users.py` |
| Code change | "add validation logic" | Full code block with the exact function |
| Test command | "run the tests" | `pytest tests/api/test_users.py::test_create_user -v` |
| Expected output | "tests pass" | `PASSED tests/api/test_users.py::test_create_user` |
| Commit message | "fix the bug" | `fix(auth): reject tokens with expired nbf claim` |
| Config value | "appropriate timeout" | `timeout: 30s` |
| Environment variable | "set the API key" | `STRIPE_SECRET_KEY=sk_test_...` in `.env` |

## Plan Structure

```markdown
## Goal
One sentence: what this plan achieves and why.

## Pre-conditions
- [ ] Specific thing that must be true before starting: `command` → expected output
- [ ] Environment variable or service that must be running

## Steps

### Step 1 — <verb> <specific target>
**File:** `absolute/path/to/file.ext`

\`\`\`language
// Full code block — no ellipsis, no "rest of function", no TODO comments
\`\`\`

**Verify:** `exact command` → `expected output`

### Step 2 — commit checkpoint
**Commit:** `type(scope): specific description of what changed`

## Rollback
- If step 3 fails: `exact command to undo`
- If migration was applied: `alembic downgrade -1`
```

## Sequencing Rules

| Rule | Reason |
|---|---|
| One concern per step | Bundled steps are harder to roll back and harder to verify |
| Database migrations before code changes | Code errors if it references a column that doesn't exist yet |
| Write the failing test before implementation | Confirms the test actually tests what you think |
| Include a commit at natural checkpoints | Enables bisect and partial rollback |
| Pre-conditions listed before any step | Eliminates "I didn't know I needed X" failures mid-plan |

## Forbidden Patterns

```
# BAD — relative path
Update the config in `settings.py`

# GOOD — absolute path
Update `src/config/settings.py` (absolute from repo root)
```

```
# BAD — vague instruction
Add error handling to the endpoint

# GOOD — complete instruction
In `src/api/routes/users.py` line 47, wrap the db.query() call:

try:
    result = db.query(User).filter(User.id == user_id).first()
except SQLAlchemyError as e:
    logger.error("db_query_failed", user_id=user_id, error=str(e))
    raise HTTPException(status_code=500, detail="Internal server error")
```

```
# BAD — no expected output
Run the tests to verify everything works.

# GOOD — exact command + expected output
$ pytest tests/api/test_users.py -v
PASSED tests/api/test_users.py::test_get_user_returns_404_when_not_found
PASSED tests/api/test_users.py::test_get_user_returns_user_data
2 passed in 0.43s
```

## When to Plan vs. When to Code

| Situation | Approach |
|---|---|
| Single-file change, < 30 lines | Code directly; inline context in chat |
| Multi-file change, clear sequence | Write a full plan first |
| Subagent will implement | Always a written plan — agents can't ask clarifying questions |
| Database migration involved | Always a written plan — irreversible if done wrong |
| Rollback must be possible | Always a written plan |
| Shape of solution is unknown | Brainstorm first; plan after the approach is clear |
| Pairing or handoff to a teammate | Written plan with pre-conditions and verify steps |

## Red Flags

- **"Implement X"** as a plan step — this is a task description, not a plan; expand into specific files, code, and verify commands
- **Relative file paths** — ambiguous across machines and working directories; always specify paths from a known root
- **No verify step after a destructive operation** — you won't know it succeeded until something later fails unexpectedly
- **Bundled steps** ("do A and B and C together") — if B fails, you can't tell what state A left the system in
- **Missing rollback for irreversible steps** — database migrations, published events, external API calls all need explicit undo instructions
- **"Add tests"** without specifying which file, which test case, and what the assertion checks
- **Missing pre-conditions** — forgetting to list required services, env vars, or setup that must exist before step 1
- **Commit messages written as "update files"** — write the actual message; vague messages make bisect and blame useless later

## Checklist

- [ ] Every file path is specified from a known root (no bare filenames)
- [ ] Every code change is a complete, runnable code block (no ellipsis or TODO)
- [ ] Every destructive step has a verify command with expected output
- [ ] No step says "implement", "add", or "update" without full specifics
- [ ] Database migrations precede model/code changes
- [ ] Commit messages are written out verbatim
- [ ] Rollback instructions exist for irreversible steps
- [ ] Pre-conditions are listed and checkable before step 1
- [ ] A person who has never seen this codebase could execute the plan without asking questions
