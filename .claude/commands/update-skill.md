Read `.claude/findings.jsonl`, show pending skill findings, and apply approved changes back to the relevant skill file.

## Instructions

1. Read `.claude/findings.jsonl`. If the file does not exist or has no entries where `reviewed: false`, say "No pending findings." and stop.

2. Filter to `reviewed: false` entries. Group by `skill` field. Print a summary table:

```
| Skill         | Count | Sources           |
|---------------|-------|-------------------|
| fastapi       |   2   | web, gap          |
| (unmatched)   |   1   | web               |
```

3. Ask the user which skill to process. Work on one skill per invocation.

4. For entries where `skill` is `null`: list the `query` / `url` / `note` for each, suggest the most likely skill match by comparing keywords against folder names under `skills/*/skill.md`, and confirm with the user before proceeding.

5. Read the target `skills/<name>/skill.md`.

6. For each unreviewed finding for this skill, determine the minimal change:
   - `source: "web"` — new info from a search: add a checklist item, update a code example, or add a `###` subsection if the topic is genuinely new
   - `source: "gap"` — pattern Claude had to invent: add a code example + checklist item in the most relevant existing section
   - `source: "bug"` — incorrect content: show the current block and the corrected version side by side as `# BEFORE` / `# AFTER` in a fenced block

7. Show every proposed change in full before touching any file. Ask for explicit approval:
   - "Apply these changes? (yes / skip / edit)"
   - "skip" marks the finding reviewed without editing the skill
   - "edit" lets the user paste a corrected version

8. On approval:
   - Edit `skills/<name>/skill.md` in-place — never rewrite the whole file, never change frontmatter or section order
   - For each processed finding, update its `reviewed` field to `true` in `findings.jsonl` (rewrite that line only)

9. After editing, run `/skill-validate` to confirm the file still passes CI format checks. If it fails, show the error and offer to fix it before proceeding.

## Format rules (enforced in every proposed change)
- Frontmatter: unchanged (`name:`, `description:` as-is)
- Checklist items: `- [ ] verb-first, present tense`
- Code examples for language-agnostic skills: Python, TypeScript, and Go as siblings
- Anti-patterns: `# BAD` comment on the bad block, `# GOOD` on the corrected block — always paired
- No meta-commentary ("as of 2026", "Claude found this", "new finding") — write as if it was always there
