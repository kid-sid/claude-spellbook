Run local CI validation on all skills and agents in the spellbook — same checks as `.github/workflows/ci.yml`.

## Instructions

Run the following checks and report results. Do NOT fix issues automatically — report them so the author can decide.

### 1. Skill Format Check

```bash
ERRORS=0
for skill in skills/*/skill.md; do
  SKILL_ERRORS=0
  head -1 "$skill" | grep -q "^---" || { echo "  FAIL [$skill]: Missing frontmatter (first line must be ---)"; SKILL_ERRORS=1; }
  grep -q "^name:" "$skill"        || { echo "  FAIL [$skill]: Missing name: field"; SKILL_ERRORS=1; }
  grep -q "^description:" "$skill" || { echo "  FAIL [$skill]: Missing description: field"; SKILL_ERRORS=1; }
  grep -q "## When to Activate" "$skill" || { echo "  FAIL [$skill]: Missing ## When to Activate section"; SKILL_ERRORS=1; }
  grep -q "## Checklist" "$skill"  || { echo "  FAIL [$skill]: Missing ## Checklist section"; SKILL_ERRORS=1; }
  grep -q "\- \[ \]" "$skill"      || { echo "  FAIL [$skill]: Checklist has no '- [ ]' items"; SKILL_ERRORS=1; }
  [ $SKILL_ERRORS -eq 0 ] && echo "  PASS [$skill]"
  ERRORS=$((ERRORS + SKILL_ERRORS))
done
```

### 2. Agent Format Check

```bash
VALID_MODELS="sonnet opus haiku inherit"
VALID_COLORS="red blue green yellow purple orange"
for agent in .claude/agents/*.md; do
  AGENT_ERRORS=0
  head -1 "$agent" | grep -q "^---"    || { echo "  FAIL [$agent]: Missing frontmatter"; AGENT_ERRORS=1; }
  grep -q "^name:"        "$agent"     || { echo "  FAIL [$agent]: Missing name:"; AGENT_ERRORS=1; }
  grep -q "^description:" "$agent"     || { echo "  FAIL [$agent]: Missing description:"; AGENT_ERRORS=1; }
  grep -q "^tools:"       "$agent"     || { echo "  FAIL [$agent]: Missing tools:"; AGENT_ERRORS=1; }
  grep -q "^model:"       "$agent"     || { echo "  FAIL [$agent]: Missing model:"; AGENT_ERRORS=1; }
  MODEL=$(grep "^model:" "$agent" | head -1 | sed 's/model:[[:space:]]*//')
  echo "$VALID_MODELS" | grep -qw "$MODEL" || { echo "  FAIL [$agent]: model '$MODEL' not in ($VALID_MODELS)"; AGENT_ERRORS=1; }
  [ $AGENT_ERRORS -eq 0 ] && echo "  PASS [$agent]"
  ERRORS=$((ERRORS + AGENT_ERRORS))
done
```

### 3. Badge & Table Sync Check

```bash
ACTUAL=$(find skills -name "skill.md" | wc -l | tr -d ' ')
BADGE=$(grep -oE 'skills-[0-9]+-blueviolet' README.md | grep -oE '[0-9]+')
TABLE_COUNT=$(grep -F '| **Skills**' README.md | awk -F'|' '{print $(NF-1)}' | tr -d ' ')
echo "Skills on disk: $ACTUAL | Badge: $BADGE | Table row: $TABLE_COUNT"
[ "$BADGE" != "$ACTUAL" ] && echo "  FAIL: Badge shows $BADGE but $ACTUAL exist — update README badge"
[ "$TABLE_COUNT" != "$ACTUAL" ] && echo "  FAIL: Table row shows $TABLE_COUNT but $ACTUAL exist — update README table"
```

### 4. Inventory Sync Check

```bash
for skill_dir in skills/*/; do
  SKILL_NAME=$(basename "$skill_dir")
  grep -q "\`${SKILL_NAME}\`" README.md || echo "  FAIL: skills/$SKILL_NAME not listed in README.md"
done

for agent_file in .claude/agents/*.md; do
  AGENT_NAME=$(basename "$agent_file" .md)
  grep -q "\`${AGENT_NAME}\`" README.md || echo "  FAIL: agent $AGENT_NAME not listed in README.md"
done
```

### 5. Slash Command Check

```bash
for cmd in .claude/commands/*.md; do
  [ -s "$cmd" ] && echo "  PASS [$cmd]" || echo "  FAIL [$cmd]: file is empty"
done
```

## Output Format

After running all checks, summarize:

```
## Skill Validate Results

### Skills  (N checked)
- PASS: X   FAIL: Y

### Agents  (N checked)
- PASS: X   FAIL: Y

### Badge sync
- Badge: N  |  Table: N  |  On disk: N  → ✅ / ❌

### Inventory
- X skills missing from README
- X agents missing from README

### Commands  (N checked)
- PASS: X   FAIL: Y

---
Total errors: N
```

List every individual failure with the file path and the specific check that failed. If zero errors, say "All checks passed ✅".
