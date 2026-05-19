Deliver a brutally honest, technically sharp roast of the current repository. Spot real bugs, code smells, security holes, and engineering sloppiness. Be pointed and witty, but every finding must be accurate and include a fix.

## Instructions

### Phase 1: Reconnaissance
1. Run `git ls-files` to enumerate all tracked files.
2. Detect the primary language(s) from file extensions.
3. Read `README.md` (if present), CI config (`.github/workflows/`, `Makefile`, etc.), and package manifests (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, etc.).
4. Collect repo stats: total files, source files, test files, lines of code (`git ls-files | xargs wc -l 2>/dev/null | tail -1`).
5. Check last 20 commit messages: `git log --oneline -20`.

### Phase 2: Code Quality (refactor skill patterns)
Scan source files for:
- Functions / methods longer than 30 lines
- Nesting deeper than 3 levels
- Magic numbers (bare literals that aren't 0, 1, or -1)
- Commented-out code blocks
- TODO / FIXME without a linked issue number
- Duplicate or near-duplicate logic blocks
- Boolean parameters (use named options/enums)
- God classes (> 10 methods or > 200 lines)
- Long parameter lists (> 4 params)

### Phase 3: Security (security-scan skill patterns)
Scan all files for:
- Hardcoded secrets: patterns like `AKIA`, `sk-`, `ghp_`, `Bearer`, `password =`, `secret =`, `token =` with string values
- Private keys: `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
- Connection strings with embedded credentials
- `eval()`, `exec()`, `shell=True` / `child_process.exec` with non-literal input
- SQL string concatenation
- `debug=True` or `DEBUG=True` in non-dev config files

### Phase 4: Test Coverage
- Count test files vs source files. Ratio below 0.5 is suspicious.
- Flag source directories with zero corresponding test files.
- Look for test files that only test the happy path (single `assert` or no edge-case names).
- Flag any critical-sounding module (auth, payment, crypto) with no test file.

### Phase 5: Engineering Hygiene
- Check `.gitignore` for common missing entries: `.env`, `node_modules/`, `__pycache__/`, `*.pyc`, `dist/`, `build/`, `.DS_Store`
- Check for committed secrets or build artifacts that should be gitignored
- Check dependency versions: floating (`^`, `~`, `*`, `>=`) vs pinned — flag if more than half are unpinned
- Check commit messages for quality: one-word commits (`fix`, `wip`, `asdf`, `update`), no conventional-commit style
- Flag any file > 500 lines that isn't a lock file or generated file

### Phase 6: Documentation
- README: empty sections, no usage example, no install instructions, stale badges (pointing to deleted branches)
- Missing `LICENSE` for a public-looking repo
- Missing `CONTRIBUTING.md` if there are open issues or PRs
- Docstrings / JSDoc present on public APIs? Flag if absent on exported functions

---

## Output Format

Use this structure exactly:

```
## Roast Report: <repo name>

> "<one-sentence savage but accurate summary of the repo's biggest sin>"

---

### What You Actually Got Right
- [genuine positives — don't skip this, empty praise is lazy]

---

### Tepid  _(minor nits — fix when you're bored)_
- [file:line] **<smell/issue>** — <what's wrong and the one-line fix>

### Spicy  _(real problems — fix before the next PR)_
- [file:line] **<smell/issue>** — <what's wrong and the one-line fix>

### Scorched  _(blocking / security risk — fix now)_
- [file:line] **<smell/issue>** — <what's wrong and the one-line fix>

---

### The Verdict
<One paragraph. Name the single most embarrassing finding, acknowledge one genuine strength, and give the repo an overall grade: S / A / B / C / D / F with a one-line justification.>
```

**Rules:**
- Every finding must cite a real `file:line`. No vague claims.
- Every finding must include a concrete fix, not just a complaint.
- If a category has zero findings, write "Nothing caught fire here." — do not invent problems.
- Scorched items always come with the exact remediation step.
- Tepid items may be grouped if they're the same smell across multiple files.
- Keep the roast tone throughout, but never sacrifice accuracy for a punchline.
