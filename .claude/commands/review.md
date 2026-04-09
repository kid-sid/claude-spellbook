Review the current changes (staged, unstaged, or a specific PR) against coding standards and security best practices.

## Instructions

1. Run `git diff` to get the current changes. If no unstaged changes, run `git diff --cached`. If the user provided a PR number, use `gh pr diff <number>`.
2. For each changed file, evaluate against these criteria:

### Code Quality (from coding-standards skill)
- Naming follows language convention (snake_case / camelCase / PascalCase)
- Functions have single responsibility, < 30 lines
- No magic numbers — named constants used
- No God Classes, Primitive Obsession, or Data Clumps
- Dependencies injected, not hardcoded
- No duplicate logic

### Security (from security skill)
- No hardcoded secrets, API keys, or credentials
- SQL queries use parameterized statements
- User input validated at API boundary
- No `eval()`, `exec()`, or `shell=True` with user input
- Auth checks resource ownership, not just role
- No sensitive data in logs

### Testing
- Changed logic has corresponding test changes
- Edge cases covered (null, empty, boundary)
- No shared mutable state between tests

### PR Hygiene
- Commit messages follow conventional commits
- No debug code (`console.log`, `print()`, `fmt.Println` for debugging)
- No commented-out code blocks
- No TODO/FIXME without a linked issue

3. Output a structured review:

```
## Review Summary
**Risk level:** [Low / Medium / High / Critical]
**Files reviewed:** N

## Issues Found

### 🔴 Critical (must fix)
- [file:line] description

### 🟡 Suggestions (should fix)
- [file:line] description

### 🔵 Nitpicks (optional)
- [file:line] description

## What Looks Good
- [positive observations]
```

4. If no issues found, say so clearly — don't invent problems.
